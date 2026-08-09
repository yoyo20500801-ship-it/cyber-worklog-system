# 檔案：src/core/mail_service.py
# 功能：客戶來信收發
#   - 收信：IMAP (imap.gmail.com) 抓取收件匣，僅保留「外部寄件者」信件，
#           依 Message-ID/References 分組為執行緒，偵測執行緒內是否有公司內部回覆。
#   - 回信：SMTP (smtp.gmail.com) 以「回覆所有人」方式寄出，並維持 Gmail 同一對話串。
# 全程使用 Python 內建套件 (imaplib / smtplib / email)，不需額外安裝。
import imaplib
import re
import smtplib
import email
import email.header
import email.utils
from email.message import EmailMessage
from datetime import datetime, timedelta
from email.utils import make_msgid

from src.db.repository import Repository

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

# 公司內部網域（排除不視為「客戶來信」；若與帳號網域不同可在此追加）
INTERNAL_DOMAINS = {"oneplus.com.tw"}

# 公司留存副本：回覆客戶信件時一律補上此信箱
COMPANY_CC_ADDRESS = "tpservice@oneplus.com.tw"

# 常見網域/停用字，比對時忽略
_STOP_TOKENS = {"www", "mail", "mail1", "mail2", "webmail", "edu", "tw", "com", "org", "net", "gov", "school"}


# ==========================================
# 解析工具
# ==========================================
def _decode_header(value):
    """解 RFC2047 編碼標頭（主旨 / 顯示名稱）。"""
    if not value:
        return ""
    try:
        return str(email.header.make_header(email.header.decode_header(value)))
    except Exception:
        return value.strip()


def _addr_list(header_value):
    """解析 To / Cc / From 標頭，回傳 [(顯示名稱, 信箱), ...]。"""
    if not header_value:
        return []
    out = []
    for name, addr in email.utils.getaddresses([header_value]):
        if addr:
            out.append((_decode_header(name), addr.lower()))
    return out


def _parse_date(value):
    try:
        dt = email.utils.parsedate_to_datetime(value)
        if dt is None:
            raise ValueError
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _strip_html(html):
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _decode_payload(part):
    """取出 part 的內文。Base64 / Quoted-Printable 需解碼；其餘直接取字串。

    注意：對無 Content-Transfer-Encoding 的 part 若呼叫 get_payload(decode=True)，
    Python 會把 str payload 以 raw-unicode-escape 編碼成 bytes，導致中文字變成
    字面 \\uXXXX，故無 CTE 時直接回傳字串。
    """
    cte = (part.get("Content-Transfer-Encoding") or "").lower().strip()
    if cte in ("base64", "quoted-printable"):
        raw = part.get_payload(decode=True)
        if raw is None:
            return ""
        charset = part.get_content_charset() or "utf-8"
        try:
            return raw.decode(charset, errors="replace")
        except (LookupError, UnicodeDecodeError):
            return raw.decode("utf-8", errors="replace")
    payload = part.get_payload()
    if isinstance(payload, list):
        return ""
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    return payload.decode("utf-8", errors="replace")


def _get_body(msg):
    """優先取 text/plain，其次 text/html（去標籤）。"""
    texts, htmls = [], []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain":
                texts.append(_decode_payload(part))
            elif ctype == "text/html":
                htmls.append(_decode_payload(part))
    else:
        ctype = msg.get_content_type()
        if ctype == "text/plain":
            texts.append(_decode_payload(msg))
        elif ctype == "text/html":
            htmls.append(_decode_payload(msg))
    if texts:
        return "\n".join(texts).strip()
    if htmls:
        return _strip_html("\n".join(htmls))
    return ""


def _message_ids(value):
    if not value:
        return []
    return [x for x in re.split(r"[<>,\s]+", value) if x.strip()]


