# 檔案：src/ui/theme.py
import ctypes
try:
    # 告訴 Windows：這個程式支援高解析度，請不要幫我模糊放大
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

from src.ui import theme_registry


class _ThemeMeta(type):
    """讓 Theme.BG_DARK 這類寫法動態取得「目前啟用主題」的色票。"""

    def __getattr__(cls, name):
        if name.startswith("__"):
            raise AttributeError(name)
        try:
            return theme_registry.get_color(name)
        except KeyError:
            raise AttributeError(f"{name} is not a valid theme token")


class Theme(metaclass=_ThemeMeta):
    """色彩動態取自 theme_registry 目前啟用的主題；字型為全主題共用。"""

    # --- 字型設定 ---
    # 預設使用系統內建的微軟正黑體，確保中文不會變亂碼
    FONT_HEADING = ("Noto Sans TC", 24, "bold")
    FONT_BODY = ("Noto Sans TC", 16)
    FONT_SMALL = ("Noto Sans TC", 14)
