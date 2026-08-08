# 檔案：src/ui/theme_registry.py
# 主題登錄表：集中管理所有主題的語意色票與圖檔清單。
# - 內建主題（THEMES）：由程式碼定義，不可刪除，可隱藏
# - 自訂主題（CUSTOM_THEMES）：儲存在 config/themes.json，可由使用者在介面新增/刪除
import json
import shutil
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "settings.json"
THEMES_JSON_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "themes.json"
ASSETS_ROOT = Path(__file__).resolve().parent.parent.parent / "assets" / "themes"

# 每個主題都必須提供的語意色票
REQUIRED_TOKENS = [
    "BG_DARK",              # 主背景
    "BG_CARD",              # 卡片 / 側邊欄背景
    "NEON_CYAN",            # 主強調色（標題、主按鈕、選中框）
    "NEON_PINK",            # 警示紅（刪除）
    "NEON_YELLOW",          # 警示黃（高峰日 / 特別標記）
    "NEON_GREEN",           # 成功綠（已處理）
    "NEON_SELECT",          # 次強調 / 選擇色
    "NEON_MAIN",            # 主文字
    "TEXT_MAIN",            # 一般文字
    "TEXT_MUTED",           # 次要文字
    "STATUS_PENDING",       # 待處理狀態色
    "STATUS_TRANSFER",      # 轉交狀態色
    "BUTTON_DISABLED",      # 停用按鈕底色
    "ON_ACCENT",            # 畫在強調色按鈕上的文字色（需與強調色對比）
]

THEMES = {
    # ==========================================
    # 賽博龐克（系統預設，即原本的暗色主題）
    # ==========================================
    "cyber": {
        "label": "賽博龐克（預設）",
        "mode": "dark",
        "colors": {
            "BG_DARK": "#0D0D12",
            "BG_CARD": "#1A1A24",
            "NEON_CYAN": "#00F0FF",
            "NEON_PINK": "#FF003C",
            "NEON_YELLOW": "#FCE205",
            "NEON_GREEN": "#00FF66",
            "NEON_SELECT": "#3399FF",
            "NEON_MAIN": "#FFFFFF",
            "TEXT_MAIN": "#FFFFFF",
            "TEXT_MUTED": "#8A8A93",
            "STATUS_PENDING": "#FF3333",
            "STATUS_TRANSFER": "#3399FF",
            "BUTTON_DISABLED": "#2A2A35",
            "ON_ACCENT": "#0D0D12",
        },
        "assets": {},
    },
    # ==========================================
    # 孤獨搖滾・後藤一里（Bocchi）粉紅暗色
    # ==========================================
    "bocchi-dark": {
        "label": "Bocchi・粉紅暗色",
        "mode": "dark",
        "colors": {
            "BG_DARK": "#18101F",
            "BG_CARD": "#241B2E",
            "NEON_CYAN": "#FF9EC4",
            "NEON_PINK": "#FF6B9D",
            "NEON_YELLOW": "#FFE08A",
            "NEON_GREEN": "#7FE0B0",
            "NEON_SELECT": "#C9A6FF",
            "NEON_MAIN": "#FFFFFF",
            "TEXT_MAIN": "#FFFFFF",
            "TEXT_MUTED": "#B7A9C4",
            "STATUS_PENDING": "#FF6B9D",
            "STATUS_TRANSFER": "#C9A6FF",
            "BUTTON_DISABLED": "#332A3D",
            "ON_ACCENT": "#1A0F1F",
        },
        "assets": {
            "mascot": "mascot.png",   # 側邊欄底部角色圖（透明 PNG，約 250x250）
            "input": "input.png",     # 輸入表單角落「趴在上面」小圖（透明 PNG，約 64x84）
        },
    },
    # ==========================================
    # 孤獨搖滾・後藤一里（Bocchi）粉嫩明亮
    # ==========================================
    "bocchi-light": {
        "label": "Bocchi・粉嫩明亮",
        "mode": "light",
        "colors": {
            "BG_DARK": "#FFF6FA",
            "BG_CARD": "#FFFFFF",
            "NEON_CYAN": "#FF7FB2",
            "NEON_PINK": "#E5484D",
            "NEON_YELLOW": "#F5C04A",
            "NEON_GREEN": "#3FBF7F",
            "NEON_SELECT": "#A78BDA",
            "NEON_MAIN": "#3D2A33",
            "TEXT_MAIN": "#3D2A33",
            "TEXT_MUTED": "#8F7D88",
            "STATUS_PENDING": "#E5484D",
            "STATUS_TRANSFER": "#A78BDA",
            "BUTTON_DISABLED": "#F0E2EA",
            "ON_ACCENT": "#3D2A33",
        },
        "assets": {
            "mascot": "mascot.png",
            "input": "input.png",
        },
    },
}

