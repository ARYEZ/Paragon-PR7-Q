"""PR7-Q on Linux's Wayland desktops (PR7-OS): the screen from the desktop portal (a stand-in portal process on a
private session bus, answering as Plasma's does), Capture window through Plasma's own dialog, the region picker on one
screen, the keys as Plasma shortcuts, start at sign-in as an autostart entry."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest

from pr7q import capture, hotkeys, portal, settings, tray as traymod

STANDIN = Path(__file__).resolve().parent / "standin_portal.py"
linux = pytest.mark.skipif(sys.platform == "win32", reason="Linux's desktop portal")
needs_bus = pytest.mark.skipif(sys.platform == "win32" or not shutil.which("dbus-daemon"), reason="needs dbus-daemon")


@pytest.fixture
def bus():
    daemon = subprocess.Popen(["dbus-daemon", "--session", "--nofork", "--print-address=1"], stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, text=True)
    yield daemon.stdout.readline().strip()
    daemon.terminate()
    daemon.wait()


def start_portal(address, picture, *extra):
    proc = subprocess.Popen([sys.executable, str(STANDIN), address, str(picture), *extra], stdout=subprocess.PIPE,
                            text=True)
    assert proc.stdout.readline().strip() == "READY"
    return proc


@pytest.fixture
def picture(tmp_path):
    img = QImage(1600, 1000, QImage.Format.Format_RGB32)
    img.fill(QColor("#DE0639"))
    for x in range(800, 1600):                       # the right half orange: a crop shows where it came from
        for y in range(0, 1000, 50):
            img.setPixelColor(x, y, QColor("#F2781E"))
    path = tmp_path / "desktop.png"
    img.save(str(path))
    return path


@needs_bus
def test_the_portal_takes_the_whole_screen(qapp, bus, picture):
    proc = start_portal(bus, picture)
    try:
        assert portal.available(bus)
        img = portal.screenshot(address=bus, timeout=10)
        options = json.loads(proc.stdout.readline())
    finally:
        proc.terminate()
        proc.wait()
    assert (img.width(), img.height()) == (1600, 1000) and img.pixelColor(10, 10) == QColor("#DE0639")
    assert options["interactive"] is False and options["handle_token"].startswith("pr7q_")
    desk = capture.from_portal(img, QRect(0, 0, 800, 500))                     # a 2x screen of 800 x 500 points
    assert desk.scale == 2.0 and desk.cursor is None
    assert desk.crop(QRect(400, 0, 400, 500)).size().width() == 800             # the right half, in pixels


@needs_bus
def test_a_cancelled_dialog_and_no_portal(qapp, bus, picture):
    proc = start_portal(bus, picture, "cancel")
    try:
        with pytest.raises(portal.PortalError, match="cancelled"):
            portal.screenshot(interactive=True, address=bus, timeout=10)
    finally:
        proc.terminate()
        proc.wait()
    assert not portal.available(bus)                                           # nobody owns the portal's name now
    with pytest.raises(portal.PortalError):
        portal.screenshot(address=bus, timeout=2)


@linux
def test_capture_window_uses_plasmas_dialog(tray, qapp):
    """Wayland doesn't say which window is under the pointer: Capture window asks Plasma's dialog instead."""
    settings.set("after", "copy")
    picked = QImage(300, 200, QImage.Format.Format_RGB32)
    picked.fill(QColor("#F2781E"))
    tray.wayland = lambda: True
    tray.portal_pick = lambda: picked
    got = []
    tray.captured.connect(lambda img, how: got.append((img.size(), how)))
    tray.capture("window")
    assert got == [(picked.size(), "window")] and qapp.clipboard().image().size() == picked.size()

    def cancelled():
        raise portal.PortalError("cancelled")
    tray.portal_pick = cancelled
    errors = []
    tray.answers["error"] = lambda text: errors.append(text)
    tray.capture("window")
    assert errors == []                                                        # cancelling isn't an error

    def refused():
        raise portal.PortalError("the desktop portal refused the screenshot")
    tray.portal_pick = refused
    tray.capture("window")
    assert errors and "refused" in errors[0]


@linux
def test_a_portal_failure_is_said(tray):
    def fails():
        raise portal.PortalError("the desktop didn't answer the screenshot request")
    tray.grabber = fails
    errors = []
    tray.answers["error"] = lambda text: errors.append(text)
    tray.capture("full")
    assert errors and "didn't answer" in errors[0] and tray.picker is None


@linux
def test_the_region_picker_on_wayland_uses_one_screen(tray, qapp):
    tray.wayland = lambda: True                    # a single screen here: the whole desktop, as before
    settings.set("after", "copy")
    tray.capture("region")
    p = tray.picker
    assert p is not None and p.desktop.geometry == tray.grabber().geometry
    QTest.keyClick(p, Qt.Key.Key_Escape)
    desk = tray.grabber()                           # part() keeps the pixels of the screen it's given (the right half)
    half = capture.part(desk, QRect(200, 0, 200, 250))
    assert half.geometry == QRect(200, 0, 200, 250) and half.image.width() == 400
    assert half.image.pixelColor(10, 10) == desk.image.pixelColor(410, 10)
    assert half.cursor is None                       # the mouse (120, 80) was on the other half


@linux
def test_start_at_sign_in_is_an_autostart_entry(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_CONFIG_DIRS", str(tmp_path / "xdg"))
    assert traymod.start_with_windows() is False
    traymod.start_with_windows(True)
    entry = (tmp_path / "config/autostart/paragon-pr7-q.desktop").read_text()
    assert "[Desktop Entry]" in entry and entry.splitlines()[4].endswith(" --tray") and "Type=Application" in entry
    assert traymod.start_with_windows() is True
    traymod.start_with_windows(False)
    assert not (tmp_path / "config/autostart/paragon-pr7-q.desktop").exists()


@linux
def test_the_keys_are_plasma_shortcuts(tray):
    assert not hotkeys.available()
    tray.answers["preferences"] = True
    tray.preferences()
    from PySide6.QtWidgets import QLabel
    texts = [w.text() for w in tray.preferences_dialog.findChildren(QLabel)]
    assert any("System Settings > Keyboard > Shortcuts" in t for t in texts)
    assert tray.preferences_dialog.keys == {}


@linux
def test_pr7os_starts_it_for_everyone_and_you_can_say_no(qapp, tmp_path, monkeypatch):
    """PR7-OS's /etc/xdg/autostart entry starts PR7-Q at sign-in; unticking writes your own Hidden=true entry of the
    same name (freedesktop.org's override), ticking again puts PR7-Q back."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_CONFIG_DIRS", str(tmp_path / "xdg"))
    (tmp_path / "xdg/autostart").mkdir(parents=True)
    (tmp_path / "xdg/autostart/paragon-pr7-q.desktop").write_text("[Desktop Entry]\nExec=pr7-q --tray\n")
    assert traymod.start_with_windows() is True
    traymod.start_with_windows(False)
    mine = tmp_path / "config/autostart/paragon-pr7-q.desktop"
    assert "Hidden=true" in mine.read_text() and traymod.start_with_windows() is False
    traymod.start_with_windows(True)
    assert "Hidden=true" not in mine.read_text() and traymod.start_with_windows() is True
