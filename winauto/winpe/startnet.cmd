wpeinit -unattend:"X:\Unattend-PE.xml"
set PATH=%PATH%;"X:\Program Files\Python\"
ping 192.168.100.100
net use z: \\192.168.100.100\home /user:test qwerqwer
pushd Z:\
@rem .\receiver.exe -d 0