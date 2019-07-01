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

# wait until process start: process name, [timeout]
waitUntil()
{
    local _PROCID=$1
    local _timeout_cnt=${2:-10}
    
    until (ps -C $_PROCID > /dev/null); 
    do 
        ((_timeout_cnt--))
        [[ $_timeout_cnt < 0 ]] && exit 1
        sleep 1
    done
    exit 0
}

set_disks()
{
    _index=0
    for _IMG in ${IMG};
    do
      if [[ -e $_IMG ]]; then
	      if [[ -b $_IMG ]] && [[ $_IMG != *nvme* ]]; then _disk_type="scsi-block"; else _disk_type="scsi-hd"; fi
  	      if [[ $_IMG == *.qcow2* ]]; then 
		      DISKS+=" $_IMG"
#		        -drive file=$_IMG,id=drive-scsi$_index,if=none,aio=native,cache=none \
#		        -device $_disk_type,scsi-id=$_index,drive=drive-scsi$_index,id=scsi0-$_index"
  	      else
		      DISKS+=" \
		        -drive file=$_IMG,id=drive-scsi$_index,if=none,format=raw,discard=unmap,aio=native,cache=none \
		        -device $_disk_type,scsi-id=$_index,drive=drive-scsi$_index,id=scsi0-$_index"
	      fi
	      ((_index++))
	  fi
    done
    [[ -z $DISKS ]] && { echo "error!! There is no disks."; exit 1; } 
}

set_cdrom()
{
    for _IMG in ${CDIMG};
    do
		if [[ -e $_IMG ]]; then
			CDROMS+=" \
			  -drive file=$_IMG,if=ide,index=$_index,media=cdrom"
			((_index++))
		fi
    done
}

set_kernel() 
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

    APPEND="-append"
    CMD+=($KERNEL $INITRD $APPEND "$PARAM")
    CONNECT=(ssh $UNAME@localhost -p $SSHPORT)
}

windows() 
{
    OPT+=" -machine q35,accel=kvm -device intel-iommu -vga qxl"

    IMG=${IMG:-"win10_1809.img /dev/sdb"}
	CDIMG="$VMHOME/cd/Win10_1809Oct_Korean_x64.iso $VMHOME/cd/virtio-win-0.1.171.iso"

    USB="-device piix4-usb-uhci"
}

RemoveSSH()
{
    sudo ssh-keygen -f "/root/.ssh/known_hosts" -R "[localhost]:$SSHPORT"
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
        b)  IMG+=$OPTARG ;;
        d)  GDB=1 ;;
        q)  QEMU=$OPTARG ;;
        k)  KERNEL_IMAGE=$OPTARG ;;
        m)  MONITOR="-monitor stdio" ;;
        *)  usage ;;
    esac
done 

shift $(($OPTIND-1)) 

[[ $1 == *vmlinuz* ]] && { KERNEL_IMAGE=$1; shift 1; }
[[ $1 == *.img* ]] && { IMG+=$1; shift 1; }

VMHOME=${VMHOME:-"$HOME/vm"}
VMNAME=${VMNAME:-${PWD##*/}}
echo Virtual machine name: $VMNAME

[[ -d $VMHOME/$VMNAME ]] || mkdir $VMHOME/$VMNAME
pushd $VMHOME/$VMNAME

[[ -f ${VMNAME}.cfg ]] && source ${VMNAME}.cfg

[[ $VMNAME == *ocssd* ]] && QEMU=${QEMU:-"$HOME/qemu/bin/qemu-system-x86_64"}
QEMU=${QEMU:-"qemu-system-x86_64"}; OCSSD= ;
QEMU+=" -name $VMNAME,process=${VMPROCID:=VM_$VMNAME}"
CMD=($QEMU)

NCORE=$(($(nproc)/2))
OPT+=" -m 8G -smp $NCORE --enable-kvm"
G_TERM=${G_TERM-"gnome-terminal --"}

if [[ ! -f ${OVMF_VARS:="OVMF_VARS.fd"} ]]; then
    cp $VMHOME/bios/OVMF_VARS.fd $OVMF_VARS
fi
UEFI=${UEFI-"-drive file=$VMHOME/bios/OVMF_CODE.fd,if=pflash,format=raw,readonly,unit=0 \
      -drive file=$OVMF_VARS,if=pflash,format=raw,unit=1"}

NET="-netdev user,id=vmnic,smb=$HOME,hostfwd=tcp::${SSHPORT:=5500}-:22 -device virtio-net,netdev=vmnic"
SPICEPORT=$(($SSHPORT+1))
SPICE="\
  -vga qxl -spice port=$SPICEPORT,disable-ticketing \
  -device virtio-serial \
  -chardev spicevmc,id=vdagent,name=vdagent \
  -device virtserialport,chardev=vdagent,name=com.redhat.spice.0"
      
SCSI="\
  -object iothread,id=iothread0 \
  -device virtio-scsi-pci,id=scsi0,iothread=iothread0"

OCSSD=${OCSSD-"\
  -drive file=${OCSSD_BACKEND:-"/dev/nvme0n1p1"},id=myocssd,format=raw,if=none,cache=none \
  -device nvme,drive=myocssd,serial=deadbeef,lnum_pu=64,lstrict=1,meta=16,mc=3,namespaces=${NUM_NS:-4} \
  --trace events=$VMHOME/$VMNAME/events"}

SERIAL="-chardev socket,id=console1,path=/tmp/console1,server,nowait -device spapr-vty,chardev=console1"
SHARE0="-virtfs local,id=fsdev0,path=$HOME,security_model=passthrough,writeout=writeout,mount_tag=host"

CONNECT=(remote-viewer spice://localhost:$SPICEPORT)

[[ -n $KERNEL_IMAGE ]] && set_kernel
set_disks
set_cdrom

CMD+=($OPT $UEFI $NET $SCSI $DISKS $OCSSD $SPICE $USB $CDROMS $SHARE0 $@)

echo "${CMD[@]}" 
echo "${CONNECT[@]}" 
(waitUntil $VMPROCID 0) || $G_TERM sudo "${CMD[@]}"
(waitUntil $VMPROCID) && $G_TERM "${CONNECT[@]}"

[[ $RMSSH -eq 1 ]] && RemoveSSH
# $VMNAME "$@" 

popd

