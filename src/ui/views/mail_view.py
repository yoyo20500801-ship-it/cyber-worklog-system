# 檔案：src/ui/views/mail_view.py
# 功能：客戶來信頁面（瀏覽 / 搜尋 / 回信 / 轉成工作日誌）
import threading
import email.utils
from datetime import datetime
import customtkinter as ctk
from tkinter import messagebox

from src.ui.theme import Theme
from src.core import mail_config, mail_service
from src.db.repository import Repository
from src.ui.components.auto_hide_scroll import AutoHideScrollableFrame
from src.ui.components.pager import PaginationBar
from src.ui.components.batch import batch_render


class MailView(ctk.CTkFrame):
    FILTERS = ["全部", "待處理", "已回覆", "同事已回覆", "已轉工作日誌"]

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.filter_var = ctk.StringVar(value="全部")
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._render_seq = 0
        self._build_header()
        self._build_list()
        self.refresh_list()

    # ==========================================
    # 介面建構
    # ==========================================
    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(0, 10))

        ctk.CTkLabel(header, text="📩客戶來信", font=Theme.FONT_HEADING, text_color=Theme.NEON_CYAN).pack(side="left")

        self.btn_sync = ctk.CTkButton(
            header, text="🔄 同步", font=Theme.FONT_BODY, width=110,
            fg_color=Theme.NEON_CYAN, text_color=Theme.ON_ACCENT, hover_color=Theme.NEON_GREEN,
            command=self.sync_now
        )
        self.btn_sync.pack(side="right", padx=(10, 0))

        self.entry_search = ctk.CTkEntry(
            header, textvariable=ctk.StringVar(), placeholder_text="搜尋寄件人 / 主旨 / 內容…", width=240
        )
        self.entry_search.pack(side="right", padx=(0, 10))
        self.entry_search.bind("<Return>", lambda _: self.refresh_list())

        self.seg_filter = ctk.CTkSegmentedButton(
            header, values=self.FILTERS, variable=self.filter_var,
            font=Theme.FONT_SMALL, width=420,
            command=lambda _: self.refresh_list()
        )
        self.seg_filter.pack(side="right", padx=(0, 10))

        self.status_label = ctk.CTkLabel(header, text="", text_color=Theme.TEXT_MUTED, font=Theme.FONT_SMALL)
        self.status_label.pack(side="right", padx=(0, 10))

    def _build_list(self):
        self.scroll = AutoHideScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=5, pady=(0, 5))

        self.pager = PaginationBar(self, page_size=30, on_change=self._on_page_change)
        self.pager.grid(row=2, column=0, sticky="ew", padx=5, pady=(0, 10))

    # ==========================================
    # 同步
    # ==========================================
    def sync_now(self):
        cfg = mail_config.load_config()
        if not mail_config.is_configured(cfg):
            messagebox.showwarning(
                "尚未設定", "請先到「系統設定 → 信件設定」\n填入 Gmail 帳號與應用程式密碼。"
            )
            return
        self.btn_sync.configure(state="disabled", text="🔄 同步中…")

        def work():
            result = mail_service.fetch_new(cfg)
            self.after(0, lambda: self._on_sync_done(result))

        threading.Thread(target=work, daemon=True).start()

    def _on_sync_done(self, result):
        self.btn_sync.configure(state="normal", text="🔄 同步")
        if not result.get("ok"):
            self.status_label.configure(text="❌ " + (result.get("error") or "同步失敗"), text_color=Theme.NEON_PINK)
            messagebox.showerror("同步失敗", result.get("error") or "同步失敗")
            return
        new = result.get("new", 0)
        updated = result.get("updated", 0)
        blocked = result.get("blocked", 0)
        own_replied = result.get("own_replied", 0)
        msg = f"✅ 新增 {new} 封、更新 {updated} 封"
        if blocked:
            msg += f"（過濾跳過 {blocked} 封）"
        if own_replied:
            msg += f"；新確認 {own_replied} 封已回覆"
        self.status_label.configure(
            text=msg, text_color=Theme.NEON_GREEN
        )
        self.refresh_list()

    # ==========================================
    # 動作：過濾寄件人
    # ==========================================
    def _block_sender(self, e):
        email_ = e.get("sender_email") or ""
        if not email_:
            return
        name = e.get("sender_name") or ""
        if not messagebox.askyesno(
            "過濾此寄件人",
            f"確定要過濾寄件人：\n{name} <{email_}>\n\n"
            "會把該寄件人的所有來信從資料庫清除，\n"
            "之後同步時也不再抓取該寄件人的信件。\n\n"
            "若要復原，請到「系統設定 → 信件設定」右側的過濾名單。",
        ):
            return
        try:
            Repository.add_email_blocklist(email_, name)
            removed = Repository.delete_emails_by_sender(email_)
        except Exception as ex:
            messagebox.showerror("錯誤", f"過濾失敗：\n{str(ex)}")
            return
        messagebox.showinfo(
            "已過濾", f"✅ 已將 {email_} 加入過濾名單。\n已清除該寄件人的 {removed} 封信件。"
        )
        self.refresh_list()

    # ==========================================
    # 清單渲染
    # ==========================================
    def _query_key(self):
        return (self.entry_search.get().strip(), self.filter_var.get())

    def _on_page_change(self):
        self.refresh_list()

    def refresh_list(self):
        self._render_seq += 1
        seq = self._render_seq
        for w in self.scroll.winfo_children():
            w.destroy()

        key = self._query_key()
        if key != getattr(self, "_last_query_key", None):
            self.pager.set_page(1)
            self._last_query_key = key

        cfg = mail_config.load_config()
        if not mail_config.is_configured(cfg):
            ctk.CTkLabel(
                self.scroll,
                text="尚未設定信箱帳號。\n請到「系統設定 → 信件設定」填入 Gmail 帳號與應用程式密碼。",
                text_color=Theme.TEXT_MUTED, justify="center",
            ).pack(pady=50)
            self.pager.set_total(0)
            self.status_label.configure(text="", text_color=Theme.TEXT_MUTED)
            return

        search = self.entry_search.get().strip() or None
        mode = self.filter_var.get()
        total = Repository.count_emails(search=search, filter_mode=mode)
        self.pager.set_total(total)
        if not total:
            ctk.CTkLabel(
                self.scroll,
                text="尚無客戶來信，按右上角「🔄 同步」抓取信件。",
                text_color=Theme.TEXT_MUTED,
            ).pack(pady=50)
            self.status_label.configure(text="", text_color=Theme.TEXT_MUTED)
            return

        page_size = self.pager.get_page_size()
        offset = (self.pager.get_page() - 1) * page_size
        emails = Repository.get_emails(
            search=search,
            filter_mode=mode,
            limit=page_size,
            offset=offset,
        )
        batch_render(
            self.scroll, emails, self._render_card,
            is_stale=lambda: self._render_seq != seq,
        )
        self.status_label.configure(text=f"共 {total} 封", text_color=Theme.TEXT_MUTED)

    def _render_card(self, e):
        card = ctk.CTkFrame(self.scroll, fg_color=Theme.BG_CARD, corner_radius=8)
        card.pack(fill="x", pady=4, padx=5)

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(10, 4))

        d_obj = self._parse_dt(e.get("received_at"))
        date_str = d_obj.strftime("%Y/%m/%d %H:%M") if d_obj else ""
        ctk.CTkLabel(top, text=date_str, text_color=Theme.TEXT_MUTED, width=130, anchor="w", font=Theme.FONT_SMALL).pack(side="left")
        ctk.CTkLabel(top, text=e.get("sender_name") or e.get("sender_email") or "", text_color=Theme.NEON_CYAN, width=180, anchor="w").pack(side="left", padx=(0, 10))
        ctk.CTkLabel(top, text=e.get("sender_email") or "", text_color=Theme.TEXT_MUTED, width=220, anchor="w", font=Theme.FONT_SMALL).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(top, text=e.get("subject") or "", text_color=Theme.TEXT_MAIN, anchor="w", justify="left").pack(side="left", fill="x", expand=True)

        mid = ctk.CTkFrame(card, fg_color="transparent")
        mid.pack(fill="x", padx=12, pady=(0, 4))

        badges = []
        if e.get("worklog_id"):
            badges.append(("已轉工作日誌", Theme.NEON_SELECT))
        if e.get("replied"):
            badges.append(("已回覆", Theme.NEON_GREEN))
        if e.get("is_internal_reply"):
            badges.append(("同事已回覆", Theme.NEON_YELLOW))
        if not badges:
            badges.append(("待處理", Theme.STATUS_PENDING))
        for text, color in badges:
            ctk.CTkLabel(mid, text=text, text_color=color, font=Theme.FONT_SMALL).pack(side="left", padx=(0, 10))

        preview = (e.get("body") or "").replace("\n", " ").strip()
        if preview:
            ctk.CTkLabel(
                mid, text=preview[:120] + ("…" if len(preview) > 120 else ""),
                text_color=Theme.TEXT_MUTED, anchor="w", justify="left", font=Theme.FONT_SMALL
            ).pack(side="left", fill="x", expand=True)

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkButton(
            btn_row, text="🚫 過濾此寄件人", width=120, font=Theme.FONT_SMALL,
            fg_color="transparent", border_width=1, border_color=Theme.NEON_PINK,
            text_color=Theme.NEON_PINK,
            command=lambda ee=e: self._block_sender(ee)
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            btn_row, text="📩回信", width=90, font=Theme.FONT_SMALL,
            fg_color=Theme.NEON_GREEN, text_color=Theme.ON_ACCENT,
            command=lambda ee=e: self._reply(ee)
        ).pack(side="right", padx=(6, 0))
        ctk.CTkButton(
            btn_row, text="📋 轉成工作日誌", width=120, font=Theme.FONT_SMALL,
            fg_color=Theme.NEON_CYAN, text_color=Theme.ON_ACCENT,
            command=lambda ee=e: self._convert(ee)
        ).pack(side="right", padx=(6, 0))
        ctk.CTkButton(
            btn_row, text="📖 展開內容", width=90, font=Theme.FONT_SMALL,
            fg_color="transparent", border_width=1, border_color=Theme.TEXT_MUTED,
            text_color=Theme.TEXT_MUTED,
            command=lambda ee=e: self._open_detail(ee)
        ).pack(side="right", padx=(6, 0))

    @staticmethod
    def _parse_dt(s):
        if not s:
            return None
        try:
            return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        except (TypeError, ValueError):
            return None

    # ==========================================
    # 動作：展開 / 回信 / 轉工作日誌
    # ==========================================
    def _open_detail(self, e):
        ReplyDetailDialog(self, e)

    def _reply(self, e):
        cfg = mail_config.load_config()
        if not mail_config.is_configured(cfg):
            messagebox.showwarning("尚未設定", "請先到「系統設定 → 信件設定」填入帳號與密碼。")
            return
        dlg = _ReplyDialog(self, cfg, e)
        self.wait_window(dlg)
        if dlg.sent:
            self.refresh_list()

    def _convert(self, e):
        dlg = _ConvertDialog(self, e)
        self.wait_window(dlg)
        if dlg.data is None:
            return
        try:
            worklog_id = Repository.add_worklog(dlg.data)
            Repository.set_email_worklog(e["id"], worklog_id)
        except Exception as ex:
            messagebox.showerror("錯誤", f"存檔失敗：\n{str(ex)}")
            return
        messagebox.showinfo("已轉成工作日誌", "✅ 已建立一筆「待處理」的工作日誌。\n可到「💻工作紀錄」查看與後續處理。")
        self.refresh_list()


