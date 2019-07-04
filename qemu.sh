#!/bin/bash

usage()
{
    echo "Usage: $0 [-p <SSH port number>] [-n <Guest login name>] [Guest image file]" 1>&2
    exit 1
}

# wait until process start: process name, [timeout]
waitUntil()
{
    local _PROCID=$1
    local _timeout=${2:-10}
    
    until (ps -C $_PROCID > /dev/null); 
    do 
        ((_timeout--))
        [[ $_timeout < 0 ]] && exit 1
        sleep 1
    done
    exit 0
}

set_disks()
{
    _index=0
    [[ -z $IMG ]] && return 

	SCSI="\
	  -object iothread,id=iothread0 \
	  -device virtio-scsi-pci,id=scsi0,iothread=iothread0"

    for _IMG in ${IMG};
    do
      if [[ -e $_IMG ]]; then
	      if [[ -b $_IMG ]] && [[ $_IMG != *nvme* ]]; then _disk_type="scsi-block"; else _disk_type="scsi-hd"; fi
  	      if [[ $_IMG == *.qcow2* ]]; then 
		      DISKS+=" \
		        -drive file=$_IMG,id=drive-$_index,if=ide,cache=writeback"
  	      else
		      DISKS+=" \
		        -drive file=$_IMG,id=drive-scsi$_index,if=none,format=raw,discard=unmap,aio=native,cache=none \
		        -device $_disk_type,scsi-id=$_index,drive=drive-scsi$_index,id=scsi0-$_index"
	      fi
	      ((_index++))
	  fi
    done
    [[ -z $DISKS ]] && { echo "error!! There is no disks."; exit 1; } 
	CMD+=($SCSI $DISKS)
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
	[[ -n $CDROMS ]] && CMD+=($CDROMS)
}

set_net()
{
	SSHPORT=${SSHPORT:-5500}
	while (lsof -i :$SSHPORT > /dev/null) || (lsof -i :$(($SSHPORT+1)) > /dev/null); do SSHPORT=$(($SSHPORT+2)); done 
	NET="-netdev user,id=vmnic,smb=$HOME,hostfwd=tcp::${SSHPORT:=5500}-:22 -device virtio-net,netdev=vmnic"
	SPICEPORT=$(($SSHPORT+1))
	SPICE="\
	  -vga qxl -spice port=$SPICEPORT,disable-ticketing \
	  -device virtio-serial \
	  -chardev spicevmc,id=vdagent,name=vdagent \
	  -device virtserialport,chardev=vdagent,name=com.redhat.spice.0"
	SHARE0="-virtfs local,id=fsdev0,path=$HOME,security_model=passthrough,writeout=writeout,mount_tag=host"
	CMD+=($NET $SPICE $SHARE0)
}

set_kernel() 
{
    KERNEL="-kernel ${KERNEL_IMAGE:="$HOME/projects/linux-ocssd/arch/x86_64/boot/bzImage"}"
    [[ $KERNEL_IMAGE == *vmlinuz* ]] && INITRD="-initrd ${KERNEL_IMAGE/"vmlinuz"/"initrd.img"}"

    if [[ $GUI_BOOT -eq 1 ]]; then
        OPT+=" -vga qxl"
        PARAM="root=/dev/sda vga=0x300"
    else
        OPT+=" -nographic -serial mon:stdio"
        PARAM="root=/dev/sda console=ttyS0"
    fi

    APPEND="-append"
    CMD+=($KERNEL $INITRD $APPEND "$PARAM")
}

set_uefi()
{
	if [[ ! -f ${OVMF_VARS:="OVMF_VARS.fd"} ]]; then
	    cp $VMHOME/bios/OVMF_VARS.fd $OVMF_VARS
	fi
	UEFI=${UEFI-"-drive file=$VMHOME/bios/OVMF_CODE.fd,if=pflash,format=raw,readonly,unit=0 \
	      -drive file=$OVMF_VARS,if=pflash,format=raw,unit=1"}
    CMD+=($UEFI)
}

set_ocssd()
{
	OCSSD=${OCSSD-"\
	  -drive file=${OCSSD_BACKEND:-"/dev/nvme0n1p1"},id=myocssd,format=raw,if=none,cache=none \
	  -device nvme,drive=myocssd,serial=deadbeef,lnum_pu=64,lstrict=1,meta=16,mc=3,namespaces=${NUM_NS:-4} \
	  --trace events=$VMHOME/$VMNAME/events"}
    CMD+=($OCSSD)
}

set_usb3()
{
    USB="\
      -device nec-usb-xhci,id=usb3 \
      -chardev spicevmc,name=usbredir,id=usbredirchardev1 \
      -device usb-redir,chardev=usbredirchardev1,id=usbredirdev1 \
      -chardev spicevmc,name=usbredir,id=usbredirchardev2 \
      -device usb-redir,chardev=usbredirchardev2,id=usbredirdev2 \
      -chardev spicevmc,name=usbredir,id=usbredirchardev3 \
      -device usb-redir,chardev=usbredirchardev3,id=usbredirdev3"
    CMD+=($USB)
}

