"""A stand-in desktop portal for the tests: org.freedesktop.portal.Screenshot on the bus given, answering each
request with the picture given (or with a cancel), as Plasma's portal does: the method returns the request's path,
then a Response signal on it carries the file's URI. Run as its own process (a real portal is one):

    python standin_portal.py BUS_ADDRESS PICTURE.png [cancel]
It prints READY once it owns the name, and each call's options as a JSON line."""
import json
import shutil
import sys
import tempfile

from PySide6.QtCore import ClassInfo, QCoreApplication, QObject, QTimer, Slot
from PySide6.QtDBus import QDBusConnection, QDBusMessage, QDBusObjectPath

address, picture = sys.argv[1], sys.argv[2]
cancel = sys.argv[3:] == ["cancel"]
app = QCoreApplication([])
bus = QDBusConnection.connectToBus(address, "portal")


@ClassInfo({"D-Bus Interface": "org.freedesktop.portal.Screenshot"})
class Portal(QObject):
    @Slot(str, "QVariantMap", "QDBusMessage", result="QDBusObjectPath")
    def Screenshot(self, parent, options, msg):
        options = dict(options)
        print(json.dumps({k: (v if isinstance(v, (bool, str, int)) else str(v)) for k, v in options.items()}),
              flush=True)
        sender = msg.service().lstrip(":").replace(".", "_")
        path = f"/org/freedesktop/portal/desktop/request/{sender}/{options['handle_token']}"
        shot = tempfile.mktemp(suffix=".png")          # a fresh temporary file per answer, as the portal makes
        shutil.copy(picture, shot)

        def answer():
            sig = QDBusMessage.createSignal(path, "org.freedesktop.portal.Request", "Response")
            sig.setArguments([1, {}] if cancel else [0, {"uri": "file://" + shot}])
            bus.send(sig)
        QTimer.singleShot(30, answer)
        return QDBusObjectPath(path)


portal = Portal()
bus.registerObject("/org/freedesktop/portal/desktop", portal, QDBusConnection.RegisterOption.ExportAllSlots)
bus.registerService("org.freedesktop.portal.Desktop")
print("READY", flush=True)
app.exec()
