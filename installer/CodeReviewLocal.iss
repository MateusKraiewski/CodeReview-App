; Instalador do CodeReview Local (Inno Setup 6)
; iscc /DAppVersion=0.1.0 installer\CodeReviewLocal.iss

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{6C1E2B7A-4F0D-4B8E-9A51-2C0F6E3D7B19}
AppName=CodeReview Local
AppVersion={#AppVersion}
AppPublisher=Mateus Kraiewski
AppPublisherURL=https://github.com/MateusKraiewski/CodeReview-App
AppSupportURL=https://github.com/MateusKraiewski/CodeReview-App/issues
DefaultDirName={localappdata}\Programs\CodeReviewLocal
DefaultGroupName=CodeReview Local
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=CodeReviewLocal-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\assets\icone.ico
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\CodeReviewLocal.exe
ChangesEnvironment=yes
CloseApplications=yes
RestartApplications=no
LicenseFile=..\LICENSE

[Languages]
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Registry]
; coloca a pasta do app no PATH do usuário para o comando "crlocal" funcionar no terminal e nas IDEs
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Check: NeedsAddPath(ExpandConstant('{app}'))

[Files]
Source: "..\dist\CodeReviewLocal\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\CodeReview Local"; Filename: "{app}\CodeReviewLocal.exe"
Name: "{group}\{cm:UninstallProgram,CodeReview Local}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\CodeReview Local"; Filename: "{app}\CodeReviewLocal.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\CodeReviewLocal.exe"; Description: "{cm:LaunchProgram,CodeReview Local}"; Flags: nowait postinstall skipifsilent
; atualização automática (instalador rodando em /SILENT): reabre o app ao terminar
Filename: "{app}\CodeReviewLocal.exe"; Flags: nowait; Check: WizardSilent

[Code]
function NeedsAddPath(Dir: string): Boolean;
var
  Current: string;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', Current) then
  begin
    Result := True;
    exit;
  end;
  Result := Pos(';' + Uppercase(Dir) + ';', ';' + Uppercase(Current) + ';') = 0;
end;
