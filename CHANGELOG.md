# Changelog

## 0.4.0

PR7-Q runs on Linux's Plasma desktop (PR7-OS), where apps may not read the screen themselves (Wayland):
- **The screen comes from the desktop portal** (org.freedesktop.portal.Screenshot): Plasma takes the picture and
  hands it over; the first time, Plasma may ask once whether PR7-Q may take screenshots. Region, last region and full
  screen work as on Windows, with the same picker and editor.
- **Capture window opens Plasma's own dialog**, where you pick the window (Wayland doesn't tell apps which window is
  under the pointer).
- **The keys are Plasma shortcuts** (Print, Shift+Print, Alt+Print, Ctrl+Print on PR7-OS; change them in System Settings
  > Keyboard > Shortcuts); Preferences says so instead of showing Windows' key boxes.
- **Start when I sign in** is an autostart entry; switching it off also overrides PR7-OS's start-for-everyone entry.
- On a desktop with several screens, the region picker covers the primary one (one Wayland window can't span screens);
  full screen still takes them all. The mouse pointer can't be included on Wayland.
Nothing changes on Windows.

## 0.3.3

- The family list (`family.py`) knows the three newest Paragon apps: PR7-HW (hardware information), PR7-BK
  (backups) and PR7-TM (terminal), so links between the apps and the PR7-U offer find them.

## 0.3.2

- The family list (`family.py`) knows the four newest Paragon apps: PR7-HX (hex editor), PR7-DB (SQLite browser),
  PR7-UN (uninstaller) and PR7-LN (launcher), so links between the apps and the PR7-U offer find them.

## 0.3.1

- The family's list knows the newest apps (PR7-HB, PR7-FS, PR7-AR, PR7-WM), so links between apps and Check for Updates find them.

## 0.3.0

- **One finish for the whole family.** Choosing OBSIDIAN or AURORA here switches every Paragon app, open ones included (within a couple of seconds), and every app starts in the family's choice. PR7-Q's tray menu has a Finish choice now.
- In AURORA, group titles and selected rows are dark and readable (they were white on the light finish).

## 0.2.1

- Knows the whole family: PR7-DU, PR7-CB, PR7-IS, PR7-PM and PR7-SM are in its list of family apps (their permanent install IDs), so the family links find them when they're installed.

## 0.2.0

- **Check for Updates knows PR7-U**, the family installer. When it's installed, the update window has **Update All in PR7-U**, and a check by hand that finds PR7-Q up to date offers to open PR7-U for the rest of the family.

## 0.1.0

- First release: a screenshot tool that works the way Greenshot works. It runs in the notification area with
  keys for region, last region, window and full screen. The region picker has a magnifier. After a capture it can
  save, copy, open the editor, open in PR7-P or print. The editor has shapes, text, speech bubbles, step numbers,
  highlighter, pixelate, crop, undo and print. Preferences cover keys, file names, format, delay, the pointer and
  starting with Windows. The installer is per user.
