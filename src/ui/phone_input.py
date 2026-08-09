# 檔案：src/ui/phone_input.py
# 「電話/#分機」欄位專用：只允許數字與電話常用符號，並在欄位取得焦點時
# 將 Windows 輸入法切換為英文（英數）模式、離開時還原。
# 非 Windows 或 API 失敗時自動忽略，不影響其他功能。
import sys

PHONE_ALLOWED = "0123456789#-+()*. /,"
_CONTROL_MASK = 0x000C  # Control (4) 或 Alt (8)：組合鍵放行

# IME 轉換模式
_IME_CMODE_ALPHANUMERIC = 0x0001  # 英文（英數）
_IME_CMODE_NATIVE = 0x0002        # 中文（原生）

_imm32 = None
_user32 = None


def _load_windows_api():
    global _imm32, _user32
    if _imm32 is not None:
        return True
    try:
        if sys.platform != "win32":
            _imm32 = False
            return False
        import ctypes
        _user32 = ctypes.windll.user32
        _imm32 = ctypes.WinDLL("imm32", use_last_error=True)
        return True
    except Exception:
        _imm32 = False
        _user32 = None
        return False


def is_phone_char(char):
    """回傳該字元是否允許出現在電話欄位（數字或電話常用符號）。"""
    if not char:
        return False
    return char in PHONE_ALLOWED


def sanitize_phone(text):
    """過濾剪貼簿內容，只保留允許的字元。"""
    return "".join(c for c in text if is_phone_char(c))


def _window_handle(widget):
    """取得 widget 所在「頂層視窗」的 HWND（imm32 需要真正的頂層視窗）。"""
    try:
        top = widget.winfo_toplevel()
        hwnd = top.winfo_id()
        hwnd = _user32.GetParent(hwnd) or hwnd
        if hwnd:
            return hwnd
    except Exception:
        pass
    try:
        return _user32.GetForegroundWindow() or None
    except Exception:
        return None


def set_ime_english(widget):
    """把 widget 所在視窗的輸入法切到英文（英數）模式。回傳是否成功。"""
    if not _load_windows_api():
        return False
    hwnd = _window_handle(widget)
    if not hwnd:
        return False
    try:
        hctx = _imm32.ImmGetContext(hwnd)
        if not hctx:
            return False
        # 直接關閉 IME → 保證是英數輸入
        _imm32.ImmSetOpenStatus(hctx, False)
        _imm32.ImmSetConversionStatus(hctx, _IME_CMODE_ALPHANUMERIC, 0)
        _imm32.ImmReleaseContext(hwnd, hctx)
        return True
    except Exception:
        return False


def set_ime_native(widget):
    """把 widget 所在視窗的輸入法切回中文（原生）模式。"""
    if not _load_windows_api():
        return False
    hwnd = _window_handle(widget)
    if not hwnd:
        return False
    try:
        hctx = _imm32.ImmGetContext(hwnd)
        if not hctx:
            return False
        _imm32.ImmSetConversionStatus(hctx, _IME_CMODE_NATIVE, 0)
        _imm32.ImmSetOpenStatus(hctx, True)
        _imm32.ImmReleaseContext(hwnd, hctx)
        return True
    except Exception:
        return False


def _is_textbox(widget):
    try:
        import customtkinter as ctk
        return isinstance(widget, ctk.CTkTextbox)
    except Exception:
        return False


def _on_keypress(event):
    """攔截按鍵：非列印鍵與 Ctrl/Alt 組合鍵放行，其餘只允許白名單字元。"""
    char = getattr(event, "char", "") or ""
    if not char or ord(char) < 32:
        return None  # 方向鍵 / BackSpace / Delete / Tab 等
    if event.state & _CONTROL_MASK:
        return None  # Ctrl+A/C/V/X、Alt 組合等
    if is_phone_char(char):
        return None
    return "break"


def _on_paste(event):
    """攔截貼上：過濾剪貼簿後手動插入（Text 與 Entry 皆支援）。"""
    widget = event.widget
    try:
        raw = widget.clipboard_get()
    except Exception:
        return None
    clean = sanitize_phone(raw)
    if not clean:
        return "break"
    try:
        widget.delete("sel.first", "sel.last")
    except Exception:
        pass
    try:
        widget.insert("insert", clean)
    except Exception:
        return None
    if _is_textbox(widget):
        adjust = getattr(widget, "_adjust_height", None)
        if adjust:
            adjust()
    return "break"


def _on_focus_in(event):
    set_ime_english(event.widget)


def _on_focus_out(event):
    set_ime_native(event.widget)


def bind_phone_input(widget):
    """對 widget（CTkEntry / CTkTextbox）啟用電話欄位的輸入限制與英文輸入法。

    用 add="+" 附加 handler，避免覆蓋原本就綁定的 FocusIn/FocusOut（例如
    AutoResizingTextbox 的 placeholder 清除/還原）。
    """
    widget.bind("<KeyPress>", _on_keypress, add="+")
    widget.bind("<<Paste>>", _on_paste, add="+")
    widget.bind("<FocusIn>", _on_focus_in, add="+")
    widget.bind("<FocusOut>", _on_focus_out, add="+")
