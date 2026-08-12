# 檔案：tests/test_mail_service.py
# 測試 mail_service 的純解析邏輯（不連網、不操作正式資料庫）
import re
import email
import email.message

from src.core import mail_service as ms


def _msg_from_string(raw: str) -> email.message.Message:
    return email.message_from_string(raw)


# ---------- 標頭解碼 ----------
def test_decode_header_plain():
    assert ms._decode_header("Hello") == "Hello"


def test_decode_header_encoded():
    assert ms._decode_header("=?utf-8?B?5rWL6K+V?=") == "测试"


def test_decode_header_none():
    assert ms._decode_header("") == ""


# ---------- 收件人解析 ----------
def test_addr_list_plain():
    result = ms._addr_list('"Alice Chen" <alice@example.com>, bob@example.com')
    assert result == [("Alice Chen", "alice@example.com"), ("", "bob@example.com")]


def test_addr_list_empty():
    assert ms._addr_list("") == []


# ---------- 內文擷取 ----------
def test_body_prefers_text_plain():
    raw = (
        "MIME-Version: 1.0\r\n"
        "Content-Type: multipart/alternative; boundary=XYZ\r\n\r\n"
        "--XYZ\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n"
        "問題內容純文字\r\n"
        "--XYZ\r\nContent-Type: text/html; charset=utf-8\r\n\r\n"
        "<html><body><b>HTML</b></body></html>\r\n"
        "--XYZ--\r\n"
    )
    assert ms._get_body(_msg_from_string(raw)) == "問題內容純文字"


def test_body_falls_back_to_html():
    raw = (
        "MIME-Version: 1.0\r\n"
        "Content-Type: text/html; charset=utf-8\r\n\r\n"
        "<html><body>登入<a href='x'>連結</a>驗證碼</body></html>"
    )
    body = ms._get_body(_msg_from_string(raw))
    assert "登入" in body
    assert "驗證碼" in body
    assert "<a" not in body


def test_body_simple_text():
    assert ms._get_body(_msg_from_string("Content-Type: text/plain; charset=utf-8\r\n\r\nHello 世界")) == "Hello 世界"


def test_body_no_cte_keeps_chinese():
    assert ms._get_body(_msg_from_string("Content-Type: text/plain; charset=utf-8\r\n\r\n您好！世界")) == "您好！世界"


def test_body_base64_decodes():
    import base64
    b64 = base64.b64encode("中文內容".encode("utf-8")).decode("ascii")
    raw = (
        "Content-Type: text/plain; charset=utf-8\r\n"
        "Content-Transfer-Encoding: base64\r\n\r\n"
        + b64
    )
    assert ms._get_body(_msg_from_string(raw)) == "中文內容"


# ---------- 執行緒 ----------
def test_thread_key_uses_oldest_reference():
    raw = (
        "Message-ID: <C@c>\r\n"
        "References: <A@a> <B@b>\r\n"
        "In-Reply-To: <B@b>\r\n\r\nbody"
    )
    assert ms._thread_key(_msg_from_string(raw)) == "A@a"


def test_thread_key_falls_back_to_in_reply_to():
    raw = "Message-ID: <C@c>\r\nIn-Reply-To: <B@b>\r\n\r\nbody"
    assert ms._thread_key(_msg_from_string(raw)) == "B@b"


def test_thread_key_falls_back_to_own_id():
    raw = "Message-ID: <Z@z>\r\n\r\nbody"
    assert ms._thread_key(_msg_from_string(raw)) == "Z@z"


# ---------- 寄件備份掃描（在 Gmail 直接回覆也能被偵測） ----------
class _FakeListM:
    """只實作 list / select 的假 IMAP，供 _list_sent_folder 測試。"""

    def __init__(self, folders):
        self.folders = folders
        self.selected = None
        names = set()
        for f in folders:
            raw = f.decode("utf-8", errors="replace") if isinstance(f, bytes) else str(f)
            m = re.search(r'"([^"]*)"\s*$', raw)
            if m:
                names.add(m.group(1))
        self.names = names

    def list(self):
        return "OK", self.folders

    def select(self, name, readonly=False):
        self.selected = name
        return ("OK", []) if name.strip('"') in self.names else ("NO", [])


def test_list_sent_folder_finds_english_name():
    fake = _FakeListM([
        b'(\\HasNoChildren \\Sent) "/" "[Gmail]/Sent Mail"',
        b'(\\HasNoChildren \\All) "/" "[Gmail]/All Mail"',
        b'(\\HasNoChildren) "/" "INBOX"',
    ])
    assert ms._list_sent_folder(fake) == "[Gmail]/Sent Mail"


def test_list_sent_folder_finds_chinese_name():
    fake = _FakeListM([
        r'(\HasNoChildren \Sent) "/" "[Gmail]/寄件備份"'.encode("utf-8"),
    ])
    assert ms._list_sent_folder(fake) == "[Gmail]/寄件備份"


def test_list_sent_folder_no_sent_returns_none():
    fake = _FakeListM([b'(\\HasNoChildren) "/" "INBOX"'])
    assert ms._list_sent_folder(fake) is None


