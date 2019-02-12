# Virtual Open-Channel SSD

## pre-install tools 
```bash
sudo apt install make cmake
sudo apt install make-guile gcc g++ curl git dpkg-dev bison flex ncurses-dev libelf-dev
sudo apt install python python3 python-pip python3-pip python-tk python3-tk 
sudo apt install libgflags-dev pkg-config

sudo apt install openjdk-8-jdk
sudo apt install maven
sudo apt install vagrant

sudo apt install libglib2.0-dev libpixman-1-dev libcap-dev libxen-dev libgtk-3-dev 
sudo apt install libspice-server-dev libattr1 libattr1-dev libsnappy-dev libaio-dev
sudo apt install debootstrap dracut-core
```



## Custom kernel for Open-channel SSD

lightnvm subsystem이 포함된 커널 소스를 다운 받는다

```bash
git clone https://github.com/OpenChannelSSD/linux.git linux-ocssd
```

커널 config 파일에서 virtio와 pblk 관련 항목을 설정하고 kernel build를 할 것이다. base로 사용할 config file을 복사 후 olddefconfig를 수행하여 default 설정 값을 setting한다. 

```bash
cp /boot/config-$(uname -r) .config
make olddefconfig
```

생성된 .config file에서 필요한 아래 항목을 수정

```
CONFIG_NVM_PBLK=y
CONFIG_VETH=y
CONFIG_VIRTIO_PCI=y
CONFIG_VIRTIO_BLK=y
CONFIG_VIRTIO_NET=y
CONFIG_9P_FS=y

CONFIG_DRM=y
CONFIG_PCI=y
CONFIG_MMU=y
CONFIG_DRM_QXL=y
CONFIG_MOUSE_PS2=y
CONFIG_MOUSE_PS2_VMMOUSE=y
CONFIG_SERIO_I8042=y

```

kernel을 build하여 bzImage 생성한다. 생성된 kernel image는 QEMU 부팅 시 사용한다.  

```bash
make prepare
make scripts
make -j `getconf _NPROCESSORS_ONLN` bzImage LOCALVERSION=-ocssd
```

필요한 경우 modules를 build 하고 rootfs에 설치한다. 이때 대상 경로는 VM disk image가 mount 된 위치이다.

```bash
make -j `getconf _NPROCESSORS_ONLN` modules LOCALVERSION=-ocssd
sudo INSTALL_MOD_PATH=${HOME}/vm/rootfs make modules_install
```

debian package image가 필요한 경우 빌드하는 방법 (option)

```bash
make -j `getconf _NPROCESSORS_ONLN` bindeb-pkg LOCALVERSION=-ocssd
```





## QEMU Development Environment

### Compiling & Installing QEMU

```bash
git clone https://github.com/OpenChannelSSD/qemu-nvme.git

cd qemu-nvme
./configure --enable-kvm --target-list=x86_64-softmmu --enable-linux-aio \
--disable-werror --disable-xen --prefix=$HOME/${PWD##*/} --enable-gtk --enable-spice \
--enable-virtfs --enable-vhost-net --enable-modules --enable-snappy \
--enable-debug --extra-cflags="-g3" --extra-ldflags="-g3" --disable-stack-protector \
--enable-trace-backends=simple --with-git='tsocks git' 

make -j `getconf _NPROCESSORS_ONLN`
make install
```



### Configuring the virtual open-channel SSD drive

* Create OCSSD backend file

```bash
dd if=/dev/zero of=ocssd_backend.img bs=1M count=16384
```

* QEMU parameter

```
Linux/Multiboot boot specific:
-kernel bzImage use 'bzImage' as kernel image
-append cmdline use 'cmdline' as kernel command line
-initrd file    use 'file' as initial ram disk
-dtb    file    use 'file' as device tree image
```

* run QEMU

