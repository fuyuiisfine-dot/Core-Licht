Unicode true
!include "MUI2.nsh"
!include "FileFunc.nsh"
Name "Core Licht Windows Preview"
OutFile "${OUTPUT}"
InstallDir "$LOCALAPPDATA\Programs\CoreLicht"
RequestExecutionLevel user
SetCompressor /SOLID lzma
SetCompressorDictSize 32
Var TestMode
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "TradChinese"
Function .onInit
  ${GetParameters} $0
  ${GetOptions} $0 "/TESTMODE" $TestMode
  IfErrors 0 +2
  StrCpy $TestMode "no"
FunctionEnd
Section
  SetShellVarContext current
  SetOutPath "$INSTDIR"
  File "${CLIENT}\CoreLicht.exe"
  File "${LAUNCHER}"
  File "${GUIDE}"
  SetOutPath "$INSTDIR\server"
  File "${SERVER}"
  SetOutPath "$INSTDIR\data"
  File "${CLIENT}\data\catalog.json"
  File /r "${CLIENT}\data\protocol"
  File /r "${CLIENT}\data\portraits"
  File /r "${CLIENT}\data\ui"
  File /r "${CLIENT}\data\voices"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  StrCmp $TestMode "no" 0 done
  CreateDirectory "$SMPROGRAMS\Core Licht"
  CreateShortcut "$SMPROGRAMS\Core Licht\Core Licht.lnk" "$INSTDIR\CoreLichtLauncher.exe"
  CreateShortcut "$SMPROGRAMS\Core Licht\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CoreLichtPreview" "DisplayName" "Core Licht Windows Preview"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CoreLichtPreview" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CoreLichtPreview" "InstallLocation" "$INSTDIR"
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CoreLichtPreview" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CoreLichtPreview" "NoRepair" 1
  done:
SectionEnd
Section "Uninstall"
  SetShellVarContext current
  IfFileExists "$INSTDIR\CoreLichtLauncher.exe" 0 done
  Delete "$INSTDIR\CoreLicht.exe"
  Delete "$INSTDIR\CoreLichtLauncher.exe"
  Delete "$INSTDIR\Windows-README.txt"
  Delete "$INSTDIR\server\CoreLichtServer.exe"
  RMDir "$INSTDIR\server"
  RMDir /r "$INSTDIR\data\protocol"
  RMDir /r "$INSTDIR\data\portraits"
  RMDir /r "$INSTDIR\data\ui"
  RMDir /r "$INSTDIR\data\voices"
  Delete "$INSTDIR\data\catalog.json"
  RMDir "$INSTDIR\data"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  ReadRegStr $0 HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CoreLichtPreview" "InstallLocation"
  StrCmp $0 $INSTDIR 0 done
  Delete "$SMPROGRAMS\Core Licht\Core Licht.lnk"
  Delete "$SMPROGRAMS\Core Licht\Uninstall.lnk"
  RMDir "$SMPROGRAMS\Core Licht"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CoreLichtPreview"
  done:
SectionEnd