def _thread_key(msg):
    """執行緒根 = References 最舊的 Message-ID；沒有則用自身 Message-ID。"""
    chain = _message_ids(msg.get("References", "")) + _message_ids(msg.get("In-Reply-To", ""))
    if chain:
        return chain[0]
    return (msg.get("Message-ID") or "").strip()


def _is_internal(sender_email, cfg):
    domain = (sender_email or "").rsplit("@", 1)[-1].lower()
    if not domain:
        return False
    if domain in INTERNAL_DOMAINS:
        return True
    own = (cfg.get("email") or "").rsplit("@", 1)[-1].lower()
    return bool(own) and domain == own


def _make_body_text(rows):
    return "\n".join(f"{r[0]} <{r[1]}>" for r in rows if r[1])


# ==========================================
# 連線測試
# ==========================================
def test_connection(email_addr: str, app_password: str):
    """測試 IMAP 帳密是否可用，回傳 (ok, message)。"""
    try:
        M = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, timeout=20)
        try:
            typ, _ = M.login(email_addr, app_password)
            if typ != "OK":
                return False, f"登入失敗：{typ}"
            typ, data = M.select("INBOX", readonly=True)
            if typ != "OK":
                return False, "無法開啟收件匣（請確認 Gmail 已啟用 IMAP）"
            M.logout()
        finally:
            try:
                M.logout()
            except Exception:
                pass
        return True, "連線成功"
    except imaplib.IMAP4.error as e:
        return False, f"登入失敗：{e}"
    except Exception as e:
        return False, f"連線失敗：{e}"


