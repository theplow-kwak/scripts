@echo off

set FOLDER=WinPE_amd64
if not .%1 == . set FOLDER=%1
echo %FOLDER%
if .%2 == .recopy goto recopy

if not exist "C:\%FOLDER%\media\sources\boot.wim" (
    copype amd64 C:\%FOLDER%
	echo complete copype... Try run again the batch to continue..
)

@REM Mount the Windows PE boot image
set WinPE_Mount=C:\%FOLDER%\mount
Dism /Mount-Image /ImageFile:"C:\%FOLDER%\media\sources\boot.wim" /index:1 /MountDir:"%WinPE_Mount%"
IF %ERRORLEVEL% NEQ 0 (
	echo Mount the Windows PE boot image fail...
	goto :eof
)

@REM add packages
@rem Dism /Add-Package /Image:"%WinPE_Mount%" /PackagePath:"C:\Program Files (x86)\Windows Kits\10\Assessment and Deployment Kit\Windows Preinstallation Environment\amd64\WinPE_OCs\WinPE-WMI.cab"
@rem Dism /Add-Package /Image:"%WinPE_Mount%" /PackagePath:"C:\Program Files (x86)\Windows Kits\10\Assessment and Deployment Kit\Windows Preinstallation Environment\amd64\WinPE_OCs\WinPE-StorageWMI.cab"
Dism /Add-Package /Image:"%WinPE_Mount%" /PackagePath:"C:\Program Files (x86)\Windows Kits\10\Assessment and Deployment Kit\Windows Preinstallation Environment\amd64\WinPE_OCs\WinPE-NetFx.cab"
Dism /Add-Package /Image:"%WinPE_Mount%" /PackagePath:"C:\Program Files (x86)\Windows Kits\10\Assessment and Deployment Kit\Windows Preinstallation Environment\amd64\WinPE_OCs\WinPE-Scripting.cab"
Dism /Add-Package /Image:"%WinPE_Mount%" /PackagePath:"C:\Program Files (x86)\Windows Kits\10\Assessment and Deployment Kit\Windows Preinstallation Environment\amd64\WinPE_OCs\WinPE-PowerShell.cab"
Dism /Add-Package /Image:"%WinPE_Mount%" /PackagePath:"C:\Program Files (x86)\Windows Kits\10\Assessment and Deployment Kit\Windows Preinstallation Environment\amd64\WinPE_OCs\WinPE-DismCmdlets.cab"

@REM Add device drivers for QEMU (.inf files)
Dism /Add-Driver /Image:"%WinPE_Mount%" /Driver:"C:\Utility\winauto\ImageSource\$WinPEDriver$\amd64\w11\viostor.inf"
Dism /Add-Driver /Image:"%WinPE_Mount%" /Driver:"C:\Utility\winauto\ImageSource\$WinPEDriver$\amd64\w11\vioscsi.inf"
Dism /Add-Driver /Image:"%WinPE_Mount%" /Driver:"C:\Utility\winauto\ImageSource\$WinPEDriver$\NetKVM\amd64\netkvm.inf"
Dism /Add-Driver /Image:"%WinPE_Mount%" /Driver:"C:\Utility\winauto\ImageSource\$WinPEDriver$\vioserial\amd64\vioser.inf"
Dism /Add-Driver /Image:"%WinPE_Mount%" /Driver:"C:\Utility\winauto\ImageSource\$WinPEDriver$\viofs\amd64\viofs.inf"

for /D %%a in ("C:\Program Files\Python*") do set PPATH=%%a
if not ".%PPATH%" == "." (
	echo %PPATH%
	xcopy /y /q /s /I "%PPATH%\" "%WinPE_Mount%\Program Files\Python"
)
copy /y .\startnet.cmd %WinPE_Mount%\Windows\System32\
copy /y .\Unattend-PE.xml %WinPE_Mount%\
copy /y "C:\%FOLDER%\bootbins\efisys_noprompt.bin" "C:\%FOLDER%\bootbins\efisys.bin"

@REM unMount the Windows PE boot image
Dism /Unmount-Image /MountDir:"%WinPE_Mount%" /commit
IF %ERRORLEVEL% NEQ 0 (
	echo unMount the Windows PE boot image fail...
	goto :eof
)

makewinpemedia /iso /f C:\%FOLDER% C:\%FOLDER%\%FOLDER%.iso
goto :eof

:recopy
@REM copy WinRE.wim
Dism /Mount-Image /ImageFile:"C:\Utility\winauto\ImageSource\sources\install.wim" /index:6 /MountDir:"%WinPE_Mount%"
xcopy "%WinPE_Mount%\Windows\System32\Recovery\winre.wim" "C:\%FOLDER%\media\sources\boot.wim" /y
Dism /Unmount-Image /MountDir:"%WinPE_Mount%" /discard

:eof