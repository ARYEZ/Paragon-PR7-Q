"""Keys that work from any program (Windows' RegisterHotKey): Print, Shift+Print, Alt+Print, Ctrl+Print by default.

Windows delivers them as WM_HOTKEY messages to this program; a native event filter turns those into callbacks.
A key another program already holds (Windows 11's Snipping Tool can own Print) can't be registered: `register`
reports which, so PR7-Q can say so and the keys can be changed in Preferences."""

from __future__ import annotations

import sys

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
WM_HOTKEY = 0x0312
NAMED_KEYS = {"print": 0x2C, "printscreen": 0x2C, "prtsc": 0x2C, "pause": 0x13, "scrolllock": 0x91,
              "insert": 0x2D, "home": 0x24, "end": 0x23, "pgup": 0x21, "pgdown": 0x22}
NAMED_KEYS.update({f"f{i}": 0x6F + i for i in range(1, 25)})

DEFAULT_KEYS = {"region": "Print", "last_region": "Shift+Print", "window": "Alt+Print", "full": "Ctrl+Print"}
LINUX_NOTE = ("Print (region), Shift+Print (last region), Alt+Print (window) and Ctrl+Print (full screen) are Plasma "
              "shortcuts: change them in System Settings > Keyboard > Shortcuts > Paragon PR7-Q.")


def parse(text: str) -> tuple[int, int] | None:
    """"Ctrl+Shift+Print" -> (modifiers, virtual key), or None if it isn't a key Windows can register."""
    parts = [p.strip().lower() for p in text.replace(" ", "").split("+") if p.strip()]
    if not parts:
        return None
    mods = 0
    for p in parts[:-1]:
        m = {"ctrl": MOD_CONTROL, "control": MOD_CONTROL, "alt": MOD_ALT, "shift": MOD_SHIFT, "win": MOD_WIN,
             "meta": MOD_WIN}.get(p)
        if m is None:
            return None
        mods |= m
    key = parts[-1]
    if key in NAMED_KEYS:
        vk = NAMED_KEYS[key]
    elif len(key) == 1 and key.isalnum():
        vk = ord(key.upper())
    else:
        return None
    return mods, vk


def available() -> bool:
    return sys.platform == "win32"


class _Filter(QAbstractNativeEventFilter):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) == b"windows_generic_MSG":
            import ctypes
            from ctypes import wintypes
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam in self.owner.ids:
                self.owner.ids[msg.wParam]()
                return True, 0
        return False, 0


class Hotkeys:
    """register({"region": ("Print", callback), ...}) -> {name: problem} for the keys that couldn't be had."""

    def __init__(self):
        self.ids: dict[int, callable] = {}
        self._filter = None
        self._next = 0xA000

    def register(self, keys: dict[str, tuple[str, callable]]) -> dict[str, str]:
        self.unregister()
        problems = {}
        if not available():
            return {name: LINUX_NOTE for name in keys}
        import ctypes
        user32 = ctypes.windll.user32
        if self._filter is None:
            self._filter = _Filter(self)
            QCoreApplication.instance().installNativeEventFilter(self._filter)
        for name, (text, callback) in keys.items():
            if not text:
                continue
            parsed = parse(text)
            if parsed is None:
                problems[name] = f"{text} isn't a key PR7-Q can use."
                continue
            mods, vk = parsed
            hid = self._next
            self._next += 1
            if user32.RegisterHotKey(None, hid, mods | MOD_NOREPEAT, vk):
                self.ids[hid] = callback
            else:
                problems[name] = f"{text} is taken by another program (Windows' Snipping Tool can hold Print)."
        return problems

    def unregister(self) -> None:
        if available() and self.ids:
            import ctypes
            for hid in list(self.ids):
                ctypes.windll.user32.UnregisterHotKey(None, hid)
        self.ids.clear()