```bash
QEMU="${HOME}/qemu-nvme/bin/qemu-system-x86_64"
OPT="-m 8G -smp 8 --enable-kvm -vga qxl"
KERNEL="-kernel ${HOME}/projects/linux-ocssd/arch/x86_64/boot/bzImage"

USERVERCD="-cdrom ${HOME}/vm/cd/ubuntu-18.10-live-server-amd64.iso"
UBUNTUCD="-cdrom ${HOME}/vm/cd/ubuntu-18.04.1-desktop-amd64.iso"
WINCD="-cdrom ${HOME}/vm/cd/Win10_1809Oct_Korean_x64.iso"

OCSSD="-drive file=${HOME}/vm/image/ocssd_backend.img,id=myocssd,format=raw,if=none \
-device nvme,drive=myocssd,serial=deadbeef,lnum_pu=4,lstrict=1,meta=16,mc=3"
GEMINI="-object iothread,id=iothread0 \
-drive file=/dev/nvme0n1,if=none,format=raw,discard=unmap,aio=native,cache=none,id=hd0 \
-device virtio-blk-pci,drive=hd0,scsi=off,config-wce=off,iothread=iothread0"
ROOTFS="-object iothread,id=iothread1 \
-drive file=rootfs.img,if=none,format=raw,discard=unmap,aio=native,cache=none,id=hd0 \
-device virtio-blk-pci,drive=hd0,scsi=off,config-wce=off,iothread=iothread1"
BOOTP="-object iothread,id=iothread2 \
-drive file=boot.img,if=none,format=raw,discard=unmap,aio=native,cache=none,id=hd1 \
-device virtio-blk-pci,drive=hd1,scsi=off,config-wce=off,iothread=iothread2"

SHARE="-virtfs local,id=fsdev0,path=${HOME}/vm/share,security_model=passthrough,writeout=writeout,mount_tag=sharepoint"
NET="-netdev user,id=vmnic,hostfwd=tcp::5555-:22 -device virtio-net,netdev=vmnic"

VNC="-vnc localhost:1"
SPICE="-vga qxl -spice port=3001,disable-ticketing"
SERIAL="-chardev socket,id=console1,path=/tmp/console1,server,nowait -device spapr-vty,chardev=console1"
QEMU3="${HOME}/qemu3/bin/qemu-system-x86_64"

sudo $QEMU $OPT $UBUNTUCD $OCSSD $SHARE $NET $ROOTFS $KERNEL -append "root=/dev/vda vga=0x380"

```

etc

```bash
-boot d
-initrd /boot/initrd.img-4.18.0-11-generic 

sudo $QEMU $OPT $UBUNTUCD $OCSSD $SHARE $NET $GEMINI $KERNEL -append "root=/dev/vda vga=0x380"
```



* connect to spice

```bash
remote-viewer spice://localhost:3001
```

- connect to Geust with SSH

```bash
ssh localhost -p 5555
```



## Setup an Ubuntu system from Debian

### Base image 생성

debootstrap을 이용하여 rootfs.img file에 ubuntu를 설치한다

```bash
_IMGFILE="./image/rootfs.img"
_TARGETDIR="./rootfs"

dd if=/dev/zero of=$_IMGFILE bs=1M count=32768
mkfs.ext4 $_IMGFILE
sudo mount -o loop $_IMGFILE $_TARGETDIR
sudo debootstrap --verbose --arch amd64 bionic $_TARGETDIR http://archive.ubuntu.com/ubuntu
```

fstab 설정

```bash
cat << '___EOF___' | sudo dd of=./rootfs/etc/fstab
# UNCONFIGURED FSTAB FOR BASE SYSTEM
#
/dev/vda        /               ext3    defaults        1 1
dev             /dev            tmpfs   rw              0 0
tmpfs           /dev/shm        tmpfs   defaults        0 0
devpts          /dev/pts        devpts  gid=5,mode=620  0 0
sysfs           /sys            sysfs   defaults        0 0
proc            /proc           proc    defaults        0 0
___EOF___
```

hostname 설정

```bash
sudo sh -c 'echo QEMU-OCSSD > ./rootfs/etc/hostname'
```

Ubuntu 17.10 이후로는 ifupdown을 더 이상 사용하지 않고 netplan을 사용하여 네트웍을 관리하고 있다. DHCP를 사용하도록 ethernet을 설정한다.

```bash
cat << '___EOF___' | sudo dd of=./rootfs/etc/netplan/01-network-all.yaml
network:
  version: 2
  renderer: networkd
  ethernets:
    ens:
      match:
        name: ens*
      dhcp4: true
___EOF___
```

apt repository 추가

```bash
cat << '___EOF___' | sudo dd of=./rootfs/etc/apt/sources.list
deb http://kr.archive.ubuntu.com/ubuntu/ bionic main restricted universe multiverse
deb-src http://kr.archive.ubuntu.com/ubuntu/ bionic main restricted universe multiverse

deb http://kr.archive.ubuntu.com/ubuntu/ bionic-updates main restricted universe multiverse
deb-src http://kr.archive.ubuntu.com/ubuntu/ bionic-updates main restricted universe multiverse

deb http://kr.archive.ubuntu.com/ubuntu/ bionic-security main restricted universe multiverse
deb-src http://kr.archive.ubuntu.com/ubuntu/ bionic-security main restricted universe multiverse
___EOF___
```



### Configure The Base System

chroot를 이용하여 guest rootfs에 연결하고 이후 설정 작업을 진행

```bash
LANG=C.UTF-8 sudo chroot ./rootfs /bin/bash
export TERM=xterm-color
```

timezone 변경

```bash
dpkg-reconfigure tzdata
```

language pack 설치

```bash
apt install language-pack-ko
```

Installing SSH and setting up access

```
apt install openssh-server 
```

