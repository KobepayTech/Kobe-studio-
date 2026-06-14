; Kobe Studio Inno Setup installer script
; Install Inno Setup, then compile this file after running build_windows.bat.

#define MyAppName "Kobe Studio"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "KobepayTech"
#define MyAppExeName "KobeStudio.exe"

[Setup]
AppId=KobeStudioApp
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Kobe Studio
DefaultGroupName=Kobe Studio
OutputDir=installer
OutputBaseFilename=KobeStudioSetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "..\dist\KobeStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Kobe Studio"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Kobe Studio"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Kobe Studio"; Flags: nowait postinstall skipifsilent
