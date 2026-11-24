"""Where a capture goes (no window of its own): the file name from a pattern, saving (PNG / JPEG / BMP), the
clipboard, printing, and opening in PR7-P (or the picture's default program when PR7-P isn't installed)."""

from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

from PySide6.QtGui import QGuiApplication, QImage, QImageWriter

FORMATS = ["png", "jpg", "bmp"]
DEFAULT_PATTERN = "Screenshot %Y-%m-%d %H.%M.%S"
BAD = '\\/:*?"<>|'


def default_folder() -> str:
    """Pictures\\Screenshots, as Windows' own screenshots use."""
    pics = None
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            FOLDERID_Pictures = "{33E28130-4E1E-4676-835A-98395C3BC3BB}"

            class GUID(ctypes.Structure):
                _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                            ("Data4", ctypes.c_ubyte * 8)]
            guid = GUID()
            ctypes.windll.ole32.CLSIDFromString(FOLDERID_Pictures, ctypes.byref(guid))
            out = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(out)) == 0:
                pics = out.value
                ctypes.windll.ole32.CoTaskMemFree(out)
        except Exception:  # noqa: BLE001 - fall back to the home folder's Pictures
            pics = None
    return os.path.join(pics or os.path.join(Path.home(), "Pictures"), "Screenshots")


def file_name(pattern: str, title: str = "", when: float | None = None) -> str:
    """The pattern with the date and time (strftime: %Y %m %d %H %M %S) and {title} (the captured window's title)
    filled in, made safe for Windows."""
    t = time.localtime(when if when is not None else time.time())
    try:
        name = time.strftime(pattern or DEFAULT_PATTERN, t)
    except ValueError:
        name = time.strftime(DEFAULT_PATTERN, t)
    name = name.replace("{title}", title or "")
    name = "".join("_" if c in BAD or ord(c) < 32 else c for c in name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name or time.strftime(DEFAULT_PATTERN, t)


def free_path(folder: str, name: str, ext: str) -> str:
    """folder/name.ext, or "name (2).ext" ... the first that isn't taken: never overwrites a capture."""
    candidate = os.path.join(folder, f"{name}.{ext}")
    n = 2
    while os.path.exists(candidate):
        candidate = os.path.join(folder, f"{name} ({n}).{ext}")
        n += 1
    return candidate


def save(img: QImage, path: str, quality: int = 90) -> str:
    """Write the picture (format from the extension); the folder is made if needed. Returns the path."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    ext = os.path.splitext(path)[1][1:].lower() or "png"
    fmt = {"jpg": "jpeg", "jpeg": "jpeg", "bmp": "bmp"}.get(ext, "png")
    from PySide6.QtCore import QFile, QIODevice
    fh = QFile(path)                     # our own file, closed before returning (Windows locks open files)
    if not fh.open(QIODevice.OpenModeFlag.WriteOnly):
        raise OSError(fh.errorString())
    w = QImageWriter(fh, fmt.encode())
    if fmt == "jpeg":
        w.setQuality(int(quality))
        img = img.convertToFormat(QImage.Format.Format_RGB32)
    ok = w.write(img)
    err = w.errorString()
    fh.close()
    if not ok:
        os.remove(path)
        raise OSError(err)
    return path


def save_directly(img: QImage, folder: str, pattern: str, fmt: str = "png", quality: int = 90, title: str = "") -> str:
    return save(img, free_path(folder, file_name(pattern, title), fmt), quality)


def copy(img: QImage) -> None:
    QGuiApplication.clipboard().setImage(img)


def open_in_pr7p(path: str, launch=None) -> bool:
    """Open a saved capture in PR7-P; without it, in Windows' default program for pictures."""
    from . import family
    if (launch or family.launch)("PR7-P", [path]):
        return True
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
    return QDesktopServices.openUrl(QUrl.fromLocalFile(path))


def print_image(img: QImage, printer) -> None:
    """The capture fitted to the paper and centred."""
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QPainter
    from PySide6.QtPrintSupport import QPrinter
    p = QPainter()
    if not p.begin(printer):
        return
    area = printer.pageRect(QPrinter.Unit.DevicePixel)
    k = min(area.width() / img.width(), area.height() / img.height(), 1.0 * printer.resolution() / 96)
    w, h = img.width() * k, img.height() * k
    p.drawImage(QRectF((area.width() - w) / 2, (area.height() - h) / 2, w, h), img)
    p.end()
