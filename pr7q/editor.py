"""The image editor (Greenshot's): the capture with shapes on it that stay editable until it's saved.

`Shape` is plain data (kind, points in image pixels, colour, width, fill, shadow, text, number); `paint_shape` draws
one, both on screen and into the saved picture (`render`), so what's shown is what's saved. Undo / Redo keep
snapshots of the picture and the shapes, so crop and canvas size undo too.

Tools (and their keys): select (Esc), rectangle R, ellipse E, line L, arrow A, freehand F, text T, speech bubble S,
step number I, highlight H, blur / pixelate O, crop C."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field, replace

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (QAction, QActionGroup, QColor, QFont, QFontMetricsF, QImage, QKeySequence, QPainter,
                           QPainterPath, QPen, QPolygonF)
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout, QInputDialog,
                               QLabel, QLineEdit, QMainWindow, QMessageBox, QScrollArea, QSpinBox, QVBoxLayout,
                               QWidget)

from . import output, settings, theme, widgets

TOOLS = [("select", "Select", "Esc"), ("rect", "Rectangle", "R"), ("ellipse", "Ellipse", "E"), ("line", "Line", "L"),
         ("arrow", "Arrow", "A"), ("pen", "Freehand", "F"), ("text", "Text", "T"), ("bubble", "Speech bubble", "S"),
         ("step", "Step number", "I"), ("highlight", "Highlight", "H"), ("obfuscate", "Blur / pixelate", "O"),
         ("crop", "Crop", "C")]
SWATCHES = ["#E0202A", "#F4353A", "#FF7A1A", "#FFB070", "#D83A6A", "#FFFFFF", "#1A1418"]
TWO_POINT = {"rect", "ellipse", "line", "arrow", "highlight", "obfuscate", "bubble"}
BOXES = {"rect", "ellipse", "highlight", "obfuscate", "bubble"}


@dataclass
class Shape:
    kind: str
    pts: list = field(default_factory=list)     # QPointF in image pixels
    colour: str = "#E0202A"
    width: int = 3
    fill: str = ""                              # "" none, "white", or a colour
    shadow: bool = True
    text: str = ""
    number: int = 0
    size: int = 18                              # text size / pixel block size

    def copy(self) -> "Shape":
        return replace(self, pts=[QPointF(p) for p in self.pts])

    def box(self) -> QRectF:
        """The rectangle the shape covers (for picking it and its handles)."""
        if self.kind == "step":
            r = step_radius(self)
            c = self.pts[0]
            return QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r)
        if self.kind == "text":
            return text_rect(self)
        xs = [p.x() for p in self.pts[:2] if self.kind in TWO_POINT] or [p.x() for p in self.pts]
        ys = [p.y() for p in self.pts[:2] if self.kind in TWO_POINT] or [p.y() for p in self.pts]
        return QRectF(QPointF(min(xs), min(ys)), QPointF(max(xs), max(ys)))

    def move(self, d: QPointF) -> None:
        self.pts = [p + d for p in self.pts]


def step_radius(s: Shape) -> float:
    return max(11.0, s.size * 0.8)


def _font(size: int, bold=True) -> QFont:
    f = QFont("Inter")
    f.setPixelSize(max(6, int(size)))
    f.setWeight(QFont.Weight.DemiBold if bold else QFont.Weight.Normal)
    return f


def text_rect(s: Shape) -> QRectF:
    fm = QFontMetricsF(_font(s.size))
    lines = (s.text or " ").split("\n")
    w = max(fm.horizontalAdvance(ln) for ln in lines) + 16
    h = fm.height() * len(lines) + 10
    return QRectF(s.pts[0], QSize(int(w), int(h)).toSizeF())


# ---------------------------------------------------------------- painting
def paint_shape(p: QPainter, s: Shape, base: QImage) -> None:
    col = QColor(s.colour)
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    if s.shadow and s.kind not in ("highlight", "obfuscate"):
        p.save()
        p.translate(3, 3)
        _paint(p, s, QColor(0, 0, 0, 90), base, shadow=True)
        p.restore()
    _paint(p, s, col, base)
    p.restore()


def _fill_brush(s: Shape, col: QColor):
    if s.fill == "white":
        return QColor("#FFFFFF")
    if s.fill == "colour":
        return col
    return Qt.BrushStyle.NoBrush


def _paint(p: QPainter, s: Shape, col: QColor, base: QImage, shadow=False):
    pen = QPen(col, s.width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    k = s.kind
    if k in ("rect", "ellipse"):
        p.setPen(pen)
        p.setBrush(QColor(0, 0, 0, 90) if shadow and s.fill else _fill_brush(s, col))
        r = s.box()
        p.drawRect(r) if k == "rect" else p.drawEllipse(r)
    elif k in ("line", "arrow"):
        a, b = s.pts[0], s.pts[-1]
        p.setPen(pen)
        p.drawLine(a, b)
        if k == "arrow" and (b - a).manhattanLength() > 1:
            ang = math.atan2(a.y() - b.y(), a.x() - b.x())
            n = 10 + s.width * 2.2
            head = QPolygonF([b, QPointF(b.x() + n * math.cos(ang + .45), b.y() + n * math.sin(ang + .45)),
                              QPointF(b.x() + n * math.cos(ang - .45), b.y() + n * math.sin(ang - .45))])
            p.setBrush(col); p.setPen(QPen(col, 1)); p.drawPolygon(head)
    elif k == "pen":
        if len(s.pts) > 1:
            path = QPainterPath(s.pts[0])
            for pt in s.pts[1:]:
                path.lineTo(pt)
            p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush); p.drawPath(path)
    elif k == "text":
        r = text_rect(s)
        if s.fill and not shadow:
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(_fill_brush(s, col)); p.drawRoundedRect(r, 4, 4)
        p.setFont(_font(s.size))
        text_col = col
        if s.fill == "colour":
            text_col = QColor("#FFFFFF") if col.lightness() < 160 else QColor("#1A1418")
        p.setPen(QColor(0, 0, 0, 90) if shadow else text_col)
        p.drawText(r.adjusted(8, 5, -8, -5), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, s.text)
    elif k == "bubble":
        r = s.box()
        tail = s.pts[2] if len(s.pts) > 2 else QPointF(r.left() + 20, r.bottom() + 24)
        path = QPainterPath()
        path.addRoundedRect(r, 8, 8)
        base_x = min(max(tail.x(), r.left() + 14), r.right() - 34)
        tri = QPainterPath(QPointF(base_x, r.bottom() - 1))
        tri.lineTo(tail); tri.lineTo(base_x + 22, r.bottom() - 1); tri.closeSubpath()
        path = path.united(tri)
        p.setPen(QPen(col, s.width)); p.setBrush(QColor(0, 0, 0, 90) if shadow else QColor("#FFFFFF"))
        p.drawPath(path)
        if not shadow:
            p.setFont(_font(s.size)); p.setPen(QColor("#1A1418"))
            p.drawText(r.adjusted(8, 4, -8, -4), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, s.text)
    elif k == "step":
        c, rad = s.pts[0], step_radius(s)
        p.setPen(QPen(QColor("#FFFFFF"), 2) if not shadow else QPen(Qt.PenStyle.NoPen))
        p.setBrush(col if not shadow else QColor(0, 0, 0, 90))
        p.drawEllipse(c, rad, rad)
        if not shadow:
            p.setFont(_font(rad * 1.05))
            p.setPen(QColor("#FFFFFF") if col.lightness() < 170 else QColor("#1A1418"))
            p.drawText(QRectF(c.x() - rad, c.y() - rad, 2 * rad, 2 * rad), Qt.AlignmentFlag.AlignCenter, str(s.number))
    elif k == "highlight":
        c = QColor(col); c.setAlphaF(.38)
        p.fillRect(s.box(), c)
    elif k == "obfuscate":
        r = s.box().toAlignedRect().intersected(base.rect())
        if r.width() > 1 and r.height() > 1:
            block = max(2, s.size // 2)
            small = base.copy(r).scaled(max(1, r.width() // block), max(1, r.height() // block),
                                        Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            p.save()
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
            p.drawImage(QRectF(r), small)
            p.restore()


def render(base: QImage, shapes: list[Shape]) -> QImage:
    """The picture with its shapes, as saved."""
    out = base.convertToFormat(QImage.Format.Format_ARGB32)
    out.setDevicePixelRatio(1.0)
    p = QPainter(out)
    for s in shapes:
        paint_shape(p, s, base)
    p.end()
    return out


def hit(s: Shape, pt: QPointF, slack: float = 6) -> bool:
    if s.kind in ("line", "arrow"):
        a, b = s.pts[0], s.pts[-1]
        ab = b - a
        length2 = ab.x() ** 2 + ab.y() ** 2
        t = 0 if not length2 else max(0, min(1, ((pt - a).x() * ab.x() + (pt - a).y() * ab.y()) / length2))
        q = a + ab * t
        return math.hypot(pt.x() - q.x(), pt.y() - q.y()) <= s.width / 2 + slack
    if s.kind == "pen":
        return any(math.hypot(pt.x() - q.x(), pt.y() - q.y()) <= s.width + slack for q in s.pts)
    return s.box().adjusted(-slack, -slack, slack, slack).contains(pt)


# ---------------------------------------------------------------- the canvas
class Canvas(QWidget):
    changed = Signal()          # shapes / picture changed (for the window's title and Undo)
    selection = Signal()

    HANDLE = 8

    def __init__(self, base: QImage, parent=None):
        super().__init__(parent)
        self.base = base.convertToFormat(QImage.Format.Format_ARGB32)
        self.base.setDevicePixelRatio(1.0)
        self.shapes: list[Shape] = []
        self.selected: Shape | None = None
        self.tool = "select"
        self.zoom = 1.0
        self.style = Shape("rect")     # colour, width, fill, shadow, size for new shapes
        self.undo: list = []
        self.redo: list = []
        self.ask_text = None           # callback(initial) -> str | None (the window's dialog; tests answer)
        self._drag = None
        self._new: Shape | None = None
        self._crop: QRectF | None = None
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._resize()

    # ------------------------------------------------------------------ model
    def snapshot(self):
        self.undo.append((self.base, [s.copy() for s in self.shapes]))
        del self.undo[:-50]
        self.redo.clear()

    def _restore(self, state):
        self.base, shapes = state
        self.shapes = [s.copy() for s in shapes]
        self.selected = None
        self._resize()
        self.changed.emit()
        self.selection.emit()
        self.update()

    def do_undo(self):
        if self.undo:
            self.redo.append((self.base, [s.copy() for s in self.shapes]))
            self._restore(self.undo.pop())

    def do_redo(self):
        if self.redo:
            self.undo.append((self.base, [s.copy() for s in self.shapes]))
            self._restore(self.redo.pop())

    def add(self, s: Shape):
        self.snapshot()
        self.shapes.append(s)
        self.selected = s
        self.changed.emit()
        self.selection.emit()
        self.update()

    def delete_selected(self):
        if self.selected in self.shapes:
            self.snapshot()
            self.shapes.remove(self.selected)
            self.selected = None
            self.changed.emit()
            self.selection.emit()
            self.update()

    def restyle(self, **changes):
        """Colour / width / fill / shadow / size: for new shapes, and the selected one."""
        for k, v in changes.items():
            setattr(self.style, k, v)
        if self.selected:
            self.snapshot()
            for k, v in changes.items():
                setattr(self.selected, k, v)
            self.changed.emit()
            self.update()

    def crop_to(self, r: QRect):
        r = r.normalized().intersected(self.base.rect())
        if r.width() < 2 or r.height() < 2:
            return
        self.snapshot()
        self.base = self.base.copy(r)
        for s in self.shapes:
            s.move(QPointF(-r.x(), -r.y()))
        self._resize()
        self.changed.emit()
        self.update()

    def canvas_size(self, left: int, top: int, right: int, bottom: int, colour: QColor = QColor("#FFFFFF")):
        """Image > Canvas size: add (or, negative, take away) a border on each side."""
        w, h = self.base.width() + left + right, self.base.height() + top + bottom
        if w < 1 or h < 1:
            return
        self.snapshot()
        out = QImage(w, h, QImage.Format.Format_ARGB32)
        out.fill(colour)
        p = QPainter(out); p.drawImage(left, top, self.base); p.end()
        self.base = out
        for s in self.shapes:
            s.move(QPointF(left, top))
        self._resize()
        self.changed.emit()
        self.update()

    def next_step(self) -> int:
        return max([s.number for s in self.shapes if s.kind == "step"], default=0) + 1

    def image(self) -> QImage:
        return render(self.base, self.shapes)

    # ------------------------------------------------------------------ view
    def set_zoom(self, z: float):
        self.zoom = min(max(z, 0.1), 8.0)
        self._resize()
        self.update()

    def _resize(self):
        self.setFixedSize(int(self.base.width() * self.zoom) + 2 * 24, int(self.base.height() * self.zoom) + 2 * 24)

    def to_image(self, pos) -> QPointF:
        return QPointF((pos.x() - 24) / self.zoom, (pos.y() - 24) / self.zoom)

    def handles(self, s: Shape) -> list[tuple[int, QPointF]]:
        """(point index, where) for the handles that change a shape's shape."""
        if s.kind in ("line", "arrow"):
            return [(0, s.pts[0]), (1, s.pts[-1])]
        if s.kind in BOXES:
            out = [(0, s.pts[0]), (1, s.pts[1])]
            if s.kind == "bubble" and len(s.pts) > 2:
                out.append((2, s.pts[2]))
            return out
        return []

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(theme.PANEL if theme.FINISH == "obsidian" else "#D9D4D6"))
        p.translate(24, 24)
        p.scale(self.zoom, self.zoom)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, self.zoom < 2)
        p.fillRect(QRectF(0, 0, self.base.width(), self.base.height()).translated(0, 4 / self.zoom),
                   QColor(0, 0, 0, 120 if theme.FINISH == "obsidian" else 40))
        p.drawImage(0, 0, self.base)
        for s in self.shapes:
            paint_shape(p, s, self.base)
        if self._new:
            paint_shape(p, self._new, self.base)
        if self._crop is not None:
            self._paint_crop(p, self._crop)
        if self.selected in self.shapes:
            self._paint_selected(p, self.selected)

    def _paint_selected(self, p: QPainter, s: Shape):
        p.save()
        r = s.box().adjusted(-5, -5, 5, 5)
        p.setPen(QPen(QColor(theme.ACCENT), 1 / self.zoom, Qt.PenStyle.DashLine))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(r)
        h = self.HANDLE / self.zoom
        p.setPen(QPen(QColor(theme.ACCENT), 1 / self.zoom))
        p.setBrush(QColor("#FFFFFF"))
        for _, pt in self.handles(s):
            p.drawRect(QRectF(pt.x() - h / 2, pt.y() - h / 2, h, h))
        p.restore()

    def _paint_crop(self, p: QPainter, r: QRectF):
        shade = QColor(0, 0, 0, 140)
        full = QRectF(0, 0, self.base.width(), self.base.height())
        r = r.normalized()
        for part in (QRectF(0, 0, full.width(), r.top()), QRectF(0, r.bottom(), full.width(), full.height() - r.bottom()),
                     QRectF(0, r.top(), r.left(), r.height()), QRectF(r.right(), r.top(), full.width() - r.right(), r.height())):
            if part.width() > 0 and part.height() > 0:
                p.fillRect(part, shade)
        p.setPen(QPen(theme.family_gradient(r.left(), 0, r.right(), 0), 2 / self.zoom))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(r)

    # ------------------------------------------------------------------ mouse
    def shape_at(self, pt: QPointF) -> Shape | None:
        for s in reversed(self.shapes):
            if hit(s, pt):
                return s
        return None

    def handle_at(self, pt: QPointF) -> int | None:
        if not self.selected:
            return None
        h = self.HANDLE / self.zoom
        for i, q in self.handles(self.selected):
            if abs(pt.x() - q.x()) <= h and abs(pt.y() - q.y()) <= h:
                return i
        return None

    def _style(self, kind: str) -> Shape:
        st = self.style
        return Shape(kind, colour=st.colour, width=st.width, fill=st.fill, shadow=st.shadow, size=st.size)

    def mousePressEvent(self, e):
        self.setFocus()
        if e.button() != Qt.MouseButton.LeftButton:
            return
        pt = self.to_image(e.position())
        if self.tool == "crop":
            self._crop = QRectF(pt, pt)
            return
        if self.tool == "select" or (self.selected and self.handle_at(pt) is not None):
            i = self.handle_at(pt)
            if i is not None:
                self.snapshot()
                self._drag = ("handle", i)
                return
            s = self.shape_at(pt)
            self.selected = s
            self.selection.emit()
            if s:
                self.snapshot()
                self._drag = ("move", pt)
            self.update()
            return
        kind = self.tool
        if kind in ("text", "step"):
            return                       # made on release (a click)
        s = self._style(kind)
        s.pts = [pt, QPointF(pt)]
        if kind == "bubble":
            s.pts.append(QPointF(pt))
        self._new = s

    def mouseMoveEvent(self, e):
        pt = self.to_image(e.position())
        if self._crop is not None:
            self._crop.setBottomRight(pt)
            self.update()
            return
        if self._new is not None:
            s = self._new
            if s.kind == "pen":
                s.pts.append(pt)
            else:
                s.pts[1] = pt
                if s.kind == "bubble":
                    r = s.box()
                    s.pts[2] = QPointF(r.left() + 18, r.bottom() + 26)
            self.update()
            return
        if self._drag and self.selected:
            if self._drag[0] == "move":
                d = pt - self._drag[1]
                self.selected.move(d)
                self._drag = ("move", pt)
            else:
                self.selected.pts[self._drag[1]] = pt
            self.update()
            return
        over = self.handle_at(pt) is not None
        self.setCursor(Qt.CursorShape.SizeAllCursor if over or (self.tool == "select" and self.shape_at(pt))
                       else Qt.CursorShape.ArrowCursor if self.tool == "select" else Qt.CursorShape.CrossCursor)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        pt = self.to_image(e.position())
        if self._crop is not None:
            r = self._crop.normalized().toAlignedRect()
            self._crop = None
            self.crop_to(r)
            return
        if self._drag:
            moved = True
            self._drag = None
            if moved:
                self.changed.emit()
            return
        if self.tool == "text":
            text = self.ask_text("") if self.ask_text else None
            if text:
                s = self._style("text"); s.pts = [pt]; s.text = text
                self.add(s)
            return
        if self.tool == "step":
            s = self._style("step"); s.pts = [pt]; s.number = self.next_step()
            self.add(s)
            return
        s, self._new = self._new, None
        if s is None:
            return
        big = s.box().width() > 3 or s.box().height() > 3 or (s.kind == "pen" and len(s.pts) > 2)
        if not big:
            self.update()
            return
        if s.kind == "bubble":
            s.text = (self.ask_text("") if self.ask_text else "") or ""
        self.add(s)

    def mouseDoubleClickEvent(self, e):
        s = self.shape_at(self.to_image(e.position()))
        if s and s.kind in ("text", "bubble") and self.ask_text:
            text = self.ask_text(s.text)
            if text is not None:
                self.snapshot()
                s.text = text
                self.changed.emit()
                self.update()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and self.selected:
            self.delete_selected()
        elif self.selected and e.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            step = 10 if e.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
            d = {Qt.Key.Key_Left: QPointF(-step, 0), Qt.Key.Key_Right: QPointF(step, 0),
                 Qt.Key.Key_Up: QPointF(0, -step), Qt.Key.Key_Down: QPointF(0, step)}[e.key()]
            self.snapshot()
            self.selected.move(d)
            self.changed.emit()
            self.update()
        else:
            super().keyPressEvent(e)

    def wheelEvent(self, e):
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.set_zoom(self.zoom * (1.25 if e.angleDelta().y() > 0 else 0.8))
            self.parent_window().sync() if self.parent_window() else None
        else:
            super().wheelEvent(e)

    def parent_window(self):
        w = self.window()
        return w if isinstance(w, EditorWindow) else None


