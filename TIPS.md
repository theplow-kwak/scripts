# pre-install tools 

Ubuntu를 기본 설치 후 개발 작업을 진행하기 위해 필요한 package들을 미리 설치한다. 

```bash
sudo apt install make 
sudo apt install make-guile gcc g++ curl git dpkg-dev bison flex ncurses-dev libelf-dev
sudo apt install python python3 python-pip python3-pip python-tk python3-tk 
sudo apt install libgflags-dev

sudo apt install openjdk-8-jdk
sudo apt install maven
sudo apt install vagrant

sudo apt install libglib2.0-dev libpixman-1-dev libxen-dev libgtk-3-dev
```



# Kernel tracing on ubuntu

> https://wiki.ubuntu.com/Kernel/BuildYourOwnKernel#Obtaining_the_source_for_an_Ubuntu_release

## get kernel source 

```bash
apt source linux-headers-$(uname -r)
sudo apt build-dep linux-headers-$(uname -r)
```

## Depackage the kernel source

```
dpkg-source -x linux_4.15.0-38.41.dsc
```

## kernel tracing patch

download nvme_driver.diff to ~/

```bash
cd ~/linux-4.15.0
patch -p1 < ../nvme_driver.diff

diff -urN nvme_u1804_org/drivers/nvme linux-4.15.0/drivers/nvme > nvme_driver.diff
```


## build NVMe module driver 
> https://wiki.ubuntu.com/KernelCustomBuild

```bash
cd drivers/nvme
make -C /lib/modules/`uname -r`/build M=`pwd` modules
sudo make -C /lib/modules/`uname -r`/build M=`pwd` modules_install install

#make M=./drivers/nvme modules
#sudo make M=./drivers/nvme modules_install install

sudo depmod -a
```


## build kernel 

```bash
fakeroot debian/rules clean
(fakeroot debian/rules editconfigs) 
debian/rules build
fakeroot debian/rules binary-headers binary-generic binary-perarch
```


## enable kernel trace  

```bash
sudo sh -c 'echo 1 > /sys/kernel/debug/tracing/events/nvme/enable'
sudo sh -c 'echo 1 > /sys/kernel/debug/tracing/tracing_on'
sudo cat /sys/kernel/debug/tracing/trace_pipe | tee ./nvme.log
```



# nvme-cli 사용 예제

```bash
sudo nvme id-ctrl /dev/nvme0
sudo nvme dir-receive /dev/nvme0 -D 1 -O 1 -H
sudo nvme smart-log /dev/nvme0
```



# bcc 설치 

```bash
sudo apt install cmake clang libedit-dev llvm libclang-dev luajit libfl-dev
sudo apt install luajit luajit-5.1-dev
sudo apt install netperf iperf 

git clone https://github.com/iovisor/bcc.git
mkdir bcc/build; cd bcc/build
cmake .. -DCMAKE_INSTALL_PREFIX=/usr -DPYTHON_CMD=python3 -DLLVM_LIBRARY_DIRS=/usr/lib/llvm-7/lib
make -j `getconf _NPROCESSORS_ONLN`
sudo make install
```



# Example of fio test

```bash
fio --randrepeat=1 --ioengine=libaio --direct=1 --gtod_reduce=1 --name=test --filename=/mnt/nvme/test --bs=4k --iodepth=64 --size=4G --readwrite=randrw --rwmixread=75
fio --randrepeat=1 --ioengine=libaio --direct=1 --gtod_reduce=1 --name=test --filename=/mnt/nvme/test --bs=4k --iodepth=64 --size=4G --readwrite=randread 
```



# iol_interact-8.0 

```bash
sudo apt-get install runit
sudo apt-get install libxml++2.6-dev 
sudo apt-get install libboost-all-dev
sudo apt-get install doxygen
sudo apt-get install linux-headers-$(uname -r)
```

dnvme.ko build시에 gcc version이 맞지 않으면 insmod에서 error 발생 (kernel patch와 연관) -> ppa:ubuntu-toolchain-r/test 사용하면 안됨



# wine 설치

```
sudo apt install wine-stable ttf-mscorefonts-installer --install-recommends
sudo apt install fonts-nanum fonts-nanum-extra fonts-nanum-coding
sudo apt install wine64
```



# fix GitKraken invalid collation character error

added ```LC_ALL=C``` to the ```Exec=env``` line, in the file ```/var/lib/snapd/desktop/applications/gitkraken_gitkraken.desktop```

```
Exec=env LC_ALL=C BAMF_DESKTOP_FILE_HINT=/var/lib/snapd/desktop/applications/gitkraken_gitkraken.desktop /snap/bin/gitkraken %U
```



# Deleting a git commit

Git server에 지저분하게 커밋된것들을 다 지우고 필요한 항목만 선정하여 깨끝하게 다시 커밋하고 싶을때 사용.

## Example git log