# ==========================================
# 抓取信件
# ==========================================
def fetch_new(cfg: dict) -> dict:
    """抓取收件匣最近信件並存入資料庫。

    回傳 {"ok": bool, "new": 新增筆數, "updated": 更新筆數,
          "fetched": 處理封數, "error": str or None}
    """
    email_addr = cfg.get("email", "").strip()
    app_password = cfg.get("app_password", "").strip()
    if not email_addr or not app_password:
        return {"ok": False, "new": 0, "updated": 0, "fetched": 0,
                "error": "尚未設定信箱帳號或應用程式密碼"}

    try:
        M = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, timeout=30)
    except Exception as e:
        return {"ok": False, "new": 0, "updated": 0, "fetched": 0, "error": f"連線失敗：{e}"}

    try:
        typ, _ = M.login(email_addr, app_password)
        if typ != "OK":
            return {"ok": False, "new": 0, "updated": 0, "fetched": 0, "error": "登入失敗，請確認帳號與應用程式密碼"}
        typ, data = M.select("INBOX", readonly=True)
        if typ != "OK":
            return {"ok": False, "new": 0, "updated": 0, "fetched": 0, "error": "無法開啟收件匣"}

        typ, data = M.search(None, "ALL")
        if typ != "OK" or not data or not data[0]:
            return {"ok": True, "new": 0, "updated": 0, "fetched": 0, "blocked": 0, "error": None}
        all_uids = data[0].split()
        # IMAP 搜尋結果由舊到新，取最新 fetch_limit 封
        fetch_limit = max(1, int(cfg.get("fetch_limit") or 300))
        uids = all_uids[-fetch_limit:]

        messages = []  # 每個元素: dict
        blocked_set = {b["sender_email"].lower() for b in Repository.get_email_blocklist()}
        blocked_count = 0
        for uid in uids:
            try:
                # 1) 先抓標頭取得寄件人；被過濾的寄件人不抓內文
                typ, hdata = M.fetch(uid, "(BODY.PEEK[HEADER.FIELDS (FROM)])")
                if typ != "OK" or not hdata:
                    continue
                hraw = None
                for part in hdata:
                    if isinstance(part, tuple):
                        hraw = part[1]
                        break
                if hraw is None:
                    continue
                hsender = _addr_list(email.message_from_bytes(hraw).get("From", ""))
                hsender_email = hsender[0][1] if hsender else ""
                if hsender_email and hsender_email.lower() in blocked_set:
                    blocked_count += 1
                    continue

                # 2) 抓完整內文
                typ, mdata = M.fetch(uid, "(RFC822)")
                if typ != "OK" or not mdata:
                    continue
                raw = None
                for part in mdata:
                    if isinstance(part, tuple):
                        raw = part[1]
                        break
                if not raw:
                    continue
                msg = email.message_from_bytes(raw)
                sender_addr = _addr_list(msg.get("From", ""))
                sender_email = sender_addr[0][1] if sender_addr else ""
                sender_name = sender_addr[0][0] if sender_addr else sender_email
                received = _parse_date(msg.get("Date", ""))
                subject = _decode_header(msg.get("Subject", ""))
                to_addrs = _addr_list(msg.get("To", ""))
                cc_addrs = _addr_list(msg.get("Cc", ""))
                messages.append({
                    "message_uid": uid.decode() if isinstance(uid, bytes) else str(uid),
                    "message_id": (msg.get("Message-ID") or "").strip(),
                    "thread_key": _thread_key(msg),
                    "received_at": received,
                    "sender_email": sender_email,
                    "sender_name": sender_name or sender_email,
                    "to_emails": _make_body_text(to_addrs),
                    "cc_emails": _make_body_text(cc_addrs),
                    "subject": subject,
                    "body": _get_body(msg)[:20000],
                    "is_internal": _is_internal(sender_email, cfg),
                })
            except Exception:
                continue

        # 2) 計算執行緒：有內部回覆的 thread 標記為「同事已回覆」
        threads = {}
        for m in messages:
            threads.setdefault(m["thread_key"], {"internal": False})
            if m["is_internal"]:
                threads[m["thread_key"]]["internal"] = True
        internal_threads = [k for k, v in threads.items() if v["internal"]]

        # 3) 只存外部寄件者的信件
        existing_uids = Repository.get_existing_email_uids()
        new_count = 0
        updated_count = 0
        for m in messages:
            if m["is_internal"]:
                continue
            is_new = m["message_uid"] not in existing_uids
            Repository.upsert_email({
                "message_uid": m["message_uid"],
                "message_id": m["message_id"],
                "thread_key": m["thread_key"],
                "received_at": m["received_at"],
                "sender_email": m["sender_email"],
                "sender_name": m["sender_name"],
                "to_emails": m["to_emails"],
                "cc_emails": m["cc_emails"],
                "subject": m["subject"],
                "body": m["body"],
            })
            if is_new:
                new_count += 1
            else:
                updated_count += 1

        Repository.mark_thread_internal_reply(internal_threads)
        return {"ok": True, "new": new_count, "updated": updated_count,
                "fetched": len(messages), "blocked": blocked_count, "error": None}
    finally:
        try:
            M.logout()
        except Exception:
            pass


# ==========================================
# 回信（回覆所有人）
# ==========================================
def send_reply(cfg: dict, email_row: dict, to_list: list, cc_list: list, body: str) -> tuple:
    """寄出回覆信件。

    參數：
        cfg        - 信箱設定
        email_row  - 資料庫中的原信紀錄
        to_list    - 主要收件人信箱
        cc_list    - 副本信箱
        body       - 回覆內文
    回傳 (ok, message)。

    注意：回覆一律自動補上公司留存副本 COMPANY_CC_ADDRESS，方便公司留存。
    """
    email_addr = cfg.get("email", "").strip()
    app_password = cfg.get("app_password", "").strip()
    if not email_addr or not app_password:
        return False, "尚未設定信箱帳號或應用程式密碼"

    to_list = [a.strip() for a in to_list if a and a.strip().lower() != email_addr.lower()]
    cc_list = [a.strip() for a in cc_list if a and a.strip().lower() != email_addr.lower()]
    # 公司留存副本：回覆一律補上（重複則略過）
    if COMPANY_CC_ADDRESS.lower() not in {a.lower() for a in cc_list}:
        cc_list.append(COMPANY_CC_ADDRESS)
    if not to_list:
        return False, "沒有有效的收件人（請確認原信寄件人信箱）"
    if not body or not body.strip():
        return False, "回覆內容不可為空！"

    subject = email_row.get("subject") or ""
    if not re.match(r"^(re:|re：|回覆[:：])", subject, flags=re.IGNORECASE):
        subject = "Re: " + subject

    msg = EmailMessage()
    msg["From"] = email_addr
    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg["Subject"] = subject
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    original_id = (email_row.get("message_id") or "").strip()
    if original_id:
        msg["In-Reply-To"] = original_id
        msg["References"] = original_id
    msg.set_content(body.strip())

    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(email_addr, app_password)
        server.send_message(msg, from_addr=email_addr, to_addrs=to_list + cc_list)
        server.quit()
        return True, "已寄出回覆"
    except smtplib.SMTPAuthenticationError:
        return False, "SMTP 登入失敗，請確認帳號與應用程式密碼"
    except smtplib.SMTPRecipientsRefused as e:
        return False, f"收件人被拒絕：{e}"
    except Exception as e:
        return False, f"寄信失敗：{e}"


