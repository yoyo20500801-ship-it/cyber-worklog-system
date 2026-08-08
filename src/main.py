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

import customtkinter as ctk
from src.db.connection import init_db
from src.ui import theme_registry
from src.ui.views.main_window import MainWindow

def main():
    # 確保資料庫已初始化（含舊版資料庫的 sort_order 欄位遷移）
    init_db()

    # 讀取上次使用的主題設定（預設為賽博龐克暗色）
    theme_registry.load_settings()

    # 依目前主題設定 customtkinter 全域外觀（影響下拉選單、捲軸等元件）
    ctk.set_appearance_mode(theme_registry.get_theme_mode())

    # 實例化主視窗並啟動事件迴圈
    app = MainWindow()
    app.mainloop()

if __name__ == "__main__":
    main()