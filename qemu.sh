#!/bin/bash

UNAME=$SUDO_USER
SSHCON=0
RMSSH=0
GDB=0
BASE=${PWD##*/}
[[ ! $BASE == *qemu* ]] && BASE="qemu"

usage()
{
    echo "Usage: $0 [-p <SSH port number>] [-n <Guest login name>] [Guest image file]" 1>&2
    exit 1
}

while getopts ":sSp:P:b:n:d" opt; do
    case $opt in
        p)  SSHPORT=$OPTARG ;;     # Specify a new ssh port.
        P)  SSHPORT=$OPTARG        # Remove existing SSH keys and specify a new ssh port.
            RMSSH=1 ;;
        s)  SSHCON=1 ;;         # make SSH connection to the running QEMU
        S)  SSHCON=1            # Remove existing SSH keys and make SSH connection to the running QEMU
            RMSSH=1 ;;
        n)  UNAME=$OPTARG ;;    # set login user name
        b)  BASE=$OPTARG ;;
        d)  GDB=1 ;;
        *)  usage ;;
    esac
done 

shift $(($OPTIND-1)) 

QEMU="$HOME/$BASE/bin/qemu-system-x86_64"
OCSSD_BACKEND="$HOME/vm/image/ocssd_$BASE.img"
if [[ $BASE == "qemu-nvme" ]]; then
    SSHPORT=5555
    SRC="/dev/nvme1n1p2"
    OCSSD_BACKEND="/dev/nvme0n1p2"
fi
if [[ $BASE == "qemu" ]]; then
    SSHPORT=5556
    SRC="/dev/nvme1n1p1" 
    OCSSD_BACKEND="/dev/nvme0n1p1"
fi
if [[ $BASE == "qemu1" ]]; then
    SSHPORT=5555
    SRC="/dev/nvme1n1p2" 
    OCSSD_BACKEND="/dev/nvme0n1p2"
fi

IMG_ROOTFS=${1:-$SRC}
NUM_NS=${NUM_NS:-4}

runQEMU() 
{
    OPT="-m 8G -smp 8 --enable-kvm -vga qxl"
    DEBUG="--trace events=$HOME/vm/$BASE/events"
    KERNEL="-kernel $HOME/projects/linux-ocssd/arch/x86_64/boot/bzImage"

    USERVERCD="-cdrom $HOME/vm/cd/ubuntu-18.10-live-server-amd64.iso"
    UBUNTUCD="-cdrom $HOME/vm/cd/ubuntu-18.04.1-desktop-amd64.iso"
    WINCD="-cdrom $HOME/vm/cd/Win10_1809Oct_Korean_x64.iso"

    OCSSD="-drive file=$OCSSD_BACKEND,id=myocssd,format=raw,if=none \
    -device nvme,drive=myocssd,serial=deadbeef,lnum_pu=64,lstrict=1,meta=16,mc=3,namespaces=$NUM_NS"
    GEMINI="-object iothread,id=iothread0 \
    -drive file=/dev/nvme0n1,if=none,format=raw,discard=unmap,aio=native,cache=none,id=hd0 \
    -device virtio-blk-pci,drive=hd0,scsi=off,config-wce=off,iothread=iothread0"
    ROOTFS="-object iothread,id=iothread1 \
    -drive file=$IMG_ROOTFS,if=none,format=raw,discard=unmap,aio=native,cache=none,id=hd0 \
    -device virtio-blk-pci,drive=hd0,scsi=off,config-wce=off,iothread=iothread1"
    BOOTP="-object iothread,id=iothread2 \
    -drive file=boot.img,if=none,format=raw,discard=unmap,aio=native,cache=none,id=hd1 \
    -device virtio-blk-pci,drive=hd1,scsi=off,config-wce=off,iothread=iothread2"

    SHARE0="-virtfs local,id=fsdev0,path=$HOME,security_model=passthrough,writeout=writeout,mount_tag=sharepoint"
    SHARE1="-virtfs local,id=fsdev1,path=$HOME/projects,security_model=passthrough,writeout=writeout,mount_tag=projects"
    NET="-netdev user,id=vmnic,hostfwd=tcp::$SSHPORT-:22 -device virtio-net,netdev=vmnic"

    VNC="-vnc localhost:1"
    SPICE="-vga qxl -spice port=3001,disable-ticketing"
    SERIAL="-chardev socket,id=console1,path=/tmp/console1,server,nowait -device spapr-vty,chardev=console1"

    if [ $GDB -eq 1 ]; then
        gdb -q --args $QEMU $OPT $OCSSD $SHARE0 $SHARE1 $NET $ROOTFS $KERNEL $DEBUG -append "root=/dev/vda vga=0x300" 
    else
        echo $QEMU $OPT $OCSSD $SHARE0 $SHARE1 $NET $ROOTFS $KERNEL $DEBUG -append "root=/dev/vda vga=0x300" 
        $QEMU $OPT $OCSSD $SHARE0 $SHARE1 $NET $ROOTFS $KERNEL $DEBUG -append "root=/dev/vda vga=0x300" &
        sleep 3
    fi
}

RemoveSSH()
{
    ssh-keygen -f "/root/.ssh/known_hosts" -R "[localhost]:$SSHPORT"
}

[[ -d $HOME/vm/$BASE ]] || mkdir $HOME/vm/$BASE
pushd $HOME/vm/$BASE

[[ $SSHCON -eq 0 ]] && runQEMU 

[[ $RMSSH -eq 1 ]] && RemoveSSH

gnome-terminal -- bash -c "ssh $UNAME@localhost -p $SSHPORT"

popd

