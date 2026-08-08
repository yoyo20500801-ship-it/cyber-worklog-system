# 檔案：tests/test_scroll_speed.py
# 測試滾輪加速：註冊表值解析、patch 安裝、handler 行為（不需 Tk/GUI）
import sys
import types

from customtkinter import CTkScrollableFrame
from src.core import scroll_speed


# ---------- 註冊表值解析 ----------
def test_parse_wheel_lines_reg_sz():
    assert scroll_speed._parse_wheel_lines("3") == 3


def test_parse_wheel_lines_reg_dword():
    assert scroll_speed._parse_wheel_lines(5) == 5


def test_parse_wheel_lines_zero_means_page():
    assert scroll_speed._parse_wheel_lines(0) == 0
    assert scroll_speed._parse_wheel_lines("0") == 0


def test_parse_wheel_lines_garbage_falls_back():
    assert scroll_speed._parse_wheel_lines("abc") == 3
    assert scroll_speed._parse_wheel_lines(None) == 3
    assert scroll_speed._parse_wheel_lines("") == 3


# ---------- patch 安裝 ----------
def test_patch_installed():
    assert CTkScrollableFrame._mouse_wheel_all is scroll_speed._mouse_wheel_all_faster


# ---------- handler 假物件 ----------
def _make_fake(shift=False):
    class FakeCanvas:
        def __init__(self):
            self.calls = []
            self._x = (0.0, 0.5)
            self._y = (0.0, 0.5)

        def xview(self, *args):
            if args:
                self.calls.append(("xview", args))
                return
            return self._x

        def yview(self, *args):
            if args:
                self.calls.append(("yview", args))
                return
            return self._y

        def xview_scroll(self, *args):
            self.calls.append(("xview_scroll", args))

        def yview_scroll(self, *args):
            self.calls.append(("yview_scroll", args))

    class FakeSelf:
        def __init__(self):
            self._parent_canvas = FakeCanvas()
            self._shift_pressed = shift

        def _check_if_valid_scroll(self, widget):
            return True

    return FakeSelf()


def _event(delta=120, num=4):
    return types.SimpleNamespace(delta=delta, num=num, widget=object())


def test_windows_scrolls_lines_times_units(monkeypatch):
    monkeypatch.setattr(scroll_speed, "_system_wheel_lines", lambda: 3)
    fake = _make_fake()
    scroll_speed._mouse_wheel_all_faster(fake, _event(delta=120))
    assert fake._parent_canvas.calls == [("yview", ("scroll", -60, "units"))]


def test_windows_zero_lines_scrolls_page(monkeypatch):
    monkeypatch.setattr(scroll_speed, "_system_wheel_lines", lambda: 0)
    fake = _make_fake()
    scroll_speed._mouse_wheel_all_faster(fake, _event(delta=-120))
    assert fake._parent_canvas.calls == [("yview_scroll", (1, "pages"))]


def test_windows_shift_uses_horizontal_axis(monkeypatch):
    monkeypatch.setattr(scroll_speed, "_system_wheel_lines", lambda: 3)
    fake = _make_fake(shift=True)
    scroll_speed._mouse_wheel_all_faster(fake, _event(delta=120))
    assert fake._parent_canvas.calls == [("xview", ("scroll", -60, "units"))]


def test_handler_skips_when_invalid_scroll():
    class FakeSelf:
        def _check_if_valid_scroll(self, widget):
            return False

    scroll_speed._mouse_wheel_all_faster(FakeSelf(), _event())
    # 無 _parent_canvas 屬性也沒關係，代表沒被觸及


def test_linux_branch_uses_fixed_multiplier(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    fake = _make_fake()
    scroll_speed._mouse_wheel_all_faster(fake, _event(num=4))
    assert fake._parent_canvas.calls == [("yview", ("scroll", -60, "units"))]
    fake = _make_fake()
    scroll_speed._mouse_wheel_all_faster(fake, _event(num=5))
    assert fake._parent_canvas.calls == [("yview", ("scroll", 75, "units"))]
