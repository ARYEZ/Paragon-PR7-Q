"""PR7-Q running in the notification area (Greenshot's way): the tray icon and its menu, the keys that work from any
program, each kind of capture, what happens after one (a menu, or the default from Preferences), and Preferences.

Everything that asks goes through `_ask(kind, ...)` (tests: `app.answers`); `grabber` is capture.grab (tests give a
stand-in desktop) and `window_at` is capture.window_at."""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QObject, QRect, QTimer, Signal
from PySide6.QtGui import QAction, QCursor, QIcon, QImage
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox, QPushButton, QSpinBox,
                               QSystemTrayIcon, QWidget)

from . import __version__, capture, finish, hotkeys, output, settings, theme
from .editor import EditorWindow
from .overlay import RegionPicker

AFTER = [("ask", "Ask (a menu after each capture)"), ("save", "Save directly"), ("save_as", "Save as..."),
         ("copy", "Copy to clipboard"), ("editor", "Open in image editor"), ("pr7p", "Open in PR7-P"),
         ("print", "Print...")]
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


class TrayApp(QObject):
    captured = Signal(QImage, str)        # every capture, with how it was taken (tests)

    def __init__(self, grabber=None, window_at=None, show_tray: bool = True):
        super().__init__()
        self.answers: dict = {}
        self.grabber = grabber or (lambda: capture.grab(settings.get_bool("include_cursor", False)))
        self.window_at = window_at if window_at is not None else capture.window_at
        self.editors: list[EditorWindow] = []
        self.last_region: QRect | None = None
        self.picker: RegionPicker | None = None
        self.last_saved: str | None = None
        self.anchor = QWidget()              # dialogs' parent (the updater's too) while there's no window
        self.anchor.setWindowTitle("Paragon PR7-Q")
        self.menu = self._build_menu()
        self.tray = None
        if show_tray and QSystemTrayIcon.isSystemTrayAvailable():
            icon = os.path.join(os.path.dirname(__file__), "icons", "app.ico")
            self.tray = QSystemTrayIcon(QIcon(icon), self)
            self.tray.setToolTip("Paragon PR7-Q: Print captures a region")
            self.tray.setContextMenu(self.menu)
            self.tray.activated.connect(self._tray_click)
            self.tray.show()
        self.hotkeys = hotkeys.Hotkeys()
        self.key_problems = self.register_keys()

    # ------------------------------------------------------------------ the menu and the keys
    def _build_menu(self) -> QMenu:
        m = QMenu()
        self.acts: dict[str, QAction] = {}
        keys = self.keys()
        for name, text in (("region", "Capture &region"), ("last_region", "Capture &last region"),
                           ("window", "Capture &window"), ("full", "Capture &full screen")):
            a = m.addAction(f"{text}\t{keys.get(name, '')}")
            a.triggered.connect(lambda _=False, n=name: self.start(n))
            self.acts[name] = a
        m.addSeparator()
        self.acts["clipboard"] = m.addAction("Capture from &clipboard", self.from_clipboard)
        self.acts["open"] = m.addAction("&Open image from file...", self.open_file)
        m.addSeparator()
        quick = m.addMenu("Quick &preferences")
        cur = quick.addAction("Include the mouse &pointer")
        cur.setCheckable(True)
        cur.setChecked(settings.get_bool("include_cursor", False))
        cur.toggled.connect(lambda on: settings.set("include_cursor", on))
        after = quick.addMenu("&After capture")
        for key, text in AFTER:
            a = after.addAction(text)
            a.setCheckable(True)
            a.setChecked(settings.get("after", "ask") == key)
            a.triggered.connect(lambda _=False, k=key: (settings.set("after", k), self._refresh_quick(after)))
        self.after_menu = after
        fin = m.addMenu("Finish")
        for name in ("obsidian", "aurora"):
            a = fin.addAction(name.upper(), lambda n=name: self.set_finish(n))
            a.setCheckable(True)
            a.setChecked(theme.FINISH == name)
            self.acts[f"finish_{name}"] = a
        self.acts["preferences"] = m.addAction("&Preferences...", self.preferences)
        m.addSeparator()
        m.addAction("Check for &updates...", self.check_updates)
        m.addAction("&About PR7-Q", self.about)
        m.addSeparator()
        m.addAction("E&xit", self.quit)
        return m

    def _refresh_quick(self, menu: QMenu):
        chosen = settings.get("after", "ask")
        for (key, _), a in zip(AFTER, menu.actions()):
            a.setChecked(key == chosen)

    def _tray_click(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:      # a left click: capture a region (Greenshot)
            self.start("region")

    def keys(self) -> dict[str, str]:
        return {name: settings.get(f"key_{name}", default) for name, default in hotkeys.DEFAULT_KEYS.items()}

    def register_keys(self) -> dict[str, str]:
        problems = self.hotkeys.register({name: (text, lambda n=name: self.start(n))
                                          for name, text in self.keys().items()})
        if problems and hotkeys.available() and self.tray:
            self.tray.showMessage("PR7-Q", "\n".join(dict.fromkeys(problems.values())) + "\nChoose other keys in Preferences.",
                                  QSystemTrayIcon.MessageIcon.Warning, 8000)
        return problems

    # ------------------------------------------------------------------ asking
    def _ask(self, kind, *args):
        if kind in self.answers:
            a = self.answers[kind]
            return a(*args) if callable(a) else a
        if kind == "after":
            m = QMenu()
            chosen = None
            for key, text in AFTER[1:]:
                a = m.addAction(text.replace("Save directly", "Save directly (" + os.path.basename(
                    settings.get("folder", output.default_folder())) + ")"))
                a.setData(key)
            m.addSeparator()
            m.addAction("Cancel")
            act = m.exec(QCursor.pos())
            if act is not None and act.data():
                chosen = act.data()
            return chosen
        if kind == "save_as":
            path, _ = QFileDialog.getSaveFileName(None, "Save As", args[0], "PNG (*.png);;JPEG (*.jpg);;BMP (*.bmp)")
            return path or None
        if kind == "open":
            path, _ = QFileDialog.getOpenFileName(None, "Open Image", settings.get("folder", output.default_folder()),
                                                  "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;All files (*)")
            return path or None
        if kind == "error":
            QMessageBox.warning(None, "Paragon PR7-Q", args[0])
        return None

    # ------------------------------------------------------------------ capturing
    def start(self, kind: str) -> None:
        """A capture of `kind` ("region", "last_region", "window", "full"), after the delay from Preferences."""
        delay = settings.get_int("delay", 0)
        if delay > 0:
            QTimer.singleShot(delay * 1000, lambda: self.capture(kind))
        else:
            self.capture(kind)

    def capture(self, kind: str) -> None:
        if self.picker is not None:
            return                          # a region is being chosen already
        self.menu.hide()
        QApplication.processEvents()
        desk = self.grabber()               # the screen as it was, before anything of ours shows
        if kind == "full":
            region = capture.active_monitor(desk) if settings.get("full_screen", "all") == "current" else desk.geometry
            self.finish(desk, region, "full")
        elif kind == "last_region" and self.last_region is not None:
            self.finish(desk, self.last_region, "region")
        elif kind == "window":
            found = self.window_at(desk.cursor) if desk.cursor is not None and self.window_at else None
            if found:
                self.finish(desk, found[0].intersected(desk.geometry), "window", found[1])
            else:
                self.finish(desk, desk.geometry, "full")
        else:
            self.picker = RegionPicker(desk, self.window_at)
            self.picker.picked.connect(lambda r, how: self._picked(desk, r, how))
            self.picker.cancelled.connect(self._picker_gone)
            self.picker.show_over_desktop()

    def _picked(self, desk, r: QRect, how: str):
        title = getattr(self.picker, "title", "")
        self._picker_gone()
        if how == "region":
            self.last_region = QRect(r)
        self.finish(desk, r, how, title)

    def _picker_gone(self):
        self.picker = None

    def finish(self, desk: capture.Desktop, region: QRect, how: str, title: str = "") -> None:
        img = desk.crop(region)
        self.captured.emit(img, how)
        self.deliver(img, title)

    def deliver(self, img: QImage, title: str = "") -> str | None:
        """After capture: the choice from Preferences, or ask with a menu. Returns what was done."""
        action = settings.get("after", "ask")
        if action == "ask":
            action = self._ask("after")
        if not action:
            return None
        quality = settings.get_int("jpeg_quality", 90)
        folder = settings.get("folder", output.default_folder())
        pattern = settings.get("pattern", output.DEFAULT_PATTERN)
        fmt = settings.get("format", "png")
        try:
            if action == "save":
                self.last_saved = output.save_directly(img, folder, pattern, fmt, quality, title)
                if self.tray:
                    self.tray.showMessage("PR7-Q", f"Saved {os.path.basename(self.last_saved)}",
                                          QSystemTrayIcon.MessageIcon.Information, 3000)
            elif action == "save_as":
                start = os.path.join(folder, output.file_name(pattern, title) + "." + fmt)
                target = self._ask("save_as", start)
                if not target:
                    return None
                self.last_saved = output.save(img, target if os.path.splitext(target)[1] else target + ".png", quality)
            elif action == "copy":
                output.copy(img)
            elif action == "editor":
                self.open_editor(img, title)
            elif action == "pr7p":
                self.last_saved = output.save_directly(img, folder, pattern, fmt, quality, title)
                output.open_in_pr7p(self.last_saved, self.answers.get("launch"))
            elif action == "print":
                ed = self.open_editor(img, title)
                ed.print_()
        except OSError as e:
            self._ask("error", f"Couldn't save the screenshot:\n{e}")
            return None
        return action

    def open_editor(self, img: QImage, title: str = "") -> EditorWindow:
        ed = EditorWindow(img, title)
        ed.answers = self.answers.setdefault("editor", {})
        ed.closed.connect(lambda e=ed: self.editors.remove(e) if e in self.editors else None)
        self.editors.append(ed)
        ed.show()
        ed.raise_()
        ed.activateWindow()
        return ed

    def from_clipboard(self):
        img = QApplication.clipboard().image()
        if img.isNull():
            self._ask("error", "There's no picture on the clipboard.")
            return
        self.open_editor(img, "Clipboard")

    def open_file(self):
        path = self._ask("open")
        if path:
            img = QImage(path)
            if img.isNull():
                self._ask("error", f"{os.path.basename(path)} isn't a picture PR7-Q can open.")
                return
            ed = self.open_editor(img, os.path.splitext(os.path.basename(path))[0])
            ed.path = path
            ed.saved_state = 0
            ed.sync()

    # ------------------------------------------------------------------ settings, help, quitting
    def set_finish(self, name: str):
        """OBSIDIAN or AURORA, for every open editor and (finish.py) every other family app."""
        from .editor import EXTRA
        theme.set_finish(name)
        finish.set(theme.FINISH)                 # every family app follows (finish.py)
        settings.set("finish", theme.FINISH)
        app = QApplication.instance()
        app.setPalette(theme.palette())
        app.setStyleSheet(theme.stylesheet())
        for ed in self.editors:
            ed.setStyleSheet(EXTRA.format(dim=theme.TEXT_DIM, bg=theme.BACKGROUND, edge=theme.PANEL_EDGE))
            ed.update()
        for n in ("obsidian", "aurora"):
            if f"finish_{n}" in self.acts:
                self.acts[f"finish_{n}"].setChecked(theme.FINISH == n)

    def preferences(self):
        dlg = PreferencesDialog(self)
        self.preferences_dialog = dlg
        if "preferences" in self.answers or dlg.exec() == QDialog.DialogCode.Accepted:
            if "preferences" not in self.answers:
                dlg.apply()
            self.key_problems = self.register_keys()
            keys = self.keys()
            for name, text in (("region", "Capture &region"), ("last_region", "Capture &last region"),
                               ("window", "Capture &window"), ("full", "Capture &full screen")):
                self.acts[name].setText(f"{text}\t{keys.get(name, '')}")
            self._refresh_quick(self.after_menu)

    def check_updates(self):
        from . import update_ui
        update_ui.check(self.anchor, manual=True)

    def about(self):
        if "about" not in self.answers:
            QMessageBox.about(None, "About Paragon PR7-Q",
                              f"<b>Paragon PR7-Q</b> {__version__}<br>A screenshot tool that works the way Greenshot "
                              "works.<br><br>Print: capture a region. Shift+Print: the last region. Alt+Print: a "
                              "window. Ctrl+Print: the full screen.")

    def quit(self):
        for ed in list(self.editors):
            if not ed.close():
                return
        self.hotkeys.unregister()
        if self.tray:
            self.tray.hide()
        QApplication.instance().quit()


# ---------------------------------------------------------------- start with Windows
def start_with_windows(on: bool | None = None) -> bool:
    """Read (on=None) or set the HKCU Run entry that starts PR7-Q when you sign in."""
    if sys.platform != "win32":
        return False
    import winreg
    exe = f'"{sys.executable}" --tray' if getattr(sys, "frozen", False) else \
        f'"{sys.executable.replace("python.exe", "pythonw.exe")}" -m pr7q --tray'
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_ALL_ACCESS) as k:
        if on is None:
            try:
                winreg.QueryValueEx(k, "Paragon PR7-Q")
                return True
            except OSError:
                return False
        if on:
            winreg.SetValueEx(k, "Paragon PR7-Q", 0, winreg.REG_SZ, exe)
        else:
            try:
                winreg.DeleteValue(k, "Paragon PR7-Q")
            except OSError:
                pass
        return on


