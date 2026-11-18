; Pinbu Note v1.0 Windows installer (Inno Setup 6 or 7)
; Place this file next to main.py and build-windows.ps1 in the extracted
; Pinbu Note v1.0 source folder. First build the app with build-windows.ps1.
;
; IMPORTANT: Keep AppId unchanged for future Pinbu Note updates, so Windows
; recognises subsequent installers as upgrades to the same application.

#define MyAppName "Pinbu Note"
#define MyAppVersion "1.0"
#define MyAppExeName "Pinbu Note.exe"

[Setup]
AppId={{974AD665-3F47-4CC5-9AAE-0A5F43565469}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
VersionInfoVersion=1.0.0.0
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=Pinbu Note
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
OutputDir=installer
OutputBaseFilename=PinbuNote_Setup_v{#MyAppVersion}
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardStyle=modern
Compression=lzma
SolidCompression=yes
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
; Include every PyInstaller onedir file, including the _internal folder.
; These files are private to Pinbu Note, so ignoreversion is appropriate.
; OCR runtime is included recursively from _internal\ocr. Do not remove it.
Source: "dist\Pinbu Note\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

; Deliberately no [Run] application launch. The installer-launched first
; process can inherit a different environment from a normal Start
; menu launch. Close Setup before starting Pinbu Note from Start.

; New Pinbu Note files open via double click; legacy Yomu Note files are still
; supported through File > Open without claiming their file association.
[Registry]
Root: HKA; Subkey: "Software\Classes\.pinbunote"; ValueType: string; ValueData: "PinbuNote.Notebook"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\PinbuNote.Notebook"; ValueType: string; ValueData: "Pinbu Note Notebook"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\PinbuNote.Notebook\DefaultIcon"; ValueType: string; ValueData: "{app}\{#MyAppExeName},0"
Root: HKA; Subkey: "Software\Classes\PinbuNote.Notebook\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
