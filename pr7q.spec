# PyInstaller build of PR7-Q: pyinstaller pr7q.spec  ->  dist/PR7-Q/PR7-Q.exe  (folder build: starts fast)
#
# Windows Defender judges unknown, unsigned programs partly by how they look: a PyInstaller program with no file
# details and the stock (shared, much-copied) starter is a common false positive. So the .exe carries proper
# version details (Properties > Details), and CI builds PyInstaller's starter from source (see build.yml).
import re
import sys
from pathlib import Path


root = Path(SPECPATH)
version = re.search(r'__version__ = "(.+?)"', (root / "pr7q" / "__init__.py").read_text()).group(1)
nums = tuple(int(x) for x in (version.split(".") + ["0", "0", "0"])[:4])
details = None
if sys.platform == "win32":  # version resources exist only in Windows programs
    from PyInstaller.utils.win32.versioninfo import (FixedFileInfo, StringFileInfo, StringStruct, StringTable,
                                                     VarFileInfo, VarStruct, VSVersionInfo)
    details = VSVersionInfo(
        ffi=FixedFileInfo(filevers=nums, prodvers=nums),
        kids=[StringFileInfo([StringTable("040904B0", [
            StringStruct("CompanyName", "Paragon"),
            StringStruct("FileDescription", "Paragon PR7-Q screenshot tool"),
            StringStruct("FileVersion", version),
            StringStruct("InternalName", "PR7-Q"),
            StringStruct("LegalCopyright", "Paragon"),
            StringStruct("OriginalFilename", "PR7-Q.exe"),
            StringStruct("ProductName", "Paragon PR7-Q"),
            StringStruct("ProductVersion", version)])]),
              VarFileInfo([VarStruct("Translation", [1033, 1200])])])

a = Analysis(
    [str(root / "tools" / "launcher.py")],
    pathex=[str(root)],
    datas=[(str(root / "pr7q" / "fonts"), "pr7q/fonts"), (str(root / "pr7q" / "icons"), "pr7q/icons")],
    # QtPrintSupport prints; QtNetwork's local socket passes a second start's capture to the running PR7-Q; Qt's
    # JPEG / BMP image plugins come with PySide6's hook.
    hiddenimports=["PySide6.QtPrintSupport", "PySide6.QtNetwork"],
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQml", "PySide6.QtQuick",
              "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PIL"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="PR7-Q", console=False, upx=False,  # no UPX: packed
          icon=str(root / "pr7q" / "icons" / "app.ico"), version=details)          # .exes look worse still
coll = COLLECT(exe, a.binaries, a.datas, name="PR7-Q", upx=False)
