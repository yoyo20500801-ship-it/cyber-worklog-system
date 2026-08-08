# 檔案：src/ui/views/db_search_view.py
import customtkinter as ctk
from src.ui.theme import Theme
from src.db.repository import Repository


class DatabaseSearchView(ctk.CTkFrame):
    """資料庫搜尋：查看資料表與欄位，下 SQL 查詢，顯示回傳結果"""

    MAX_DISPLAY_ROWS = 200

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)

        self._build_schema_panel()
        self._build_sql_panel()
        self._build_result_panel()
        self.load_schema()

    # ==========================================
    # 左側：資料表與欄位
    # ==========================================
    def _build_schema_panel(self):
        panel = ctk.CTkFrame(self, fg_color=Theme.BG_CARD, corner_radius=8, width=300)
        panel.grid(row=0, column=0, rowspan=2, sticky="nsw", padx=(0, 15), pady=0)
        panel.grid_propagate(False)
        panel.grid_rowconfigure(1, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            panel, text="📋 資料表與欄位（點資料表自動帶入 SQL）",
            font=Theme.FONT_BODY, text_color=Theme.NEON_CYAN, anchor="w"
        ).grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 5))

        self.schema_scroll = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        self.schema_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 15))

    # ==========================================
    # 右側上方：SQL 輸入區
    # ==========================================
    def _build_sql_panel(self):
        sql_frame = ctk.CTkFrame(self, fg_color=Theme.BG_CARD, corner_radius=8)
        sql_frame.grid(row=0, column=1, sticky="ew", pady=(0, 15))
        sql_frame.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(sql_frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=15, pady=(10, 5))
        ctk.CTkLabel(header, text="🔍 SQL 查詢語法", font=Theme.FONT_BODY, text_color=Theme.NEON_CYAN).pack(side="left")
        self.status_label = ctk.CTkLabel(header, text="", text_color=Theme.TEXT_MUTED)
        self.status_label.pack(side="right")

        self.sql_textbox = ctk.CTkTextbox(
            sql_frame, height=130, border_width=1, border_color=Theme.TEXT_MUTED,
            font=("Consolas", 13), text_color=Theme.TEXT_MAIN
        )
        self.sql_textbox.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 5))
        self.sql_textbox.insert("0.0", "SELECT * FROM worklogs ORDER BY created_at DESC LIMIT 100;")
        self.sql_textbox.bind("<F5>", self.run_query)

        btn_row = ctk.CTkFrame(sql_frame, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 10))

        self.btn_run = ctk.CTkButton(
            btn_row, text="▶ 執行 (F5)", fg_color=Theme.NEON_GREEN, text_color=Theme.ON_ACCENT,
            width=130, command=self.run_query
        )
        self.btn_run.pack(side="left")

        self.btn_clear_sql = ctk.CTkButton(
            btn_row, text="清空", fg_color="transparent", text_color=Theme.TEXT_MUTED,
            border_width=1, border_color=Theme.TEXT_MUTED, width=80, command=self.clear_sql
        )
        self.btn_clear_sql.pack(side="left", padx=(10, 0))

        ctk.CTkLabel(
            btn_row, text="支援 SELECT / INSERT / UPDATE / DELETE（修改類語句執行後自動存檔）",
            font=Theme.FONT_SMALL, text_color=Theme.TEXT_MUTED
        ).pack(side="left", padx=(20, 0))

    # ==========================================
    # 右側下方：執行結果顯示區
    # ==========================================
    def _build_result_panel(self):
        result_frame = ctk.CTkFrame(self, fg_color=Theme.BG_CARD, corner_radius=8)
        result_frame.grid(row=1, column=1, sticky="nsew")
        result_frame.grid_rowconfigure(1, weight=1)
        result_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            result_frame, text="📄 執行結果", font=Theme.FONT_BODY,
            text_color=Theme.NEON_CYAN, anchor="w"
        ).grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 5))

        self.result_scroll = ctk.CTkScrollableFrame(result_frame, fg_color="transparent")
        self.result_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

    # ==========================================
    # 行為
    # ==========================================
    def load_schema(self):
        for w in self.schema_scroll.winfo_children():
            w.destroy()
        try:
            schema = Repository.get_db_schema()
        except Exception as e:
            ctk.CTkLabel(self.schema_scroll, text=f"讀取失敗：{e}", text_color=Theme.NEON_PINK).pack(anchor="w", padx=5, pady=5)
            return
        if not schema:
            ctk.CTkLabel(self.schema_scroll, text="（無資料表）", text_color=Theme.TEXT_MUTED).pack(anchor="w", padx=5, pady=5)
            return

        for t in schema:
            table_name = t["table"]
            card = ctk.CTkFrame(self.schema_scroll, fg_color=Theme.BG_DARK, corner_radius=6)
            card.pack(fill="x", pady=3)

            btn = ctk.CTkButton(
                card, text=f"🗂  {table_name}", font=Theme.FONT_SMALL, fg_color="transparent",
                text_color=Theme.TEXT_MAIN, anchor="w", hover_color=Theme.BG_CARD,
                command=lambda name=table_name: self._use_table(name)
            )
            btn.pack(fill="x", padx=5, pady=(5, 0))

            cols = "、".join(t["columns"]) if t["columns"] else "（無欄位）"
            ctk.CTkLabel(
                card, text=cols, font=Theme.FONT_SMALL, text_color=Theme.TEXT_MUTED,
                anchor="w", justify="left", wraplength=260
            ).pack(fill="x", padx=12, pady=(0, 6))

    def _use_table(self, table_name):
        self.sql_textbox.delete("0.0", "end")
        self.sql_textbox.insert("0.0", f'SELECT * FROM "{table_name}" LIMIT 100;')

    def clear_sql(self):
        self.sql_textbox.delete("0.0", "end")

    def run_query(self, event=None):
        sql = self.sql_textbox.get("0.0", "end-1c").strip()
        if not sql:
            return
        for w in self.result_scroll.winfo_children():
            w.destroy()

        try:
            result = Repository.execute_sql(sql)
        except Exception as e:
            self.status_label.configure(text="執行失敗", text_color=Theme.NEON_PINK)
            ctk.CTkLabel(
                self.result_scroll, text=f"❌ SQL 錯誤：\n{e}",
                text_color=Theme.NEON_PINK, anchor="w", justify="left"
            ).pack(fill="x", padx=10, pady=10)
            return

        if result["is_select"]:
            self._render_select_result(result)
        else:
            count = result["rowcount"]
            self.status_label.configure(text=f"✅ 執行成功，影響 {count} 列", text_color=Theme.NEON_GREEN)
            ctk.CTkLabel(
                self.result_scroll, text=f"執行成功，影響 {count} 列。",
                text_color=Theme.NEON_GREEN
            ).pack(anchor="w", padx=10, pady=10)

    def _render_select_result(self, result):
        columns = result["columns"]
        rows = result["rows"]
        total = len(rows)

        if total == 0:
            self.status_label.configure(text="查詢完成，0 列", text_color=Theme.TEXT_MUTED)
            ctk.CTkLabel(self.result_scroll, text="查詢完成，沒有任何資料列。", text_color=Theme.TEXT_MUTED).pack(anchor="w", padx=10, pady=10)
            return

        display = rows[: self.MAX_DISPLAY_ROWS]
        grid = ctk.CTkFrame(self.result_scroll, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=5, pady=5)

        for c, col in enumerate(columns):
            ctk.CTkLabel(grid, text=str(col), font=Theme.FONT_SMALL, text_color=Theme.NEON_CYAN, anchor="w").grid(row=0, column=c, sticky="w", padx=3, pady=1)

        for r, row in enumerate(display, start=1):
            for c, val in enumerate(row):
                text = "NULL" if val is None else str(val)
                ctk.CTkLabel(grid, text=text, font=Theme.FONT_SMALL, text_color=Theme.TEXT_MAIN, anchor="w").grid(row=r, column=c, sticky="w", padx=3, pady=1)

        note = f"共 {total} 列" + (f"，僅顯示前 {self.MAX_DISPLAY_ROWS} 列。" if total > self.MAX_DISPLAY_ROWS else "。")
        self.status_label.configure(text=f"✅ {note}", text_color=Theme.NEON_GREEN)
