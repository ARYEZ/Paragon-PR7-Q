import json
import os
import sys
import time

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest

from pr7q import __version__, app, settings


def test_full_screen_saved_directly(tray):
    settings.set("after", "save")
    got = []
    tray.captured.connect(lambda img, how: got.append((img.size(), how)))
    tray.capture("full")
    assert got[0][1] == "full" and (got[0][0].width(), got[0][0].height()) == (800, 500)
    assert tray.last_saved.startswith(settings.get("folder")) and os.path.exists(tray.last_saved)
    assert QImage(tray.last_saved).size() == got[0][0]


def test_region_then_last_region(tray, qapp):
    settings.set("after", "copy")
    tray.capture("region")
    p = tray.picker
    assert p is not None and p.isVisible()
    QTest.mousePress(p, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(100, 0))
    QTest.mouseMove(p, QPoint(150, 50))
    QTest.mouseRelease(p, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(150, 50))
    clip = qapp.clipboard().image()
    assert (clip.width(), clip.height()) == (100, 100) and clip.pixelColor(10, 10) == QColor("#F07A2A")
    assert tray.picker is None and tray.last_region == QRect(100, 0, 50, 50)
    qapp.clipboard().clear()
    tray.capture("last_region")                          # the same place again, no picking
    assert qapp.clipboard().image().size() == clip.size()


def test_window_under_the_mouse(tray, qapp):
    settings.set("after", "editor")
    tray.capture("window")
    ed = tray.editors[-1]
    assert (ed.canvas.base.width(), ed.canvas.base.height()) == (300, 200) and ed.capture_title == "Notes - PR7-W"
    settings.set("pattern", "{title}")
    assert ed.save() and os.path.basename(ed.path) == "Notes - PR7-W.png"


def test_after_capture_menu_choice(tray):
    settings.set("after", "ask")
    tray.answers["after"] = "save"
    assert tray.deliver(QImage(20, 20, QImage.Format.Format_RGB32)) == "save" and os.path.exists(tray.last_saved)
    tray.answers["after"] = None                          # Cancel in the menu
    assert tray.deliver(QImage(20, 20, QImage.Format.Format_RGB32)) is None


def test_open_in_pr7p_saves_first(tray):
    settings.set("after", "pr7p")
    opened = []
    tray.answers["launch"] = lambda appname, args: opened.append((appname, args)) or True
    tray.capture("full")
    assert opened == [("PR7-P", [tray.last_saved])] and os.path.exists(tray.last_saved)


def test_delay(tray, qapp):
    settings.set("after", "copy")
    settings.set("delay", 1)
    qapp.clipboard().clear()
    tray.start("full")
    assert qapp.clipboard().image().isNull()              # not yet
    end = time.time() + 3
    while qapp.clipboard().image().isNull() and time.time() < end:
        qapp.processEvents(); time.sleep(0.02)
    assert not qapp.clipboard().image().isNull()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows' own keys (on Linux they're Plasma shortcuts)")
def test_preferences_change_the_menu(tray):
    tray.answers["preferences"] = True
    settings.set("key_region", "Ctrl+Shift+4")
    tray.preferences()
    assert tray.acts["region"].text().endswith("\tCtrl+Shift+4")
    assert tray.preferences_dialog.keys["region"].text() == "Ctrl+Shift+4"


def test_from_clipboard_and_open_file(tray, qapp, tmp_path):
    img = QImage(64, 32, QImage.Format.Format_RGB32); img.fill(QColor("#D83A6A"))
    qapp.clipboard().setImage(img)
    tray.from_clipboard()
    assert tray.editors[-1].canvas.base.size() == img.size()
    path = tmp_path / "pic.png"
    img.save(str(path))
    tray.answers["open"] = str(path)
    tray.open_file()
    assert tray.editors[-1].path == str(path) and not tray.editors[-1].modified


# ---------------------------------------------------------------- the command line
def test_version(capsys):
    assert app.main(["--version"]) == 0 and capsys.readouterr().out.strip() == __version__


def test_a_second_start_asks_the_running_pr7q_to_capture(tray, qapp):
    import subprocess
    settings.set("after", "save")
    assert app.listen(tray) is not None
    code = ("import sys; sys.path.insert(0, sys.argv[1]); from PySide6.QtCore import QCoreApplication; "
            "a = QCoreApplication([]); from pr7q import app; sys.exit(0 if app.hand_over('full') else 1)")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proc = subprocess.Popen([sys.executable, "-c", code, root])
    end = time.time() + 20
    while (tray.last_saved is None or proc.poll() is None) and time.time() < end:
        qapp.processEvents(); time.sleep(0.01)
    assert proc.wait(5) == 0 and tray.last_saved and os.path.exists(tray.last_saved)
    tray.instance_server.close()


def test_selftest(qapp, tmp_path):
    out = tmp_path / "out.json"
    assert app.selftest(str(out)) == 0
    got = json.loads(out.read_text())
    assert got["full"] == [1600, 1000] and got["region"] == [400, 200] and got["edited"] == [400, 200]
    assert got["red_border"] and got["jpeg_ok"] and got["jpeg"].endswith(".jpg") and got["fonts"]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows' own keys (on Linux they're Plasma shortcuts)")
def test_a_problem_shared_by_every_key_is_said_once(tray):
    tray.key_problems = {k: "Same reason." for k in ("region", "window", "full")}
    tray.answers["preferences"] = True
    tray.preferences()
    from PySide6.QtWidgets import QLabel
    texts = [w.text() for w in tray.preferences_dialog.findChildren(QLabel) if "Same reason." in w.text()]
    assert texts == ["Same reason."]