class _FakeSentM:
    """假 IMAP：寄件備份資料夾內有 msgs 封原始信，UID 從 1 開始編號。"""

    def __init__(self, msgs):
        self.msgs = msgs

    def list(self):
        return "OK", [b'(\\HasNoChildren \\Sent) "/" "[Gmail]/Sent Mail"']

    def select(self, name, readonly=False):
        return "OK", []

    def search(self, charset, criteria):
        uids = b" ".join(bytes(str(i + 1).encode()) for i in range(len(self.msgs)))
        return "OK", [uids]

    def fetch(self, uid, what):
        idx = int(uid) - 1
        return "OK", [(uid, self.msgs[idx].encode("utf-8"))]


def test_scan_sent_messages_finds_own_reply_only():
    own_reply = (
        "From: me@oneplus.com.tw\r\n"
        "Message-ID: <reply@x>\r\n"
        "In-Reply-To: <orig@x>\r\n"
        "Date: Mon, 01 Jan 2024 10:00:00 +0800\r\n"
        "Subject: Re: hello\r\n"
        "\r\n"
        "回覆內容"
    )
    other_email = (
        "From: colleague@oneplus.com.tw\r\n"
        "Message-ID: <other@x>\r\n"
        "Date: Mon, 01 Jan 2024 09:00:00 +0800\r\n"
        "Subject: hello\r\n"
        "\r\n"
        "body"
    )
    fake = _FakeSentM([own_reply, other_email])
    msgs = ms._scan_sent_messages(fake, "01-Jan-2024", {"email": "me@oneplus.com.tw"})
    assert len(msgs) == 1
    assert msgs[0]["sender_email"] == "me@oneplus.com.tw"
    assert msgs[0]["thread_key"] == "orig@x"


def test_scan_sent_messages_empty_when_no_sent_folder():
    fake = _FakeListM([b'(\\HasNoChildren) "/" "INBOX"'])
    assert ms._scan_sent_messages(fake, "01-Jan-2024", {"email": "me@oneplus.com.tw"}) == []


# ---------- 內部寄件者判斷 ----------
def test_is_internal_own_domain():
    cfg = {"email": "me@oneplus.com.tw"}
    assert ms._is_internal("colleague@oneplus.com.tw", cfg)


def test_is_internal_same_as_account_domain():
    cfg = {"email": "me@example.com"}
    assert ms._is_internal("boss@example.com", cfg)


def test_is_not_internal_external_sender():
    cfg = {"email": "me@oneplus.com.tw"}
    assert not ms._is_internal("customer@gmail.com", cfg)


def test_is_not_internal_empty():
    assert not ms._is_internal("", {"email": "me@oneplus.com.tw"})


# ---------- 回信一律補上公司留存副本 ----------
def _fake_smtp(monkeypatch):
    sent = {}

    class FakeSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def ehlo(self):
            pass

        def starttls(self):
            pass

        def login(self, *args):
            pass

        def send_message(self, msg, from_addr=None, to_addrs=None):
            sent["msg"] = msg
            sent["to_addrs"] = to_addrs

        def quit(self):
            pass

    monkeypatch.setattr(ms.smtplib, "SMTP", FakeSMTP)
    return sent


def test_send_reply_always_ccs_company(monkeypatch):
    sent = _fake_smtp(monkeypatch)
    ok, message = ms.send_reply(
        {"email": "me@oneplus.com.tw", "app_password": "x"},
        {"subject": "hello", "message_id": "<orig@a>"},
        ["customer@example.com"],
        [],
        "回覆內容",
    )
    assert ok
    assert ms.COMPANY_CC_ADDRESS in sent["msg"]["Cc"]
    assert sent["msg"]["To"] == "customer@example.com"
    assert ms.COMPANY_CC_ADDRESS in sent["to_addrs"]


def test_send_reply_cc_no_duplicate_company(monkeypatch):
    sent = _fake_smtp(monkeypatch)
    ok, _ = ms.send_reply(
        {"email": "me@oneplus.com.tw", "app_password": "x"},
        {"subject": "hello", "message_id": "<orig@a>"},
        ["customer@example.com"],
        [ms.COMPANY_CC_ADDRESS, "others@example.com"],
        "回覆內容",
    )
    assert ok
    cc_addrs = [a.strip() for a in sent["msg"]["Cc"].split(",")]
    assert cc_addrs.count(ms.COMPANY_CC_ADDRESS) == 1


def test_send_reply_removes_own_email_from_cc(monkeypatch):
    sent = _fake_smtp(monkeypatch)
    ok, _ = ms.send_reply(
        {"email": "me@oneplus.com.tw", "app_password": "x"},
        {"subject": "hello", "message_id": "<orig@a>"},
        ["customer@example.com"],
        ["me@oneplus.com.tw", "others@example.com"],
        "回覆內容",
    )
    assert ok
    cc = sent["msg"]["Cc"]
    assert "me@oneplus.com.tw" not in cc
    assert "others@example.com" in cc
    assert ms.COMPANY_CC_ADDRESS in cc