The installed system will be very basic. If you would like to make the system a bit more mature, there is an easy method to install all packages with "standard" priority

```bash
apt install tasksel net-tools nvme-cli
tasksel install standard
```

user를 추가하고 root password 설정

```bash
adduser $USERNAME
addgroup --system admin
adduser $USERNAME admin
passwd root
```

작업 완료 후 rootfs.img file을 닫고 QEMU booting

```bash
sudo umount ./rootfs

KERNEL="-kernel ${HOME}/projects/linux-ocssd/arch/x86_64/boot/bzImage -append root=/dev/vda"
sudo $QEMU $OPT $ROOTFS $KERNEL $SHARE
```



### Host와 Guest OS 사이에 공유 폴더 설정 

virtio 9P sharing을 사용하여 host의 폴더를 guest와 공유하도록 설정한다. 

```bash
SHARE="-virtfs local,id=fsdev0,path=./path to/share,security_model=passthrough,writeout=writeout,mount_tag=sharepoint"
```



security_model로는 mapped, passthrough, none 세가지가 있다. mapped를 사용하면 guest에서 write한 파일의 소유자가 host에서는 root로 적용되고, passthrough를 사용하여야 guest user의 소유자 정보대로 파일이 생성된다. 이에 `security_model`은 `passthrough`를 사용한다.

```bash
SHARE="-virtfs local,id=fsdev0,path=${HOME}/vm/share,security_model=passthrough,writeout=writeout,mount_tag=sharepoint"
```



Guest OS에서 sharepoint mount 하기

```bash
sudo mount -t 9p -o trans=virtio sharepoint ./share
```



## Setting OCSSD

Open-Channel SSDs 를 구동하고 test하는데 필요한 library와 tool 설치



### liblightnvm

liblightnvm source를 다운 받고 빌드시 필요한 library  libcunit1-dev을 설치한다.

```bash
git clone https://github.com/OpenChannelSSD/liblightnvm.git
sudo apt install libcunit1-dev
```

build and install

```bash
make debug_on configure
make
sudo make install
```



### lnvm 

Administrative tool for LightNVM compatible Open-Channel SSDs 

```bash
git clone https://github.com/OpenChannelSSD/lnvm.git
make
```



### lnvm-tools  

Tools for conditioning, testing, and verify integrity on Open-Channel SSDs 

```bash
git clone https://github.com/OpenChannelSSD/lnvm-tools.git
make
```

linlightnvme 최신 code를 설치하면 pblk_tools build시 *"error: expected declaration specifiers or ‘...’ before ‘sizeof’ "* 가 발생한다. 이를 해결하려면 **C11 Compiler**를 사용해야 한다. 

linlightnvme v0.1.3 이후 version에서 `struct nvm_ret` 가 변경되면서 아래와 같은 에러 발생한다.  

> nvm_pblk.c:219:44: error: invalid operands to binary || (have ‘int’ and ‘const union <anonymous>’)
>   int smeta_read = !(line->smeta_ret.status || line->smeta_ret.result);



### pblk_tools

```bash
git clone https://github.com/OpenChannelSSD/pblk-tools.git
sudo apt install libudev-dev
make
```

* linlightnvme 최신 code를 설치하면 pblk_tools build시 ***"error: expected declaration specifiers or ‘...’ before ‘sizeof’ "*** 가 발생한다. 이를 해결하려면 **C11 Compiler**를 사용해야 한다. 

* linlightnvme v0.1.3 이후 version에서 `struct nvm_ret` 가 변경되면서 아래와 같은 에러 발생.  

  > nvm_pblk.c:219:44: error: invalid operands to binary || (have ‘int’ and ‘const union <anonymous>’)
  >   int smeta_read = !(line->smeta_ret.status || line->smeta_ret.result);



Documentation available at http://lightnvm.io/pblk-tools



## OCSSD test in Guest OS

```bash
sudo nvme lnvm list
```

LightNVM 초기화

```bash
DEVICE=nvme0n1
sudo nvme lnvm init -d $DEVICE
```

Add Target pblk: QEMU 실행시 parallel unit을 4로 지정하였기 때문에 LUN을 0~3으로 한다.

```bash
DEVICE=nvme0n1
TARGET_NAME=pblk0
TARGET_TYPE=pblk
LUN_BEGIN=0
LUN_END=3
sudo nvme lnvm create -d $DEVICE -n $TARGET_NAME -t $TARGET_TYPE -b $LUN_BEGIN -e $LUN_END
```



# GDB 사용법

b <function>

handle SIGUSR1 nostop noprint





catch fork

catch vfork

set follow-fork-mode child



# ezfio

./ocssd.sh init

./ocssd.sh pblk 0 63

cd /mnt/host/projects/ezfio/

sudo ./ezfio.py -d /dev/pblk0 

sudo ./ezfio.py -d /dev/nvme0n1 