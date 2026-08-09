# 檔案：src/ui/components/dual_scroll_frame.py
# 雙向捲動容器：同時提供垂直與水平捲動。
# - 水平捲軸只有在內容比視窗寬時才顯示，否則自動隱藏
# - 滑鼠滾輪＝垂直捲動，Shift＋滾輪＝水平捲動（與 CTkScrollableFrame 一致）
import sys
import tkinter as tk

import customtkinter as ctk

from src.ui.theme import Theme


class DualScrollableFrame(ctk.CTkFrame):
    def __init__(self, master, fg_color="transparent"):
        super().__init__(master, fg_color=fg_color)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        bg = Theme.BG_CARD if fg_color == "transparent" else fg_color

        self.canvas = tk.Canvas(self, highlightthickness=0, bg=bg)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.configure(xscrollincrement=1, yscrollincrement=1)

        self.vbar = ctk.CTkScrollbar(self, orientation="vertical", command=self.canvas.yview)
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self._update_vbar)

        self.hbar = ctk.CTkScrollbar(self, orientation="horizontal", command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=self._update_hscroll)

        self.content = ctk.CTkFrame(self.canvas, fg_color=bg)
        self._window_id = self.canvas.create_window((0, 0), window=self.content, anchor="nw")

        self.content.bind("<Configure>", self._update_scrollregion)
        self.canvas.bind("<Configure>", self._fit_width)

        root = self.winfo_toplevel()
        root.bind_all("<MouseWheel>", self._on_mousewheel, add=True)
        if sys.platform == "linux":
            root.bind_all("<Button-4>", self._on_mousewheel, add=True)
            root.bind_all("<Button-5>", self._on_mousewheel, add=True)

    # ==========================================
    # 捲動區域與捲軸
    # ==========================================
    def _update_scrollregion(self, event=None):
        # 延遲到下一個 idle 再重算，確保子元件已排版完成（reqwidth 才準確）
        self.after_idle(self._rebuild_layout)

    def _fit_width(self, event):
        self.after_idle(self._rebuild_layout)

    def _rebuild_layout(self):
        try:
            req_w = self.content.winfo_reqwidth()
            req_h = self.content.winfo_reqheight()
            canvas_w = self.canvas.winfo_width()
        except Exception:
            return
        # 內容比視窗寬 → 維持內容自然寬度（可水平捲動）；較窄 → 填滿視窗寬度
        self.canvas.itemconfigure(self._window_id, width=max(req_w, canvas_w))
        self.canvas.configure(scrollregion=(0, 0, req_w, req_h))
        self._clamp_view()
        self._update_hscroll()
        self._update_vbar()

    def _update_vbar(self, *args):
        first, last = self.canvas.yview()
        self.vbar.set(first, last)
        if first <= 0.0 and last >= 1.0:
            if self.vbar.winfo_manager():
                self.vbar.grid_remove()
        elif not self.vbar.winfo_manager():
            self.vbar.grid(row=0, column=1, sticky="ns")

    def _clamp_view(self):
        """把視圖限制在內容範圍內，避免捲到空白處（只能往右／往下捲到內容為止）。"""
        try:
            req_w = max(1, self.content.winfo_reqwidth())
            req_h = max(1, self.content.winfo_reqheight())
            cw = self.canvas.winfo_width()
            ch = self.canvas.winfo_height()
        except Exception:
            return
        max_x = max(0.0, 1.0 - cw / req_w)
        max_y = max(0.0, 1.0 - ch / req_h)
        xf, _ = self.canvas.xview()
        yf, _ = self.canvas.yview()
        if xf < 0 or xf > max_x:
            self.canvas.xview_moveto(min(max(xf, 0.0), max_x))
        if yf < 0 or yf > max_y:
            self.canvas.yview_moveto(min(max(yf, 0.0), max_y))

    def _update_hscroll(self, *args):
        first, last = self.canvas.xview()
        self.hbar.set(first, last)
        if first <= 0.0 and last >= 1.0:
            if self.hbar.winfo_manager():
                self.hbar.grid_remove()
        elif not self.hbar.winfo_manager():
            self.hbar.grid(row=1, column=0, sticky="ew")

    # ==========================================
    # 滑鼠滾輪
    # ==========================================
    def _on_mousewheel(self, event):
        if not self._is_inside(event.widget):
            return
        if sys.platform == "linux":
            step = -1 if event.num == 4 else 1
            if event.state & 0x0001:
                self.canvas.xview_scroll(step, "units")
            else:
                self.canvas.yview_scroll(step, "units")
            return
        delta = int(getattr(event, "delta", 0) / 6)
        if event.state & 0x0001:  # Shift：水平捲動
            self.canvas.xview("scroll", -delta, "units")
        else:
            self.canvas.yview("scroll", -delta, "units")

    def _is_inside(self, widget):
        if widget == self.canvas or widget == self.content:
            return True
        if isinstance(widget, ctk.CTkScrollbar):
            return False
        try:
            if widget.master is not None:
                return self._is_inside(widget.master)
        except Exception:
            pass
        return False

    def get_content_frame(self):
        return self.content

    def refresh(self):
        """內容變更後呼叫，重新計算捲動範圍與捲軸顯示狀態。"""
        self.after_idle(self._rebuild_layout)
