"""Capture region: the frozen desktop shown full screen, dimmed except what's being chosen, with crosshair guides,
the size, and a magnifier (the pixels under the pointer eight times bigger, its position and colour).

Drag to choose a region; a click without dragging takes the window under the pointer; Enter takes the whole screen;
Esc or a right click cancels. The arrow keys move the pointer one pixel (Shift+arrows change the selection)."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QGuiApplication, QColor, QCursor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from . import theme
from .capture import Desktop

MAG_PIXELS, MAG_ZOOM = 15, 8


def span(a: QPoint, b: QPoint) -> QRect:
    """The box dragged from a to b: as wide as the drag (a QRect from two corners would count both end pixels)."""
    return QRect(min(a.x(), b.x()), min(a.y(), b.y()), abs(b.x() - a.x()), abs(b.y() - a.y()))


class RegionPicker(QWidget):
    picked = Signal(QRect, str)      # the region (points) and how: "region", "window", "full"
    cancelled = Signal()

    def __init__(self, desktop: Desktop, window_at=None):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint |
                         Qt.WindowType.Tool)
        self.desktop = desktop
        self.window_at = window_at          # point -> (rect, title) or None (capture.window_at on Windows)
        self.start: QPoint | None = None
        self.sel = QRect()
        self.pos_ = desktop.cursor or desktop.geometry.center()
        self.hover_window: QRect | None = None
        self.setGeometry(desktop.geometry)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def show_over_desktop(self):
        from .capture import on_wayland
        self.setGeometry(self.desktop.geometry)
        if on_wayland():                    # Wayland places windows itself: full screen covers the picked screen
            for screen in QGuiApplication.screens():
                if screen.geometry() == self.desktop.geometry:
                    self.setScreen(screen)
            self.showFullScreen()
        else:
            self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()

    # coordinates: the widget covers the desktop, so desktop point = widget point + geometry.topLeft()
    def _desk(self, p: QPoint) -> QPoint:
        return p + self.desktop.geometry.topLeft()

    def _local(self, r: QRect) -> QRect:
        return r.translated(-self.desktop.geometry.topLeft())

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        full = QRectF(self.rect())
        p.drawImage(full, self.desktop.image)
        shade = QColor(0, 0, 0, 140)
        sel = self._local(self.sel) if not self.sel.isNull() else (
            self._local(self.hover_window) if self.hover_window else QRect())
        if sel.isNull():
            p.fillRect(full, shade)
        else:
            r = QRectF(sel)
            for part in (QRectF(0, 0, full.width(), r.top()), QRectF(0, r.bottom() + 1, full.width(), full.height()),
                         QRectF(0, r.top(), r.left(), r.height()), QRectF(r.right() + 1, r.top(), full.width(), r.height())):
                if part.width() > 0 and part.height() > 0:
                    p.fillRect(part, shade)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(QPen(theme.family_gradient(r.left(), 0, r.right(), 0), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(r.adjusted(-1, -1, 1, 1))
            self._label(p, f"{sel.width()} x {sel.height()}", QPointF(r.left(), r.top() - 30 if r.top() > 34 else r.top() + 6))
        pos = self.pos_ - self.desktop.geometry.topLeft()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        p.setPen(QPen(QColor(255, 255, 255, 110), 1, Qt.PenStyle.DashLine))
        p.drawLine(pos.x(), 0, pos.x(), self.height())
        p.drawLine(0, pos.y(), self.width(), pos.y())
        self._magnifier(p, pos)

    def _label(self, p: QPainter, text: str, at: QPointF):
        f = QFont("Inter"); f.setPixelSize(12); f.setWeight(QFont.Weight.DemiBold); p.setFont(f)
        tw = p.fontMetrics().horizontalAdvance(text) + 16
        box = QRectF(at.x(), at.y(), tw, 22)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(theme.MENU)); p.drawRoundedRect(box, 4, 4)
        p.setPen(QColor(theme.ON_DARK)); p.drawText(box, Qt.AlignmentFlag.AlignCenter, text)

    def pixel_colour(self, pos: QPoint) -> QColor:
        k = self.desktop.scale
        x, y = int(pos.x() * k), int(pos.y() * k)
        img = self.desktop.image
        if 0 <= x < img.width() and 0 <= y < img.height():
            return img.pixelColor(x, y)
        return QColor("#000000")

    def _magnifier(self, p: QPainter, pos: QPoint):
        n, z = MAG_PIXELS, MAG_ZOOM
        k = self.desktop.scale
        src = self.desktop.image.copy(QRect(int(pos.x() * k) - n // 2, int(pos.y() * k) - n // 2, n, n))
        x = pos.x() + 24 if pos.x() + 24 + n * z < self.width() else pos.x() - 24 - n * z
        y = pos.y() + 24 if pos.y() + 24 + n * z + 32 < self.height() else pos.y() - 24 - n * z - 32
        mag = QRectF(x, y, n * z, n * z)
        path = QPainterPath(); path.addEllipse(mag)
        p.save()
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        p.setClipPath(path)
        p.fillRect(mag, QColor("#000000"))
        p.drawImage(mag, src)
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        for i in range(1, n):
            p.drawLine(QPointF(mag.left() + i * z, mag.top()), QPointF(mag.left() + i * z, mag.bottom()))
            p.drawLine(QPointF(mag.left(), mag.top() + i * z), QPointF(mag.right(), mag.top() + i * z))
        p.restore()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(theme.ACCENT), 2))
        p.drawRect(QRectF(mag.left() + (n // 2) * z, mag.top() + (n // 2) * z, z, z))
        p.setPen(QPen(theme.family_gradient(mag.left(), 0, mag.right(), 0), 3))
        p.drawEllipse(mag)
        d = self._desk(pos)
        self._label(p, f"{d.x()}, {d.y()}   #{self.pixel_colour(pos).name()[1:].upper()}",
                    QPointF(mag.left(), mag.bottom() + 8))

    # ------------------------------------------------------------------ mouse and keys
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.RightButton:
            self.cancel()
            return
        if e.button() == Qt.MouseButton.LeftButton:
            self.start = self._desk(e.position().toPoint())
            self.sel = QRect()

    def mouseMoveEvent(self, e):
        self.pos_ = self._desk(e.position().toPoint())
        if self.start is not None:
            self.sel = span(self.start, self.pos_)
        elif self.window_at:
            found = self.window_at(self.pos_)
            self.hover_window = found[0].intersected(self.desktop.geometry) if found else None
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton or self.start is None:
            return
        end = self._desk(e.position().toPoint())
        r = span(self.start, end)
        self.start = None
        if r.width() > 3 and r.height() > 3:
            self.finish(r, "region")
        elif self.window_at:
            found = self.window_at(end)
            if found:
                self.finish(found[0].intersected(self.desktop.geometry), "window", found[1])
            else:
                self.finish(self.desktop.geometry, "full")
        else:
            self.finish(self.desktop.geometry, "full")

    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key.Key_Escape:
            self.cancel()
            return
        if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.finish(self.sel if not self.sel.isNull() else self.desktop.geometry,
                        "region" if not self.sel.isNull() else "full")
            return
        d = {Qt.Key.Key_Left: QPoint(-1, 0), Qt.Key.Key_Right: QPoint(1, 0), Qt.Key.Key_Up: QPoint(0, -1),
             Qt.Key.Key_Down: QPoint(0, 1)}.get(k)
        if d is not None:
            if e.modifiers() & Qt.KeyboardModifier.ShiftModifier and not self.sel.isNull():
                self.sel = self.sel.adjusted(0, 0, d.x(), d.y())
            else:
                self.pos_ += d
                QCursor.setPos(self.pos_)
                if self.start is not None:
                    self.sel = span(self.start, self.pos_)
            self.update()

    def finish(self, r: QRect, how: str, title: str = ""):
        self.title = title
        self.hide()
        self.picked.emit(r, how)
        self.close()

    def cancel(self):
        self.hide()
        self.cancelled.emit()
        self.close()
