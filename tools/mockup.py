"""Mock-up pictures of PR7-Q, drawn offscreen with real Qt widgets: python tools/mockup.py OUT_DIR"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

_cfg = Path(tempfile.gettempdir()) / "pr7q_offscreen.json"
_cfg.write_text(json.dumps({"screens": [{"name": "s", "x": 0, "y": 0, "width": 3200, "height": 2200,
                                          "logicalDpi": 96, "logicalBaseDpi": 96, "dpr": 1}]}))
os.environ.setdefault("QT_QPA_PLATFORM", f"offscreen:configfile={_cfg}")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPolygonF  # noqa: E402
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QMainWindow,  # noqa: E402
                               QMenu, QVBoxLayout, QWidget)

from pr7q import theme, widgets  # noqa: E402
import sample_images  # noqa: E402

out = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/mockup")
out.mkdir(parents=True, exist_ok=True)
app = QApplication([])
theme.load_fonts()
W, H = 1280, 800
APP_SHOT = QImage(sys.argv[2] if len(sys.argv) > 2 else
                  "/home/user/paragon-pr7-e/docs/screenshots/grid.png")


def desktop() -> QImage:
    """A stand-in desktop: wallpaper, a family app's window, the taskbar with PR7-Q's tray icon."""
    img = QImage(W * 2, H * 2, QImage.Format.Format_RGB32)
    img.setDevicePixelRatio(2)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.drawImage(QRectF(0, 0, W, H), sample_images.photo(0, "hills", W * 2, H * 2))
    win = QRectF(120, 60, 880, 550)
    p.fillRect(win.translated(0, 10), QColor(0, 0, 0, 120))
    p.drawImage(win, APP_SHOT)
    bar = QRectF(0, H - 44, W, 44)
    p.fillRect(bar, QColor(18, 14, 18, 235))
    widgets.draw_icon(p, "region", QRectF(W - 150, H - 33, 22, 22), QColor(theme.LED_ORANGE), 1.7)
    f = QFont("Inter"); f.setPixelSize(12); p.setFont(f); p.setPen(QColor("#FFFFFF"))
    p.drawText(QRectF(W - 110, H - 44, 100, 44), Qt.AlignmentFlag.AlignCenter, "22:56\n24/11/2026")
    p.end()
    return img


DESK = desktop()
REGION = QRect(150, 120, 640, 400)          # what the editor shows (logical pixels on the desktop)
DRAG = QRect(150, 95, 485, 130)            # the region being dragged: it ends on a photo, for the magnifier

TRAY = ["Capture &region\tPrint", "Capture &last region\tShift+Print", "Capture &window\tAlt+Print",
        "Capture &full screen\tCtrl+Print", "-", "Capture from &clipboard", "&Open image from file...", "-",
        "Quick &preferences", "&Preferences...", "-", "&Help", "&About PR7-Q", "-", "E&xit"]
AFTER = ["&Save directly (Pictures\\Screenshots)", "Save &as...", "&Copy to clipboard", "Open in image &editor",
         "Open in &PR7-P", "&Print...", "-", "&Cancel"]


def menu_pixmap(items, active, parent=None, sub=()):
    m = QMenu(parent)
    for t in items:
        if t == "-":
            m.addSeparator()
        elif t in sub:
            m.addMenu(t)
        else:
            m.addAction(t)
    m.resize(m.sizeHint())
    m.show(); app.processEvents()
    m.setActiveAction([a for a in m.actions() if not a.isSeparator()][active]); app.processEvents()
    pm = m.grab()
    m.hide()
    return pm


def save(img, name):
    img.save(str(out / f"{name}.png"))
    print(out / f"{name}.png")


def shot_tray():
    img = QImage(DESK)
    p = QPainter(img)
    pm = menu_pixmap(TRAY, 0, sub=("Quick &preferences",))
    s = pm.deviceIndependentSize()
    p.drawPixmap(int(W - 160 - s.width() + 40), int(H - 48 - s.height()), pm)
    p.end()
    save(img, "tray_menu")


def overlay(p: QPainter, sel: QRect, cursor: QPoint, menu=False):
    """Greenshot's region capture: the screen dimmed except the selection, guides, size, and the magnifier."""
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    shade = QColor(0, 0, 0, 140)
    r = QRectF(sel)
    for part in (QRectF(0, 0, W, r.top()), QRectF(0, r.bottom(), W, H - r.bottom()),
                 QRectF(0, r.top(), r.left(), r.height()), QRectF(r.right(), r.top(), W - r.right(), r.height())):
        p.fillRect(part, shade)
    p.setPen(QPen(theme.family_gradient(r.left(), 0, r.right(), 0), 2))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(r)
    p.setPen(QPen(QColor(255, 255, 255, 110), 1, Qt.PenStyle.DashLine))
    p.drawLine(QPointF(cursor.x(), 0), QPointF(cursor.x(), H))
    p.drawLine(QPointF(0, cursor.y()), QPointF(W, cursor.y()))
    f = QFont("Inter"); f.setPixelSize(12); f.setWeight(QFont.Weight.DemiBold); p.setFont(f)
    label = f"{sel.width()} x {sel.height()}"
    tw = p.fontMetrics().horizontalAdvance(label) + 16
    box = QRectF(r.left(), r.top() - 30, tw, 22)
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(theme.MENU)); p.drawRoundedRect(box, 4, 4)
    p.setPen(QColor(theme.ON_DARK)); p.drawText(box, Qt.AlignmentFlag.AlignCenter, label)
    if menu:
        return
    # the magnifier: 15 x 15 pixels around the pointer, 8 times bigger, with the centre pixel marked
    n, k = 15, 8
    src = DESK.copy(QRect((cursor.x() - n // 2) * 2, (cursor.y() - n // 2) * 2, n * 2, n * 2))
    mag = QRectF(cursor.x() + 24, cursor.y() + 24, n * k, n * k)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
    path = QPainterPath(); path.addEllipse(mag)
    p.save(); p.setClipPath(path); p.drawImage(mag, src)
    p.setPen(QPen(QColor(255, 255, 255, 40), 1))
    for i in range(1, n):
        p.drawLine(QPointF(mag.left() + i * k, mag.top()), QPointF(mag.left() + i * k, mag.bottom()))
        p.drawLine(QPointF(mag.left(), mag.top() + i * k), QPointF(mag.right(), mag.top() + i * k))
    p.restore()
    c = QRectF(mag.left() + (n // 2) * k, mag.top() + (n // 2) * k, k, k)
    p.setBrush(Qt.BrushStyle.NoBrush)        # the size label's fill would cover the magnified pixels
    p.setPen(QPen(QColor(theme.ACCENT), 2)); p.drawRect(c)
    p.setPen(QPen(theme.family_gradient(mag.left(), 0, mag.right(), 0), 3)); p.drawEllipse(mag)
    info = f"{cursor.x()}, {cursor.y()}   #{DESK.pixelColor(cursor.x() * 2, cursor.y() * 2).name().upper()[1:]}"
    ib = QRectF(mag.left(), mag.bottom() + 8, mag.width(), 22)
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(theme.MENU)); p.drawRoundedRect(ib, 4, 4)
    p.setPen(QColor(theme.ON_DARK)); p.drawText(ib, Qt.AlignmentFlag.AlignCenter, info)


def shot_region():
    img = QImage(DESK)
    p = QPainter(img)
    overlay(p, DRAG, DRAG.bottomRight())
    p.end()
    save(img, "region")


def shot_after():
    img = QImage(DESK)
    p = QPainter(img)
    overlay(p, REGION, REGION.bottomRight(), menu=True)
    pm = menu_pixmap(AFTER, 4)
    p.drawPixmap(REGION.right() + 8, REGION.bottom() - int(pm.deviceIndependentSize().height()) + 40, pm)
    p.end()
    save(img, "after_capture")


# ---------------------------------------------------------------- the editor
class Canvas(QWidget):
    def __init__(self):
        super().__init__()
        self.cap = DESK.copy(QRect(REGION.x() * 2, REGION.y() * 2, REGION.width() * 2, REGION.height() * 2))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor(theme.PANEL if theme.FINISH == "obsidian" else "#D9D4D6"))
        cw, ch = REGION.width(), REGION.height()
        x0, y0 = (self.width() - cw) / 2, (self.height() - ch) / 2
        r = QRectF(x0, y0, cw, ch)
        p.fillRect(r.translated(0, 5), QColor(0, 0, 0, 120 if theme.FINISH == "obsidian" else 40))
        p.drawImage(r, self.cap)
        red, orange = QColor("#E0202A"), QColor(theme.LED_ORANGE)
        # pixelated area (the obfuscate tool)
        pix = QRectF(x0 + 470, y0 + 300, 150, 60)
        small = self.cap.copy(QRect(int((pix.x() - x0) * 2), int((pix.y() - y0) * 2), 300, 120)).scaled(
            15, 6, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        p.drawImage(pix, small)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        # highlight band
        hl = QColor(theme.LED_ORANGE); hl.setAlphaF(.35)
        p.fillRect(QRectF(x0 + 24, y0 + 100, 170, 26), hl)
        # rectangle
        p.setPen(QPen(red, 3)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(x0 + 250, y0 + 90, 180, 150), 3, 3)
        # arrow
        a, b = QPointF(x0 + 560, y0 + 60), QPointF(x0 + 440, y0 + 140)
        p.setPen(QPen(red, 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)); p.drawLine(a, b)
        import math
        ang = math.atan2(a.y() - b.y(), a.x() - b.x())
        head = QPolygonF([b, QPointF(b.x() + 18 * math.cos(ang + .45), b.y() + 18 * math.sin(ang + .45)),
                          QPointF(b.x() + 18 * math.cos(ang - .45), b.y() + 18 * math.sin(ang - .45))])
        p.setBrush(red); p.setPen(Qt.PenStyle.NoPen); p.drawPolygon(head)
        # text label with a speech bubble
        bub = QRectF(x0 + 470, y0 + 20, 150, 40)
        path = QPainterPath(); path.addRoundedRect(bub, 8, 8)
        path.moveTo(bub.left() + 30, bub.bottom()); path.lineTo(bub.left() + 20, bub.bottom() + 14)
        path.lineTo(bub.left() + 48, bub.bottom())
        p.setBrush(QColor("#FFFFFF")); p.setPen(QPen(red, 2)); p.drawPath(path)
        f = QFont("Inter"); f.setPixelSize(14); f.setWeight(QFont.Weight.DemiBold); p.setFont(f)
        p.setPen(QColor("#1A1418")); p.drawText(bub, Qt.AlignmentFlag.AlignCenter, "Your photos")
        # numbered steps
        for i, (sx, sy) in enumerate(((x0 + 12, y0 + 88), (x0 + 238, y0 + 78), (x0 + 458, y0 + 288)), 1):
            c = QRectF(sx - 13, sy - 13, 26, 26)
            p.setPen(QPen(QColor("#FFFFFF"), 2)); p.setBrush(red); p.drawEllipse(c)
            f.setPixelSize(13); f.setWeight(QFont.Weight.Bold); p.setFont(f)
            p.setPen(QColor("#FFFFFF")); p.drawText(c, Qt.AlignmentFlag.AlignCenter, str(i))
        # the selected object's handles (the rectangle)
        sel = QRectF(x0 + 250, y0 + 90, 180, 150)
        p.setPen(QPen(QColor(theme.ACCENT), 1, Qt.PenStyle.DashLine)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(sel.adjusted(-5, -5, 5, 5))
        p.setPen(QPen(QColor(theme.ACCENT), 1)); p.setBrush(QColor("#FFFFFF"))
        for pt in (sel.topLeft(), sel.topRight(), sel.bottomLeft(), sel.bottomRight(),
                   QPointF(sel.center().x(), sel.top()), QPointF(sel.center().x(), sel.bottom()),
                   QPointF(sel.left(), sel.center().y()), QPointF(sel.right(), sel.center().y())):
            p.drawRect(QRectF(pt.x() - 9, pt.y() - 9, 8, 8).translated(4.5 - (pt.x() - sel.left() > 0) * 0, 4.5))
        _ = orange


def swatch_row() -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(5)
    for i, c in enumerate(("#E0202A", "#F4353A", "#FF7A1A", "#FFB070", "#D83A6A", "#FFFFFF", "#1A1418")):
        s = QFrame()
        s.setFixedSize(22, 22)
        border = "2px solid #FFFFFF" if i == 0 else f"1px solid {theme.PANEL_EDGE}"
        s.setStyleSheet(f"background: {c}; border: {border}; border-radius: 4px;")
        lay.addWidget(s)
    return w


EXTRA = """
QLabel#prop {{ color: {dim}; font-weight: 600; font-size: 11px; }}
QWidget#status {{ background: {bg}; border-top: 1px solid {edge}; }}
QLabel#stat {{ color: {dim}; font-size: 12px; }}
QWidget#tools {{ background: {bg}; border-right: 1px solid {edge}; }}
"""


def editor() -> QMainWindow:
    win = QMainWindow()
    win.resize(1280, 820)
    for t in ("&File", "&Edit", "&Object", "&Help"):
        win.menuBar().addMenu(t)
    c = QWidget()
    col = QVBoxLayout(c)
    col.setContentsMargins(0, 0, 0, 0)
    col.setSpacing(0)
    col.addWidget(widgets.Header("SCREENSHOTS"))
    bar = QWidget()
    lay = QHBoxLayout(bar)
    lay.setContentsMargins(12, 8, 12, 8)
    lay.setSpacing(4)

    def gap(l=lay):
        line = QFrame(); line.setFixedSize(1, 22); line.setStyleSheet(f"background: {theme.PANEL_EDGE};")
        l.addSpacing(6); l.addWidget(line); l.addSpacing(6)

    for name, tip in (("save", "Save (Ctrl+S)"), ("copy", "Copy to clipboard (Ctrl+Shift+C)"), ("print", "Print"),
                      ("open", "Open in PR7-P")):
        lay.addWidget(widgets.SmallKey(name, tip))
    gap()
    for name, tip in (("undo", "Undo"), ("redo", "Redo")):
        lay.addWidget(widgets.SmallKey(name, tip))
    gap()
    for label, w in (("LINE", None), ("", "thick"), ("COLOUR", "swatch"), ("FILL", "fill"), ("", "shadow")):
        if label:
            lab = QLabel(label); lab.setObjectName("prop"); lay.addWidget(lab); lay.addSpacing(4)
        if w == "thick":
            cb = QComboBox(); cb.addItems(["3 px", "1 px", "2 px", "5 px", "8 px"]); cb.setFixedWidth(80); lay.addWidget(cb)
            lay.addSpacing(10)
        elif w == "swatch":
            lay.addWidget(swatch_row()); lay.addSpacing(10)
        elif w == "fill":
            cb = QComboBox(); cb.addItems(["None", "White", "Colour"]); cb.setFixedWidth(90); lay.addWidget(cb)
            lay.addSpacing(10)
        elif w == "shadow":
            ch = QCheckBox("Shadow"); ch.setChecked(True); lay.addWidget(ch)
    lay.addStretch(1)
    zoom = QComboBox(); zoom.addItems(["100%", "Fit"]); zoom.setFixedWidth(84); lay.addWidget(zoom)
    col.addWidget(bar)
    mid = QHBoxLayout()
    mid.setSpacing(0)
    tools = QWidget(); tools.setObjectName("tools")
    tl = QVBoxLayout(tools)
    tl.setContentsMargins(8, 10, 8, 10)
    tl.setSpacing(4)
    for name, tip, on in (("select", "Select (Esc)", False), ("rect", "Rectangle (R)", True), ("ellipse", "Ellipse (E)", False),
                          ("line", "Line (L)", False), ("arrow", "Arrow (A)", False), ("pen", "Freehand (F)", False),
                          ("text", "Text (T)", False), ("bubble", "Speech bubble (S)", False),
                          ("step", "Step number (I)", False), ("highlight", "Highlight (H)", False),
                          ("obfuscate", "Blur / pixelate (O)", False), ("crop", "Crop (C)", False)):
        k = widgets.SmallKey(name, tip, True); k.setChecked(on); tl.addWidget(k)
    tl.addStretch(1)
    mid.addWidget(tools)
    mid.addWidget(Canvas(), 1)
    col.addLayout(mid, 1)
    st = QWidget(); st.setObjectName("status")
    sl = QHBoxLayout(st); sl.setContentsMargins(14, 4, 14, 6); sl.setSpacing(26)
    for t in ("640 x 400", "100 %", "6 objects", "Not saved yet"):
        lab = QLabel(t); lab.setObjectName("stat"); sl.addWidget(lab)
    sl.addStretch(1)
    lab = QLabel("Screenshot 2026-11-24 22.56.png"); lab.setObjectName("stat"); sl.addWidget(lab)
    col.addWidget(st)
    win.setCentralWidget(c)
    return win


def shot_editor(name):
    app.setPalette(theme.palette())
    app.setStyleSheet(theme.stylesheet() + EXTRA.format(dim=theme.TEXT_DIM, bg=theme.BACKGROUND, edge=theme.PANEL_EDGE))
    w = editor()
    w.show()
    end = time.time() + .5
    while time.time() < end:
        app.processEvents(); time.sleep(.02)
    w.grab().save(str(out / f"{name}.png"))
    print(out / f"{name}.png")
    w.close()


app.setPalette(theme.palette())
app.setStyleSheet(theme.stylesheet())
shot_tray()
shot_region()
shot_after()
shot_editor("editor")
theme.set_finish("aurora")
shot_editor("editor_aurora")
