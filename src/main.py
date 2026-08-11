# 檔案：src/main.py
import os
import sys
from pathlib import Path

# 確保可從專案根目錄執行（python src\main.py）時能正確匯入 src 套件
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 用 pythonw.exe 啟動時沒有主控台，stdout/stderr 為 None；
# 若直接 print() 會崩潰，故先導向空裝置（GUI 程式不需主控台輸出）。
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

# 檢查 tkinter：Python 安裝時未勾選「tcl/tk and IDLE」會缺少此元件，
# pythonw 無主控台會靜默失敗，故改用 Windows 訊息框明確提示原因。
try:
    import tkinter  # noqa: F401
except ModuleNotFoundError:
    import ctypes
    ctypes.windll.user32.MessageBoxW(
        0,
        "無法啟動：Python 缺少 tkinter 元件。\n\n"
        "請重新執行 Python 安裝程式，選擇「Modify」，"
        "勾選「tcl/tk and IDLE」後完成安裝，"
        "再重新執行一次 安裝.bat 即可。",
        "工作日誌 - 啟動失敗",
        0x10,
    )
    sys.exit(1)

import customtkinter as ctk
from src.db.connection import init_db
from src.ui import theme_registry
from src.core import scroll_speed
from src.ui.views.main_window import MainWindow

def main():
    # 設定 AppUserModelID，讓 Windows 工作列正確顯示視窗圖示
    # （否則 pythonw.exe 啟動時工作列會沿用 Python 圖示）
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("CyberWorklogSystem.1")
    except Exception:
        pass

    # 確保資料庫已初始化（含舊版資料庫的 sort_order 欄位遷移）
    init_db()

    # 讀取上次使用的主題設定（預設為賽博龐克暗色）
    theme_registry.load_settings()

    # 依目前主題設定 customtkinter 全域外觀（影響下拉選單、捲軸等元件）
    ctk.set_appearance_mode(theme_registry.get_theme_mode())

    # 加快捲動：覆寫 CTkScrollableFrame._mouse_wheel_all（在任何實例建立前套用）
    scroll_speed.apply()

    # 實例化主視窗並啟動事件迴圈
    app = MainWindow()
    app.mainloop()

if __name__ == "__main__":
    main()