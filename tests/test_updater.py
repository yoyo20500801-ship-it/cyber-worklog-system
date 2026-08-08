# 檔案：tests/test_updater.py
import importlib.util
import io
import json
import shutil
import zipfile
from pathlib import Path

from src.core import updater

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class FakeResp:
    """模擬 urllib 回應：可當 context manager，且 read() 支援分段讀取。"""

    def __init__(self, data):
        self._buf = io.BytesIO(data)

    def __enter__(self):
        return self._buf

    def __exit__(self, *args):
        self._buf.close()
        return False


# ==========================================
# 版本比對
# ==========================================
def test_parse_version():
    assert updater.parse_version("1.0.0") == (1, 0, 0)
    assert updater.parse_version("v2.3.4") == (2, 3, 4)
    assert updater.parse_version("  v10.20.30 ") == (10, 20, 30)
    assert updater.parse_version("abc") == (0, 0, 0)


def test_is_newer():
    assert updater.is_newer("v1.1.0", "1.0.0") is True
    assert updater.is_newer("v1.0.0", "1.0.0") is False
    assert updater.is_newer("v0.9.9", "1.0.0") is False
    assert updater.is_newer("v1.0.1", "1.0.0") is True


def test_get_version(monkeypatch, tmp_path):
    v = tmp_path / "VERSION"
    v.write_text("1.2.3\n", encoding="utf-8")
    monkeypatch.setattr(updater, "VERSION_FILE", v)
    assert updater.get_version() == "1.2.3"
    v.write_text("", encoding="utf-8")
    assert updater.get_version() == "0.0.0"


def test_is_configured(monkeypatch):
    monkeypatch.setattr(updater, "GITHUB_OWNER", "your-github-username")
    monkeypatch.setattr(updater, "GITHUB_REPO", "worklog-system")
    assert updater.is_configured() is False
    monkeypatch.setattr(updater, "GITHUB_OWNER", "realuser")
    assert updater.is_configured() is True


# ==========================================
# 檢查更新（模擬 GitHub API）
# ==========================================
def test_check_for_update_not_configured(monkeypatch):
    monkeypatch.setattr(updater, "GITHUB_OWNER", "your-github-username")
    result = updater.check_for_update()
    assert "error" in result


def test_check_for_update_found_newer(monkeypatch, tmp_path):
    v = tmp_path / "VERSION"
    v.write_text("1.0.0\n", encoding="utf-8")
    monkeypatch.setattr(updater, "VERSION_FILE", v)
    monkeypatch.setattr(updater, "GITHUB_OWNER", "owner")
    monkeypatch.setattr(updater, "GITHUB_REPO", "repo")
    monkeypatch.setattr(
        updater, "_github_request",
        lambda url, timeout: FakeResp(json.dumps({"tag_name": "v1.2.0"}).encode("utf-8")),
    )
    result = updater.check_for_update()
    assert result["tag"] == "v1.2.0"
    assert "archive/refs/tags/v1.2.0.zip" in result["zip_url"]


def test_check_for_update_already_latest(monkeypatch, tmp_path):
    v = tmp_path / "VERSION"
    v.write_text("1.2.0\n", encoding="utf-8")
    monkeypatch.setattr(updater, "VERSION_FILE", v)
    monkeypatch.setattr(updater, "GITHUB_OWNER", "owner")
    monkeypatch.setattr(updater, "GITHUB_REPO", "repo")
    monkeypatch.setattr(
        updater, "_github_request",
        lambda url, timeout: FakeResp(json.dumps({"tag_name": "v1.2.0"}).encode("utf-8")),
    )
    assert updater.check_for_update() is None


def test_check_for_update_network_error(monkeypatch):
    monkeypatch.setattr(updater, "GITHUB_OWNER", "owner")
    monkeypatch.setattr(updater, "GITHUB_REPO", "repo")

    def boom(url, timeout):
        raise ConnectionError("no network")

    monkeypatch.setattr(updater, "_github_request", boom)
    result = updater.check_for_update()
    assert "error" in result


