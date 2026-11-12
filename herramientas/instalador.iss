; Instalador de AFK-Community (Inno Setup 6).
;
; Lo genera herramientas\construir_exe.py, que le pasa la versión y las rutas:
;   ISCC /DAppVersion=X.Y.Z /DSourceDir=...\dist\AFK-Community /DOutputDir=...\dist /DIconFile=...\build\icono.ico instalador.iss
;
; Se instala POR USUARIO en %LOCALAPPDATA%\Programs\AFK-Community, sin pedir permisos de administrador:
; la app guarda sus datos junto al .exe y el actualizador reemplaza los .py, así que la carpeta tiene que
; poder escribirse (en C:\Program Files no se podría).

#define AppName "AFK-Community"
#define AppExe "AFK-Community.exe"

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\AFK-Community"
#endif
#ifndef OutputDir
  #define OutputDir "..\dist"
#endif
#ifndef OutputName
  #define OutputName "AFK-Community-setup"
#endif

[Setup]
; El AppId identifica la app para actualizar y desinstalar: NO cambiarlo nunca.
AppId={{CFC87292-88A6-4010-9015-CE6FC53BEE95}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppName}
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename={#OutputName}
#ifdef IconFile
SetupIconFile={#IconFile}
#endif
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Si la app está abierta, el instalador ofrece cerrarla
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[CustomMessages]
english.BorrarDatos=Do you also want to delete your data (accounts, imported files, backups and settings)?%n%nChoose "No" to keep it in case you install the app again.
spanish.BorrarDatos=¿Quieres borrar también tus datos (cuentas, archivos importados, respaldos y preferencias)?%n%nElige "No" para conservarlos por si vuelves a instalar la app.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; El código que el actualizador fue reemplazando o agregando (el desinstalador solo conoce lo que instaló).
; Los datos del usuario (app\cuentas, app\preferencias.json...) se quedan, salvo que pida borrarlos.
Type: filesandordirs; Name: "{app}\app\aplicacion"
Type: filesandordirs; Name: "{app}\app\navegador"
Type: filesandordirs; Name: "{app}\app\idiomas"
Type: filesandordirs; Name: "{app}\app\recursos"
Type: filesandordirs; Name: "{app}\app\docs"
Type: filesandordirs; Name: "{app}\app\herramientas"
Type: filesandordirs; Name: "{app}\app\__pycache__"
Type: files; Name: "{app}\app\*.py"
Type: files; Name: "{app}\app\requirements.txt"
Type: files; Name: "{app}\app\README.md"
Type: files; Name: "{app}\app\.gitignore"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  { Los datos del usuario no los instaló el instalador: se pregunta antes de borrarlos }
  if (CurUninstallStep = usPostUninstall) and not UninstallSilent then
    if DirExists(ExpandConstant('{app}')) then
      if MsgBox(CustomMessage('BorrarDatos'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(ExpandConstant('{app}'), True, True, True);
end;
