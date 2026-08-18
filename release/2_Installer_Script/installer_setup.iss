; Inno Setup Script for WIKA CPG1500 Pressure Analyzer

#define MyAppName "WIKA CPG1500 Pressure Analyzer"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "WIKA Analyzer Tools"
#define MyAppExeName "WIKA CPG1500 Processor.exe"

[Setup]
AppId={{D37E860B-9B92-441A-B472-A2D5E19A6245}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\WIKA CPG1500 Processor
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=release\2_Installer
OutputBaseFilename=WIKA_CPG1500_Setup
SetupIconFile=resources\app_icon.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\WIKA CPG1500 Processor.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "config.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "resources\app_icon.ico"; DestDir: "{app}\resources"; Flags: ignoreversion

[Dirs]
Name: "{app}\output"
Name: "{app}\output\graphs"
Name: "{app}\output\excel"
Name: "{app}\output\reports"
Name: "{app}\output\logs"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\resources\app_icon.ico"
Name: "{group}\Open Output Folder"; Filename: "{app}\output"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\resources\app_icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
