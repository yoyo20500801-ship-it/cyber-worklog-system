# 檔案：tests/test_theme_registry.py
from src.ui import theme_registry as tr


def test_all_themes_have_required_tokens():
    assert "cyber" in tr.THEMES
    for name, theme in tr.THEMES.items():
        assert theme["mode"] in ("dark", "light")
        assert theme["label"]
        assert set(tr.REQUIRED_TOKENS).issubset(theme["colors"])


def test_theme_proxy_returns_active_color(monkeypatch):
    monkeypatch.setattr(tr, "CONFIG_PATH", None)
    monkeypatch.setattr(tr, "_active", "bocchi-dark")
    from src.ui.theme import Theme
    assert Theme.BG_DARK == "#18101F"
    assert Theme.NEON_CYAN == "#FF9EC4"

    monkeypatch.setattr(tr, "_active", "bocchi-light")
    assert Theme.BG_DARK == "#FFF6FA"
    assert Theme.TEXT_MAIN == "#3D2A33"


def test_unknown_token_raises_attribute_error(monkeypatch):
    from src.ui.theme import Theme
    try:
        Theme.NOT_A_REAL_TOKEN
    except AttributeError:
        return
    raise AssertionError("unknown token should raise AttributeError")


def test_set_active_theme_rejects_unknown():
    assert tr.set_active_theme("no-such-theme", persist=False) is False


def test_settings_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "CONFIG_PATH", tmp_path / "settings.json")
    assert tr.set_active_theme("bocchi-light", persist=True)
    tr.load_settings()
    assert tr.active_theme_name() == "bocchi-light"
    # 還原成預設，避免影響後續測試
    tr.set_active_theme("cyber", persist=True)


def test_asset_path_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "ASSETS_ROOT", tmp_path / "assets")
    assert tr.asset_path("bocchi-dark", "mascot") is None
    assert tr.asset_path("cyber", "mascot") is None


def _full_colors():
    return {t: "#123456" for t in tr.REQUIRED_TOKENS}


def _isolate(tmp_path, monkeypatch):
    """把自訂主題 / 設定導到暫存檔，避免污染真實 config。"""
    monkeypatch.setattr(tr, "CONFIG_PATH", tmp_path / "settings.json")
    monkeypatch.setattr(tr, "THEMES_JSON_PATH", tmp_path / "themes.json")
    monkeypatch.setattr(tr, "ASSETS_ROOT", tmp_path / "assets")
    tr.load_settings()
    return tr


