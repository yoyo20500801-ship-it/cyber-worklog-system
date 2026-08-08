# 檔案：更新_runner.py
# 自動更新執行器：由 src/core/updater.py 以目前環境的 python 啟動（無視窗）。
# 流程：等待主程式結束 → 把新版程式檔覆蓋到安裝目錄（保留使用者資料）→ 更新版本號 → 重新啟動程式。
# 只使用 Python 標準庫，且不匯入專案套件（避免更新過程中被覆蓋造成異常）。
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROTECTED_DIRS = {"venv", "__pycache__", ".git", ".pytest_cache", "temp", "release", "config"}
PROTECTED_FILES = {"worklog.db", "worklog.sqlite3"}

LOG_PATH = None


def log(msg):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except OSError:
        pass


def _ignore_names(directory, names):
    """覆蓋時跳過的使用者資料：config、自訂主題圖（custom_*）與本機環境檔。"""
    ignored = set()
    for name in names:
        if name in PROTECTED_DIRS or name in PROTECTED_FILES or name.startswith("custom_"):
            ignored.add(name)
    return ignored


def wait_for_exit(pid, timeout=600):
    """輪詢等待指定 PID 的程式完全結束。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return True
        time.sleep(1)
    return False


def main(job_path):
    global LOG_PATH
    try:
        job = json.loads(Path(job_path).read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"無法讀取更新任務：{exc}")
        return 1

    install = Path(job["install"])
    LOG_PATH = install / "temp" / "update_log.txt"
    log("更新程式啟動")
    log(f"新版來源：{job['source']}")

    if not wait_for_exit(job["pid"]):
        log("等待主程式關閉逾時，放棄更新")
        return 1

    src = Path(job["source"])
    if not src.is_dir():
        log(f"新版內容不存在：{src}")
        return 1

    try:
        shutil.copytree(src, install, dirs_exist_ok=True, ignore=_ignore_names)
    except Exception as exc:
        log(f"覆蓋檔案失敗：{exc}")
        return 1

    try:
        version = str(job.get("tag", "")).lstrip("v").strip() or "0.0.0"
        (install / "VERSION").write_text(version + "\n", encoding="utf-8")
        log(f"版本號已更新為 {version}")
    except OSError as exc:
        log(f"寫入版本號失敗：{exc}")

    log("更新完成，重新啟動程式")
    python = job.get("python") or sys.executable
    subprocess.Popen(
        [python, "src/main.py"],
        cwd=str(install),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
