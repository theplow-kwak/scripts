
# Create WinPE image
Client를 실행할 WinPE image를 작성. (makepe.cmd)
- Download and install the Windows ADK: https://learn.microsoft.com/en-us/windows-hardware/get-started/adk-install
	- Windows ADK 10.1.26100.2454 (December 2024)
	- Windows PE add-on for the Windows ADK 10.1.26100.2454 (December 2024)
- C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Windows Kits\Windows ADK\Deployment and Imaging Tools Environment 로 command 창을 연다.
- makepe.cmd 실행


## 설치가 필요한 package:

- WinPE-WMI.cab
- WinPE-NetFx.cab
- WinPE-Scripting.cab
- WinPE-PowerShell.cab
- WinPE-StorageWMI.cab
- WinPE-DismCmdlets.cab


## Auto startup program

WinPE의 "\Windows\System32\startnet.cmd" file이 부팅시에 자동으로 실행된다. 필요한 내용은 이 파일에 추가

- X:\Windows\System32\startnet.cmd
  	wpeinit -unattend:"X:\Unattend-PE.xml"
    	set PATH=%PATH%;"X:\Program Files\Python\"


## Disable the firewall
Unattend-PE.xml file에서 firewall 설정을 false로 수정:

- ​	<EnableFirewall>false</EnableFirewall>

## 추가 설정

- Python Windows embeddable package (64-bit)를 다운 받아 "\Program Files\Python"에 copy
- WinPE.iso 부팅시에 'press any key'를 방지하기 위해 'efisys_noprompt.bin' file을 PE image에 copy