def test_add_custom_theme_persists(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    key = tr.add_custom_theme("灰原哀・暗色", "dark", _full_colors())
    assert key.startswith("custom_")
    assert tr.is_custom(key)
    assert tr.list_themes()[key]["label"] == "灰原哀・暗色"
    assert (tr.ASSETS_ROOT / key).is_dir()

    # 重新載入後仍在
    tr.load_settings()
    assert tr.is_custom(key)


def test_add_custom_theme_validation(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    try:
        tr.add_custom_theme("  ", "dark", _full_colors())
    except ValueError:
        pass
    else:
        raise AssertionError("空白名稱應拋出 ValueError")

    missing = dict(_full_colors())
    missing.pop("NEON_CYAN")
    try:
        tr.add_custom_theme("測試", "dark", missing)
    except ValueError:
        pass
    else:
        raise AssertionError("缺色票應拋出 ValueError")


def test_delete_custom_theme(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    colors = _full_colors()
    colors["BG_DARK"] = "#111111"
    key = tr.add_custom_theme("待刪", "light", colors)

    # 啟用它再刪除 → 應回退預設
    assert tr.set_active_theme(key, persist=True)
    assert tr.delete_custom_theme(key) is True
    assert not tr.is_custom(key)
    assert key not in tr.list_themes()
    assert tr.active_theme_name() == tr.DEFAULT_THEME

    # 內建主題不可刪
    assert tr.delete_custom_theme("cyber") is False


def test_delete_custom_theme_with_assets(tmp_path, monkeypatch):
    tr = _isolate(tmp_path, monkeypatch)
    key = tr.add_custom_theme("含圖", "dark", _full_colors())
    folder = tr.ASSETS_ROOT / key
    (folder / "mascot.png").write_bytes(b"fake")
    assert folder.is_dir()

    tr.delete_custom_theme(key, delete_assets=True)
    assert not folder.is_dir()


def test_hidden_themes_persist(tmp_path, monkeypatch):
    tr = _isolate(tmp_path, monkeypatch)
    assert tr.set_hidden("bocchi-dark", True) is True
    assert tr.is_hidden("bocchi-dark")
    assert "bocchi-dark" in tr.get_hidden_keys()

    tr.load_settings()
    assert tr.is_hidden("bocchi-dark")

    # 顯示回來
    assert tr.set_hidden("bocchi-dark", False) is True
    assert not tr.is_hidden("bocchi-dark")

    # 不存在的 key
    assert tr.set_hidden("no-such-theme", True) is False


# ---------- 編輯主題 ----------
def test_update_custom_theme_persists(tmp_path, monkeypatch):
    tr = _isolate(tmp_path, monkeypatch)
    key = tr.add_custom_theme("灰原哀・暗色", "dark", _full_colors())
    assert (tr.ASSETS_ROOT / key).is_dir()

    colors = dict(_full_colors())
    colors["NEON_CYAN"] = "#00AAFF"
    tr.update_theme(key, "灰原哀・新色", "light", colors)

    theme = tr.list_themes()[key]
    assert theme["label"] == "灰原哀・新色"
    assert theme["mode"] == "light"
    assert theme["colors"]["NEON_CYAN"] == "#00AAFF"
    # key 不變 → 圖片資料夾保留
    assert (tr.ASSETS_ROOT / key).is_dir()

    # 重載後仍在
    tr.load_settings()
    assert tr.list_themes()[key]["colors"]["NEON_CYAN"] == "#00AAFF"


def test_update_theme_validation(tmp_path, monkeypatch):
    tr = _isolate(tmp_path, monkeypatch)
    key = tr.add_custom_theme("測試", "dark", _full_colors())

    # 空白名稱
    try:
        tr.update_theme(key, "  ", "dark", _full_colors())
    except ValueError:
        pass
    else:
        raise AssertionError("空白名稱應拋出 ValueError")

    # 缺色票
    missing = dict(_full_colors())
    missing.pop("NEON_CYAN")
    try:
        tr.update_theme(key, "測試", "dark", missing)
    except ValueError:
        pass
    else:
        raise AssertionError("缺色票應拋出 ValueError")

    # 不存在的 key
    try:
        tr.update_theme("no-such", "測試", "dark", _full_colors())
    except ValueError:
        pass
    else:
        raise AssertionError("不存在的 key 應拋出 ValueError")


def test_update_builtin_theme_override(tmp_path, monkeypatch):
    tr = _isolate(tmp_path, monkeypatch)
    original = tr.THEMES["cyber"]["colors"]["NEON_CYAN"]

    colors = dict(tr.THEMES["cyber"]["colors"])
    colors["NEON_CYAN"] = "#123456"
    tr.update_theme("cyber", "賽博龐克（改）", "dark", colors)

    assert tr.list_themes()["cyber"]["colors"]["NEON_CYAN"] == "#123456"
    assert tr.list_themes()["cyber"]["label"] == "賽博龐克（改）"
    # 程式碼原始定義不變
    assert tr.THEMES["cyber"]["colors"]["NEON_CYAN"] == original
    # assets 保留
    assert tr.list_themes()["cyber"]["assets"] == tr.THEMES["cyber"]["assets"]

    # 重載後仍在
    tr.load_settings()
    assert tr.list_themes()["cyber"]["colors"]["NEON_CYAN"] == "#123456"


def test_revert_builtin_theme(tmp_path, monkeypatch):
    tr = _isolate(tmp_path, monkeypatch)
    colors = dict(tr.THEMES["cyber"]["colors"])
    colors["NEON_CYAN"] = "#123456"
    tr.update_theme("cyber", "改過", "dark", colors)

    assert tr.revert_builtin_theme("cyber") is True
    assert tr.list_themes()["cyber"]["colors"]["NEON_CYAN"] == tr.THEMES["cyber"]["colors"]["NEON_CYAN"]
    # 再次還原失敗
    assert tr.revert_builtin_theme("cyber") is False

    # 自訂主題不可「還原」
    key = tr.add_custom_theme("自訂", "dark", _full_colors())
    assert tr.revert_builtin_theme(key) is False
