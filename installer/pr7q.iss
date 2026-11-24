; Paragon PR7-Q installer (Inno Setup 6).
;   iscc /DAppVersion=0.1.0 installer\pr7q.iss      (after pyinstaller pr7q.spec has made dist\PR7-Q)
;
; Per-user (no admin rights) into %LOCALAPPDATA%\Programs\PR7-Q, with a Start menu entry. Ticked by default, PR7-Q
; starts with Windows (an HKCU Run entry written by PR7-Q itself: --startup on|off, so installer and Preferences
; agree), as a screenshot tool should be there when Print is pressed. --unregister on uninstall takes it away.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
; AppId is permanent: it's how a new version finds and upgrades the installed one. Never change it.
AppId={{D7ED5F6F-F80A-403C-8739-AA5BA3676C97}
AppName=Paragon PR7-Q
AppVersion={#AppVersion}
AppVerName=Paragon PR7-Q {#AppVersion}
AppPublisher=Paragon
VersionInfoVersion={#AppVersion}
PrivilegesRequired=lowest
DefaultDirName={autopf}\PR7-Q
DefaultGroupName=Paragon PR7-Q
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
UsePreviousTasks=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist
OutputBaseFilename=PR7-Q-Setup-{#AppVersion}
SetupIconFile=..\pr7q\icons\app.ico
UninstallDisplayIcon={app}\PR7-Q.exe
UninstallDisplayName=Paragon PR7-Q
WizardStyle=modern
WizardImageFile=wizard-large-1x.bmp,wizard-large-2x.bmp
WizardSmallImageFile=wizard-small-1x.bmp,wizard-small-2x.bmp
Compression=lzma2/max
SolidCompression=yes
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "startup"; Description: "Start PR7-Q with Windows (Print captures a region)"; GroupDescription: "Windows:"
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\PR7-Q\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\Paragon PR7-Q"; Filename: "{app}\PR7-Q.exe"; Comment: "Screenshots"
Name: "{autodesktop}\Paragon PR7-Q"; Filename: "{app}\PR7-Q.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\PR7-Q.exe"; Parameters: "--startup on"; Flags: runhidden waituntilterminated; Tasks: startup
Filename: "{app}\PR7-Q.exe"; Parameters: "--startup off"; Flags: runhidden waituntilterminated; Tasks: not startup
Filename: "{app}\PR7-Q.exe"; Parameters: "--tray"; Description: "{cm:LaunchProgram,Paragon PR7-Q}"; Flags: nowait postinstall skipifsilent
; Updates (Check for Updates runs this installer with /SILENT /relaunch=1): start PR7-Q again when done.
Filename: "{app}\PR7-Q.exe"; Parameters: "--tray"; Flags: nowait runasoriginaluser; Check: Relaunch

[UninstallRun]
Filename: "{app}\PR7-Q.exe"; Parameters: "--unregister"; Flags: runhidden waituntilterminated; RunOnceId: "Unregister"

[Code]
// True only when the updater asked for it (/relaunch=1): normal and CI installs behave as before.
function Relaunch: Boolean;
begin
  Result := ExpandConstant('{param:relaunch|0}') = '1';
end;
