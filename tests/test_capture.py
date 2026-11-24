import os
import time

import pytest
from PySide6.QtCore import QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest

from conftest import stripes
from pr7q import capture, hotkeys, output
from pr7q.capture import Desktop
from pr7q.overlay import RegionPicker


# ---------------------------------------------------------------- the desktop and its pixels
def test_crop_turns_points_into_pixels(desk):
    img = desk.crop(QRect(50, 0, 50, 100))               # points 50-100 = pixels 100-200: the second band
    assert (img.width(), img.height()) == (100, 200)
    assert img.pixelColor(50, 50) == QColor("#E2502A")
    whole = desk.crop(QRect())
    assert whole.size() == desk.image.size()


def test_crop_with_a_monitor_left_of_the_main_one():
    d = Desktop(stripes(), QRect(-200, 0, 400, 250), 2.0)    # the desktop starts at x = -200 points
    assert d.crop(QRect(-200, 0, 50, 50)).pixelColor(10, 10) == QColor("#C2183F")
    assert d.to_pixels(QRect(-150, 0, 50, 50)).x() == 100


def test_pointer_drawn_where_the_mouse_was(desk):
    before = desk.image.copy()
    capture.draw_cursor(desk)                           # at (120, 80) points = (240, 160) pixels
    assert desk.image.pixelColor(242, 172) == QColor("#FFFFFF")      # inside the white arrow
    assert desk.image.pixelColor(300, 300) == before.pixelColor(300, 300)


def test_window_lookup_is_windows_only(qapp):
    import sys
    if sys.platform != "win32":
        assert capture.window_at(QPoint(10, 10)) is None


# ---------------------------------------------------------------- names and files
def test_file_names(tmp_path):
    when = time.mktime((2026, 11, 24, 22, 56, 7, 0, 0, -1))
    assert output.file_name(output.DEFAULT_PATTERN, when=when) == "Screenshot 2026-11-24 22.56.07"
    assert output.file_name("%Y %m - {title}", "Report: Q3 <draft>", when) == "2026 11 - Report_ Q3 _draft_"
    (tmp_path / "a.png").write_bytes(b"x")
    assert output.free_path(str(tmp_path), "a", "png").endswith("a (2).png")


def test_save_formats(tmp_path):
    img = stripes(300, 200)
    for ext in ("png", "jpg", "bmp"):
        path = output.save(img, str(tmp_path / "sub" / f"shot.{ext}"), 85)
        back = QImage(path)
        assert back.size() == img.size()
        c = back.pixelColor(150, 100)
        assert abs(c.red() - QColor("#E2502A").red()) < 30
    first = output.save_directly(img, str(tmp_path), "%Y", "png")
    second = output.save_directly(img, str(tmp_path), "%Y", "png")
    assert first != second and os.path.exists(first) and second.endswith("(2).png")     # never overwrites


def test_open_in_pr7p_uses_it_when_installed(tmp_path):
    called = []
    assert output.open_in_pr7p(str(tmp_path / "x.png"), launch=lambda app, args: called.append((app, args)) or True)
    assert called == [("PR7-P", [str(tmp_path / "x.png")])]


# ---------------------------------------------------------------- keys
def test_key_names():
    assert hotkeys.parse("Print") == (0, 0x2C)
    assert hotkeys.parse("Ctrl+Shift+Print") == (hotkeys.MOD_CONTROL | hotkeys.MOD_SHIFT, 0x2C)
    assert hotkeys.parse("Alt+F11") == (hotkeys.MOD_ALT, 0x7A)
    assert hotkeys.parse("Ctrl+4") == (hotkeys.MOD_CONTROL, ord("4"))
    assert hotkeys.parse("Hyper+Print") is None and hotkeys.parse("") is None


# ---------------------------------------------------------------- choosing a region
def picker(desk, window_at=None):
    got = []
    p = RegionPicker(desk, window_at)
    p.picked.connect(lambda r, how: got.append((r, how, getattr(p, "title", ""))))
    p.cancelled.connect(lambda: got.append("cancelled"))
    p.show_over_desktop()
    return p, got


def test_drag_a_region(desk, qapp):
    p, got = picker(desk)
    QTest.mousePress(p, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(50, 40))
    QTest.mouseMove(p, QPoint(150, 120))
    assert p.sel == QRect(50, 40, 100, 80)                      # as wide and high as the drag
    QTest.mouseRelease(p, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(150, 120))
    assert got and got[0][1] == "region" and got[0][0] == QRect(50, 40, 100, 80)


def test_click_takes_the_window_under_the_pointer(desk, qapp):
    p, got = picker(desk, lambda pt: (QRect(10, 10, 100, 60), "Notes"))
    QTest.mouseClick(p, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(30, 30))
    assert got[0] == (QRect(10, 10, 100, 60), "window", "Notes")


def test_escape_cancels_and_enter_takes_the_screen(desk, qapp):
    p, got = picker(desk)
    QTest.keyClick(p, Qt.Key.Key_Escape)
    assert got == ["cancelled"]
    p, got = picker(desk)
    QTest.keyClick(p, Qt.Key.Key_Return)
    assert got[0][1] == "full" and got[0][0] == desk.geometry


def test_magnifier_reads_the_pixel(desk, qapp):
    p, _ = picker(desk)
    assert p.pixel_colour(QPoint(160, 10)) == QColor("#7A2230")      # 160 points = 320 px: the fourth band
    p.grab()                                                         # paints without trouble
    p.cancel()
