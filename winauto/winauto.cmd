echo off

set target=Win11_22H2_English_x64v1
if not [%1]==[] set target=%1

set srcfolder=.\ImageSource
set targetfile=.\%target%_auto.iso

if not [%2]==[] set targetfile=%2

echo %srcfolder% %targetfile%
oscdimg.exe -bootdata:2#p0,e,b"%srcfolder%\boot\etfsboot.com"#pEF,e,b"%srcfolder%\efi\Microsoft\boot\efisys.bin" "%srcfolder%" "%targetfile%" -lCCCOMA_X64FRE_EN-US_DV9 -o -h -m -u2 -udfver102
