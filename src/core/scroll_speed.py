# 檔案：src/core/scroll_speed.py
# 功能：讓 CTkScrollableFrame 的滑鼠滾輪捲動速度跟隨 Windows「滾輪捲動行數」設定。
#   以 class-level monkey-patch 覆寫 _mouse_wheel_all，套用時機在任何
#   CTkScrollableFrame 實例建立之前，故所有頁面（工作紀錄列表、客戶來信、設定各分頁、
#   總覽、轉交、資料庫搜尋等）以及主題重建後的新實例都會生效。
#   文字框 (CTkTextbox / 內建 Text) 不在範圍內，維持原速。
#
#   Windows 行為：
#     每格捲動 int(delta/6) × WheelScrollLines 單位（1 單位 = 1px），
#     也就是每格 = 設定行數 × 20px；設定 3 行 → 約 60px/格（原本固定 20px）。
#     WheelScrollLines = 0（控制台設定「一次捲一頁」）→ 每格捲一整頁。
#   macOS / Linux 沒有此設定：維持原邏輯 × 固定倍數。
import sys
import winreg

from customtkinter import CTkScrollableFrame

# 非 Windows 平台的固定倍數（macOS / Linux 無「捲動行數」系統設定）
FALLBACK_MULTIPLIER = 3


def _parse_wheel_lines(raw):
    """把註冊表讀到的值轉成整數行數（相容 REG_SZ 字串 / REG_DWORD；0 = 一次捲一頁）。"""
    try:
        text = str(raw).strip()
        if not text:
            return 3
        n = int(text)
    except (TypeError, ValueError):
        return 3
    return max(0, n)


def _system_wheel_lines():
    """讀取 Windows「滑鼠滾輪每格捲動行數」（HKCU\\Control Panel\\Desktop\\WheelScrollLines）。

    回傳 0 代表控制台設為「一次捲一頁」；讀取失敗時回傳系統預設 3。
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop") as key:
            value, _ = winreg.QueryValueEx(key, "WheelScrollLines")
        return _parse_wheel_lines(value)
    except Exception:
        return 3


def _mouse_wheel_all_faster(self, event):
    """取代 CTkScrollableFrame._mouse_wheel_all：捲動速度跟隨系統滾輪設定。"""
    if not self._check_if_valid_scroll(event.widget):
        return
    if sys.platform.startswith("win"):
        lines = _system_wheel_lines()
        if self._shift_pressed:
            if lines == 0:
                if self._parent_canvas.xview() != (0.0, 1.0):
                    self._parent_canvas.xview_scroll(1 if event.delta < 0 else -1, "pages")
            else:
                if self._parent_canvas.xview() != (0.0, 1.0):
                    self._parent_canvas.xview("scroll", -int(event.delta / 6) * lines, "units")
        else:
            if lines == 0:
                if self._parent_canvas.yview() != (0.0, 1.0):
                    self._parent_canvas.yview_scroll(1 if event.delta < 0 else -1, "pages")
            else:
                if self._parent_canvas.yview() != (0.0, 1.0):
                    self._parent_canvas.yview("scroll", -int(event.delta / 6) * lines, "units")
    elif sys.platform == "darwin":
        if self._shift_pressed:
            if self._parent_canvas.xview() != (0.0, 1.0):
                self._parent_canvas.xview("scroll", -event.delta * FALLBACK_MULTIPLIER, "units")
        else:
            if self._parent_canvas.yview() != (0.0, 1.0):
                self._parent_canvas.yview("scroll", -event.delta * FALLBACK_MULTIPLIER, "units")
    else:
        if event.num == 4:
            if self._parent_canvas.yview() != (0.0, 1.0):
                self._parent_canvas.yview("scroll", -event.num * 5 * FALLBACK_MULTIPLIER, "units")
        elif event.num == 5:
            if self._parent_canvas.yview() != (0.0, 1.0):
                self._parent_canvas.yview("scroll", event.num * 5 * FALLBACK_MULTIPLIER, "units")


def apply():
    """套用加速。必須在任何 CTkScrollableFrame 實例建立前呼叫一次。"""
    CTkScrollableFrame._mouse_wheel_all = _mouse_wheel_all_faster


apply()
