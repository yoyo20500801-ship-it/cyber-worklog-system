# 檔案：src/core/updater.py
# 內建自動更新：透過 GitHub Releases 檢查最新版本、下載更新檔並啟動更新程式。
# 只使用 Python 標準庫（urllib / zipfile / subprocess），不需額外安裝套件。
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

# ================================================================
# 發佈設定
# GitHub repo 建立後，把下方 GITHUB_OWNER 改成你的帳號、GITHUB_REPO 改成 repo 名稱。
# 例如：GITHUB_OWNER = "hsinyi123"、GITHUB_REPO = "worklog-system"
# ================================================================
GITHUB_OWNER = "yoyo20500801-ship-it"
GITHUB_REPO = "cyber-worklog-system"
# ================================================================

# 專案根目錄（從本檔位置往上三層）
BASE_DIR = Path(__file__).resolve().parent.parent.parent
VERSION_FILE = BASE_DIR / "VERSION"
TEMP_DIR = BASE_DIR / "temp"
RUNNER_PATH = BASE_DIR / "更新_runner.py"

# 更新時永不覆蓋的本機使用者資料（依名稱比對）
PROTECTED_DIRS = {"venv", "__pycache__", ".git", ".pytest_cache", "temp", "release", "config"}
PROTECTED_FILES = {"worklog.db", "worklog.sqlite3"}


# ================================================================
# 版本比對
# ================================================================
def get_version():
    """讀取 VERSION 檔，回傳目前版本字串（預設 0.0.0）。"""
    try:
        text = VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        text = ""
    return text or "0.0.0"


def parse_version(text):
    """把 v1.2.3 → (1, 2, 3)；無法解析時回傳 (0, 0, 0)。"""
    match = re.match(r"v?(\d+)\.(\d+)\.(\d+)", str(text).strip())
    if not match:
        return (0, 0, 0)
    return tuple(int(x) for x in match.groups())


def is_newer(remote_tag, local_version=None):
    """遠端標籤是否比本機版本新。"""
    local = local_version if local_version is not None else get_version()
    return parse_version(remote_tag) > parse_version(local)


def is_configured():
    """repo 資訊是否已設定（避免用預設佔位值去連 GitHub）。"""
    return bool(GITHUB_OWNER and GITHUB_REPO and GITHUB_OWNER != "your-github-username")


# ================================================================
# 檢查更新
# ================================================================
def _latest_release_api_url():
    return f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"


def _release_zip_url(tag):
    return f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/archive/refs/tags/{tag}.zip"


def _github_request(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": "worklog-updater"})
    return urllib.request.urlopen(req, timeout=timeout)


def check_for_update(timeout=8):
    """檢查是否有新版本。

    回傳：
      {"tag": "v1.1.0", "zip_url": "..."} → 有新版
      None                                 → 已是最新
      {"error": "..."}                     → 檢查失敗
    """
    if not is_configured():
        return {"error": "尚未設定 GitHub 發佈資訊（請修改 src/core/updater.py 的 GITHUB_OWNER）"}
    try:
        with _github_request(_latest_release_api_url(), timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {"error": f"無法連線檢查更新：{exc}"}

    tag = str(data.get("tag_name") or "").strip()
    if not tag:
        return {"error": "GitHub 上找不到最新版本標籤"}
    if not is_newer(tag):
        return None
    return {"tag": tag, "zip_url": _release_zip_url(tag)}


# ================================================================
# 套用更新
# ================================================================
def _find_source_dir(extract_dir):
    """GitHub 原始碼 zip 解壓後第一層是「repo名-版本」資料夾，回傳真正的內容資料夾。"""
    children = [p for p in extract_dir.iterdir() if p.is_dir()]
    if len(children) == 1:
        return children[0]
    return extract_dir


def apply_update(zip_url, tag):
    """下載並解壓新版本、寫入更新任務檔，再啟動更新程式（它會等本程式關閉後覆蓋並重啟）。

    回傳 (成功與否, 訊息)。
    """
    try:
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        version = tag.lstrip("v")
        zip_path = TEMP_DIR / f"update_{version}.zip"
        extract_dir = TEMP_DIR / f"update_{version}"

        with _github_request(zip_url, timeout=60) as resp, open(zip_path, "wb") as fh:
            shutil.copyfileobj(resp, fh)

        if extract_dir.exists():
            shutil.rmtree(extract_dir, ignore_errors=True)
        shutil.unpack_archive(str(zip_path), str(extract_dir))
        source_dir = _find_source_dir(extract_dir)

        job = {
            "source": str(source_dir),
            "install": str(BASE_DIR),
            "tag": tag,
            "python": sys.executable,
            "pid": os.getpid(),
        }
        job_path = TEMP_DIR / "update_job.json"
        job_path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")

        subprocess.Popen(
            [sys.executable, str(RUNNER_PATH), str(job_path)],
            cwd=str(BASE_DIR),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True, f"更新檔已下載，關閉程式後會自動套用 {tag}"
    except Exception as exc:
        return False, f"更新失敗：{exc}"
