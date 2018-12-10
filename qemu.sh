#!/bin/bash

PORT=5555
UNAME=$SUDO_USER
SSHCON=0
RMSSH=0

echo $UNAME
 
while getopts ":rsp:" opt; do
    case $opt in
        p)  PORT=$OPTARG ;;	
        n)  UNAME=$OPTARG ;;
        r)  RMSSH=1 ;;
        s)  SSHCON=$OPTARG ;;
        \?) echo "Invalid option: -$OPTARG" >&2 ;;
        :)  echo "Option -$OPTARG requires an argument." >&2 ;;
    esac
done 

shift $(($OPTIND-1)) 

IMGFILE=${1:-"/dev/nvme0n1p2"}

runQEMU() 
{
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
    -drive file=$IMGFILE,if=none,format=raw,discard=unmap,aio=native,cache=none,id=hd0 \
    -device virtio-blk-pci,drive=hd0,scsi=off,config-wce=off,iothread=iothread1"
    BOOTP="-object iothread,id=iothread2 \
    -drive file=boot.img,if=none,format=raw,discard=unmap,aio=native,cache=none,id=hd1 \
    -device virtio-blk-pci,drive=hd1,scsi=off,config-wce=off,iothread=iothread2"

    SHARE0="-virtfs local,id=fsdev0,path=${HOME},security_model=passthrough,writeout=writeout,mount_tag=sharepoint"
    SHARE1="-virtfs local,id=fsdev1,path=${HOME}/projects,security_model=passthrough,writeout=writeout,mount_tag=projects"
    NET="-netdev user,id=vmnic,hostfwd=tcp::$PORT-:22 -device virtio-net,netdev=vmnic"

    VNC="-vnc localhost:1"
    SPICE="-vga qxl -spice port=3001,disable-ticketing"
    SERIAL="-chardev socket,id=console1,path=/tmp/console1,server,nowait -device spapr-vty,chardev=console1"
    QEMU3="${HOME}/qemu3/bin/qemu-system-x86_64"

    $QEMU $OPT $OCSSD $SHARE0 $SHARE1 $NET $ROOTFS $KERNEL -append "root=/dev/vda vga=0x300" &
    sleep 5
}

RemoveSSH()
{
    ssh-keygen -f "/root/.ssh/known_hosts" -R "[localhost]:$PORT"
}

[[ $SSHCON ]] && runQEMU 

[[ $RMSSH -eq 1 ]] && RemoveSSH

ssh "$UNAME"@localhost -p $PORT

