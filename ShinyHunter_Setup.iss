#define AppName    "Shiny Hunter"
#define AppVersion "0.5.17"
#define AppPublisher "whistlingwilly"
#define AppURL     "https://github.com/whistlingwilly/Pokemon-Shiny-Hunter"
#define AppExeName "ShinyHunter.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} v{#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}/releases
DefaultDirName={autopf}\ShinyHunter
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputBaseFilename=ShinyHunterSetup_v{#AppVersion}
OutputDir=installer_output
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\shiny_hunter_config.json"
Type: files; Name: "{app}\shiny_hunter_baseline.png"
Type: files; Name: "{app}\shiny_hunter_baseline.png.meta"
Type: filesandordirs; Name: "{app}\sequences"
Type: filesandordirs; Name: "{app}\screenshots"
