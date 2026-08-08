# 檔案：build_release.py
# 建立發布用 zip（不含虛擬環境與使用者資料），並印出 GitHub 發布步驟。
# 用法：venv\Scripts\python build_release.py
import sys
import zipfile
from pathlib import Path

# 讓中文與 emoji 在 Windows 主控台正常顯示
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent
VERSION = (BASE_DIR / "VERSION").read_text(encoding="utf-8").strip()

# 要包進 zip 的頂層項目
INCLUDE_TOP = [
    "src",
    "database",
    "templates",
    "assets",
    "requirements.txt",
    "README.md",
    "VERSION",
    "啟動.bat",
    "安裝.bat",
    "更新_runner.py",
    "build_release.py",
]

# 永不包進發布檔的目錄 / 檔案（使用者資料與本機環境）
EXCLUDE_DIRS = {"venv", "__pycache__", ".git", ".pytest_cache", "temp", "release", "config"}
EXCLUDE_FILES = {"worklog.db", "worklog.sqlite3"}


def main():
    out_dir = BASE_DIR / "release"
    out_dir.mkdir(exist_ok=True)
    zip_name = f"工作日誌-v{VERSION}.zip"
    out_path = out_dir / zip_name

    count = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for top in INCLUDE_TOP:
            p = BASE_DIR / top
            if not p.exists():
                print(f"  略過（不存在）：{top}")
                continue
            if p.is_file():
                zf.write(p, p.name)
                count += 1
                continue
            for f in sorted(p.rglob("*")):
                if any(part in EXCLUDE_DIRS for part in f.parts):
                    continue
                if f.name in EXCLUDE_FILES:
                    continue
                if f.is_file():
                    zf.write(f, f.relative_to(BASE_DIR))
                    count += 1

    print(f"✅ 已產生：{out_path}（{count} 個檔案）")
    print()
    print("接下來在專案資料夾執行：")
    print("  git add -A")
    print(f'  git commit -m "v{VERSION}"')
    print("  git push")
    print(f"  git tag v{VERSION}")
    print(f"  git push origin v{VERSION}")
    print()
    print("打完標籤後，GitHub 會自動產生該版本的原始碼 zip，")
    print("所有使用者的程式就會在啟動時收到更新通知。")


if __name__ == "__main__":
    main()
