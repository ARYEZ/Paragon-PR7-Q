"""Taking the picture: every screen grabbed into one image of the whole desktop at full resolution (with Windows'
display scaling, a screen of 1280 x 720 points can be 2560 x 1440 pixels), the window under the mouse (Windows'
own idea of its frame, without the invisible resize border), and the mouse pointer drawn where it was.

`Desktop.image` is in pixels; `Desktop.geometry` is the desktop in Qt's points and `scale` pixels per point, so a
region picked on screen (points) is cut out of the image with `crop`. Tests build a Desktop from any picture."""

from __future__ import annotations

import sys
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QImage, QPainter, QPainterPath, QPen


@dataclass
class Desktop:
    image: QImage            # the whole desktop, in pixels
    geometry: QRect          # the same, in points (top left can be negative with a monitor on the left)
    scale: float = 1.0       # pixels per point
    cursor: QPoint | None = None   # where the mouse was (points)

    def to_pixels(self, r: QRect) -> QRect:
        """A rectangle on the desktop (points) as pixels in `image`."""
        k = self.scale
        x = round((r.x() - self.geometry.x()) * k)
        y = round((r.y() - self.geometry.y()) * k)
        return QRect(x, y, round(r.width() * k), round(r.height() * k)).intersected(self.image.rect())

    def crop(self, r: QRect) -> QImage:
        """The pixels of a region picked on screen (points); the whole desktop for an empty rectangle."""
        if r.isNull() or r.isEmpty():
            return self.image.copy()
        img = self.image.copy(self.to_pixels(r))
        img.setDevicePixelRatio(1.0)
        return img


def grab(include_cursor: bool = False) -> Desktop:
    """Every screen, side by side as Windows places them, in one picture."""
    screens = QGuiApplication.screens()
    virtual = QRect()
    for s in screens:
        virtual = virtual.united(s.geometry())
    k = max((s.devicePixelRatio() for s in screens), default=1.0)
    img = QImage(max(1, round(virtual.width() * k)), max(1, round(virtual.height() * k)), QImage.Format.Format_RGB32)
    img.fill(QColor("#000000"))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    for s in screens:
        g = s.geometry()
        shot = s.grabWindow(0)
        target = QRectF((g.x() - virtual.x()) * k, (g.y() - virtual.y()) * k, g.width() * k, g.height() * k)
        p.drawPixmap(target, shot, QRectF(shot.rect()))
    p.end()
    pos = QCursor.pos()
    d = Desktop(img, virtual, k, pos)
    if include_cursor:
        draw_cursor(d)
    return d


POINTER = [(0, 0), (0, 16.5), (4.2, 12.6), (7, 18.6), (9.6, 17.4), (6.9, 11.6), (12.4, 11.6)]


def draw_cursor(d: Desktop) -> None:
    """The mouse pointer where it was: a white arrow with a black edge (the standard Windows pointer's shape)."""
    if d.cursor is None or not d.geometry.contains(d.cursor):
        return
    k = d.scale
    x, y = (d.cursor.x() - d.geometry.x()) * k, (d.cursor.y() - d.geometry.y()) * k
    path = QPainterPath(QPointF(x + POINTER[0][0] * k, y + POINTER[0][1] * k))
    for px, py in POINTER[1:]:
        path.lineTo(x + px * k, y + py * k)
    path.closeSubpath()
    p = QPainter(d.image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor("#000000"), 1.2 * k, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(QColor("#FFFFFF"))
    p.drawPath(path)
    p.end()


# ---------------------------------------------------------------- the window under the mouse (Windows)
def window_at(pos: QPoint, scale: float = 1.0) -> tuple[QRect, str] | None:
    """The top-level window under a point (points): its frame as Windows draws it (DWM's extended frame bounds,
    without the invisible resize border) in points, and its title. None off Windows or over the desktop."""
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    dwmapi = ctypes.windll.dwmapi
    pt = wintypes.POINT(round(pos.x() * scale), round(pos.y() * scale))
    user32.WindowFromPoint.restype = wintypes.HWND
    user32.WindowFromPoint.argtypes = [wintypes.POINT]
    hwnd = user32.WindowFromPoint(pt)
    if not hwnd:
        return None
    user32.GetAncestor.restype = wintypes.HWND
    root = user32.GetAncestor(hwnd, 2)        # GA_ROOT
    if not root:
        return None
    cls = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(root, cls, 256)
    if cls.value in ("Progman", "WorkerW", "Shell_TrayWnd"):     # the desktop and the taskbar aren't windows
        return None
    rect = wintypes.RECT()
    DWMWA_EXTENDED_FRAME_BOUNDS = 9
    if dwmapi.DwmGetWindowAttribute(root, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(rect), ctypes.sizeof(rect)) != 0:
        user32.GetWindowRect(root, ctypes.byref(rect))
    title = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(root, title, 512)
    r = QRect(QPoint(round(rect.left / scale), round(rect.top / scale)),
              QPoint(round(rect.right / scale) - 1, round(rect.bottom / scale) - 1))
    return r, title.value


def active_monitor(d: Desktop) -> QRect:
    """The screen the mouse is on (points): Capture full screen's "current monitor" choice."""
    for s in QGuiApplication.screens():
        if d.cursor is not None and s.geometry().contains(d.cursor):
            return s.geometry()
    return d.geometry
