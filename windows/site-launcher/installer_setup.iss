#define MyAppName "ARDOR Pressure Test"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "ARDOR"

#ifndef LauncherPath
  #define LauncherPath "dist\ARDOR Pressure Test.exe"
#endif
#ifndef IconPath
  #define IconPath "ardor-pressure-test.ico"
#endif
#ifndef OutputDir
  #define OutputDir "release"
#endif

[Setup]
AppId={{A7DB292E-FC58-4CB3-8620-5031C0186D56}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#OutputDir}
OutputBaseFilename=ARDOR-Pressure-Test-Setup
SetupIconFile={#IconPath}
UninstallDisplayIcon={app}\ARDOR Pressure Test.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные ярлыки:"; Flags: checkedonce

[Files]
Source: "{#LauncherPath}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\ARDOR Pressure Test.exe"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\ARDOR Pressure Test.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\ARDOR Pressure Test.exe"; Description: "Открыть {#MyAppName}"; Flags: nowait postinstall skipifsilent