class PreferencesDialog(QDialog):
    def __init__(self, app: TrayApp):
        super().__init__(app.anchor)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(520)
        form = QFormLayout(self)
        self.keys = {}
        for name, label in (("region", "CAPTURE REGION"), ("last_region", "LAST REGION"), ("window", "WINDOW"),
                            ("full", "FULL SCREEN")):
            e = QLineEdit(app.keys()[name])
            e.setPlaceholderText("e.g. Print, Ctrl+Shift+4")
            self.keys[name] = e
            form.addRow(label, e)
        if app.key_problems:
            warn = QLabel("\n".join(dict.fromkeys(app.key_problems.values())))
            warn.setStyleSheet(f"color: {theme.LED_ORANGE};")
            warn.setWordWrap(True)
            form.addRow(warn)
        self.after = QComboBox()
        for key, text in AFTER:
            self.after.addItem(text, key)
        self.after.setCurrentIndex(max(0, self.after.findData(settings.get("after", "ask"))))
        form.addRow("AFTER CAPTURE", self.after)
        folder_row = QWidget()
        fl = QHBoxLayout(folder_row); fl.setContentsMargins(0, 0, 0, 0)
        self.folder = QLineEdit(settings.get("folder", output.default_folder()))
        browse = QPushButton("...")
        browse.setFixedWidth(40)
        browse.clicked.connect(lambda: self.folder.setText(
            QFileDialog.getExistingDirectory(self, "Screenshots Folder", self.folder.text()) or self.folder.text()))
        fl.addWidget(self.folder, 1); fl.addWidget(browse)
        form.addRow("FOLDER", folder_row)
        self.pattern = QLineEdit(settings.get("pattern", output.DEFAULT_PATTERN))
        self.pattern.setToolTip("%Y %m %d %H %M %S: the date and time; {title}: the window's title")
        form.addRow("FILE NAME", self.pattern)
        self.example = QLabel("")
        self.example.setStyleSheet(f"color: {theme.TEXT_DIM};")
        self.pattern.textChanged.connect(self._example)
        form.addRow("", self.example)
        self.format = QComboBox()
        for f in output.FORMATS:
            self.format.addItem(f.upper(), f)
        self.format.setCurrentIndex(max(0, self.format.findData(settings.get("format", "png"))))
        form.addRow("FORMAT", self.format)
        self.quality = QSpinBox(); self.quality.setRange(1, 100); self.quality.setValue(settings.get_int("jpeg_quality", 90))
        form.addRow("JPEG QUALITY", self.quality)
        self.delay = QSpinBox(); self.delay.setRange(0, 60); self.delay.setSuffix(" s")
        self.delay.setValue(settings.get_int("delay", 0))
        form.addRow("DELAY", self.delay)
        self.full = QComboBox()
        self.full.addItem("All screens", "all"); self.full.addItem("The screen the mouse is on", "current")
        self.full.setCurrentIndex(max(0, self.full.findData(settings.get("full_screen", "all"))))
        form.addRow("FULL SCREEN", self.full)
        self.cursor = QCheckBox("Include the mouse pointer")
        self.cursor.setChecked(settings.get_bool("include_cursor", False))
        form.addRow(self.cursor)
        self.startup = QCheckBox("Start PR7-Q with Windows")
        self.startup.setChecked(start_with_windows())
        self.startup.setEnabled(sys.platform == "win32")
        form.addRow(self.startup)
        from . import update_ui
        self.updates = QCheckBox("Check for updates automatically"); self.updates.setChecked(update_ui.auto_enabled())
        form.addRow(self.updates)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        form.addRow(bb)
        self._example()

    def _example(self):
        self.example.setText(output.file_name(self.pattern.text(), "Window title") + "." + self.format.currentData())

    def apply(self):
        from . import update_ui
        for name, e in self.keys.items():
            settings.set(f"key_{name}", e.text().strip())
        settings.set("after", self.after.currentData())
        settings.set("folder", self.folder.text().strip())
        settings.set("pattern", self.pattern.text().strip() or output.DEFAULT_PATTERN)
        settings.set("format", self.format.currentData())
        settings.set("jpeg_quality", self.quality.value())
        settings.set("delay", self.delay.value())
        settings.set("full_screen", self.full.currentData())
        settings.set("include_cursor", self.cursor.isChecked())
        if sys.platform == "win32":
            start_with_windows(self.startup.isChecked())
        update_ui.set_auto(self.updates.isChecked())
