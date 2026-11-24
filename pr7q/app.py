"""Start PR7-Q.

    PR7-Q.exe                     run in the notification area (the keys work from any program); started again, it
                                  tells the running PR7-Q to capture a region instead of starting twice
    PR7-Q.exe --region | --window | --full | --last-region    that capture (in the running PR7-Q, else a new one)
    PR7-Q.exe --tray              start quietly (Windows' start-up entry)
    PR7-Q.exe --startup on|off    start with Windows or not (the installer's task)
    PR7-Q.exe --unregister        take the start-up entry away (the uninstaller)
    PR7-Q.exe --version
    PR7-Q.exe --selftest OUT.json capture, annotate and save on a stand-in desktop offscreen, and write what came out
                                  (CI checks the installed program with it)
"""

from __future__ import annotations

import getpass
import hashlib
import json
import os
import sys

TIMEOUT_MS = 1500
COMMANDS = {"--region": "region", "--window": "window", "--full": "full", "--last-region": "last_region"}


def server_name() -> str:
    try:
        user = getpass.getuser()
    except Exception:  # noqa: BLE001
        user = "user"
    return "Paragon-PR7-Q-" + hashlib.sha1(user.encode()).hexdigest()[:12]


def hand_over(command: str) -> bool:
    """If PR7-Q is running, ask it for a capture ("region", ...) or "" for nothing; True if it was there."""
    from PySide6.QtNetwork import QLocalSocket
    s = QLocalSocket()
    s.connectToServer(server_name())
    if not s.waitForConnected(TIMEOUT_MS):
        return False
    s.write(json.dumps({"capture": command}).encode() + b"\n")
    s.flush()
    s.waitForBytesWritten(TIMEOUT_MS)
    if not s.waitForDisconnected(TIMEOUT_MS):
        s.disconnectFromServer()
    return True


def listen(tray):
    """Take capture requests from later launches (PR7-R's hand-off, with its Windows fix)."""
    from PySide6.QtNetwork import QLocalServer
    server = QLocalServer(tray)
    QLocalServer.removeServer(server_name())
    if not server.listen(server_name()):
        return None

    def connection():
        sock = server.nextPendingConnection()
        if sock is None:
            return
        buf = bytearray()
        done = []

        def read():
            buf.extend(bytes(sock.readAll()))
            if buf.endswith(b"\n") and not done:
                done.append(True)
                try:
                    msg = json.loads(buf.decode())
                except ValueError:
                    return
                if msg.get("capture"):
                    tray.start(msg["capture"])
                sock.disconnectFromServer()
        sock.readyRead.connect(read)
        sock.disconnected.connect(read)
        if sock.bytesAvailable():
            read()
    server.newConnection.connect(connection)
    tray.instance_server = server
    return server


def selftest(out: str) -> int:
    """The whole path on a stand-in desktop: a full-screen and a region capture saved directly, then the editor with
    a rectangle, an arrow, a step number and a pixelated area, saved as PNG and JPEG; what was written is reported."""
    import tempfile
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtCore import QPoint, QPointF, QRect, QSettings
    from PySide6.QtGui import QColor, QFontDatabase, QImage
    from PySide6.QtWidgets import QApplication
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, tempfile.mkdtemp())
    result = {}
    try:
        from . import __version__, capture, settings, theme
        from .editor import Shape
        from .tray import TrayApp
        app = QApplication.instance() or QApplication(sys.argv[:1])
        theme.load_fonts()
        folder = tempfile.mkdtemp()
        settings.set("folder", folder)
        settings.set("after", "save")
        img = QImage(1600, 1000, QImage.Format.Format_RGB32)
        img.fill(QColor("#204060"))
        desk = capture.Desktop(img, QRect(0, 0, 800, 500), 2.0, QPoint(100, 100))
        tray = TrayApp(grabber=lambda: desk, window_at=None, show_tray=False)
        tray.capture("full")
        full = QImage(tray.last_saved)
        tray.finish(desk, QRect(100, 50, 200, 100), "region")
        region = QImage(tray.last_saved)
        ed = tray.open_editor(region)
        rect = Shape("rect", [QPointF(20, 20), QPointF(200, 120)], colour="#E0202A", width=6, shadow=False)
        ed.canvas.add(rect)
        ed.canvas.add(Shape("step", [QPointF(300, 150)], number=1, shadow=False))
        ed.canvas.add(Shape("obfuscate", [QPointF(250, 20), QPointF(390, 90)]))
        png = os.path.join(folder, "edited.png")
        ed.answers["save_as"] = png
        ed.save_as()
        edited = QImage(png)
        settings.set("format", "jpg")
        ed2 = tray.open_editor(region)
        ed2.save()
        result = {"version": __version__, "full": [full.width(), full.height()],
                  "region": [region.width(), region.height()],
                  "edited": [edited.width(), edited.height()],
                  "red_border": edited.pixelColor(20, 60).red() > 180,
                  "jpeg": os.path.basename(ed2.path or ""), "jpeg_ok": not QImage(ed2.path or "").isNull(),
                  "files": sorted(os.listdir(folder)), "fonts": "Inter" in QFontDatabase.families()}
        for e in list(tray.editors):
            e.answers["save_changes"] = "discard"
            e.close()
    except Exception as e:  # noqa: BLE001 - reported in the output
        result = {"error": f"{type(e).__name__}: {e}"}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh)
    return 0 if "edited" in result else 1


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["--version"]:
        from . import __version__
        print(__version__)
        return 0
    if argv[:1] == ["--selftest"] and len(argv) == 2:
        return selftest(argv[1])
    if argv[:1] == ["--startup"] and len(argv) == 2:
        from .tray import start_with_windows
        start_with_windows(argv[1].lower() in ("on", "1", "yes"))
        return 0
    if argv[:1] == ["--unregister"]:
        from .tray import start_with_windows
        start_with_windows(False)
        return 0
    command = next((COMMANDS[a] for a in argv if a in COMMANDS), "")
    quiet = "--tray" in argv
    from PySide6.QtWidgets import QApplication

    from . import settings, theme
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setOrganizationName("Paragon")
    app.setApplicationName("PR7-Q")
    app.setQuitOnLastWindowClosed(False)          # it lives in the notification area
    if hand_over(command or ("" if quiet else "region")):
        return 0
    theme.set_finish(settings.get("finish", "obsidian"))
    theme.load_fonts()
    app.setPalette(theme.palette())
    app.setStyleSheet(theme.stylesheet())
    from PySide6.QtGui import QIcon
    icon = os.path.join(os.path.dirname(__file__), "icons", "app.ico")
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))
    from .tray import TrayApp
    tray = TrayApp()
    listen(tray)
    if command:
        tray.start(command)
    elif not quiet and tray.tray:
        keys = tray.keys()
        tray.tray.showMessage("PR7-Q is running", f"{keys['region']}: capture a region. Its menu is here in the "
                              "notification area.", tray.tray.MessageIcon.Information, 5000)
    from . import update_ui
    update_ui.start(tray.anchor)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
