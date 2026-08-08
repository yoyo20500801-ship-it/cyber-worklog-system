# 檔案：src/core/mail_config.py
# 功能：信件功能設定檔 (config/mail_config.json) 的讀寫
# 注意：config/ 已在 .gitignore，帳號與應用程式密碼不會上傳 GitHub / 打包進發布檔。
import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = BASE_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "mail_config.json"

DEFAULTS = {
    "email": "",
    "app_password": "",
    "fetch_days": 30,          # 只抓最近 N 天
    "fetch_limit": 300,        # 最多抓 N 封
    "auto_sync": True,         # 啟動時背景自動同步
    "last_synced_at": "",
}


def load_config() -> dict:
    """讀取信件設定（不存在或格式錯誤時回傳預設值）。"""
    cfg = dict(DEFAULTS)
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                cfg.update({k: data[k] for k in DEFAULTS if k in data})
    except Exception:
        pass
    return cfg


def save_config(cfg: dict):
    """寫入信件設定。"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {k: cfg.get(k, DEFAULTS.get(k)) for k in DEFAULTS}
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_configured(cfg: dict) -> bool:
    return bool(cfg.get("email") and cfg.get("app_password"))
