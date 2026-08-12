# 檔案：src/ui/views/overview_view.py
import customtkinter as ctk
from datetime import datetime
from src.ui.theme import Theme
from src.db.repository import Repository
from src.utils.date_helper import selectable_years
from src.ui.components.auto_hide_scroll import AutoHideScrollableFrame
from src.ui.components.pager import PaginationBar
from src.ui.components.batch import batch_render

STATUS_ORDER = ("已處理", "待處理", "轉交")
STATUS_COLORS = {"已處理": Theme.NEON_GREEN, "待處理": Theme.STATUS_PENDING, "轉交": Theme.STATUS_TRANSFER}
WEEKDAY_MAP = {0: "一", 1: "二", 2: "三", 3: "四", 4: "五", 5: "六", 6: "日"}


class OverviewView(ctk.CTkFrame):
    """總覽：每月件數統計、點擊帶出紀錄、專案/每日/比較等數據"""

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        now = datetime.now()
        self.year_var = ctk.StringVar(value=str(now.year))
        self.month_var = ctk.StringVar(value=str(now.month).zfill(2))
        self.current_filter = "全部"

        self._data_version = -1
        self._render_seq = 0
        self._refresh_after_id = None

        self._build_header()
        self._build_stat_cards()
        self._build_main_area()
        self.refresh_all()

    # ==========================================
    # 頁首：標題 + 年月切換 + 重新整理
    # ==========================================
    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=Theme.BG_CARD, corner_radius=8)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 15), ipadx=10, ipady=10)

        ctk.CTkLabel(
            header, text="📊 總覽",
            font=Theme.FONT_HEADING, text_color=Theme.NEON_CYAN
        ).pack(side="left", padx=15, pady=10)

        years = selectable_years(Repository.get_min_worklog_year())
        months = [str(m).zfill(2) for m in range(1, 13)]

        self.combo_year = ctk.CTkComboBox(
            header, values=years, variable=self.year_var, width=80,
            command=lambda _: self._schedule_refresh()
        )
        self.combo_year.pack(side="left", padx=(20, 5))

        self.combo_month = ctk.CTkComboBox(
            header, values=months, variable=self.month_var, width=60,
            command=lambda _: self._schedule_refresh()
        )
        self.combo_month.pack(side="left", padx=5)

        self.btn_refresh = ctk.CTkButton(
            header, text="🔄 重新整理", width=110, fg_color=Theme.NEON_SELECT,
            text_color=Theme.TEXT_MAIN, command=self.refresh_all
        )
        self.btn_refresh.pack(side="right", padx=15)

    def _schedule_refresh(self):
        # 年月下拉連動時常連續觸發，合併成一次刷新
        if self._refresh_after_id is not None:
            self.after_cancel(self._refresh_after_id)
        self._refresh_after_id = self.after(120, self.refresh_all)

    # ==========================================
    # 統計卡：總件數 / 已處理 / 待處理 / 轉交（可點擊）
    # ==========================================
    def _build_stat_cards(self):
        self.cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.cards_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 15))
        for i in range(4):
            self.cards_frame.grid_columnconfigure(i, weight=1)

        self.stat_cards = {}
        items = [("總件數", "全部"), ("已處理", "已處理"), ("待處理", "待處理"), ("轉交", "轉交")]
        for i, (label, key) in enumerate(items):
            card = ctk.CTkFrame(self.cards_frame, fg_color=Theme.BG_CARD, corner_radius=8, cursor="hand2")
            card.grid(row=0, column=i, sticky="ew", padx=6, pady=2)

            value_label = ctk.CTkLabel(
                card, text="0", font=("Microsoft JhengHei", 36, "bold"),
                text_color=STATUS_COLORS.get(key, Theme.NEON_MAIN)
            )
            value_label.pack(pady=(12, 2))
            name_label = ctk.CTkLabel(
                card, text=label, font=Theme.FONT_SMALL, text_color=Theme.TEXT_MUTED
            )
            name_label.pack(pady=(0, 10))

            card.bind("<Button-1>", lambda e, k=key: self._apply_filter(k))
            value_label.bind("<Button-1>", lambda e, k=key: self._apply_filter(k))
            name_label.bind("<Button-1>", lambda e, k=key: self._apply_filter(k))

            self.stat_cards[key] = card
            self.stat_cards[key + "_value"] = value_label

    def _apply_filter(self, key):
        self.current_filter = "全部" if key == "總件數" else key
        self._refresh_records()
        self._highlight_cards()

    def _highlight_cards(self):
        for key in ("全部", "已處理", "待處理", "轉交"):
            card = self.stat_cards[key]
            if self.current_filter == key:
                card.configure(border_width=2, border_color=Theme.NEON_CYAN)
            else:
                card.configure(border_width=0)

    # ==========================================
    # 主區：左欄紀錄清單 + 右欄數據面板
    # ==========================================
    def _build_main_area(self):
        self.main_area = ctk.CTkFrame(self, fg_color="transparent")
        self.main_area.grid(row=2, column=0, columnspan=2, sticky="nsew")
        self.main_area.grid_columnconfigure(0, weight=1)
        self.main_area.grid_columnconfigure(1, weight=0)
        self.main_area.grid_rowconfigure(0, weight=1)

        list_frame = ctk.CTkFrame(self.main_area, fg_color=Theme.BG_CARD, corner_radius=8)
        list_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        list_frame.grid_rowconfigure(1, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        self.records_title = ctk.CTkLabel(
            list_frame, text="紀錄清單", font=Theme.FONT_BODY,
            text_color=Theme.NEON_CYAN, anchor="w"
        )
        self.records_title.grid(row=0, column=0, sticky="ew", padx=15, pady=(12, 5))

        self.records_scroll = AutoHideScrollableFrame(list_frame, fg_color="transparent")
        self.records_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        self.records_pager = PaginationBar(list_frame, page_size=30, on_change=self._refresh_records)
        self.records_pager.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 12))

        self.stats_panel = AutoHideScrollableFrame(
            self.main_area, fg_color=Theme.BG_CARD, corner_radius=8, width=340
        )
        self.stats_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.stats_panel.grid_columnconfigure(0, weight=1)

    # ==========================================
    # 刷新
    # ==========================================
    def reset_to_now(self):
        now = datetime.now()
        target = (str(now.year), str(now.month).zfill(2))
        current = (self.year_var.get(), self.month_var.get())
        self.combo_year.configure(values=selectable_years(Repository.get_min_worklog_year()))
        self.year_var.set(target[0])
        self.month_var.set(target[1])
        # 年月沒變且資料沒被改過 → 畫面已是現況，直接略過重建
        if current == target and self._data_version == Repository.get_data_version():
            return
        self.refresh_all()

    def refresh_all(self):
        summary = Repository.get_status_summary(self.year_var.get(), self.month_var.get())
        self.refresh_summary(summary)
        self._refresh_records()
        self._refresh_extra_stats(summary)
        self._highlight_cards()

    def refresh_summary(self, summary):
        mapping = {"全部": "總計", "已處理": "已處理", "待處理": "待處理", "轉交": "轉交"}
        for key, skey in mapping.items():
            label = self.stat_cards[key + "_value"]
            label.configure(text=str(summary[skey]))

    def _refresh_records(self):
        self._render_seq += 1
        seq = self._render_seq
        for w in self.records_scroll.winfo_children():
            w.destroy()
        y = self.year_var.get()
        m = self.month_var.get()
        status = None if self.current_filter == "全部" else self.current_filter

        # 篩選條件改變時跳回第一頁
        key = (y, m, status)
        if key != getattr(self, "_last_records_key", None):
            self.records_pager.set_page(1)
            self._last_records_key = key

        total = Repository.count_worklogs(y, m, status)
        self.records_pager.set_total(total)

        filter_text = "所有狀態" if status is None else f"狀態：{status}"
        self.records_title.configure(text=f"紀錄清單 ({filter_text}) · {total} 筆")

        if not total:
            ctk.CTkLabel(
                self.records_scroll, text=f"{y} 年 {m} 月 沒有符合條件的紀錄。",
                text_color=Theme.TEXT_MUTED
            ).pack(pady=30)
            self._data_version = Repository.get_data_version()
            return
        page_size = self.records_pager.get_page_size()
        offset = (self.records_pager.get_page() - 1) * page_size
        logs = Repository.get_worklogs_page(y, m, status, page_size, offset)
        self._data_version = Repository.get_data_version()
        batch_render(
            self.records_scroll, logs, self._build_record_card,
            is_stale=lambda: self._render_seq != seq,
        )

    def _build_record_card(self, log):
        card = ctk.CTkFrame(self.records_scroll, fg_color=Theme.BG_DARK, corner_radius=6)
        card.pack(fill="x", pady=4, padx=2)

        d_obj = datetime.strptime(log['work_date'], "%Y-%m-%d")
        t_str = log['work_time'][:5] if log.get('work_time') else ""
        time_str = f"{d_obj.month}/{d_obj.day} {t_str}"
        status = log.get('status') or '已處理'

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
        ctk.CTkLabel(
            top_row, text=status, text_color=STATUS_COLORS.get(status, Theme.TEXT_MAIN),
            width=55, anchor="e"
        ).pack(side="right", padx=(5, 0))

        bottom_row = ctk.CTkFrame(card, fg_color="transparent")
        bottom_row.pack(fill="x", padx=10, pady=(0, 8))
        bottom_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            bottom_row, text=f"▸ 處理情形: {log.get('solution') or '－'}",
            text_color=Theme.TEXT_MUTED, anchor="w", justify="left"
        ).grid(row=0, column=0, sticky="w", padx=(315, 10))
        ctk.CTkLabel(
            bottom_row, text=f"🔒 個資: {log.get('pii_info') or '－'}",
            text_color=Theme.TEXT_MUTED, anchor="w" #, width=280
        ).grid(row=0, column=1, sticky="w", padx=(0, 10))
        if log.get('transfer_to'):
            ctk.CTkLabel(
                bottom_row, text=f"⮑ 轉交: {log.get('transfer_to')}",
                text_color=Theme.STATUS_TRANSFER, anchor="e" #, width=150
            ).grid(row=0, column=2, sticky="e")

    # ==========================================
    # 右欄數據面板
    # ==========================================
    def _refresh_extra_stats(self, summary):
        for w in self.stats_panel.winfo_children():
            w.destroy()
        y = self.year_var.get()
        m = self.month_var.get()

        self._build_project_stats(y, m)
        self._build_daily_stats(y, m)
        self._build_month_compare(y, m, summary)

    def _section(self, title):
        frame = ctk.CTkFrame(self.stats_panel, fg_color="transparent")
        frame.pack(fill="x", padx=12, pady=(14, 4))
        ctk.CTkLabel(
            frame, text=title, font=Theme.FONT_BODY, text_color=Theme.NEON_CYAN, anchor="w"
        ).pack(fill="x")
        ctk.CTkFrame(frame, fg_color=Theme.BG_DARK, height=1).pack(fill="x", pady=4)
        return frame

    def _build_project_stats(self, y, m):
        frame = self._section("📦 各專案件數排行")
        projects = Repository.get_project_summary(y, m)
        if not projects:
            ctk.CTkLabel(frame, text="本月無資料", text_color=Theme.TEXT_MUTED, font=Theme.FONT_SMALL, anchor="w").pack(fill="x", pady=2)
            return
        total = sum(p["cnt"] for p in projects) or 1
        max_cnt = max(p["cnt"] for p in projects) or 1
        for p in projects:
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(
                row, text=p["project_name"], font=Theme.FONT_SMALL,
                text_color=Theme.TEXT_MAIN, anchor="w", width=90
            ).pack(side="left")
            bar = ctk.CTkProgressBar(row, width=130, fg_color=Theme.BG_DARK, progress_color=Theme.NEON_CYAN)
            bar.set(p["cnt"] / max_cnt)
            bar.pack(side="left", padx=(8, 8))
            ctk.CTkLabel(
                row, text=f"{p['cnt']} / {p['cnt'] / total * 100:.0f}%",
                font=Theme.FONT_SMALL, text_color=Theme.TEXT_MUTED
            ).pack(side="left")

    def _build_daily_stats(self, y, m):
        frame = self._section("📅 每日件數分布")
        days = Repository.get_daily_summary(y, m)
        if not days:
            ctk.CTkLabel(frame, text="本月無資料", text_color=Theme.TEXT_MUTED, font=Theme.FONT_SMALL, anchor="w").pack(fill="x", pady=2)
            return
        max_cnt = max(d["cnt"] for d in days) or 1
        for d in days:
            d_obj = datetime.strptime(d["work_date"], "%Y-%m-%d")
            label = f"{d_obj.day}日 (星期{WEEKDAY_MAP[d_obj.weekday()]})"
            is_peak = d["cnt"] == max_cnt
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(
                row, text=label, font=Theme.FONT_SMALL,
                text_color=Theme.NEON_YELLOW if is_peak else Theme.TEXT_MAIN,
                anchor="w", width=95
            ).pack(side="left")
            bar = ctk.CTkProgressBar(row, width=120, fg_color=Theme.BG_DARK, progress_color=Theme.NEON_GREEN if is_peak else Theme.NEON_SELECT)
            bar.set(d["cnt"] / max_cnt)
            bar.pack(side="left", padx=(8, 8))
            ctk.CTkLabel(
                row, text=f"{d['cnt']} 件", font=Theme.FONT_SMALL,
                text_color=Theme.NEON_YELLOW if is_peak else Theme.TEXT_MUTED
            ).pack(side="left")

    def _build_month_compare(self, y, m, cur):
        frame = self._section("⚖️ 本月 vs 上月比較")
        y_i, m_i = int(y), int(m)
        if m_i == 1:
            prev_y, prev_m = str(y_i - 1), "12"
        else:
            prev_y, prev_m = str(y_i), str(m_i - 1).zfill(2)

        prev = Repository.get_status_summary(prev_y, prev_m)

        for key in ("總計", "已處理", "待處理", "轉交"):
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            label = "總件數" if key == "總計" else key
            delta = cur[key] - prev[key]
            if delta > 0:
                diff_text = f"▲ +{delta}"
                diff_color = Theme.NEON_GREEN
            elif delta < 0:
                diff_text = f"▼ {delta}"
                diff_color = Theme.STATUS_PENDING
            else:
                diff_text = "─ 持平"
                diff_color = Theme.TEXT_MUTED
            ctk.CTkLabel(
                row, text=f"{label}: {cur[key]} 件", font=Theme.FONT_SMALL,
                text_color=Theme.TEXT_MAIN, anchor="w", width=120
            ).pack(side="left")
            ctk.CTkLabel(
                row, text=diff_text, font=Theme.FONT_SMALL, text_color=diff_color
            ).pack(side="left", padx=(8, 0))

        ctk.CTkLabel(
            frame, text=f"上月({prev_y}-{prev_m})：{prev['總計']} 件",
            font=Theme.FONT_SMALL, text_color=Theme.TEXT_MUTED, anchor="w"
        ).pack(fill="x", pady=(6, 2))
