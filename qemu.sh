#!/bin/bash

UNAME=${SUDO_USER:-$USER}
SSHCON=0
RMSSH=0
GDB=0

usage()
{
    echo "Usage: $0 [-p <SSH port number>] [-n <Guest login name>] [Guest image file]" 1>&2
    exit 1
}

while getopts ":sSp:P:v:n:dk:q:mrb:" opt; do
    case $opt in
        p)  SSHPORT=$OPTARG ;;     # Specify a new ssh port.
        P)  SSHPORT=$OPTARG        # Remove existing SSH keys and specify a new ssh port.
            RMSSH=1 ;;
        s)  SSHCON=1 ;;         # make SSH connection to the running QEMU
        S)  SSHCON=1            # Remove existing SSH keys and make SSH connection to the running QEMU
            RMSSH=1 ;;
        r)  RMSSH=1 ;;          # Remove existing SSH keys 
        n)  UNAME=$OPTARG ;;    # set login user name
        v)  VMNAME=$OPTARG ;;
        b)  BOOTIMG=$OPTARG ;;
        d)  GDB=1 ;;
        q)  QEMU=$OPTARG ;;
        k)  KERNEL_IMAGE=$OPTARG ;;
        m)  MONITOR="-monitor stdio" ;;
        *)  usage ;;
    esac
done 

shift $(($OPTIND-1)) 

