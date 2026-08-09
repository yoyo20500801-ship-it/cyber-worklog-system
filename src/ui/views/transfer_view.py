# 檔案：src/ui/views/transfer_view.py
import customtkinter as ctk
from datetime import datetime
from tkinter import messagebox
from src.ui.theme import Theme
from src.db.repository import Repository
from src.utils.date_helper import selectable_years
from src.ui.components.auto_hide_scroll import AutoHideScrollableFrame
from src.ui.components.pager import PaginationBar


class TransferSystemView(ctk.CTkFrame):
    """轉交系統：查看轉交紀錄，整理工作日誌並複製，供使用者自行貼上轉交"""

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        now = datetime.now()
        self.year_var = ctk.StringVar(value=str(now.year))
        self.month_var = ctk.StringVar(value=str(now.month).zfill(2))
        self.current_logs = []

        self._build_header()
        self._build_list()
        self.refresh_list()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=Theme.BG_CARD, corner_radius=8)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 15), ipadx=10, ipady=10)

        ctk.CTkLabel(
            header, text="📚 轉交系統 (TRANSFER CENTER)",
            font=Theme.FONT_HEADING, text_color=Theme.NEON_CYAN
        ).pack(side="left", padx=15, pady=10)

        years = selectable_years(Repository.get_min_worklog_year())
        months = [str(m).zfill(2) for m in range(1, 13)]

        self.combo_year = ctk.CTkComboBox(
            header, values=years, variable=self.year_var, width=80,
            command=lambda _: self.refresh_list()
        )
        self.combo_year.pack(side="left", padx=(20, 5))

        self.combo_month = ctk.CTkComboBox(
            header, values=months, variable=self.month_var, width=60,
            command=lambda _: self.refresh_list()
        )
        self.combo_month.pack(side="left", padx=5)

        self.btn_copy_all = ctk.CTkButton(
            header, text="📋 複製全部", width=110, fg_color=Theme.NEON_SELECT,
            text_color=Theme.TEXT_MAIN, command=self._copy_all
        )
        self.btn_copy_all.pack(side="right", padx=(0, 10))

        self.btn_refresh = ctk.CTkButton(
            header, text="🔄 重新整理", width=110, fg_color=Theme.NEON_SELECT,
            text_color=Theme.TEXT_MAIN, command=self.refresh_list
        )
        self.btn_refresh.pack(side="right", padx=(0, 15))

    def _build_list(self):
        self.scroll = AutoHideScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=5, pady=(0, 5))

        self.pager = PaginationBar(self, page_size=30, on_change=self._on_page_change)
        self.pager.grid(row=2, column=0, sticky="ew", padx=5, pady=(0, 10))

    def reset_to_now(self):
        now = datetime.now()
        self.combo_year.configure(values=selectable_years(Repository.get_min_worklog_year()))
        self.year_var.set(str(now.year))
        self.month_var.set(str(now.month).zfill(2))
        self.refresh_list()

    def _on_page_change(self):
        self.refresh_list()

    def refresh_list(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        y = self.year_var.get()
        m = self.month_var.get()
        key = (y, m)
        if key != getattr(self, "_last_query_key", None):
            self.pager.set_page(1)
            self._last_query_key = key
        self.current_logs = Repository.get_transfer_logs_by_month(y, m)
        self.pager.set_total(len(self.current_logs))
        if not self.current_logs:
            ctk.CTkLabel(self.scroll, text=f"沒有 {y} 年 {m} 月的轉交紀錄。", text_color=Theme.TEXT_MUTED).pack(pady=30)
            return
        for log in self.pager.get_slice(self.current_logs):
            self._build_card(log)

    def _build_card(self, log):
        card = ctk.CTkFrame(self.scroll, fg_color=Theme.BG_DARK, corner_radius=6)
        card.pack(fill="x", pady=4, padx=2)

        d_obj = datetime.strptime(log['work_date'], "%Y-%m-%d")
        t_str = log['work_time'][:5] if log.get('work_time') else ""
        time_str = f"{d_obj.month}/{d_obj.day} {t_str}"
        status = log.get('status') or '轉交'

        # --- 第一排：時間戳記 | 專案 | 學校 | 問題內容 | 電話 | 聯絡人 | 狀態 ---
        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(top_row, text=time_str, text_color=Theme.TEXT_MUTED, width=75, anchor="w").pack(side="left")
        ctk.CTkLabel(top_row, text=f"[{log.get('project_name', '未知')}]", text_color=Theme.NEON_CYAN, width=120, anchor="w").pack(side="left", padx=(0, 5))
        ctk.CTkLabel(top_row, text=log.get('school_name', ''), text_color=Theme.TEXT_MAIN, width=100, anchor="w").pack(side="left", padx=(0, 10))

        ctk.CTkLabel(top_row, text=log['issue_content'], text_color=Theme.TEXT_MAIN, anchor="w", justify="left").pack(side="left", fill="x", expand=True)

        if log.get('phone_ext'):
            ctk.CTkLabel(top_row, text=f"☎ {log['phone_ext']}", text_color=Theme.TEXT_MUTED, anchor="e").pack(side="left", padx=5)
        if log.get('contact_person'):
            ctk.CTkLabel(top_row, text=f"👤 {log['contact_person']}", text_color=Theme.TEXT_MUTED, anchor="e").pack(side="left", padx=5)
        ctk.CTkLabel(top_row, text=status, text_color=Theme.STATUS_TRANSFER, width=55, anchor="e").pack(side="right", padx=(5, 0))

        # --- 第二排：處理情形(左/灰) | 個資(中/灰) | 轉交人員(右/藍) | 複製按鈕 ---
        bottom_row = ctk.CTkFrame(card, fg_color="transparent")
        bottom_row.pack(fill="x", padx=10, pady=(0, 8))
        bottom_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            bottom_row, text=f"▸ 處理情形: {log.get('solution') or '－'}",
            text_color=Theme.TEXT_MUTED, anchor="w", justify="left"
        ).grid(row=0, column=0, sticky="w", padx=(315, 10))
        ctk.CTkLabel(
            bottom_row, text=f"🔒 個資: {log.get('pii_info') or '－'}",
            text_color=Theme.TEXT_MUTED, anchor="w", width=280
        ).grid(row=0, column=1, sticky="w", padx=(0, 10))
        if log.get('transfer_to'):
            ctk.CTkLabel(
                bottom_row, text=f"⮑ 轉交: {log.get('transfer_to')}",
                text_color=Theme.STATUS_TRANSFER, anchor="e", justify="right"
            ).grid(row=0, column=2, sticky="e")
        ctk.CTkButton(
            bottom_row, text="📋 整理並複製", width=120, fg_color=Theme.NEON_SELECT,
            text_color=Theme.TEXT_MAIN,
            command=lambda lid=log["id"]: self._copy_single(lid)
        ).grid(row=0, column=3, sticky="e", padx=(10, 0))

    @staticmethod
    def _build_message(log):
        """整理單筆工作日誌成可複製的文字"""
        lines = [
            "【工作日誌轉交通知】",
            f"專案：{log.get('project_name') or '無'}",
            f"學校：{log.get('school_name') or '無'}",
            f"問題內容：{log.get('issue_content') or ''}",
        ]
        if log.get('pii_info'):
            lines.append(f"個資：{log['pii_info']}")
        if log.get('phone_ext'):
            lines.append(f"電話：{log['phone_ext']}")
        if log.get('contact_person'):
            lines.append(f"聯絡人：{log['contact_person']}")
        
        return "\n".join(lines)

    def _find_log(self, log_id):
        return next((lg for lg in self.current_logs if lg["id"] == log_id), None)

    def _copy_single(self, log_id):
        log = self._find_log(log_id)
        if log is None:
            messagebox.showwarning("提示", "找不到這筆紀錄，請按「重新整理」。")
            return
        _CopyDialog(self.winfo_toplevel(), self._build_message(log))

    def _copy_all(self):
        if not self.current_logs:
            messagebox.showinfo("提示", "目前沒有可複製的轉交紀錄。")
            return
        separator = "\n\n" + "=" * 30 + "\n\n"
        text = separator.join(self._build_message(lg) for lg in self.current_logs)
        _CopyDialog(self.winfo_toplevel(), text)


