echo off

set srcfolder=.\Win11_25H2
if not [%1]==[] set srcfolder=%1

For /F %%A in ("%srcfolder%") do (set target=%%~nxA)
set targetfile=z:\vm\cd\%target%_auto.iso
if not [%2]==[] set targetfile=%2

echo %srcfolder% %targetfile%
oscdimg.exe -bootdata:2#p0,e,b"%srcfolder%\boot\etfsboot.com"#pEF,e,b"%srcfolder%\efi\microsoft\boot\efisys.bin" "%srcfolder%" "%targetfile%" -lCCCOMA_X64FRE_EN-US_DV9 -o -h -m -u2