| Number | Hash    | Commit Message                                         | Author       |
| ------ | ------- | ------------------------------------------------------ | ------------ |
| 1      | 2c6a45b | (HEAD) Adding public method to access protected method | Tom          |
| 2      | ae45fab | Updates to database interface                          | Contractor 1 |
| 3      | 77b9b82 | Improving database interface                           | Contractor 2 |
| 4      | 3c9093c | Merged develop branch into master                      | Tom          |
| 5      | b3d92c5 | Adding new Event CMS Module                            | Paul         |
| 6      | 7feddbb | Adding CMS class and files                             | Tom          |
| 7      | a809379 | Adding project to Git                                  | Tom          |

## Using Cherry Pick

**Step 1:** Find the commit before the commit you want to remove `git log`

**Step 2:** Checkout that commit `git checkout <commit hash>`

**Step 3:** Make a new branch using your current checkout commit `git checkout -b <new branch>`

**Step 4:** Now you need to add the commit after the removed commit `git cherry-pick <commit hash>`

**Step 5:** Now repeat Step 4 for all other commits you want to keep.

**Step 6:** Once all commits have been added to your new branch and have been commited. Check that everything is in the correct state and working as intended. Double check everything has been commited: `git status`

**Step 7:** Switch to your broken branch `git checkout <broken branch>`

**Step 8:** Now perform a hard reset on the broken branch to the commit prior to the one your want to remove `git reset --hard <commit hash>`

**Step 9:** Merge your fixed branch into this branch `git merge <branch name>`

**Step 10:** Push the merged changes back to origin. **WARNING: This will overwrite the remote repo!** `git push --force origin <branch name>`

You can do the process without creating a new branch by replacing **Step 2 & 3** with **Step 8** then not carry out **Step 7 & 9.**

### **Example**

Say we want to remove commits 2 & 4 from the repo.

1. `git checkout b3d92c5` Checkout the last usable commit.
2. `git checkout -b repair` Create a new branch to work on.
3. `git cherry-pick 77b9b82` Run through commit 3.
4. `git cherry-pick 2c6a45b` Run through commit 1.
5. `git checkout master` Checkout master.
6. `git reset --hard b3d92c5` Reset master to last usable commit.
7. `git merge repair` Merge our new branch onto master.
8. `git push --hard origin master` Push master to the remote repo.





# 레드햇에서 YUM 사용하는 방법

1. CD 이용하여 local repo 사용

   vim /etc/yum.repos.d/local.repo 

   ```
   [local-repo]
   name=Local Repository
   baseurl=file:///localrepo/
   enabled=1
   gpgcheck=0
   ```

2. CENTOS repo 사용하기

   vim /etc/yum.repos.d/rhel-source.repo

   ```
   [base]
   name=CentOS-$releasever - Base
   baseurl=http://mirror.kakao.com/centos/$releasever/os/$basearch/
   gpgcheck=1
   
   #released updates
   [update]
   name=CentOS-$releasever - Updates
   baseurl=http://mirror.kakao.com/centos/$releasever/updates/$basearch/
   gpgcheck=1
   ```

   ```bash
   sudo rpm --import http://mirror.kakao.com/centos/7/os/x86_64/RPM-GPG-KEY-CentOS-7 
   ```
   
   이후 yum repolist all 로 확인
   
   ```bash
   sudo yum --enablerepo=update clean metadata
   ```
   
   
   
3. CentOS 7.2: Yum repo configuration fails
   yum update 실행시 '[Errno 14] HTTP Error 404 - Not Found Trying other mirror.'  발생

   ```
   sudo mkdir -p /etc/yum/vars
   sudo sh -c 'echo 7.7.1908 > /etc/yum/vars/releasever'
   ```

   Replace "7.7.1908" with your own release version if you are having this problem and nothing else has worked. (7.6.1810)



# ftrace를 이용한 디버깅 방법

- call graph 출력

current_tracer에 function_graph를 설정하고 set_graph_function에 보고자 하는 function name을 설정한다.

function_graph를 종료하고 싶을때는 current_tracer에 nop를 설정

```bash
cd /sys/kernel/debug/tracing/
echo function_graph > current_tracer
echo scsi_queue_rq > set_graph_function
cat trace_pipe 
echo nop > current_tracer
```

```
echo 1 > /proc/sys/kernel/stack_tracer_enabled
stacktrace
```



# 유용한 shell script

```bash
for file in ~/projects/scripts/*.sh; do name=${file##*/}; ln -s $file ${name%%.*}; done
```

```bash
tar --exclude=".*" -czvf ssdsnoop.tar.gz ssdsnoop/
```



# Samba

## Ubuntu

