#!/bin/bash

NCORE=$(nproc)
NCORE=$((NCORE/2))

while getopts ":sSp:P:b:n:dk:q:mr" opt; do
    case $opt in
        p)  SSHPORT=$OPTARG ;;     # Specify a new ssh port.
        P)  SSHPORT=$OPTARG        # Remove existing SSH keys and specify a new ssh port.
            RMSSH=1 ;;
        s)  SSHCON=1 ;;         # make SSH connection to the running QEMU
        S)  SSHCON=1            # Remove existing SSH keys and make SSH connection to the running QEMU
            RMSSH=1 ;;
        r)  RMSSH=1 ;;          # Remove existing SSH keys 
        n)  UNAME=$OPTARG ;;    # set login user name
        b)  BASE=$OPTARG ;;
        d)  GDB=1 ;;
        q)  QEMU=$OPTARG ;;
        k)  KERNEL_IMAGE=$OPTARG ;;
        m)  MONITOR="-monitor stdio" ;;
        *)  usage ;;
    esac
done 

BASE=${PWD##*/}
[[ $BASE == *qemu* ]] && QEMU=${QEMU:-"$HOME/$BASE/bin/qemu-system-x86_64"}
QEMU=${QEMU:-"qemu-system-x86_64"}


runQEMU() 
{
    OPT="-m 8G -smp $NCORE --enable-kvm"
    DISPLAY="-vga qxl"
    USB="-device qemu-xhci,id=xhci"

    SSHPORT=5556
    NET="-netdev user,id=vmnic,hostfwd=tcp::$SSHPORT-:22 -device virtio-net,netdev=vmnic"

    UEFI="-bios /usr/share/ovmf/OVMF.fd"
    UEFI_VAR="-drive file=$HOME/.config/qemu-windows.nvram,if=pflash,format=raw,unit=1"

    WINHD="-drive file=/dev/sda,format=raw,cache=none"
    WINCD="-cdrom $HOME/temp/Win10_1903_V1_Korean_x64.iso"

    CMD="$QEMU $OPT $DISPLAY $UEFI $WINHD $WINCD $MONITOR $@"
    echo $CMD
    sudo $CMD
}

runQEMU