# ==========================================
# 信件內容視窗（展開 / 回信 / 轉工作日誌）
# ==========================================
class ReplyDetailDialog(ctk.CTkToplevel):
    def __init__(self, master, e):
        super().__init__(master)
        self.email_row = e
        self.title("信件內容")
        self.geometry("680x520")
        self.minsize(520, 400)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        info = ctk.CTkFrame(self, fg_color=Theme.BG_CARD)
        info.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 8))
        info.grid_columnconfigure(1, weight=1)

        rows = [
            ("寄件人", f"{e.get('sender_name') or ''} <{e.get('sender_email') or ''}>"),
            ("日期", e.get("received_at") or ""),
            ("主旨", e.get("subject") or ""),
        ]
        for i, (label, value) in enumerate(rows):
            ctk.CTkLabel(info, text=label, text_color=Theme.TEXT_MUTED, font=Theme.FONT_SMALL, width=60, anchor="w").grid(row=i, column=0, sticky="nw", padx=(10, 5), pady=4)
            ctk.CTkLabel(info, text=value, text_color=Theme.TEXT_MAIN, font=Theme.FONT_SMALL, anchor="w", justify="left", wraplength=520).grid(row=i, column=1, sticky="ew", padx=(0, 10), pady=4)

        body = ctk.CTkTextbox(self, fg_color=Theme.BG_CARD, border_width=1, border_color=Theme.TEXT_MUTED)
        body.grid(row=2, column=0, sticky="nsew", padx=15, pady=(0, 10))
        body.insert("1.0", e.get("body") or "(無內容)")
        body.configure(state="disabled")

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=3, column=0, sticky="ew", padx=15, pady=(0, 15))
        ctk.CTkButton(
            btns, text="📩回信", fg_color=Theme.NEON_GREEN, text_color=Theme.ON_ACCENT,
            width=100, command=lambda: self._do_reply()
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            btns, text="📋 轉成工作日誌", fg_color=Theme.NEON_CYAN, text_color=Theme.ON_ACCENT,
            width=130, command=lambda: self._do_convert()
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            btns, text="關閉", fg_color="transparent", text_color=Theme.TEXT_MUTED,
            width=80, command=self.destroy
        ).pack(side="right", padx=(8, 0))

        self.transient(master.winfo_toplevel())
        self.grab_set()
        self.lift()

    def _do_reply(self):
        self.destroy()
        parent = self.master
        if hasattr(parent, "_reply"):
            parent._reply(self.email_row)

    def _do_convert(self):
        self.destroy()
        parent = self.master
        if hasattr(parent, "_convert"):
            parent._convert(self.email_row)