# ==========================================
# 自動比對專案 / 學校
# ==========================================
def suggest_project_school(sender_email: str, subject: str, body: str) -> dict:
    """依寄件人網域與信件內容，自動建議對應的學校與專案。

    回傳 {"school_id", "school_name", "project_id", "project_name", "confidence"}
    confidence: "high"（網域/代碼/名稱直接命中）| "low"（內容弱比對）| None
    """
    schools = Repository.get_all_schools()
    if not schools:
        return {"school_id": None, "school_name": "", "project_id": None,
                "project_name": "", "confidence": None}

    text = f"{subject or ''} {body or ''}"
    text_low = text.lower()
    sender_low = (sender_email or "").lower()
    domain = sender_low.rsplit("@", 1)[-1] if "@" in sender_low else sender_low
    domain_tokens = [t for t in re.split(r"[^a-z0-9]+", domain) if len(t) >= 3 and t not in _STOP_TOKENS]

    best = None
    best_score = 0
    for s in schools:
        name = s.get("school_name") or ""
        code = (s.get("school_code") or "").lower()
        name_low = name.lower()
        score = 0
        reason = ""

        # 內文直接出現校名 → 強命中
        if name and name_low in text_low:
            score = 100
            reason = "name-in-content"
        # 學校代碼出現在寄件人網域 → 強命中
        elif code and code and code in domain:
            score = 90
            reason = "code-in-domain"
        # 網域 token 與校名 token 互相包含
        elif domain_tokens:
            name_tokens = [t for t in re.split(r"[^a-z0-9]+", name_low) if len(t) >= 3 and t not in _STOP_TOKENS]
            for dt in domain_tokens:
                if dt in name_low:
                    score = max(score, 70)
                    reason = "domain-in-name"
                    break
                if any(dt == nt for nt in name_tokens):
                    score = max(score, 80)
                    reason = "token-match"
                    break
        # 校名短詞出現在內容
        if score < 70 and name and len(name) >= 2:
            short = re.sub(r"[（(].*?[)）]", "", name).strip()
            if len(short) >= 3 and short.lower() in text_low:
                score = max(score, 60)
                reason = "short-name-in-content"

        if score > best_score:
            best_score = score
            best = (s, reason)

    if best is None or best_score < 40:
        return {"school_id": None, "school_name": "", "project_id": None,
                "project_name": "", "confidence": None}

    school = best[0]
    confidence = "high" if best_score >= 70 else "low"
    project_id = project_name = None
    rel = Repository.get_schools_by_project(school["id"])
    if rel:
        project_id = rel[0]["project_id"]
        project_name = next(
            (p["name"] for p in Repository.get_all_projects() if p["id"] == project_id),
            "",
        )
    return {
        "school_id": school["id"],
        "school_name": school["school_name"],
        "project_id": project_id,
        "project_name": project_name,
        "confidence": confidence,
    }
