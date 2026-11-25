import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PARAGON_FAMILY_FILE"] = os.path.join(__import__("tempfile").mkdtemp(prefix="family-"), "finish")  # never the real choice


@pytest.fixture(scope="session")
def qapp(tmp_path_factory):
    # Tests never write the real settings: QSettings goes to INI files in a temp folder.
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    from pr7q import theme
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path_factory.mktemp("settings")))
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    theme.load_fonts()
    app.setPalette(theme.palette())
    app.setStyleSheet(theme.stylesheet())
    yield app
    for w in app.topLevelWidgets():
        w.close()
    app.clipboard().clear()
    app.processEvents()


@pytest.fixture
def clean_settings(qapp, tmp_path):
    from PySide6.QtCore import QSettings
    from pr7q import settings
    s = QSettings(QSettings.defaultFormat(), QSettings.Scope.UserScope, "Paragon", "PR7-Q")
    s.clear(); s.sync()
    settings.set("folder", str(tmp_path / "Screenshots"))     # never the real Pictures folder
    yield
    s.clear(); s.sync()


def stripes(w=800, h=500):
    """A stand-in desktop picture: vertical bands of colour 100 px wide, so a crop shows where it came from."""
    from PySide6.QtGui import QColor, QImage, QPainter
    img = QImage(w, h, QImage.Format.Format_RGB32)
    p = QPainter(img)
    cols = ["#C2183F", "#E2502A", "#F07A2A", "#7A2230", "#D83A6A", "#FFB070", "#5A1426", "#FFE2C2"]
    for i in range(0, w, 100):
        p.fillRect(i, 0, 100, h, QColor(cols[(i // 100) % len(cols)]))
    p.end()
    return img


@pytest.fixture
def desk(qapp):
    """A desktop of 400 x 250 points shown at 2x (800 x 500 pixels), the mouse at (120, 80)."""
    from PySide6.QtCore import QPoint, QRect
    from pr7q.capture import Desktop
    return Desktop(stripes(), QRect(0, 0, 400, 250), 2.0, QPoint(120, 80))


@pytest.fixture
def tray(qapp, clean_settings, desk):
    from PySide6.QtCore import QRect
    from pr7q.tray import TrayApp
    t = TrayApp(grabber=lambda: desk, window_at=lambda pt: (QRect(50, 25, 150, 100), "Notes - PR7-W"),
                show_tray=False)
    t.answers["error"] = lambda text: pytest.fail(f"PR7-Q showed an error: {text}")
    yield t
    for e in list(t.editors):
        e.answers["save_changes"] = "discard"
        e.close()
    t.hotkeys.unregister()