[사용자 공유 기능 활성화](https://access.redhat.com/documentation/ko-kr/red_hat_enterprise_linux/8/html/deploying_different_types_of_servers/assembly_enabling-users-to-share-directories-on-a-samba-server_assembly_using-samba-as-a-server#doc-wrapper)

```bash
sudo apt install samba
sudo usermod -aG sambashare $USER
sudo smbpasswd -a $USER
sudo smbpasswd -e $USER
net usershare add home /home/$USER/ "" Everyone:F guest_ok=no
```



```bash
net usershare info
sudo smbstatus
```



## CentOS / RHEL 7 : Eable To Start The Samba Service

**Configure SELinux to allow SAMBA services**
In case if you do not want to disable SELinux, you can review the SELinux policy allowing the SAMBA subsystem to run. To check the current SELinux policies, use the below commands.

```
# getsebool -a | grep samba
# getsebool -a | grep nmb
```

This should give a list of options and whether these are on or off. They should be on. The settings can be changed using the commands given below.
Syntax :

```
# setsebool -P [boolean] on
```

For example:

```
# setsebool -P bacula_use_samba on
```



## Samba mount

```bash
cat << _EOF_ | sudo tee /etc/.smb.cred
username=<username>
password=<password>
domain=WORKGROUP
_EOF_
sudo chmod 600 /etc/.smb.cred
```

```bash
sudo apt install cifs-utils
```

```bash
sudo mount -t cifs -o credentials=/etc/.smb.cred,uid=$(id -u `whoami`),gid=$(id -g `whoami`),vers=3.0 //192.168.100.1/path_from ~/path_to
```



```bash
sudo mount -t cifs -o username=uname //10.0.2.4/qemu ./host
```

```bash
gio mount "smb://WORKGROUP;uname@10.0.2.2/home/"
```



## Windows 10에서 samba server 인증 안되는 경우 해결 방안

Windows 10에서 samba server에 연결이 안되고 계속 인증 에러가 나는 경우 발생. ubuntu에서 `sudo smbstatus`로 확인 결과 user name이 ***nobody***로 바뀌어 있다.

```
Samba version 4.8.4-Ubuntu
PID     Username     Group        Machine                                   Protocol Version  Encryption           Signing              
----------------------------------------------------------------------------------------------------------------------------------------
3406    nobody       nogroup      10.0.0.210 (ipv4:10.0.0.210:61267) SMB3_11           -                    -                    
```



- Ubuntu samba에서 설정하는 방법:

You can also fix this on the server (Ubuntu 18.04.1 LTS) side: In `/etc/samba/smb.conf`, put:

```
ntlm auth = true
```



- Windows에서 설정하는 방법:

if anyone else runs into this problem, my solution was to adjust the security policies on the Windows client.

`Run > Secpol.msc`

then I set Local Policies > Security Options > Network Security: LAN Manager authentication level to 'Send NTLMv2 response only. Refuse LM & NTLM'



- 조직의 보안 정책에서 인증되지 않은 게스트 액세스를 차단하므로 이 공유 폴더에 액세스할 수 없습니다.

https://vhrms.tistory.com/772

1. mmc 실행
2. 파일 > 스냅인 추가/제거 클릭 > 그룹 정책 개체 편집기 > 추가
3. 컴퓨터 구성 > 관리 템플릿 > 네트워크 > Lanman 워크스테이션 > 보안되지 않은 게스트 로그온 사용 > 사용



# QEMU

qemu를 사용하는데 유용한 tip



## How to create a bridge, named br0

The procedure to add a bridge interface on Linux is as follows when you want to use Network Manager.

```bash
_eth_device=$(nmcli -t -f DEVICE c show --active)
_eth_name=$(nmcli -t -f NAME c show --active)
_br_name="br0"
sudo nmcli con add ifname ${_br_name} type bridge con-name ${_br_name}
sudo nmcli con add type bridge-slave ifname ${_eth_device} master ${_br_name}
sudo nmcli con modify ${_br_name} bridge.stp no
sudo nmcli con down "${_eth_name}"
sudo nmcli con up ${_br_name}
```

https://www.cyberciti.biz/faq/how-to-add-network-bridge-with-nmcli-networkmanager-on-linux/

To view the bridge settings, issue the following command:

```bash
nmcli -f bridge con show br0
```



## libvirt network bridge 설정

아래 site를 참고하여 `libvirt-daemon-system`을 설치

> [Installation of KVM](https://help.ubuntu.com/community/KVM/Installation)

```bash
sudo apt-get install libvirt-daemon-system
```

The proper way fo changing address is using virsh. You can stop network (e.g. ifdown): (option)

```bash
sudo virsh net-destroy default
```

As you edited default.xml file this should be enough. But for editing you can use: 

```bash
sudo virsh net-edit default
```

And you can start it with: (option)

```bash
sudo virsh net-start default
sudo virsh net-autostart default
```

Find the IP addresses of VMs in KVM with virsh

```bash
virsh net-list
virsh net-info default
virsh net-dhcp-leases default
```



##  Bridged networking using qemu-bridge-helper

This method does not require a start-up script and readily accommodates multiple taps and multiple bridges. It uses `/usr/lib/qemu/qemu-bridge-helper` binary, which allows creating tap devices on an existing bridge.

First, create a configuration file containing the names of all bridges to be used by QEMU:

```
/etc/qemu/bridge.conf
--------------------------------------------
allow all
```

```
qemu ... NET="-nic bridge,br=br0,model=virtio-net-pci,mac=$macaddr" ...
```

https://wiki.archlinux.org/index.php/QEMU#Bridged_networking_using_qemu-bridge-helper



## Docker에서 'virbr0"에 연결하는 방법

First create the configuration file /etc/docker/daemon.json as suggested in the Docker documentation with the following content (the iptables line may not even be needed):

```
{
"bridge": "virbr0",
"iptables": false
}
```

Than you stop the containers and restart the docker daemon service:

```bash
systemctl restart docker
```



## ENHANCING VIRTUALIZATION WITH THE QEMU GUEST AGENT AND SPICE AGENT

### QEMU Guest Agent

```bash
sudo yum install qemu-guest-agent
sudo systemctl start qemu-guest-agent
```

```bash
GUEST_AGENT="\
-chardev socket,path=/tmp/qga.sock,server,nowait,id=qga0,name=qga0 \
-device virtio-serial \
-device virtserialport,chardev=qga0,name=org.qemu.guest_agent.0"
```



### SPICE AGENT

```bash
sudo yum install spice-vdagent
sudo systemctl start spice-vdagent
```

```bash
SPICE_AGENT="\
-chardev spicevmc,id=vdagent,name=vdagent \
-device virtio-serial \
-device virtserialport,chardev=vdagent,name=com.redhat.spice.0"
```

## virtiofs

mount virtiofs in linux: 

```bash
sudo mount -t virtiofs hostfs ~/host/
```

## i386 apt

- sudo dpkg --add-architecture i386
- sudo dpkg --remove-architecture i386
- dpkg --get-selections | awk '/i386/{print $1}'
- sudo dpkg --purge --force-remove-protected {???,111,222}:i386



# Jenkins

## Jenkins docker 설치

```bash
docker pull jenkins
```



## Jenkins 실행

```bash
docker run -d -p 8080:8080 -v /jenkins:/var/jenkins_home --network host --name jenkins -u root jenkins
```

- host에 ***/jenkins*** folder를 생성하고 이를 docker의 ***jenkins_home***으로 binding한다  
- Jenkins를 처음 시작시 필요한 initial password는 다음 파일에서 찾을 수 있다 : 
  ***/jenkins/secrets/initialAdminPassword*** 

첫번째 실행 종료 후 재 실행시에는 ```docker start jenkins```를 사용한다.



jenkins.war를 직접 실행하는 방법

```bash
cd /home/qa-tools/jenkins/apache-tomcat-8/webapps/
java -jar jenkins.war &
```



## Jenkins shell 연결

```bash
docker exec -it -u 0 jenkins /bin/bash
```



## Plug-in 설치

필요한 plug-in

- P4 Plugin
- Build Failure Analyzer
- Build Monitor View
- 



## 

## Jenkins and python

> [Jenkins에서 파이썬 출력을 실시간으로 보고싶다면?](https://taetaetae.github.io/2018/12/02/python-buffer/)
>
> [Python + Jenkins 연동](https://tomining.tistory.com/147)



## Jenkins plugin



```bash
mvn -DdownloadSources=true -DdownloadJavadocs=true -DoutputDirectory=target/eclipse-classes -Declipse.workspace=${HOME}/eclipse-workspace eclipse:eclipse eclipse:configure-workspace
```

```bash
pip install jenkins
pip install ConfigObj
pip install python-jenkins
pip install wcmatch
```





# SQL Server 

## Docker를 이용한 SQL server 설치



In the first step, we will pull the SQL Server 2019 container image from the Microsoft syndicates container catalog (mcr.microsfoft.com)

```bash
docker pull mcr.microsoft.com/mssql/server:2017-latest
```



Run the below command with some configuration options:


```bash
docker run -d -e 'ACCEPT_EULA=Y' -e 'SA_PASSWORD=password' --network host --name mssql -v /home/uname/vm/docker/mssql:/var/opt/mssql mcr.microsoft.com/mssql/server:2017-latest
```
- -e ‘SA_PASSWORD : Specify the sa password
- -p: Specify the port address in the format of 1433:1433 which means TCP 1433 port on both the container and the host
- –name: name for the container
- –V: mount a volume for the installation



Connect to Microsoft SQL Server You can connect to the SQL Server using the sqlcmd tool inside of the container by using the following command on the host

```bash
docker exec -it mssql /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P 'password'
```



SQL command를 사용하여 test는 방법

```
tsql -H 127.0.0.1 -p 1433 -U sa -P 'password'
tsql -H 10.0.0.114 -p 1433 -U sa -P 'password'
```



CREATE DATABASE 'sse_db'

select * FROM INFORMATION_SCHEMA.TABLES

select * from information_schema.columns where table_name = 'ovt'



참고:

> [Install SQL Server 2019 on Ubuntu Docker](https://www.sqlshack.com/sql-server-2019-on-linux-with-a-docker-container-on-ubuntu/)
>
> [Official images for Microsoft SQL Server on Linux for Docker Engine](https://hub.docker.com/_/microsoft-mssql-server)



## DB 사용법

### DB 생성





### Table 생성



## Azure Data Studio 설치

> [Azure Data Studio 다운로드 및 설치](https://docs.microsoft.com/ko-kr/sql/azure-data-studio/download-azure-data-studio?view=sql-server-ver15)



# Windows 관련

## Windows server 설정

- Network static IP setting:

  ```powershell
  netsh -c interface ip set address name='Embedded LOM 1 Port 1' source=static addr=$ipaddr mask=255.255.255.0 gateway=10.0.1.1 gwmetric=0
  sleep 5
  netsh -c interface ip set dns name='Embedded LOM 1 Port 1' source=static addr=10.0.0.61 register=PRIMARY
  netsh -c interface ip add dns name='Embedded LOM 1 Port 1' addr=10.0.0.64 index=2
  netsh interface ip show config
  ```



- samba mount

  ```powershell
  New-SmbMapping -LocalPath 'X:' -RemotePath '\\remote_server\shared_folder' -UserName 'username' -Password 'password'
  ```



- 인증서 import

  ```powershell
  Import-Certificate -FilePath 'x:\vm\share\yourCertificate.crt' -CertStoreLocation Cert:\LocalMachine\Root
  ```

  

- Install OpenSSH using PowerShell

  ```powershell
  Get-WindowsCapability -Online -Name 'OpenSSH*' | Add-WindowsCapability -Online
  ```

  

- Download  latest OpenSSH from github

  ```powershell
  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
  $url = 'https://github.com/PowerShell/Win32-OpenSSH/releases/latest/'
  $request = [System.Net.WebRequest]::Create($url)
  $request.AllowAutoRedirect=$false
  $response=$request.GetResponse()
  $openssh_url = $([String]$response.GetResponseHeader("Location")).Replace('tag','download') + '/OpenSSH-Win64.zip'  
  
  wget $openssh_url
  ```

  

- Using PowerShell to Unzip Files

  ```powershell
  if ( -not (Test-Path -Path 'C:\Program Files\OpenSSH-Win64\' -PathType Container ) ) 
  {
      Expand-Archive -LiteralPath '.\OpenSSH-Win64.zip' -DestinationPath 'C:\Program Files\' InvoicesUnzipped
  }
  ```



- start SSH service 

  ```powershell
  Set-Service -Name sshd -StartupType 'Automatic'
  Set-Service -Name ssh-agent -StartupType 'Automatic'
  Start-Service sshd
  Start-Service ssh-agent
  Get-Service -Name *ssh* | select DisplayName, Status, StartType
  ```



- SSH connection을 받을 수 있도록 Firewall rule 설정

  ```powershell
  New-NetFirewallRule -Name sshd -DisplayName 'OpenSSH Server (sshd)' -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22
  New-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShell -Value "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -PropertyType String -Force
  ```



- 자동 로그인 설정

  netplwiz를 실행하여 



* Could not find the recovery environment

  ```
  reagentc /enable
  reagentc /info
  ```



## Windows 10 WSL 2 설치

Command line으로 Windows 10 WSL 2 설치하기

> [Manually download Windows Subsystem for Linux distro packages](https://docs.microsoft.com/en-us/windows/wsl/install-manual)



Manually download Windows Subsystem for Linux distro packages 

```powershell
curl.exe -L -o ubuntu-1804.appx https://aka.ms/wsl-ubuntu-1804
```



Installing your distro

```powershell
Add-AppxPackage .\ubuntu-1804.appx
```



check Locate the VHD file fullpath used by your WSL 2 installation

```powershell
$PackageFamilyName = (Get-AppxPackage -Name "*ubuntu*").PackageFamilyName
dir $env:LOCALAPPDATA\Packages\$PackageFamilyName\LocalState\
```



## Enable the access to network drives from elevated apps running as administrator

1. Open [Registry Editor](https://winaero.com/blog/windows-registry-editor-for-dummies/).
2. Go to the following Registry key:

```text
HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System
```

3. Create a new DWORD value called **EnableLinkedConnections**, and set it to 1
4. Restart your PC and you are done.



## Default login 

```
HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon
```

String value DefaultUserName, DefaultPassword

## Dual Boot Windows with Virtual Hard Disk (VHDX)

[Boot to a virtual hard disk: Add a VHDX or VHD to the boot menu]: https://docs.microsoft.com/en-us/windows-hardware/manufacture/desktop/boot-to-vhd--native-boot--add-a-virtual-hard-disk-to-the-boot-menu?view=windows-11
[Native Boot Windows 11 Virtual Hard Disk (VHDX)]: https://www.elevenforum.com/t/native-boot-windows-11-virtual-hard-disk-vhdx.611/



# Python 참고

## PIP Certification 

### Using a certificate as parameter

```py
$ pip install --cert /path/to/mycertificate.crt packagename
```

### Using a certificate in a `pip.conf`

Create this file:

```py
$HOME/.pip/pip.conf (Linux)

%HOME%\pip\pip.ini (Windows)
```

and add these lines:

```py
cat << _EOF_ | tee .pip/pip.conf
[global]
cert = /path/to/mycertificate.crt
_EOF_
```

### Set the configuration in Windows

```text
# Windows
pip config set global.cert %USERPROFILE%\certs\ca-bundle.crt
pip config list
```

### Ignoring certificate and using HTTP

```py
$ pip install --trusted-host pypi.python.org packagename
```

### Ignoring certificate and using HTTP in a pip.conf

Create this file:

```py
$HOME/.pip/pip.conf (Linux)

%HOME%\pip\pip.ini (Windows)
```

and add these lines:

```py
cat << _EOF_ | tee .pip/pip.conf
[global]
trusted-host = pypi.python.org
               files.pythonhosted.org
_EOF_
```



## PIP upgrade 

PIP upgrade pip itself

```bash
pip install --upgrade pip
```



PIP upgrade all packages

```bash
pip freeze | cut -d'=' -f1 | xargs pip install --upgrade
```



pip upgrade 도중 library가 없어 에러가 발생하는 경우 아래 package 설치 필요

```bash
sudo apt install libgirepository1.0-dev libcairo2-dev librsync-dev libcups2-dev libgpgme-dev swig
sudo apt install build-essential libdbus-glib-1-dev libgirepository1.0-dev
```



## jupyter lab 설치

```bash
pip install jupyterlab
```



# Perforce 

## p4v 설치 방법

Perforce's package repositories allow simplified installation of Perforce products and product updates on popular Linux platforms. 

### 1. Ubuntu

```bash
wget -qO - https://package.perforce.com/perforce.pubkey | sudo gpg --dearmor -o /usr/share/keyrings/perforce-archive-keyring.gpg

echo "deb [signed-by=/usr/share/keyrings/perforce-archive-keyring.gpg] http://package.perforce.com/apt/ubuntu focal release" | sudo tee /etc/apt/sources.list.d/perforce.list

sudo apt update && sudo apt install helix-cli
```

### 2. RHEL

1. Add Perforce's repository to your YUM configuration.

Create a file called `/etc/yum.repos.d/perforce.repo` with the following content:

```
[perforce]
name=Perforce
baseurl=http://package.perforce.com/yum/rhel/7/x86_64/
enabled=1
gpgcheck=1
```

2. Add Perforce's packaging key to your RPM keyring:

```bash
sudo rpm --import https://package.perforce.com/perforce.pubkey
```

3. install 

```bash
sudo yum install helix-cli
```



> [Perforce Packages](https://www.perforce.com/perforce-packages)



## P4 client 설정

1. `.p4config` 파일을 아래 내용으로 생성 : 

```
P4CLIENT=p4client
P4USER=p4user
P4PASSWD=p4password
P4PORT=p4.port.com:1666
```



2. '`P4CONFIG`' 환경 변수 설정

```bash
export P4CONFIG=~/.p4config
export P4CLIENT=p4client
```

```text
/etc/profile.d/p4config.sh
  P4CONFIG=.p4config
  export P4CONFIG
```



3. '`p4 client`' 설정

```bash
p4 client -i << _EOF
Client:     ${P4CLIENT}
Root:       ${HOME}/
Options:  allwrite clobber nocompress unlocked nomodtime normdir
View:       //SQA/... //${P4CLIENT}/SQA/...
_EOF
```



4. client 확인: 

```bash
p4 client -o ${P4CLIENT}
```



5. '`p4 sync`'  실행.  or '`p4 sync -f`'



# ca-certification

- 'git clone' 시 fail 회피 방안

  - fatal: unable to access 'https://example.com/path/to/git': SSL certificate problem: EE certificate key too weak

  - `-c http.sslVerify=false`  사용

    ```bash
    git -c http.sslVerify=false clone https://example.com/path/to/git
    ```
    
    or 
    
    ```bash
    git config --global http.sslVerify false
    ```
    
    

- 'wget' 사용시 fail 회피 방안

  - WARNING: The certificate of ‘dl.google.com’ is not trusted.
    WARNING: The certificate of ‘dl.google.com’ was signed using an insecure algorithm.

  - `--no-check-certificate` 사용

    ```bash
    wget --no-check-certificate https://dl.google.com/linux/direct/google-chrome-stable_current_`uname -m`.rpm
    ```

    

# mvn 개발 환경 설정



```bash
export VER="3.6.3"
wget http://www-eu.apache.org/dist/maven/maven-3/${VER}/binaries/apache-maven-${VER}-bin.tar.gz
tar xvf apache-maven-${VER}-bin.tar.gz  
sudo mv apache-maven-${VER} /opt/maven
cat <<EOF | sudo tee /etc/profile.d/maven.sh
export MAVEN_HOME=/opt/maven
export PATH=\$PATH:\$MAVEN_HOME/bin
EOF
source /etc/profile.d/maven.sh
```



```bash
cd hello-plugin/
mvn -U archetype:generate -Dfilter="io.jenkins.archetypes:"
cd hello/
mvn verify
cd target/
sudo cp -rf hello hello.hpi /jenkins/plugins/
```



```bash
mvn -DdownloadSources=true -DdownloadJavadocs=true -Declipse.workspace=$HOME/eclipse-workspace eclipse:eclipse eclipse:configure-workspace
echo $JAVA_HOME
which java
export JAVA_HOME=$(dirname $(dirname $(readlink -f /usr/bin/java)))
echo $JAVA_HOME
mvn hpi:run
mvn verify
mvn clean
```



# Ubuntu

## Ubuntu repository 변경

apt repository를 'mirror.kakao.com'으로 변경

```bash
sudo sed -i -re 's/([a-z]{2}\.)?archive.ubuntu.com|security.ubuntu.com|extras.ubuntu.com/mirror.kakao.com/g' /etc/apt/sources.list
```

disco repository는 old-releases.ubuntu.com로 변경

```bash
sudo sed -i -re 's/([a-z]{2}\.)?archive.ubuntu.com|security.ubuntu.com|extras.ubuntu.com/old-releases.ubuntu.com/g' /etc/apt/sources.list
```



## Barrier 설정

barrier 설치

```bash
sudo apt install barrier
```

booting시 barrier 자동 실행: 

아래의 full cli command를 `시작프로그램`에 새 항목으로 추가

```bash
$ ps aux | grep barrier
uname      1926  0.5  0.0  98868  9360 ?        Sl   08:58   0:04 /usr/bin/barrierc -f --debug INFO --name uname-AORUS --enable-crypto [10.0.0.150]:24800
```

```bash
client:
/snap/barrier/384/usr/bin/barrierc -f --no-tray --debug INFO --name test-X570-AORUS-ELITE --enable-crypto [10.0.0.150]:24800
server:
/snap/barrier/384/usr/bin/barriers -f --no-tray --debug INFO --name uname-AORUS --enable-crypto -c /home/uname/barrier.conf --address :24800
```

ERROR: ssl certificate doesn't exist: /home/test/.local/share/barrier/SSL/Barrier.pem

```bash
cd /home/test/.local/share/barrier/SSL/
openssl req -x509 -nodes -days 365 -subj /CN=Barrier -newkey rsa:4096 -keyout Barrier.pem -out Barrier.pem
```


## Fix Time Differences in Ubuntu & Windows 10 Dual Boot

**Disable UTC and use Local Time in Ubuntu**

```bash
timedatectl set-local-rtc 1 --adjust-system-clock
```



## How to Change MAC Address on Ubuntu

https://www.wikihow.com/Change-MAC-Address-on-Ubuntu

```
ip link show
sudo ip link set dev xxxx down 
sudo ip link set dev xxxx address xx:xx:xx:xx:xx:xx 
sudo ip link set dev xxxx up
```



## OS disk 이동

Ubuntu 설치 디스크를 다른 디스크로 변경하려고 한다. 

 ```
mkdir src dest
sudo mkfs.ext4 /dev/nvme1n1p2
sudo mount -o loop /dev/nvme0n1p2 src/
sudo mount -o loop /dev/nvme1n1p2 dest/
cd dest/
sudo cp -av ../src/* .
cd ..
sudo umount src dest
 ```



## NTFS mount 

For my case, The command `sudo dmesg | tail` shows:

```
ntfs3: Unknown parameter 'windows_names'
```

It seems the new `ntfs3` driver does not support the 'windows_names' flag anymore. Base on [this suggestion](https://github.com/storaged-project/udisks/pull/917#issuecomment-962596147) I made `/etc/udisks2/mount_options.conf` file containing:

```text
[defaults]
ntfs_defaults=uid=$UID,gid=$GID
ntfs_allow=uid=$UID,gid=$GID,nls,umask,dmask,fmask,nohidden,sys_immutable,discard,force,sparse,showmeta,prealloc,no_acs_rules,acl,noatime
```


## Ubuntu upgrade 

```bash
sudo apt remove snapd
sudo apt autoremove
sudo apt update && sudo apt dist-upgrade
sudo apt install update-manager-core
sudo sed -i 's/=lts/=normal/g' /etc/update-manager/release-upgrades
do-release-upgrade
```

## NVMe Multipath 

```bash
sudo multipath -ll
sudo multipath -F
systemctl disable multipathd
systemctl stop multipathd
```



## Bluetooth Pairing on Dual Boot of Windows & Linux

Use `chntpw` from your Linux distro (easier). Start in a terminal then:

1. `sudo apt-get install chntpw`

2. Mount your Windows system drive

3. `cd /[WindowsSystemDrive]/Windows/System32/config`

4. `chntpw -e SYSTEM` opens a console

5. Run these commands in that console:

   ```
   > cd CurrentControlSet\Services\BTHPORT\Parameters\Keys
   > # if there is no CurrentControlSet, then try ControlSet001
   > # on Windows 7, "services" above is lowercased.
   > ls
   # shows you your Bluetooth port's MAC address
   Node has 1 subkeys and 0 values
     key name
     <aa1122334455>
   > cd aa1122334455  # cd into the folder
   > ls  
   # lists the existing devices' MAC addresses
   Node has 0 subkeys and 1 values
     size     type            value name             [value if type DWORD]
       16  REG_BINARY        <001f20eb4c9a>
   > hex 001f20eb4c9a
   => :00000 XX XX XX XX XX XX XX XX XX XX XX XX XX XX XX XX ...ignore..chars..
   # ^ the XXs are the pairing key
   ```

6. Make a note of which Bluetooth device MAC address matches which pairing key. The Mint/Ubuntu one won't need the spaces in-between.  Ignore the `:00000`.

Go back to Linux

1. Switch to root: `su -`


2. cd to your Bluetooth config location `/var/lib/bluetooth/[bth port  MAC addresses]`

3. Here you'll find folders for each device you've paired with. The folder names being the Bluetooth devices' MAC addresses and contain a single file `info`. In these files, you'll see the link key you need to replace with your Windows ones, like so:

   ```
   [LinkKey]
   Key=B99999999FFFFFFFFF999999999FFFFF
   ```



# Cloud-image

## Prepare Cloud Image

Download CentOS Cloud Images from https://cloud.centos.org/centos/7/images/



Create a snapshot so that we can branch from this disk image without affecting the parent.  We will also use this opportunity to increase the root filesystem from 8G to 10G.

```bash
qemu-img create -f qcow2 -F qcow2 -b CentOS-8-GenericCloud-8.2.2004-20200611.2.aarch64.qcow2 centos-8.3.qcow2
qemu-img resize centos-8.3.qcow2 60G
qemu --arch aarch64 --connect ssh --net bridge --uname test centos-8.3.qcow2 cloud_init.iso
qemu --arch aarch64 --connect ssh --net bridge --uname test centos-8.3.qcow2 
```



## Create ssh keypair

```bash
ssh-keygen -t rsa
```



## Install virt-customize on Linux

```bash
sudo apt -y install libguestfs-tools
```



## Setup/inject an ssh keys

```bash
sudo virt-customize -a centos-2003.qcow2 --ssh-inject centos:file:/home/uname/.ssh/id_rsa.pub
```



## Create cloud-init configuration

Create a file named “cloud_init.cfg” with the below content.

```text
#cloud-config
hostname: <host_name>
users:
  - name: <your_user>
    groups: wheel
    lock_passwd: false
    passwd: <your_passord_hash>
    shell: /bin/bash
    sudo: ['ALL=(ALL) NOPASSWD:ALL']
    ssh-authorized-keys:
      - <your_public_ssh_key>
ssh_pwauth: false
disable_root: false
package_upgrade: true
packages:
  - qemu-guest-agent
runcmd:
  - [ sh, -c, 'touch /etc/cloud/cloud-init.disabled' ]
  - [ sh, -c, 'sudo poweroff' ]
final_message: "The system is finally up, after $UPTIME seconds"
```

Now we generate a seed disk that has the cloud-config metadata.

```text
cloud-localds -v cloud_init.iso cloud_init.cfg 
```



## ssh key setting

```bash
ssh-copy-id user@server.com
```



## Correct SSH Permission denied

The only real difference was some security context differences on files and directories between those that worked and those that didn't.

```bash
sudo ls -laZ <user-home>/.ssh
```

You should see some ssh_home_t and user_home_t attributes. If you don't, use the chcon command to add the missing attributes.

```bash
home="$(getent passwd <user> | cut -d: -f6)"
sudo chcon -R unconfined_u:object_r:ssh_home_t:s0 "$home"/.ssh
sudo chcon unconfined_u:object_r:user_home_t:s0 "$home"
```

```bash
restorecon -r -v -F /home/centos/.ssh
```



## Centos

### cloud image

- CentOS Stream EL9

download CentOS Stream9 from https://www.centos.org/download/

- Install Linux Kernel 6.5 on CentOS Stream EL9

```bash
sudo dnf upgrade --refresh
sudo rpm --import https://www.elrepo.org/RPM-GPG-KEY-elrepo.org
sudo dnf install https://www.elrepo.org/elrepo-release-9.el9.elrepo.noarch.rpm -y
dnf list available --disablerepo='*' --enablerepo=elrepo-kernel
sudo dnf --enablerepo=elrepo-kernel install kernel-ml -y
```

- Disable SELinux Permanently

```bash
sudo grubby --update-kernel ALL --args selinux=0
sudo reboot
```



### Install Centos aarch64 GPG key 

```bash
sudo rpm --import https://www.centos.org/keys/RPM-GPG-KEY-CentOS-7-aarch64
```



## virbr dhcp 확인

sudo virsh net-start default

virsh net-list
virsh net-info default
virsh net-dhcp-leases default



# msys64

https://www.msys2.org/

1. Download and install: [msys2-x86_64-20210604.exe](https://repo.msys2.org/distrib/x86_64/msys2-x86_64-20210604.exe)
2. place *.crt in /etc/pki/ca-trust/source/anchors and run update-ca-trust
3. or C:\msys64\usr\ssl\certs\ca-bundle.trust.crt, ca-bundle.crt 에 추가
4. Update the package database and base packages. 
   1. pacman -Syu
   2. pacman -Su
   3. pacman -S --needed base-devel mingw-w64-x86_64-toolchain
   4. pacman -S mingw-w64-x86_64-rust
   5. pacman -S git



# pciutils for windows 

https://edwinwang.com/2011/04/compile-pciutils-lspci-setpci-in-windows-x86%EF%BC%8C%E5%9C%A8-windows-x86-%E5%B9%B3%E5%8F%B0%E4%B8%8B%E7%BC%96%E8%AF%91-pciutils-%EF%BC%88lspci-setpci%EF%BC%89/

1. MinGW-full-gcc-4.2.5-Dec-2010.7z  압축 풀기
2. MinGW/home/test/pciutils  에 pciutils-3.5.5.tar.gz 풀기
3. patch file 적용 -> patch < pciutils-crosscompile.patch
4. win32의 configh, config.mk를 lib에 copy
4. make 



# network 

https://ubuntu.com/server/docs/network-configuration

```bash
sudo lshw -class network
ip link set dev enp0s25 up
ip link set dev enp0s25 down
```

```bash
sudo dhclient eth0
```



# VS Code

