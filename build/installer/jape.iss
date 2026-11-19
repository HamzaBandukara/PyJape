; Inno Setup script — wraps the PyInstaller one-folder app (build/dist/PyJape)
; into a single Windows installer. Build with:  ISCC.exe build\installer\jape.iss
; (install Inno Setup 6 first; the CI does this with `choco install innosetup`).

[Setup]
AppName=PyJape
AppVersion=1.0.0
AppPublisher=PyJape
AppPublisherURL=https://github.com/HamzaBandukara/PyJape
LicenseFile=..\..\LICENSE
DefaultDirName={autopf}\PyJape
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=PyJape-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "..\dist\PyJape\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\PyJape"; Filename: "{app}\PyJape.exe"
Name: "{autodesktop}\PyJape"; Filename: "{app}\PyJape.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\PyJape.exe"; Description: "Launch PyJape"; Flags: nowait postinstall skipifsilent