def test_find_source_dir(tmp_path):
    flat = tmp_path / "flat"
    flat.mkdir()
    (flat / "a.txt").write_text("x", encoding="utf-8")
    assert updater._find_source_dir(flat) == flat

    wrap = tmp_path / "wrap"
    inner = wrap / "repo-1.0.0"
    inner.mkdir(parents=True)
    (inner / "b.txt").write_text("x", encoding="utf-8")
    assert updater._find_source_dir(wrap) == inner


# ==========================================
# 完整模擬：下載 → 解壓 → 更新程式覆蓋（保留使用者資料）
# ==========================================
def _make_new_version_zip(tmp_path):
    inner = tmp_path / "repo-9.9.9"
    (inner / "src").mkdir(parents=True)
    (inner / "config").mkdir(parents=True)
    (inner / "assets" / "themes" / "custom_1").mkdir(parents=True)
    (inner / "VERSION").write_text("9.9.9\n", encoding="utf-8")
    (inner / "src" / "feature.py").write_text("print('new')\n", encoding="utf-8")
    # 這些「不該被覆蓋」的使用者資料，也刻意放進 zip 測試保護機制
    (inner / "config" / "settings.json").write_text('{"theme": "x"}', encoding="utf-8")
    (inner / "assets" / "themes" / "custom_1" / "mascot.png").write_bytes(b"new-image")

    zip_path = tmp_path / "new_version.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in inner.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(tmp_path))
    return zip_path.read_bytes()


def test_apply_update_and_runner(tmp_path, monkeypatch):
    # --- 建立「使用者本機」安裝目錄 ---
    install = tmp_path / "install"
    (install / "src").mkdir(parents=True)
    (install / "config").mkdir(parents=True)
    (install / "assets" / "themes" / "custom_1").mkdir(parents=True)
    (install / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    (install / "worklog.db").write_bytes(b"old-db")
    (install / "config" / "settings.json").write_text('{"theme": "bocchi"}', encoding="utf-8")
    (install / "assets" / "themes" / "custom_1" / "mascot.png").write_bytes(b"old-image")
    (install / "src" / "old.py").write_text("old", encoding="utf-8")

    zip_bytes = _make_new_version_zip(tmp_path)
    temp = tmp_path / "temp"
    runner_script = tmp_path / "更新_runner.py"
    shutil.copyfile(PROJECT_ROOT / "更新_runner.py", runner_script)

    monkeypatch.setattr(updater, "TEMP_DIR", temp)
    monkeypatch.setattr(updater, "RUNNER_PATH", runner_script)
    monkeypatch.setattr(updater, "VERSION_FILE", install / "VERSION")
    monkeypatch.setattr(updater, "BASE_DIR", install)
    monkeypatch.setattr(updater, "_github_request", lambda url, timeout: FakeResp(zip_bytes))
    monkeypatch.setattr(updater.subprocess, "Popen", lambda *a, **k: None)

    ok, msg = updater.apply_update("http://fake/v9.9.9.zip", "v9.9.9")
    assert ok, msg

    job_path = temp / "update_job.json"
    assert job_path.is_file()
    job = json.loads(job_path.read_text(encoding="utf-8"))
    assert job["tag"] == "v9.9.9"
    assert Path(job["source"]).name == "repo-9.9.9"
    assert Path(job["install"]) == install

    # 把 pid 改成不存在的行程，讓更新程式不必等待
    job["pid"] = 999999
    job_path.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")

    # 載入更新程式並執行（攔截重新啟動，不真的開 GUI）
    spec = importlib.util.spec_from_file_location("runner_test", str(runner_script))
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **k: None)

    assert runner.main(str(job_path)) == 0

    # --- 新版已套用 ---
    assert (install / "VERSION").read_text(encoding="utf-8").strip() == "9.9.9"
    assert (install / "src" / "feature.py").is_file()

    # --- 使用者資料保留 ---
    assert (install / "worklog.db").read_bytes() == b"old-db"
    assert (install / "config" / "settings.json").read_text(encoding="utf-8") == '{"theme": "bocchi"}'
    assert (install / "assets" / "themes" / "custom_1" / "mascot.png").read_bytes() == b"old-image"

    # --- 更新只增不刪 ---
    assert (install / "src" / "old.py").is_file()