# ---------------------------------------------------------------- the window
EXTRA = """
QLabel#prop {{ color: {dim}; font-weight: 600; font-size: 11px; }}
QWidget#status {{ background: {bg}; border-top: 1px solid {edge}; }}
QLabel#stat {{ color: {dim}; font-size: 12px; }}
QWidget#tools {{ background: {bg}; border-right: 1px solid {edge}; }}
"""


class Swatch(QFrame):
    clicked = Signal(str)

    def __init__(self, colour: str):
        super().__init__()
        self.colour = colour
        self.on = False
        self.setFixedSize(22, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(colour)
        self.restyle()

    def restyle(self):
        border = "2px solid #FFFFFF" if self.on else f"1px solid {theme.PANEL_EDGE}"
        self.setStyleSheet(f"background: {self.colour}; border: {border}; border-radius: 4px;")

    def mouseReleaseEvent(self, e):
        self.clicked.emit(self.colour)


class EditorWindow(QMainWindow):
    closed = Signal()

    def __init__(self, img: QImage, title: str = "", parent=None):
        super().__init__(parent)
        self.answers: dict = {}
        self.capture_title = title
        self.path: str | None = None
        self.saved_state = 0
        self.setWindowTitle("Paragon PR7-Q")
        self.resize(1180, 780)
        self.canvas = Canvas(img)
        self.canvas.ask_text = lambda initial: self._ask("text", initial)
        self.canvas.changed.connect(self.sync)
        self.canvas.selection.connect(self._selected)
        self.canvas.style.colour = settings.get("colour", SWATCHES[0])
        self.canvas.style.width = settings.get_int("line_width", 3)
        self.canvas.style.shadow = settings.get_bool("shadow", True)
        self._build()
        self.set_tool("select")
        self.sync()

    # ------------------------------------------------------------------ building
    def _key(self, icon, tip, slot, checkable=False):
        k = widgets.SmallKey(icon, tip, checkable)
        k.clicked.connect(slot)
        return k

    def _build(self):
        self.acts: dict[str, QAction] = {}
        mb = self.menuBar()
        f = mb.addMenu("&File")
        self._act(f, "&Save", self.save, "Ctrl+S", "save")
        self._act(f, "Save &as...", self.save_as, "Ctrl+Shift+S", "save_as")
        self._act(f, "&Copy to clipboard", self.copy, "Ctrl+Shift+C", "copy")
        self._act(f, "&Print...", self.print_, "Ctrl+P", "print")
        self._act(f, "Open in PR7-&P", self.open_pr7p, None, "pr7p")
        f.addSeparator()
        self._act(f, "&Close", self.close, "Ctrl+W", "close")
        e = mb.addMenu("&Edit")
        self._act(e, "&Undo", self.canvas.do_undo, "Ctrl+Z", "undo")
        self._act(e, "&Redo", self.canvas.do_redo, ["Ctrl+Y", "Ctrl+Shift+Z"], "redo")
        e.addSeparator()
        self._act(e, "&Delete", self.canvas.delete_selected, None, "delete")
        o = mb.addMenu("&Object")
        g = QActionGroup(self)
        for name, label, key in TOOLS:
            a = self._act(o, label, lambda _=False, n=name: self.set_tool(n), key, f"tool_{name}", checkable=True)
            g.addAction(a)
        o.addSeparator()
        self._act(o, "Bring to &front", lambda: self._order(True), "Home", "front")
        self._act(o, "Send to &back", lambda: self._order(False), "End", "back")
        im = mb.addMenu("&Image")
        self._act(im, "&Canvas size...", self.canvas_dialog, None, "canvas")
        h = mb.addMenu("&Help")
        self._act(h, "&Keyboard shortcuts", self.shortcuts, "F1", "shortcuts")

        central = QWidget()
        col = QVBoxLayout(central)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        self.header = widgets.Header("SCREENSHOTS")
        col.addWidget(self.header)
        bar = QWidget()
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(4)

        def gap():
            line = QFrame(); line.setFixedSize(1, 22); line.setObjectName("gap")
            line.setStyleSheet(f"background: {theme.PANEL_EDGE};")
            lay.addSpacing(6); lay.addWidget(line); lay.addSpacing(6)

        for icon, tip, slot in (("save", "Save (Ctrl+S)", self.save), ("copy", "Copy to clipboard (Ctrl+Shift+C)", self.copy),
                                ("print", "Print (Ctrl+P)", self.print_), ("open", "Open in PR7-P", self.open_pr7p)):
            lay.addWidget(self._key(icon, tip, slot))
        gap()
        self.k_undo = self._key("undo", "Undo (Ctrl+Z)", self.canvas.do_undo); lay.addWidget(self.k_undo)
        self.k_redo = self._key("redo", "Redo (Ctrl+Y)", self.canvas.do_redo); lay.addWidget(self.k_redo)
        gap()
        lab = QLabel("LINE"); lab.setObjectName("prop"); lay.addWidget(lab); lay.addSpacing(4)
        self.width_box = QComboBox()
        for w in (1, 2, 3, 5, 8, 12):
            self.width_box.addItem(f"{w} px", w)
        self.width_box.setFixedWidth(80)
        self.width_box.setCurrentIndex(max(0, self.width_box.findData(self.canvas.style.width)))
        self.width_box.activated.connect(lambda i: self._style(width=self.width_box.itemData(i)))
        lay.addWidget(self.width_box); lay.addSpacing(10)
        lab = QLabel("COLOUR"); lab.setObjectName("prop"); lay.addWidget(lab); lay.addSpacing(4)
        self.swatches = []
        for c in SWATCHES:
            s = Swatch(c)
            s.clicked.connect(lambda col: self._style(colour=col))
            lay.addWidget(s)
            self.swatches.append(s)
        more = QLabel("<a href='#' style='color: %s; text-decoration: none'>OTHER</a>" % theme.TEXT_DIM)
        more.setObjectName("prop")
        more.linkActivated.connect(lambda _l: self._other_colour())
        lay.addSpacing(4); lay.addWidget(more); lay.addSpacing(10)
        lab = QLabel("FILL"); lab.setObjectName("prop"); lay.addWidget(lab); lay.addSpacing(4)
        self.fill_box = QComboBox()
        for text, val in (("None", ""), ("White", "white"), ("Colour", "colour")):
            self.fill_box.addItem(text, val)
        self.fill_box.setFixedWidth(96)
        self.fill_box.activated.connect(lambda i: self._style(fill=self.fill_box.itemData(i)))
        lay.addWidget(self.fill_box); lay.addSpacing(10)
        lab = QLabel("SIZE"); lab.setObjectName("prop"); lay.addWidget(lab); lay.addSpacing(4)
        self.size_box = QSpinBox(); self.size_box.setRange(8, 96); self.size_box.setValue(self.canvas.style.size)
        self.size_box.setFixedWidth(64)
        self.size_box.editingFinished.connect(lambda: self._style(size=self.size_box.value()))
        lay.addWidget(self.size_box); lay.addSpacing(10)
        self.shadow_box = QCheckBox("Shadow"); self.shadow_box.setChecked(self.canvas.style.shadow)
        self.shadow_box.toggled.connect(lambda on: self._style(shadow=on))
        lay.addWidget(self.shadow_box)
        lay.addStretch(1)
        self.zoom_box = QComboBox()
        for z in (25, 50, 75, 100, 150, 200, 400):
            self.zoom_box.addItem(f"{z}%", z / 100)
        self.zoom_box.setFixedWidth(84)
        self.zoom_box.activated.connect(lambda i: self.set_zoom(self.zoom_box.itemData(i)))
        lay.addWidget(self.zoom_box)
        col.addWidget(bar)

        mid = QHBoxLayout()
        mid.setSpacing(0)
        tools = QWidget(); tools.setObjectName("tools")
        tl = QVBoxLayout(tools)
        tl.setContentsMargins(8, 10, 8, 10)
        tl.setSpacing(4)
        self.tool_keys = {}
        for name, label, key in TOOLS:
            k = self._key(name if name != "select" else "select", f"{label} ({key})",
                          lambda _=False, n=name: self.set_tool(n), True)
            tl.addWidget(k)
            self.tool_keys[name] = k
        tl.addStretch(1)
        mid.addWidget(tools)
        self.scroll = QScrollArea()
        self.scroll.setWidget(self.canvas)
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        mid.addWidget(self.scroll, 1)
        col.addLayout(mid, 1)
        st = QWidget(); st.setObjectName("status")
        sl = QHBoxLayout(st); sl.setContentsMargins(14, 4, 14, 6); sl.setSpacing(26)
        self.stat = []
        for _ in range(4):
            lab = QLabel(""); lab.setObjectName("stat"); sl.addWidget(lab); self.stat.append(lab)
        sl.addStretch(1)
        self.stat_name = QLabel(""); self.stat_name.setObjectName("stat"); sl.addWidget(self.stat_name)
        col.addWidget(st)
        self.setCentralWidget(central)
        self.setStyleSheet(EXTRA.format(dim=theme.TEXT_DIM, bg=theme.BACKGROUND, edge=theme.PANEL_EDGE))
        fit = min(1.0, 1000 / max(1, self.canvas.base.width()), 560 / max(1, self.canvas.base.height()))
        self.set_zoom(fit)

    def _act(self, menu, text, slot, shortcut, key, checkable=False):
        a = QAction(text, self)
        if shortcut:
            a.setShortcuts([QKeySequence(s) for s in (shortcut if isinstance(shortcut, list) else [shortcut])])
        a.setCheckable(checkable)
        a.triggered.connect(slot)
        menu.addAction(a)
        self.acts[key] = a
        return a

    # ------------------------------------------------------------------ asking
    def _ask(self, kind, *args):
        if kind in self.answers:
            a = self.answers[kind]
            return a(*args) if callable(a) else a
        if kind == "text":
            text, ok = QInputDialog.getMultiLineText(self, "Text", "Text:", args[0])
            return text if ok else None
        if kind == "save_as":
            path, _ = QFileDialog.getSaveFileName(self, "Save As", args[0], "PNG (*.png);;JPEG (*.jpg);;BMP (*.bmp)")
            return path or None
        if kind == "save_changes":
            b = QMessageBox.question(self, "Paragon PR7-Q", "The screenshot hasn't been saved. Save it?",
                                     QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard |
                                     QMessageBox.StandardButton.Cancel)
            return {QMessageBox.StandardButton.Save: "save", QMessageBox.StandardButton.Discard: "discard"}.get(b, "cancel")
        if kind == "canvas":
            v, ok = QInputDialog.getInt(self, "Canvas Size", "Add a border on every side (pixels, negative to take "
                                        "away):", 20, -2000, 2000)
            return v if ok else None
        if kind == "error":
            QMessageBox.warning(self, "Paragon PR7-Q", args[0])
        return None

    # ------------------------------------------------------------------ tools and style
    def set_tool(self, name: str):
        self.canvas.tool = name
        if name != "select":
            self.canvas.selected = None
            self.canvas.update()
        for n, k in self.tool_keys.items():
            k.setChecked(n == name)
        self.acts[f"tool_{name}"].setChecked(True)
        self.canvas.setCursor(Qt.CursorShape.ArrowCursor if name == "select" else Qt.CursorShape.CrossCursor)
        self.canvas.setFocus()

    def _style(self, **changes):
        self.canvas.restyle(**changes)
        for k, v in changes.items():
            if k == "colour":
                settings.set("colour", v)
            elif k == "width":
                settings.set("line_width", v)
            elif k == "shadow":
                settings.set("shadow", v)
        self._show_style()

    def _other_colour(self):
        c = QColorDialog.getColor(QColor(self.canvas.style.colour), self, "Colour")
        if c.isValid():
            self._style(colour=c.name())

    def _selected(self):
        s = self.canvas.selected
        if s:
            st = self.canvas.style
            st.colour, st.width, st.fill, st.shadow, st.size = s.colour, s.width, s.fill, s.shadow, s.size
        self._show_style()

    def _show_style(self):
        st = self.canvas.style
        for sw in self.swatches:
            sw.on = sw.colour.lower() == st.colour.lower()
            sw.restyle()
        self.width_box.setCurrentIndex(max(0, self.width_box.findData(st.width)))
        self.fill_box.setCurrentIndex(max(0, self.fill_box.findData(st.fill)))
        self.size_box.setValue(st.size)
        self.shadow_box.blockSignals(True); self.shadow_box.setChecked(st.shadow); self.shadow_box.blockSignals(False)

    def _order(self, front: bool):
        s = self.canvas.selected
        if s in self.canvas.shapes:
            self.canvas.snapshot()
            self.canvas.shapes.remove(s)
            self.canvas.shapes.insert(len(self.canvas.shapes) if front else 0, s)
            self.canvas.changed.emit()
            self.canvas.update()

    def set_zoom(self, z: float):
        self.canvas.set_zoom(z)
        self.sync()

    def canvas_dialog(self):
        v = self._ask("canvas")
        if v:
            self.canvas.canvas_size(v, v, v, v)

    # ------------------------------------------------------------------ saving
    @property
    def modified(self) -> bool:
        return len(self.canvas.undo) != self.saved_state or self.path is None

    def save(self) -> bool:
        """Ctrl+S: the first time into the screenshots folder by the name pattern, then over the same file."""
        img = self.canvas.image()
        try:
            if self.path:
                output.save(img, self.path, settings.get_int("jpeg_quality", 90))
            else:
                self.path = output.save_directly(img, settings.get("folder", output.default_folder()),
                                                 settings.get("pattern", output.DEFAULT_PATTERN),
                                                 settings.get("format", "png"), settings.get_int("jpeg_quality", 90),
                                                 self.capture_title)
        except OSError as e:
            self._ask("error", f"Couldn't save the screenshot:\n{e}")
            return False
        self.saved_state = len(self.canvas.undo)
        self.sync()
        return True

    def save_as(self) -> bool:
        start = self.path or os.path.join(settings.get("folder", output.default_folder()),
                                          output.file_name(settings.get("pattern", output.DEFAULT_PATTERN),
                                                           self.capture_title) + "." + settings.get("format", "png"))
        target = self._ask("save_as", start)
        if not target:
            return False
        if not os.path.splitext(target)[1]:
            target += ".png"
        try:
            output.save(self.canvas.image(), target, settings.get_int("jpeg_quality", 90))
        except OSError as e:
            self._ask("error", f"Couldn't save {os.path.basename(target)}:\n{e}")
            return False
        self.path = target
        self.saved_state = len(self.canvas.undo)
        self.sync()
        return True

    def copy(self):
        output.copy(self.canvas.image())
        self.stat[3].setText("Copied to the clipboard")

    def print_(self):
        from PySide6.QtPrintSupport import QPrintDialog, QPrinter
        printer = self.answers.get("print")
        if printer is None:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            if QPrintDialog(printer, self).exec() != QDialog.DialogCode.Accepted:
                return
        output.print_image(self.canvas.image(), printer)

    def open_pr7p(self):
        if (self.modified or not self.path) and not self.save():
            return
        output.open_in_pr7p(self.path, self.answers.get("launch"))

    # ------------------------------------------------------------------ the window follows
    def sync(self):
        c = self.canvas
        self.k_undo.setEnabled(bool(c.undo))
        self.k_redo.setEnabled(bool(c.redo))
        self.acts["undo"].setEnabled(bool(c.undo))
        self.acts["redo"].setEnabled(bool(c.redo))
        name = os.path.basename(self.path) if self.path else ""
        self.setWindowTitle(f"{name or 'Screenshot'}{' *' if self.modified and self.path else ''} - Paragon PR7-Q")
        self.stat[0].setText(f"{c.base.width()} x {c.base.height()}")
        self.stat[1].setText(f"{c.zoom * 100:.0f} %")
        self.stat[2].setText(f"{len(c.shapes)} object{'s' if len(c.shapes) != 1 else ''}")
        self.stat[3].setText("Not saved yet" if not self.path else ("Changed" if self.modified else "Saved"))
        self.stat_name.setText(name)
        i = self.zoom_box.findData(round(c.zoom, 2))
        self.zoom_box.setCurrentIndex(i) if i >= 0 else self.zoom_box.setEditText(f"{c.zoom * 100:.0f}%")

    def shortcuts(self):
        QMessageBox.information(self, "Keyboard Shortcuts", "\n".join(
            [f"{label}: {key}" for _, label, key in TOOLS] +
            ["Delete the selected object: Del", "Move it: arrow keys (Shift: 10 px)", "Undo / redo: Ctrl+Z / Ctrl+Y",
             "Save / save as: Ctrl+S / Ctrl+Shift+S", "Copy: Ctrl+Shift+C", "Zoom: Ctrl+wheel"]))

    def closeEvent(self, e):
        if self.modified:              # never saved, or changed since: Greenshot asks too
            answer = self._ask("save_changes")
            if answer == "cancel" or (answer == "save" and not self.save()):
                e.ignore()
                return
        self.closed.emit()
        super().closeEvent(e)
