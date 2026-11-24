"""Windows only, on CI: keys that work from any program and the start-with-Windows entry (they touch the real
session and registry, so never on the owner's computer)."""
import os
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32" or not os.environ.get("CI"),
                                reason="registers keys and writes HKCU: Windows CI only")


def test_register_a_key(qapp):
    from pr7q import hotkeys
    h = hotkeys.Hotkeys()
    problems = h.register({"x": ("Ctrl+Alt+Shift+F24", lambda: None)})
    assert problems == {} and len(h.ids) == 1
    other = hotkeys.Hotkeys()
    taken = other.register({"x": ("Ctrl+Alt+Shift+F24", lambda: None)})
    assert "taken" in taken["x"]                       # the same key twice: the second can't have it
    h.unregister()
    assert not h.ids


def test_start_with_windows():
    from pr7q.tray import start_with_windows
    start_with_windows(True)
    try:
        assert start_with_windows() is True
    finally:
        start_with_windows(False)
    assert start_with_windows() is False
