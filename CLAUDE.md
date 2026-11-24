# Paragon PR7-Q: notes for Claude

**Paragon PR7-Q** is the owner's personal screenshot tool: Python (**PySide6**) that **works the way Greenshot works**,
in the Paragon family look (PR7-Z, PR7-W, PR7-L, PR7-F, PR7-E, PR7-R, PR7-P, PR7-M `ARYEZ/Paragon-PR7-M`). Windows
10/11 x64 is the target; it runs on Linux for tests. The owner writes Python; explain the why of changes.

## How it's built

- `pr7q/capture.py`: `Desktop(image, geometry, scale, cursor)` = the frozen desktop (geometry in points, image in
  pixels at the highest screen DPR); `to_pixels` / `crop` convert. `grab(include_cursor)` composites every screen;
  `draw_cursor` paints an arrow at the pointer; `window_at` (Windows: WindowFromPoint + GetAncestor + DWM extended
  frame bounds, title) else None.
- `pr7q/overlay.py`: `RegionPicker` (dim, guides, size label, magnifier; click = window, Enter = full screen, Esc /
  right click = cancel). Use `span(a, b)` for dragged boxes: `QRect(a, b)` counts both end pixels.
- `pr7q/hotkeys.py`: RegisterHotKey + a QAbstractNativeEventFilter for WM_HOTKEY; `register` returns problems per key
  (shown once each in the tray balloon and Preferences).
- `pr7q/output.py` (no widgets): `file_name` (strftime + `{title}`, made safe), `free_path` (never overwrites), `save`
  (its own QFile, closed before anything else touches the file: PR7-P's Windows lesson), `copy`, `open_in_pr7p` (finds
  PR7-P through `family.py`), `print_image`.
- `pr7q/editor.py`: `Shape` (kind, pts, style) drawn by `paint_shape`; `render(base, shapes)` flattens; `Canvas` keeps
  shapes as objects until saved, undo / redo as snapshots; `EditorWindow` menus, tools, style bar. `answers` for tests.
- `pr7q/tray.py`: `TrayApp(grabber, window_at, show_tray)` - capture, after-capture actions (`deliver`), editors,
  Preferences; `start_with_windows` (HKCU Run "Paragon PR7-Q", `--tray`). Tests pass a stand-in grabber.
- `pr7q/app.py`: one per user (QLocalSocket hand-off, PR7-R's Windows fix); `--region` etc. go to the running one;
  `--selftest OUT.json` (CI runs it on the installed exe).
- Installer `installer/pr7q.iss` (per user, AppId {D7ED5F6F-F80A-403C-8739-AA5BA3676C97} permanent; tasks startup,
  desktopicon); CI installs it, `tools/verify_install.py installed`, uninstalls, `... uninstalled`. Spec: file details,
  no UPX, PyInstaller's bootloader built in CI, Defender scan (PR7-F's false-positive fix).
- Updates: `pr7q/updates.py` (no Qt; GitHub's public releases/latest, User-Agent names only the app, installer asset
  `PR7-Q-Setup-*.exe`, run with /SILENT /relaunch=1) and `update_ui.py`. Same files in every family app: keep them in
  step. `family.py`: the other family apps by their permanent AppIds.

## The look (family rules)

- Theme is PR7-M's (OBSIDIAN + AURORA via `theme.set_finish`). Colours: the family's only (hues ~318 -> 0 -> 42 deg,
  pearl and onyx greys) for the UI; the annotation palette is the family's too. Inter; labels UPPER CASE.
- The PR7-Q mark: PR7 `Logo.cpp` geometry plus a Q (`widgets.Q_OUTER` / `Q_COUNTER`); icon by `tools/make_icon.py`,
  wizard art by `tools/make_installer_art.py`. Check visuals with `QT_SCALE_FACTOR=2 python tools/screenshots.py OUT`.

## Rules

- Behaviour questions: do what Greenshot does (keys, after-capture choices, editor tools).
- Tests: `python -m pytest` (offscreen) on stand-in desktops (`conftest.desk`, `stripes`). Never the real settings or
  screenshot folder (conftest), or, outside CI, the registry or global keys.
- Releases: bump `__version__` in `pr7q/__init__.py`, add a `## x.y.z` section to CHANGELOG.md; Run workflow with
  "Publish a release" (or a `v*` tag) publishes.
