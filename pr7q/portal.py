"""Screenshots on Linux's Wayland desktops (Plasma's included): apps may not read the screen themselves there (Qt's
grabWindow gives nothing), so the desktop portal takes the picture: org.freedesktop.portal.Screenshot on the session
bus. The call returns a request; the answer comes later as that request's Response signal with the picture's file.

    screenshot(interactive=False)   the whole desktop, at once (Plasma may ask once whether PR7-Q may do this)
    screenshot(interactive=True)    Plasma's own dialog, where you pick a window or an area (Capture window)

Both return a QImage, or raise PortalError with what went wrong. D-Bus through jeepney (pure Python; PR7-OS has it,
keyring uses it): PySide's QtDBus can't read the a{sv} the answer carries. `address` lets tests use a private bus with
a stand-in portal (tests/standin_portal.py).
"""
from __future__ import annotations

import os
import secrets
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

from PySide6.QtGui import QImage

SERVICE = "org.freedesktop.portal.Desktop"
PATH = "/org/freedesktop/portal/desktop"
INTERFACE = "org.freedesktop.portal.Screenshot"
REQUEST = "org.freedesktop.portal.Request"


class PortalError(Exception):
    pass


def _connect(address: str | None):
    try:
        from jeepney.io.blocking import open_dbus_connection
    except ImportError as e:
        raise PortalError("jeepney (Python's D-Bus library) isn't installed") from e
    try:
        return open_dbus_connection(bus=address or "SESSION")
    except Exception as e:  # noqa: BLE001 - no bus, no address
        raise PortalError(f"there's no desktop session bus to ask for the screen ({e})") from e


def available(address: str | None = None) -> bool:
    """Is a desktop portal there to take screenshots?"""
    try:
        from jeepney import message_bus
        from jeepney.io.blocking import Proxy
        with _connect(address) as conn:
            return bool(Proxy(message_bus, conn).NameHasOwner(SERVICE)[0])
    except Exception:  # noqa: BLE001
        return False


def request_path(unique_name: str, token: str) -> str:
    """Where the portal puts our request: /org/freedesktop/portal/desktop/request/<our name, : dropped, . as _>/token."""
    return f"{PATH}/request/{unique_name.lstrip(':').replace('.', '_')}/{token}"


def _is_temporary(path: Path) -> bool:
    roots = [tempfile.gettempdir(), os.environ.get("XDG_RUNTIME_DIR", "")]
    return any(r and str(path).startswith(os.path.join(r, "")) for r in roots)


def screenshot(interactive: bool = False, address: str | None = None, timeout: float = 120) -> QImage:
    from jeepney import DBusAddress, MatchRule, MessageType, message_bus, new_method_call
    from jeepney.io.blocking import Proxy
    with _connect(address) as conn:
        token = "pr7q_" + secrets.token_hex(6)
        handle = request_path(conn.unique_name, token)
        rule = MatchRule(type="signal", interface=REQUEST, member="Response", path=handle)
        Proxy(message_bus, conn).AddMatch(rule)          # watched before asking: the answer can come at once
        with conn.filter(rule) as answers:
            portal = DBusAddress(PATH, bus_name=SERVICE, interface=INTERFACE)
            call = new_method_call(portal, "Screenshot", "sa{sv}",
                                   ("", {"handle_token": ("s", token), "interactive": ("b", interactive),
                                         "modal": ("b", True)}))
            try:
                reply = conn.send_and_get_reply(call, timeout=10)
            except Exception as e:  # noqa: BLE001 - no portal, a timeout
                raise PortalError(f"the desktop portal didn't answer ({e})") from e
            if reply.header.message_type == MessageType.error:
                raise PortalError(f"the desktop portal refused the screenshot ({reply.body})")
            try:
                response = conn.recv_until_filtered(answers, timeout=timeout)
            except TimeoutError as e:
                raise PortalError("the desktop didn't answer the screenshot request") from e
    code, results = response.body
    if code == 1:
        raise PortalError("cancelled")
    uri = results.get("uri", ("s", ""))[1]
    if code != 0 or not uri:
        raise PortalError("the desktop didn't take the screenshot (PR7-Q may need permission: try again and allow it)")
    path = Path(unquote(urlparse(uri).path))
    img = QImage(str(path))
    if img.isNull():
        raise PortalError(f"the screenshot couldn't be read ({path})")
    if _is_temporary(path):                       # the portal's own temporary file; anything else is left alone
        try:
            path.unlink()
        except OSError:
            pass
    return img
