# Virtual Open-Channel SSD

## pre-install tools 
```bash
sudo apt install make 
sudo apt install make-guile gcc g++ curl git dpkg-dev 
sudo apt install python python3 python-pip python3-pip python-tk python3-tk bison
sudo apt install libgflags-dev

sudo apt install openjdk-8-jdk
sudo apt install maven
sudo apt install vagrant

sudo apt install libglib2.0-dev libpixman-1-dev libxen-dev libgtk-3-dev
sudo apt install libspice-server-dev
sudo apt install debootstrap
sudo apt install dracut-core
```

## Compiling & Installing QEMU
```bash
git clone https://github.com/OpenChannelSSD/qemu-nvme.git

cd qemu-nvme
./configure --enable-kvm --target-list=x86_64-softmmu --enable-linux-aio --disable-werror --disable-xen --prefix=$HOME/qemu-nvme --enable-gtk --enable-spice

make -j `getconf _NPROCESSORS_ONLN`
make install
```

## Configuring the virtual open-channel SSD drive

Create OCSSD backend file

```bash
dd if=/dev/zero of=ocssd_backend.img bs=1M count=16384
```

QEMU reference

```bash
sudo $HOME/qemu-nvme/bin/qemu-system-x86_64 -m 4G -smp 8 -s \
-drive file={path to vm image},id=diskdrive,format=raw,if=none \
-device virtio-blk-pci,drive=diskdrive,scsi=off,config-wce=off,x-data-plane=on \
-drive file={path to ocssd backend file},id=myocssd,format=raw,if=none \
-device nvme,drive=myocssd,serial=deadbeef,lnum_pu=4,lstrict=1,meta=16,mc=3
```

QEMU parameter

```
Linux/Multiboot boot specific:
-kernel bzImage use 'bzImage' as kernel image
-append cmdline use 'cmdline' as kernel command line
-initrd file    use 'file' as initial ram disk
-dtb    file    use 'file' as device tree image
```

create boot/rootfs image 

```bash
$HOME/qemu-nvme/bin/qemu-img create -f raw boot.img 1G
$HOME/qemu-nvme/bin/qemu-img create -f raw rootfs.img 16G
```

run QEMU

```bash
sudo $HOME/qemu-nvme/bin/qemu-system-x86_64 -m 8G -smp 8 --enable-kvm \
-cdrom ubuntu-18.10-live-server-amd64.iso \
-object iothread,id=iothread0 \
-drive file=boot.img,if=none,format=raw,discard=unmap,aio=native,cache=none,id=hd0 \
-device virtio-blk-pci,drive=hd0,scsi=off,config-wce=off,iothread=iothread0 \
-object iothread,id=iothread1 \
-drive file=rootfs.img,if=none,format=raw,discard=unmap,aio=native,cache=none,id=hd1 \
-device virtio-blk-pci,drive=hd1,scsi=off,config-wce=off,iothread=iothread1 \
-drive file=ocssd_backend.img,id=myocssd,format=raw,if=none \
-device nvme,drive=myocssd,serial=deadbeef,lnum_pu=4,lstrict=1,meta=16,mc=3 \
-kernel $HOME/projects/linux-ocssd/arch/x86_64/boot/bzImage -append root=/dev/vdb1 \
-device qxl-vga \
-monitor stdio

-boot d

-initrd /boot/initrd.img-4.18.0-11-generic 

-vga qxl -spice port=3001,disable-ticketing \
-vnc localhost:1 \
-chardev socket,id=console1,path=/tmp/console1,server,nowait \
-device spapr-vty,chardev=console1 \
```

connect to  spice

```bash
remote-viewer spice://localhost:3001
```

To setup an Ubuntu system from Debian:

```bash
mkdir ubuntu_bionic
sudo debootstrap --arch=amd64 bionic ubuntu_bionic http://archive.ubuntu.com/ubuntu/
```

```bash
dd if=/dev/zero of=rootfs.img bs=400M count=1
mkfs.ext4 ./rootfs.img
sudo mount -o loop ./rootfs.img /mnt/rootfs
sudo debootstrap --verbose --arch amd64 bionic /mnt/rootfs http://archive.ubuntu.com/ubuntu
cat << '___EOF___' | sudo dd of=/mnt/rootfs/etc/fstab
# UNCONFIGURED FSTAB FOR BASE SYSTEM
#
/dev/vda        /               ext3    defaults        1 1
dev             /dev            tmpfs   rw              0 0
tmpfs           /dev/shm        tmpfs   defaults        0 0
devpts          /dev/pts        devpts  gid=5,mode=620  0 0
sysfs           /sys            sysfs   defaults        0 0
proc            /proc           proc    defaults        0 0
___EOF___

sudo umount /mnt/rootfs

```

Direct connect to Physical drive Gemini NVMe 

```bash
sudo $HOME/qemu-nvme/bin/qemu-system-x86_64 -m 8G -smp 8 --enable-kvm \
-cdrom ubuntu-18.04.1-desktop-amd64.iso \
-object iothread,id=iothread0 \
-drive file=/dev/nvme0n1,if=virtio,cache=none,id=hd0 \
-drive file=ocssd_backend.img,id=myocssd,format=raw,if=none \
-device nvme,drive=myocssd,serial=deadbeef,lnum_pu=4,lstrict=1,meta=16,mc=3 \
-kernel $HOME/projects/linux-ocssd/arch/x86_64/boot/bzImage -append root=/dev/vda1 \
-device qxl-vga 
```

