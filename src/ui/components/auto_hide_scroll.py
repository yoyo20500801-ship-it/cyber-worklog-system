# 檔案：src/ui/components/auto_hide_scroll.py
# 自動隱藏捲軸的捲動框架：內容沒有溢位時隱藏捲軸，有溢位才顯示。
import customtkinter as ctk


class AutoHideScrollableFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        info = dict(self._scrollbar.grid_info())
        info.pop("in", None)
        self._scrollbar_grid = info
        self._parent_canvas.bind("<Configure>", self._autohide_check, add=True)
        self.bind("<Configure>", self._autohide_check, add=True)
        self.after(50, self._autohide_check)

    def _autohide_check(self, event=None):
        if not self.winfo_viewable():
            return
        self.after_idle(self._apply_autohide)

    def _apply_autohide(self):
        try:
            sr = self._parent_canvas.cget("scrollregion")
            if not sr or " " not in sr:
                return
            parts = sr.split()
            region_w = float(parts[2]) - float(parts[0])
            region_h = float(parts[3]) - float(parts[1])
            cw = self._parent_canvas.winfo_width()
            ch = self._parent_canvas.winfo_height()
        except Exception:
            return
        if self._orientation == "vertical":
            overflow = region_h > ch + 1
        else:
            overflow = region_w > cw + 1
        if overflow:
            if not self._scrollbar.winfo_manager():
                self._scrollbar.grid(**self._scrollbar_grid)
        elif self._scrollbar.winfo_manager():
            self._scrollbar.grid_remove()
