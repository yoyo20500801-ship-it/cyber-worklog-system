# 檔案：tests/test_phone_input.py
# 測試「電話/#分機」欄位的字元過濾邏輯（純函式，不需視窗）
from src.ui import phone_input


def test_is_phone_char_digits():
    for c in "0123456789":
        assert phone_input.is_phone_char(c), f"數字 {c!r} 應允許"


def test_is_phone_char_symbols():
    for c in "#-+()*. /,":
        assert phone_input.is_phone_char(c), f"符號 {c!r} 應允許"


def test_is_phone_char_blocks_letters():
    for c in "abcXYZ":
        assert not phone_input.is_phone_char(c), f"英文字母 {c!r} 應擋掉"


def test_is_phone_char_blocks_chinese_and_fullwidth():
    for c in "中文字全形１２３（）":
        assert not phone_input.is_phone_char(c), f"{c!r} 應擋掉"


def test_is_phone_char_blocks_empty():
    assert not phone_input.is_phone_char("")
    assert not phone_input.is_phone_char(None)


def test_sanitize_phone_keeps_allowed_only():
    assert phone_input.sanitize_phone("02-1234#5678abc中") == "02-1234#5678"


def test_sanitize_phone_empty_result():
    assert phone_input.sanitize_phone("完全中文") == ""
