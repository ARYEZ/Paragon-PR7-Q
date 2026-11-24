"""Check a real install of PR7-Q-Setup.exe (CI, Windows): python tools/verify_install.py installed|uninstalled

`installed` runs the installed PR7-Q.exe --selftest (offscreen: a full-screen and a region capture saved directly,
the editor with shapes saved as PNG and JPEG on a stand-in desktop), so the frozen program is shown to have Qt, its
image plugins and the Inter fonts; it also checks the start-with-Windows entry. `uninstalled` checks it's gone."""
import json
import os
import subprocess
import sys
import tempfile
import time
import winreg
from pathlib import Path

HKCU = winreg.HKEY_CURRENT_USER
APP = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "PR7-Q"
SHORTCUT = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Paragon PR7-Q.lnk"
UNINSTALL = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{D7ED5F6F-F80A-403C-8739-AA5BA3676C97}_is1"
RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"


def value(path, name=""):
    try:
        with winreg.OpenKey(HKCU, path) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


def check(ok, what, p):
    print(("ok    " if ok else "FAIL  ") + what)
    if not ok:
        p.append(what)


def installed():
    p = []
    exe = APP / "PR7-Q.exe"
    for f in (exe, APP / "unins000.exe", APP / "_internal" / "pr7q" / "fonts" / "Inter-Regular.ttf",
              APP / "_internal" / "pr7q" / "icons" / "app.ico"):
        check(f.is_file(), f"file {f}", p)
    check(SHORTCUT.is_file(), "Start menu shortcut", p)
    check(value(UNINSTALL, "DisplayName") == "Paragon PR7-Q", "Installed apps entry", p)
    run = value(RUN, "Paragon PR7-Q") or ""
    check(str(exe).lower() in run.lower() and "--tray" in run, f"starts with Windows: {run}", p)
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "out.json"
        subprocess.run([str(exe), "--selftest", str(out)], timeout=180, check=False)
        got = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
        check(got.get("full") == [1600, 1000] and got.get("region") == [400, 200], f"captures ({got})", p)
        check(got.get("edited") == [400, 200] and got.get("red_border") is True, "the editor's shapes are saved", p)
        check(got.get("jpeg_ok") is True and str(got.get("jpeg", "")).endswith(".jpg"), "saves JPEG", p)
        check(got.get("fonts") is True, "Inter fonts", p)
    return p


def uninstalled():
    deadline = time.time() + 60
    while True:
        p = []
        check(not (APP / "PR7-Q.exe").exists(), "program files removed", p)
        check(not SHORTCUT.exists(), "Start menu shortcut removed", p)
        check(value(UNINSTALL, "DisplayName") is None, "Installed apps entry removed", p)
        check(value(RUN, "Paragon PR7-Q") is None, "start-with-Windows entry removed", p)
        if not p or time.time() > deadline:
            return p
        print("... waiting for the uninstaller to finish")
        time.sleep(3)


if __name__ == "__main__":
    problems = {"installed": installed, "uninstalled": uninstalled}[sys.argv[1]]()
    print("\nALL OK" if not problems else f"\n{len(problems)} problem(s)")
    sys.exit(1 if problems else 0)