VMNAME=${VMNAME:-${PWD##*/}}
echo $VMNAME
[[ $VMNAME == *ocssd* ]] && QEMU=${QEMU:-"$HOME/qemu/bin/qemu-system-x86_64"}
QEMU=${QEMU:-"qemu-system-x86_64"}

QEMU+=" -name $VMNAME,process=VM_$VMNAME"

OCSSD_BACKEND="$HOME/vm/image/ocssd_$VMNAME.img"
VMHOME=${VMHOME:-"$HOME/vm"}

if [[ $VMNAME == "ocssd" ]]; then
    SSHPORT=5556
    OS_SRC="/dev/nvme1n1p1" 
    OCSSD_BACKEND="/dev/nvme0n1p1"
fi
if [[ $VMNAME == "windows" ]]; then
    SSHPORT=5555
    OS_SRC="/dev/sdb" 
    OCSSD_BACKEND="/dev/nvme0n1p2"
fi

NUM_NS=${NUM_NS:-4}
NCORE=$(($(nproc)/2))
M_TERM=${M_TERM-"gnome-terminal --"}
OPT="-m 8G -smp $NCORE --enable-kvm"

USERVERCD="-cdrom $VMHOME/cd/ubuntu-18.10-live-server-amd64.iso"
UBUNTUCD="-cdrom $VMHOME/cd/ubuntu-18.04.1-desktop-amd64.iso"
WINCD="-cdrom $VMHOME/cd/Win10_1809Oct_Korean_x64.iso"
VIRTCD="-drive file=$VMHOME/cd/virtio-win-0.1.171.iso,index=3,media=cdrom"

ocssd() 
{
    KERNEL="-kernel ${KERNEL_IMAGE:="$HOME/projects/linux-ocssd/arch/x86_64/boot/bzImage"}"
    [[ $KERNEL_IMAGE == *vmlinuz* ]] && INITRD="-initrd ${KERNEL_IMAGE/"vmlinuz"/"initrd.img"}"

    if [[ $GRAPHIC -eq 1 ]]; then
        OPT+=" -vga qxl"
        PARAM="root=/dev/sda vga=0x300"
    else
        OPT+=" -nographic -serial mon:stdio"
        PARAM="root=/dev/sda console=ttyS0"
    fi
    DEBUG="--trace events=$VMHOME/$VMNAME/events"

    OCSSD="\
      -drive file=$OCSSD_BACKEND,id=myocssd,format=raw,if=none,cache=none \
      -device nvme,drive=myocssd,serial=deadbeef,lnum_pu=64,lstrict=1,meta=16,mc=3,namespaces=$NUM_NS"
    SCSI="\
      -object iothread,id=iothread0 \
      -device virtio-scsi-pci,id=scsi0,iothread=iothread0"
    ROOTFS="\
      -drive file=$OS_SRC,id=drive-scsi0,if=none,format=raw,discard=unmap,aio=native,cache=none \
      -device scsi-hd,scsi-id=0,drive=drive-scsi0,id=scsi0-0"

    UEFI=${UEFI-"-drive file=$VMHOME/bios/OVMF_CODE.fd,if=pflash,format=raw,unit=0 \
          -drive file=$VMHOME/bios/OVMF_VARS.ms.fd,if=pflash,format=raw,unit=1"}

    SHARE0="-virtfs local,id=fsdev0,path=$HOME,security_model=passthrough,writeout=writeout,mount_tag=host"
    NET="-netdev user,id=vmnic,hostfwd=tcp::$SSHPORT-:22 -device virtio-net,netdev=vmnic"

    VNC="-vnc localhost:1"
    SPICE="-vga qxl -spice port=3001,disable-ticketing"
    SERIAL="-chardev socket,id=console1,path=/tmp/console1,server,nowait -device spapr-vty,chardev=console1"

    CMD="$QEMU $OPT $UEFI $OCSSD $SHARE0 $NET $SCSI $ROOTFS $KERNEL $INITRD $DEBUG"
    
    if [ $GDB -eq 1 ]; then
        gdb -q --args $CMD -append "$PARAM"
    else
        echo $CMD -append $PARAM 
        (ps -C "VM_$VMNAME" > null) || $M_TERM sudo $CMD -append "$PARAM"
        until (ps -C "VM_$VMNAME" > null); do sleep 1; done; $M_TERM ssh $UNAME@localhost -p $SSHPORT
    fi
}

windows() 
{
    OPT+=" -machine q35,accel=kvm -device intel-iommu -vga qxl"

    OCSSD="\
      -drive file=$OCSSD_BACKEND,id=myocssd,format=raw,if=none,cache=none \
      -device nvme,drive=myocssd,serial=deadbeef,lnum_pu=64,lstrict=1,meta=16,mc=3,namespaces=$NUM_NS"
    BOOTIMG=${BOOTIMG:-"win10_1809.img"}

    SCSI="\
      -object iothread,id=iothread0 \
      -device virtio-scsi-pci,id=scsi0,iothread=iothread0"
    ROOTFS="\
      -drive file=$BOOTIMG,id=drive-scsi0,if=none,format=raw,discard=unmap,aio=native,cache=none \
      -device scsi-hd,scsi-id=0,drive=drive-scsi0,id=scsi0-0,bootindex=1"
    SSD="\
      -drive file=$OS_SRC,id=drive-scsi1,if=none,format=raw,discard=unmap,aio=native,cache=none \
      -device scsi-block,scsi-id=1,drive=drive-scsi1,id=scsi0-1"

    USB="-device piix4-usb-uhci"
    UEFI=${UEFI-"-drive file=$VMHOME/bios/OVMF_CODE.fd,if=pflash,format=raw,unit=0 \
          -drive file=$VMHOME/bios/OVMF_VARS.ms.fd,if=pflash,format=raw,unit=1"}

    NET="-netdev user,id=vmnic,smb=$HOME,hostfwd=tcp::$SSHPORT-:22 -device virtio-net,netdev=vmnic"
         
    SPICEPORT=$(($SSHPORT+1))
    SPICE="\
      -vga qxl -spice port=$SPICEPORT,disable-ticketing \
      -device virtio-serial \
      -chardev spicevmc,id=vdagent,name=vdagent \
      -device virtserialport,chardev=vdagent,name=com.redhat.spice.0"

    CMD="$QEMU $OPT $UEFI $USB $NET $WINCD $VIRTCD $SCSI $ROOTFS $SSD $SPICE $@"

    echo $CMD 
    (ps -C "VM_$VMNAME" > null) || $M_TERM sudo $CMD
    until (ps -C "VM_$VMNAME" > null); do sleep 1; done; remote-viewer spice://localhost:$SPICEPORT &
}

RemoveSSH()
{
    sudo ssh-keygen -f "/root/.ssh/known_hosts" -R "[localhost]:$SSHPORT"
}

[[ -d $VMHOME/$VMNAME ]] || mkdir $VMHOME/$VMNAME
pushd $VMHOME/$VMNAME

[[ $RMSSH -eq 1 ]] && RemoveSSH
[[ $SSHCON -eq 0 ]] && ($VMNAME "$@") || $M_TERM ssh $UNAME@localhost -p $SSHPORT

popd

