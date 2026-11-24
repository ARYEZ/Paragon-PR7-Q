"""Screenshots of the real windows (offscreen): python tools/screenshots.py OUT_DIR [APP_SCREENSHOT.png]"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

_cfg = Path(tempfile.gettempdir()) / "pr7q_offscreen.json"
_cfg.write_text(json.dumps({"screens": [{"name": "s", "x": 0, "y": 0, "width": 1280, "height": 800,
                                          "logicalDpi": 96, "logicalBaseDpi": 96, "dpr": 1}]}))
os.environ.setdefault("QT_QPA_PLATFORM", f"offscreen:configfile={_cfg}")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
work = Path(tempfile.mkdtemp())

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSettings  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

QSettings.setDefaultFormat(QSettings.Format.IniFormat)
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(work / "settings"))
import sample_images  # noqa: E402
from pr7q import settings, theme  # noqa: E402
from pr7q.capture import Desktop  # noqa: E402
from pr7q.editor import EditorWindow, Shape  # noqa: E402
from pr7q.overlay import RegionPicker  # noqa: E402
from pr7q.tray import PreferencesDialog, TrayApp  # noqa: E402

out = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/screenshots")
out.mkdir(parents=True, exist_ok=True)
app = QApplication([])
theme.load_fonts()
app.setPalette(theme.palette())
app.setStyleSheet(theme.stylesheet())
settings.set("folder", str(work / "Screenshots"))
W, H, K = 1280, 800, 2
shot_path = sys.argv[2] if len(sys.argv) > 2 else "/home/user/paragon-pr7-e/docs/screenshots/grid.png"
img = QImage(W * K, H * K, QImage.Format.Format_RGB32)
p = QPainter(img)
p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
p.drawImage(QRectF(0, 0, W * K, H * K), sample_images.photo(0, "hills", W * K, H * K))
if os.path.exists(shot_path):
    p.drawImage(QRectF(120 * K, 60 * K, 880 * K, 550 * K), QImage(shot_path))
p.end()
desk = Desktop(img, QRect(0, 0, W, H), K, QPoint(634, 224))


def settle():
    end = time.time() + .5
    while time.time() < end:
        app.processEvents(); time.sleep(.02)


def save(w, name):
    settle()
    w.grab().save(str(out / f"{name}.png"))
    print(out / f"{name}.png")


picker = RegionPicker(desk)
picker.sel = QRect(150, 95, 485, 130)
picker.pos_ = QPoint(634, 224)
picker.show_over_desktop()
save(picker, "region")
picker.close()

ed = EditorWindow(desk.crop(QRect(150, 120, 640, 400)), "PR7-E")
ed.resize(1280, 820)
c = ed.canvas
c.add(Shape("highlight", [QPointF(50, 170), QPointF(420, 212)], colour="#FF7A1A"))
c.add(Shape("rect", [QPointF(560, 160), QPointF(920, 440)], colour="#E0202A", width=5))
c.add(Shape("arrow", [QPointF(1150, 120), QPointF(940, 300)], colour="#E0202A", width=5))
c.add(Shape("bubble", [QPointF(1000, 30), QPointF(1260, 100), QPointF(1030, 125)], colour="#E0202A", width=3,
            text="Your photos", size=26))
for i, (x, y) in enumerate(((30, 190), (545, 150), (930, 470)), 1):
    c.add(Shape("step", [QPointF(x, y)], colour="#E0202A", number=i, size=24))
c.add(Shape("obfuscate", [QPointF(950, 520), QPointF(1250, 640)], size=24))
ed.show()
ed.set_zoom(0.62)
c.selected = c.shapes[1]
c.update()
save(ed, "editor")
dlg = PreferencesDialog(TrayApp(grabber=lambda: desk, window_at=None, show_tray=False))
dlg.show()
save(dlg, "preferences")
theme.set_finish("aurora")
app.setPalette(theme.palette())
app.setStyleSheet(theme.stylesheet())
ed2 = EditorWindow(desk.crop(QRect(150, 120, 640, 400)), "PR7-E")
ed2.resize(1280, 820)
for s in c.shapes:
    ed2.canvas.shapes.append(s.copy())
ed2.show()
ed2.set_zoom(0.62)
save(ed2, "editor_aurora")
for e in (ed, ed2):
    e.answers["save_changes"] = "discard"
    e.close()