class _CopyDialog(ctk.CTkToplevel):
    """顯示整理好的工作日誌文字，並提供複製到剪貼簿的按鈕"""

    def __init__(self, master, text):
        super().__init__(master)
        self.title("整理工作日誌")
        self.geometry("560x480")
        self.minsize(420, 320)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self, text="📋 以下為整理好的工作日誌，按下「複製」即可貼到任何地方：",
            font=Theme.FONT_SMALL, text_color=Theme.TEXT_MUTED, anchor="w"
        ).grid(row=0, column=0, sticky="ew", padx=15, pady=(12, 6))

        box = ctk.CTkTextbox(self, wrap="word", font=Theme.FONT_BODY, fg_color=Theme.BG_DARK)
        box.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 10))
        box.insert("1.0", text)
        box.configure(state="disabled")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 12))
        self.btn_copy = ctk.CTkButton(
            btn_frame, text="📋 複製到剪貼簿", fg_color=Theme.NEON_GREEN,
            text_color=Theme.ON_ACCENT, width=140,
            command=lambda: self._do_copy(text)
        )
        self.btn_copy.pack(side="right")
        ctk.CTkButton(
            btn_frame, text="關閉", fg_color="transparent", text_color=Theme.TEXT_MUTED,
            width=80, command=self.destroy
        ).pack(side="right", padx=(0, 10))

        self.transient(master)
        self.grab_set()
        self.lift()

    def _do_copy(self, text):
        root = self.winfo_toplevel()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        self.btn_copy.configure(text="✅ 已複製！")
