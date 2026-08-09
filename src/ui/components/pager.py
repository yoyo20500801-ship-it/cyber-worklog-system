# 檔案：src/ui/components/pager.py
# 分頁工具列：上一頁 / 下一頁與頁碼顯示。
from math import ceil

import customtkinter as ctk

from src.ui.theme import Theme


class PaginationBar(ctk.CTkFrame):
    def __init__(self, master, page_size=30, on_change=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.page_size = page_size
        self.on_change = on_change
        self.page = 1
        self.total = 0
        self.pages = 1

        self.btn_prev = ctk.CTkButton(
            self, text="◀ 上一頁", width=90, font=Theme.FONT_SMALL,
            fg_color=Theme.BG_CARD, text_color=Theme.TEXT_MAIN, command=self._prev
        )
        self.btn_prev.pack(side="left", padx=(0, 10))

        self.label = ctk.CTkLabel(
            self, text="", font=Theme.FONT_SMALL, text_color=Theme.TEXT_MUTED
        )
        self.label.pack(side="left")

        self.btn_next = ctk.CTkButton(
            self, text="下一頁 ▶", width=90, font=Theme.FONT_SMALL,
            fg_color=Theme.BG_CARD, text_color=Theme.TEXT_MAIN, command=self._next
        )
        self.btn_next.pack(side="left", padx=(10, 0))

    def set_total(self, total):
        self.total = max(0, total)
        self.pages = max(1, ceil(self.total / self.page_size))
        if self.page > self.pages:
            self.page = self.pages
        self._update()

    def set_page(self, page):
        self.page = max(1, min(page, self.pages))
        self._update()

    def get_page(self):
        return self.page

    def get_page_size(self):
        return self.page_size

    def get_slice(self, items):
        start = (self.page - 1) * self.page_size
        return items[start:start + self.page_size]

    def _prev(self):
        if self.page > 1:
            self.page -= 1
            self._update()
            if self.on_change:
                self.on_change()

    def _next(self):
        if self.page < self.pages:
            self.page += 1
            self._update()
            if self.on_change:
                self.on_change()

    def _update(self):
        self.label.configure(text=f"第 {self.page} / {self.pages} 頁 · 共 {self.total} 筆")
        self.btn_prev.configure(state="normal" if self.page > 1 else "disabled")
        self.btn_next.configure(state="normal" if self.page < self.pages else "disabled")
