#!/bin/bash

IMGFILE="./image/rootfs.img"

while getopts ":ui:" opt; do
	case $opt in
		u)    UNLOAD=1 ;;	
		i)    IMGFILE=$OPTARG ;;
		\?)   echo "Invalid option: -$OPTARG" >&2 ;;
		:)    echo "Option -$OPTARG requires an argument." >&2 ;;
	esac
done 

QEMU="${HOME}/qemu-nvme/bin/qemu-system-x86_64"
QEMU3="${HOME}/qemu3/bin/qemu-system-x86_64"
OPT="-m 8G -smp 8 --enable-kvm -vga qxl"
USERVERCD="-cdrom ${HOME}/vm/cd/ubuntu-18.10-live-server-amd64.iso"
UBUNTUCD="-cdrom ${HOME}/vm/cd/ubuntu-18.04.1-desktop-amd64.iso"
WINCD="-cdrom ${HOME}/vm/cd/Win10_1809Oct_Korean_x64.iso"
OCSSD="-drive file=${HOME}/vm/image/ocssd_backend.img,id=myocssd,format=raw,if=none -device nvme,drive=myocssd,serial=deadbeef,lnum_pu=4,lstrict=1,meta=16,mc=3"
KERNEL="-kernel ${HOME}/projects/linux-ocssd/arch/x86_64/boot/bzImage"
GEMINI="-object iothread,id=iothread0 -drive file=/dev/nvme0n1,if=none,format=raw,discard=unmap,aio=native,cache=none,id=hd0 -device virtio-blk-pci,drive=hd0,scsi=off,config-wce=off,iothread=iothread0"
ROOTFS="-object iothread,id=iothread1 -drive file=${IMGFILE},if=none,format=raw,discard=unmap,aio=native,cache=none,id=hd0 -device virtio-blk-pci,drive=hd0,scsi=off,config-wce=off,iothread=iothread1"
BOOT="-object iothread,id=iothread2 -drive file=boot.img,if=none,format=raw,discard=unmap,aio=native,cache=none,id=hd1 -device virtio-blk-pci,drive=hd1,scsi=off,config-wce=off,iothread=iothread2"
VNC="-vnc localhost:1"
SPICE="-vga qxl -spice port=3001,disable-ticketing"
SERIAL="-chardev socket,id=console1,path=/tmp/console1,server,nowait -device spapr-vty,chardev=console1"
SHARE="-fsdev local,id=fsdev0,path=${HOME}/vm/share,security_model=mapped -device virtio-9p-pci,fsdev=fsdev0,mount_tag=sharepoint"
NET="-netdev user,id=vmnic -device virtio-net,netdev=vmnic"

sudo $QEMU $OPT $UBUNTUCD $OCSSD $SHARE $NET $ROOTFS $KERNEL -append "root=/dev/vda vga=0x380"
