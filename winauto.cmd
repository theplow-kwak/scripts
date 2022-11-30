echo off

set srcfolder=.\Win11_22H2_English_x64v1
set targetfile=.\Win11_22H2_English_x64v1.iso
if not [%1]==[] set srcfolder=%1
if not [%2]==[] set targetfile=%2

echo %srcfolder% %targetfile%
oscdimg.exe -bootdata:2#p0,e,b"%srcfolder%\boot\etfsboot.com"#pEF,e,b"%srcfolder%\efi\Microsoft\boot\efisys.bin" "%srcfolder%" "%targetfile%" -lCCCOMA_X64FRE_EN-US_DV9 -o -h -m -u2 -udfver102