# ==========================================
# 回信視窗
# ==========================================
class _ReplyDialog(ctk.CTkToplevel):
    def __init__(self, master, cfg, e):
        super().__init__(master)
        self.cfg = cfg
        self.email_row = e
        self.sent = False
        self.title("回覆客戶")
        self.geometry("640x520")
        self.minsize(520, 420)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        to_list = [e.get("sender_email") or ""]
        cc_list = self._original_cc(e)
        # 公司留存副本：回信一律帶入（若尚未在名單中）
        if mail_service.COMPANY_CC_ADDRESS.lower() not in {a.lower() for a in cc_list}:
            cc_list.append(mail_service.COMPANY_CC_ADDRESS)
        info = ctk.CTkFrame(self, fg_color=Theme.BG_CARD)
        info.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 8))

        ctk.CTkLabel(info, text=f"原信主旨：{e.get('subject') or ''}", text_color=Theme.TEXT_MUTED, font=Theme.FONT_SMALL, anchor="w", justify="left", wraplength=560).pack(anchor="w", padx=10, pady=(8, 6))

        ctk.CTkLabel(info, text="收件人 (To)", text_color=Theme.TEXT_MUTED, font=Theme.FONT_SMALL, anchor="w").pack(anchor="w", padx=10, pady=(0, 2))
        self.entry_to = ctk.CTkEntry(info, width=580)
        self.entry_to.insert(0, ", ".join(to_list))
        self.entry_to.pack(anchor="w", padx=10, pady=(0, 6))

        ctk.CTkLabel(info, text="副本 (Cc)", text_color=Theme.TEXT_MUTED, font=Theme.FONT_SMALL, anchor="w").pack(anchor="w", padx=10, pady=(0, 2))
        self.entry_cc = ctk.CTkEntry(info, width=580)
        self.entry_cc.insert(0, ", ".join(cc_list))
        self.entry_cc.pack(anchor="w", padx=10, pady=(0, 8))

        ctk.CTkLabel(info, text="回覆內容", text_color=Theme.TEXT_MUTED, font=Theme.FONT_SMALL, anchor="w").pack(anchor="w", padx=10, pady=(0, 2))
        self.txt_body = ctk.CTkTextbox(self, fg_color=Theme.BG_CARD, border_width=1, border_color=Theme.TEXT_MUTED)
        self.txt_body.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 10))

        self.status_label = ctk.CTkLabel(self, text="", text_color=Theme.NEON_GREEN, font=Theme.FONT_SMALL, anchor="w")
        self.status_label.grid(row=2, column=0, sticky="ew", padx=15)

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=3, column=0, sticky="ew", padx=15, pady=(0, 15))
        self.btn_send = ctk.CTkButton(
            btns, text="📤 發送", fg_color=Theme.NEON_GREEN, text_color=Theme.ON_ACCENT,
            width=110, command=self._send
        )
        self.btn_send.pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            btns, text="取消", fg_color="transparent", text_color=Theme.TEXT_MUTED,
            width=80, command=self.destroy
        ).pack(side="right", padx=(8, 0))

        self.transient(master.winfo_toplevel())
        self.grab_set()
        self.lift()

    def _original_cc(self, e):
        """回覆所有人：原收件人 + 副本，扣除寄件人與自己。"""
        own = (self.cfg.get("email") or "").lower()
        raw = f"{e.get('to_emails') or ''},{e.get('cc_emails') or ''}".replace("\n", ",")
        addrs = []
        for _, addr in email.utils.getaddresses([raw]):
            a = addr.lower()
            if a and a != own and a != (e.get("sender_email") or "").lower():
                addrs.append(addr)
        return addrs

    def _send(self):
        body = self.txt_body.get("1.0", "end-1c").strip()
        to_list = [a.strip() for a in self.entry_to.get().replace(",", " ").split() if a.strip()]
        cc_list = [a.strip() for a in self.entry_cc.get().replace(",", " ").split() if a.strip()]
        if not to_list:
            messagebox.showwarning("警告", "收件人不可為空！")
            return
        if not body:
            messagebox.showwarning("警告", "回覆內容不可為空！")
            return
        self.btn_send.configure(state="disabled", text="📤 發送中…")
        self.status_label.configure(text="")

        def work():
            ok, msg = mail_service.send_reply(self.cfg, self.email_row, to_list, cc_list, body)
            self.after(0, lambda: self._on_sent(ok, msg))

        threading.Thread(target=work, daemon=True).start()

    def _on_sent(self, ok, msg):
        if not ok:
            self.btn_send.configure(state="normal", text="📤 發送")
            self.status_label.configure(text=f"❌ {msg}", text_color=Theme.NEON_PINK)
            messagebox.showerror("寄信失敗", msg)
            return
        try:
            Repository.mark_email_replied(
                self.email_row["id"],
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
        except Exception:
            pass
        self.sent = True
        self.destroy()


# ==========================================
# 轉成工作日誌視窗
# ==========================================
class _ConvertDialog(ctk.CTkToplevel):
    def __init__(self, master, e):
        super().__init__(master)
        self.email_row = e
        self.data = None
        self.projects = Repository.get_all_projects()
        self.title("轉成工作日誌")
        self.geometry("620x660")
        self.minsize(540, 580)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)

        suggest = mail_service.suggest_project_school(
            e.get("sender_email") or "", e.get("subject") or "", e.get("body") or ""
        )
        self.sugg = suggest

        body = ctk.CTkFrame(self, fg_color=Theme.BG_CARD)
        body.grid(row=0, column=0, sticky="nsew", padx=15, pady=(15, 8))
        body.grid_columnconfigure(1, weight=1)

        self.project_names = [p["name"] for p in self.projects]
        self.project_var = ctk.StringVar(value=suggest.get("project_name") or "【不指定】")
        ctk.CTkLabel(body, text="專案", text_color=Theme.TEXT_MUTED, font=Theme.FONT_SMALL, anchor="w").grid(row=0, column=0, sticky="w", padx=10, pady=6)
        self.combo_project = ctk.CTkComboBox(
            body, variable=self.project_var, values=["【不指定】"] + self.project_names,
            width=300, command=lambda _: self._on_project_change()
        )
        self.combo_project.grid(row=0, column=1, sticky="w", padx=(0, 10), pady=6)

        self.school_var = ctk.StringVar(value="【不指定】")
        ctk.CTkLabel(body, text="學校", text_color=Theme.TEXT_MUTED, font=Theme.FONT_SMALL, anchor="w").grid(row=1, column=0, sticky="w", padx=10, pady=6)
        self.combo_school = ctk.CTkComboBox(body, variable=self.school_var, values=["【不指定】"], width=300)
        self.combo_school.grid(row=1, column=1, sticky="w", padx=(0, 10), pady=6)

        self.contact_var = ctk.StringVar(value=e.get("sender_name") or "")
        ctk.CTkLabel(body, text="聯絡人", text_color=Theme.TEXT_MUTED, font=Theme.FONT_SMALL, anchor="w").grid(row=2, column=0, sticky="w", padx=10, pady=6)
        ctk.CTkEntry(body, textvariable=self.contact_var, width=300).grid(row=2, column=1, sticky="w", padx=(0, 10), pady=6)

        self.phone_var = ctk.StringVar(value="Email")
        ctk.CTkLabel(body, text="電話/分機", text_color=Theme.TEXT_MUTED, font=Theme.FONT_SMALL, anchor="w").grid(row=3, column=0, sticky="w", padx=10, pady=6)
        self.phone_entry = ctk.CTkEntry(body, textvariable=self.phone_var, width=300)
        self.phone_entry.grid(row=3, column=1, sticky="w", padx=(0, 10), pady=6)

        ctk.CTkLabel(body, text="問題內容", text_color=Theme.TEXT_MUTED, font=Theme.FONT_SMALL, anchor="w").grid(row=4, column=0, sticky="nw", padx=10, pady=6)
        self.txt_issue = ctk.CTkTextbox(body, fg_color=Theme.BG_DARK, border_width=1, border_color=Theme.TEXT_MUTED, height=130)
        self.txt_issue.grid(row=4, column=1, sticky="nsew", padx=(0, 10), pady=6)
        subject = e.get("subject") or ""
        self.txt_issue.insert("1.0", f"[客戶來信] {subject}")

        ctk.CTkLabel(body, text="處理情形", text_color=Theme.TEXT_MUTED, font=Theme.FONT_SMALL, anchor="w").grid(row=5, column=0, sticky="nw", padx=10, pady=6)
        self.txt_solution = ctk.CTkTextbox(body, fg_color=Theme.BG_DARK, border_width=1, border_color=Theme.TEXT_MUTED, height=130)
        self.txt_solution.grid(row=5, column=1, sticky="nsew", padx=(0, 10), pady=6)

        hint = ctk.CTkLabel(
            self, text=f"自動比對：{self._suggest_text(suggest)}",
            text_color=Theme.NEON_YELLOW if suggest.get("confidence") else Theme.TEXT_MUTED,
            font=Theme.FONT_SMALL, anchor="w", justify="left"
        )
        hint.grid(row=1, column=0, sticky="ew", padx=15)

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 15))
        ctk.CTkButton(
            btns, text="存檔", fg_color=Theme.NEON_GREEN, text_color=Theme.ON_ACCENT,
            width=110, command=self._ok
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            btns, text="取消", fg_color="transparent", text_color=Theme.TEXT_MUTED,
            width=80, command=self.destroy
        ).pack(side="right", padx=(8, 0))

        self._on_project_change()
        self.transient(master.winfo_toplevel())
        self.grab_set()
        self.lift()

    @staticmethod
    def _suggest_text(s):
        if not s.get("confidence"):
            return "無（將以「不指定」儲存，之後可在工作紀錄中修改）"
        level = "高" if s["confidence"] == "high" else "低"
        proj = s.get("project_name") or "不指定專案"
        return f"學校「{s.get('school_name')}」→ 專案「{proj}」（可信度 {level}，可手動更改）"

    def _on_project_change(self):
        pname = self.project_var.get()
        pid = next((p["id"] for p in self.projects if p["name"] == pname), None)
        schools = []
        if pid is not None:
            schools = [s["school_name"] for s in Repository.get_schools_by_project(pid)]
        self.combo_school.configure(values=["【不指定】"] + schools)
        sugg_school = self.sugg.get("school_name") or ""
        if sugg_school in schools:
            self.school_var.set(sugg_school)
        elif self.school_var.get() not in schools and self.school_var.get() != "【不指定】":
            self.school_var.set("【不指定】")

    def _ok(self):
        issue = self.txt_issue.get("1.0", "end-1c").strip()
        if not issue:
            messagebox.showwarning("警告", "問題內容不可為空！")
            return
        now = datetime.now()
        pname = self.project_var.get()
        sname = self.school_var.get()
        project_id = next((p["id"] for p in self.projects if p["name"] == pname), None)
        school_id = None
        if project_id is not None and sname != "【不指定】":
            school_id = next(
                (s["id"] for s in Repository.get_schools_by_project(project_id) if s["school_name"] == sname),
                None,
            )
        self.data = {
            "work_date": now.strftime("%Y-%m-%d"),
            "work_time": now.strftime("%H:%M:%S"),
            "project_id": project_id,
            "school_id": school_id,
            "contact_person": self.contact_var.get().strip() or None,
            "phone_ext": self.phone_var.get().strip() or None,
            "pii_info": None,
            "issue_content": issue,
            "solution": self.txt_solution.get("1.0", "end-1c").strip() or None,
            "status": "待處理",
            "transfer_to": None,
            "finish_date": None,
            "finish_time": None,
        }
        self.destroy()