DEFAULT_THEME = "cyber"

_active = DEFAULT_THEME
CUSTOM_THEMES = {}   # 使用者自訂主題（來自 config/themes.json）
_hidden = set()      # 被隱藏的主題 key


# ==========================================
# 基本存取（內建 + 自訂合併）
# ==========================================
def all_themes():
    merged = dict(THEMES)
    merged.update(CUSTOM_THEMES)
    return merged


def list_themes():
    return all_themes()


def active_theme_name():
    return _active


def active_theme():
    merged = all_themes()
    if _active not in merged:
        return merged[DEFAULT_THEME]
    return merged[_active]


def get_color(token):
    try:
        return active_theme()["colors"][token]
    except KeyError:
        raise KeyError(f"主題「{_active}」缺少色票 token：{token}")


def get_theme_mode(theme_name=None):
    name = theme_name or _active
    theme = all_themes().get(name)
    return theme["mode"] if theme else THEMES[DEFAULT_THEME]["mode"]


def is_custom(key):
    return key in CUSTOM_THEMES


def is_hidden(key):
    return key in _hidden


def get_hidden_keys():
    return sorted(_hidden)


# ==========================================
# 切換與持久化
# ==========================================
def set_active_theme(name, persist=True):
    global _active
    if name not in all_themes():
        return False
    _active = name
    if persist:
        save_settings()
    return True


def set_hidden(key, hidden):
    """內建與自訂主題皆可隱藏 / 顯示。回傳是否成功。"""
    if key not in all_themes():
        return False
    if hidden:
        _hidden.add(key)
    else:
        _hidden.discard(key)
    save_settings()
    return True


def load_settings():
    global _active
    load_custom_themes()
    _active = DEFAULT_THEME
    _hidden.clear()
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        name = data.get("theme", DEFAULT_THEME)
        hidden = data.get("hidden_themes", [])
        if name in all_themes():
            _active = name
        if isinstance(hidden, list):
            _hidden.update(h for h in hidden if h in all_themes())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass


def save_settings():
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps({"theme": _active, "hidden_themes": sorted(_hidden)}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


# ==========================================
# 自訂主題（config/themes.json）
# ==========================================
def load_custom_themes():
    global CUSTOM_THEMES
    try:
        data = json.loads(THEMES_JSON_PATH.read_text(encoding="utf-8"))
        custom = data.get("custom_themes", {})
        if isinstance(custom, dict):
            CUSTOM_THEMES = {
                k: v for k, v in custom.items()
                if isinstance(v, dict) and set(REQUIRED_TOKENS).issubset(v.get("colors", {}))
            }
        else:
            CUSTOM_THEMES = {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        CUSTOM_THEMES = {}


def save_custom_themes():
    try:
        THEMES_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        THEMES_JSON_PATH.write_text(
            json.dumps({"custom_themes": CUSTOM_THEMES}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def _next_custom_key():
    n = 1
    while f"custom_{n}" in all_themes():
        n += 1
    return f"custom_{n}"


def add_custom_theme(label, mode, colors):
    """新增使用者自訂主題，自動建立圖片資料夾並回傳主題 key。"""
    label = label.strip()
    if not label:
        raise ValueError("主題名稱不可為空")
    if mode not in ("dark", "light"):
        raise ValueError("明暗設定不合法")
    missing = set(REQUIRED_TOKENS) - set(colors)
    if missing:
        raise ValueError(f"缺少色票：{', '.join(sorted(missing))}")

    key = _next_custom_key()
    CUSTOM_THEMES[key] = {
        "label": label,
        "mode": mode,
        "colors": {t: colors[t] for t in REQUIRED_TOKENS},
        "assets": {"mascot": "mascot.png", "input": "input.png"},
    }
    save_custom_themes()
    try:
        (ASSETS_ROOT / key).mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return key


def delete_custom_theme(key, delete_assets=False):
    """刪除使用者自訂主題；內建主題回傳 False。若刪除的是啟用中的主題會自動回退預設。"""
    global _active
    if not is_custom(key):
        return False
    CUSTOM_THEMES.pop(key, None)
    _hidden.discard(key)
    if _active == key:
        _active = DEFAULT_THEME
    save_custom_themes()
    save_settings()
    if delete_assets:
        folder = ASSETS_ROOT / key
        if folder.is_dir():
            shutil.rmtree(folder, ignore_errors=True)
    return True


# ==========================================
# 主題圖檔
# ==========================================
def asset_path(theme_name=None, key="mascot"):
    """回傳主題圖檔的完整路徑；檔案不存在時回傳 None。"""
    name = theme_name or _active
    theme = all_themes().get(name)
    if not theme:
        return None
    filename = (theme.get("assets") or {}).get(key)
    if not filename:
        return None
    path = ASSETS_ROOT / name / filename
    return path if path.is_file() else None