set_usb2()
{
    USB="-device ich9-usb-ehci1,id=usb \
      -device ich9-usb-uhci1,masterbus=usb.0,firstport=0,multifunction=on \
      -device ich9-usb-uhci2,masterbus=usb.0,firstport=2 \
      -device ich9-usb-uhci3,masterbus=usb.0,firstport=4 \
      -chardev spicevmc,name=usbredir,id=usbredirchardev1 \
      -device usb-redir,chardev=usbredirchardev1,id=usbredirdev1 \
      -chardev spicevmc,name=usbredir,id=usbredirchardev2 \
      -device usb-redir,chardev=usbredirchardev2,id=usbredirdev2 \
      -chardev spicevmc,name=usbredir,id=usbredirchardev3 \
      -device usb-redir,chardev=usbredirchardev3,id=usbredirdev3"
    CMD+=($USB)
}

windows() 
{
    OPT+=" -machine q35,accel=kvm -device intel-iommu"

    IMG=${IMG:-"win10_1809.img /dev/sdb"}
	CDIMG="$VMHOME/cd/Win10_1809Oct_Korean_x64.iso $VMHOME/cd/virtio-win-0.1.171.iso"

    USB="-device piix4-usb-uhci"
}

RemoveSSH()
{
    sudo ssh-keygen -f "/root/.ssh/known_hosts" -R "[localhost]:$SSHPORT"
}

# main

UNAME=${SUDO_USER:-$USER}
SSHCON=0
RMSSH=0
GDB=0

while getopts ":sSv:n:dk:q:mri:c:u" opt; do
    case $opt in
        s)  SSHCON=1 ;;         # make SSH connection to the running QEMU
        S)  SSHCON=1            # Remove existing SSH keys and make SSH connection to the running QEMU
            RMSSH=1 ;;
        r)  RMSSH=1 ;;          # Remove existing SSH keys 
        n)  UNAME=$OPTARG ;;    # set login user name
        v)  VMNAME=$OPTARG ;;
        i)  IMG+=$OPTARG ;;
        d)  GDB=1 ;;
        q)  QEMU=$OPTARG ;;
        k)  KERNEL_IMAGE=$OPTARG ;;
        m)  MONITOR="-monitor stdio" ;;
        c)  CFGFILE=$OPTARG ;;
        u)  USE_UEFI=1 ;;
        *)  usage ;;
    esac
done 

shift $(($OPTIND-1)) 

while (($#)); do
    case $1 in 
        *vmlinuz*)  KERNEL_IMAGE=$1;;
        *.img*)		IMG+="$1 ";;
        *.qcow2*)	IMG+="$1 ";;
        */dev/*)	IMG+="$1 ";;
        * )			break;;
    esac
    shift
done

VMHOME=${VMHOME:-"$HOME/vm"}
VMNAME=${VMNAME:-${PWD##*/}}
echo Virtual machine name: $VMNAME

[[ -d $VMHOME/$VMNAME ]] || mkdir $VMHOME/$VMNAME
pushd $VMHOME/$VMNAME

CFGFILE=${CFGFILE:-${VMNAME}.cfg}
[[ -f $CFGFILE ]] && source $CFGFILE

[[ $VMNAME == *ocssd* ]] && QEMU=${QEMU:-"$HOME/qemu/bin/qemu-system-x86_64"}
QEMU=${QEMU:-"qemu-system-x86_64"}; OCSSD= ;
QEMU+=" -name $VMNAME,process=${VMPROCID:=VM_$VMNAME}"

NCORE=$(($(nproc)/2))
OPT+=" -cpu host -m 8G -smp $NCORE --enable-kvm -machine q35,accel=kvm -device intel-iommu -monitor stdio"
G_TERM=${G_TERM-"gnome-terminal --"}
CMD=($QEMU)

SERIAL="-chardev socket,id=console1,path=/tmp/console1,server,nowait -device spapr-vty,chardev=console1"

[[ $USE_UEFI -eq 1 ]] && set_uefi
[[ -n $KERNEL_IMAGE ]] && set_kernel
set_disks
set_cdrom
set_ocssd
set_net
set_usb3

CMD+=($OPT $@)
[[ $SSHCON -eq 1 ]] && CONNECT=($G_TERM ssh $UNAME@localhost -p $SSHPORT) || CONNECT=(remote-viewer spice://localhost:$SPICEPORT --spice-usbredir-auto-redirect-filter="0x03,-1,-1,-1,0|-1,-1,-1,-1,1")
[[ $RMSSH -eq 1 ]] && RemoveSSH

echo "${CMD[@]}" 
echo "${CONNECT[@]}" 
(waitUntil $VMPROCID 0) || ($G_TERM sudo "${CMD[@]}")
(waitUntil $VMPROCID) && ("${CONNECT[@]}")&

popd

