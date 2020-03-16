#!/bin/bash

setup_qemu()
{
    sudo apt install -y qemu-kvm
    sudo apt install -y virt-viewer    
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

    for _IMG in ${IMG[@]};
    do
      if [[ -e $_IMG ]]; then
          if (sudo lsof $_IMG >& /dev/null); then continue; fi
          if [[ -b $_IMG ]] && [[ $_IMG != *nvme* ]]; then _disk_type="scsi-block"; else _disk_type="scsi-hd"; fi
          if [[ $_IMG == *.qcow2* ]]; then 
              DISKS+=" \
                -drive file=$_IMG,id=drive-$_index,if=ide,cache=writeback"
          else
              DISKS+=" \
                -drive file=$_IMG,id=drive-$_index,if=none,format=raw,discard=unmap,aio=native,cache=none \
                -device $_disk_type,scsi-id=$_index,drive=drive-$_index,id=scsi0-$_index"
          fi
          ((_index++))
      fi
    done

    if [[ -z $DISKS ]]; then
        echo "error!! There is no disks."
        (waitUntil $VMPROCID 0) || exit 1
    fi 
    CMD+=($SCSI $DISKS)
}

set_cdrom()
{
    for _IMG in ${CDIMG[@]};
    do
        if [[ -e $_IMG ]]; then
            CDROMS+=" \
              -drive file=$_IMG,if=ide,index=$_index,media=cdrom,readonly"
            ((_index++))
        fi
    done
    [[ -n $CDROMS ]] && CMD+=($CDROMS)
}

set_net()
{
    local _set=$1
    local _backend=${NET_T-"user"}

    [[ $RMSSH -eq 1 ]] && { rm /tmp/${VMPROCID}*; _set=1; }
    [ -f /tmp/${VMPROCID}_SSH ] && read SSHPORT < /tmp/${VMPROCID}_SSH
    [ -f /tmp/${VMPROCID}_SPICE ] && read SPICEPORT < /tmp/${VMPROCID}_SPICE

    if [[ $_set -eq 1 ]]; then
        SSHPORT=${SSHPORT:-5900}
        while (lsof -i :$SSHPORT > /dev/null) || (lsof -i :$(($SSHPORT+1)) > /dev/null); do SSHPORT=$(($SSHPORT+2)); done 
        macaddr=$(echo ${IMG[0]}|md5sum|sed 's/^\(..\)\(..\)\(..\).*$/52:54:00:\1:\2:\3/')
		case $_backend in 
		    "user"|"u" )
    	        NET="-nic user,model=virtio-net-pci,mac=$macaddr,smb=$HOME,hostfwd=tcp::${SSHPORT}-:22"
    	        ;;
	        "tap"|"t" )
    	        NET="-nic tap,model=virtio-net-pci,mac=$macaddr,script=$VMHOME/share/qemu-ifup" # ,downscript=$VMHOME/share/qemu-ifdown
    	        ;;
	        "bridge"|"b" )
    	        NET="-nic bridge,br=br0,model=virtio-net-pci,mac=$macaddr"
    	        ;;
	    esac
        
        GRAPHIC=${GRAPHIC-"virtio"}
        SPICEPORT=$(($SSHPORT+1))
        SPICE="\
          -vga $GRAPHIC -spice port=$SPICEPORT,disable-ticketing \
          -soundhw hda \
          -device virtio-serial \
          -chardev spicevmc,id=vdagent,name=vdagent \
          -device virtserialport,chardev=vdagent,name=com.redhat.spice.0"
        SHARE0="-virtfs local,id=fsdev0,path=$HOME,security_model=passthrough,writeout=writeout,mount_tag=host"
        CMD+=($NET $SPICE)
        echo $SSHPORT > /tmp/${VMPROCID}_SSH
        echo $SPICEPORT > /tmp/${VMPROCID}_SPICE
    fi

    [[ $RMSSH -eq 1 ]] && RemoveSSH
    [[ $USE_SSH -eq 1 ]] && CONNECT=($G_TERM ssh $UNAME@localhost -p $SSHPORT) || CONNECT=(remote-viewer -t ${VMNAME} spice://localhost:$SPICEPORT --spice-usbredir-redirect-on-connect="0x03,-1,-1,-1,0|-1,-1,-1,-1,1" --spice-usbredir-auto-redirect-filter="0x03,-1,-1,-1,0|-1,-1,-1,-1,1")
}

set_kernel() 
{
    [[ -n $KERNEL_IMAGE ]] || return
    KERNEL="-kernel ${KERNEL_IMAGE:="$HOME/projects/linux-ocssd/arch/x86_64/boot/bzImage"}"
    [[ $KERNEL_IMAGE == *vmlinuz* ]] && INITRD="-initrd ${KERNEL_IMAGE/"vmlinuz"/"initrd.img"}"

    if [[ $GUI_BOOT -eq 1 ]]; then
        OPT+=" -vga qxl"
        PARAM="root=/dev/sda vga=0x300"
    else
        OPT=${OPT/"-monitor stdio"/""}
        OPT+=" -nographic -serial mon:stdio"
        PARAM="root=/dev/sda console=ttyS0"
    fi

    APPEND="-append"
    CMD+=($KERNEL $INITRD $APPEND "$PARAM")
}

set_uefi()
{
    [[ $USE_UEFI -eq 1 ]] || return
    OVMF_PATH=${OVMF_PATH:-"/usr/share/OVMF"}
    OVMF_CODE="$OVMF_PATH/OVMF_CODE.fd"
    if [[ ! -f ${OVMF_VARS:="OVMF_${VMNAME}.fd"} ]]; then
        (cp $OVMF_PATH/OVMF_VARS.fd $OVMF_VARS) || return
    fi
    UEFI=${UEFI-"-drive file=$OVMF_CODE,if=pflash,format=raw,readonly,unit=0 \
          -drive file=$OVMF_VARS,if=pflash,format=raw,unit=1"}
    CMD+=($UEFI)
}

check_file()
{
    local _fname=$1
    local _size="${2}G"
    
    [[ -e $_fname ]] || qemu-img create -f raw $_fname $_size
    if ! (sudo lsof $_fname >& /dev/null); then
        exit 0
    fi
    exit 1
}

set_nvme()
{   
    [[ $USE_NVME -eq 1 ]] || return
    NUM_NS=${NUM_NS:-4}
    NVME_BACKEND=${NVME_BACKEND:-"nvme${V_UID}"}

    for _NVME in ${NVME_BACKEND[@]};
    do
        case $CUSTOM_QEMU in
            "qemu-nvme" )   
                NVME+=" \
                    -device nvme,serial=beef${_NVME},id=${_NVME}"
                for ((_nsid=1;_nsid<=$NUM_NS;_nsid++))
                do
                    ns_backend=${_NVME}n${_nsid}.img
                    if (check_file $ns_backend 20); then
                        NVME+=" \
                          -drive file=$ns_backend,id=${_NVME}${_nsid},format=raw,if=none,cache=none \
                          -device nvme-ns,drive=${_NVME}${_nsid},bus=${_NVME},nsid=${_nsid}"
                    fi
                done 
                ;;

            "qemu" )
                if (check_file ${_NVME}.img 40); then
                    NVME+=" \
                        -drive file=${_NVME}.img,id=${_NVME},format=raw,if=none,cache=none"
                    NVME+=" \
                        -device nvme,drive=${_NVME},serial=beef${_NVME},namespaces=$NUM_NS"
                fi
                ;;
                
            * )             
                if (check_file ${_NVME}.img 40); then
                    NVME+=" \
                        -drive file=${_NVME}.img,id=${_NVME},format=raw,if=none,cache=none"
                    NVME+=" \
                        -device nvme,drive=${_NVME},serial=beef${_NVME}" 
                fi
                ;;
        esac
    done
    [[ -f ./events ]] && NVME+=${NVME:+" --trace events=./events"}
    [[ -n $NVME ]] && CMD+=($NVME)
}

set_usb3()
{
    [[ $USE_USB3 -eq 1 ]] || return
    USB="\
      -device qemu-xhci,id=usb3 \
      -chardev spicevmc,name=usbredir,id=usbredirchardev1 \
      -device usb-redir,chardev=usbredirchardev1,id=usbredirdev1 \
      -chardev spicevmc,name=usbredir,id=usbredirchardev2 \
      -device usb-redir,chardev=usbredirchardev2,id=usbredirdev2 \
      -chardev spicevmc,name=usbredir,id=usbredirchardev3 \
      -device usb-redir,chardev=usbredirchardev3,id=usbredirdev3"
    USB_PT="-device usb-host,hostbus=3,hostport=1"
    CMD+=($USB)
}

set_M_Q35()
{
    [[ $M_Q35 -eq 1 ]] || return 
    OPT+=" \
      -machine type=q35,accel=kvm,usb=on -device intel-iommu"
    RNGRANDOM="-object rng-random,id=rng0,filename=/dev/urandom -device virtio-rng-pci,rng=rng0"
    CMD+=($RNGRANDOM)   
}

set_ipmi()
{
    case $USE_IPMI in
        "internal" )
            IPMI="-device ipmi-bmc-sim,id=bmc0"
            ;;
            
        "external" )
            IPMI="\
              -chardev socket,id=ipmi0,host=localhost,port=9002,reconnect=10 \
              -device ipmi-bmc-extern,chardev=ipmi0,id=bmc1 \
              -device isa-ipmi-kcs,bmc=bmc1"
            ;;
    esac

    [[ -n $IPMI ]] && CMD+=($IPMI)   
}

RemoveSSH()
{
    ssh-keygen -R "[localhost]:$SSHPORT"
}

usage()
{
cat << EOM
Usage: $0 [OPTIONS] [cfg file] [Guest image files..] [CD image files..]

Options:
    -s              make SSH connection to the running QEMU
    -S              Remove existing SSH keys and make SSH connection to the running QEMU
    -r              Remove existing SSH keys 
    -u UNAME        set login user name
    -i IMG          disk images
    -d              debug mode
    -q QEMU         use custom qemu
    -k KERNEL       kernel image
    -c cfg_file     read configurations from cfg_file
    -n NET          Network card model - 'user'(default), 'tap'
    -m IPMI         IPMI model - 'external', 'internal'
    -b 0|1          0 - boot from MBR BIOS, 1 - boot from UEFI
    -o n            0 - do not use nvme, gt 1 - set numbers of multi name space
    -g GRAPHIC      set the type of VGA graphic card. 'virtio'(default), 'qxl'
    -e NVME_BACKEND set NVME_BACKEND. ex) 'nvme0'
EOM
}

# main

UNAME=${SUDO_USER:-$USER}
RMSSH=0
GDB=0
USE_UEFI=1

options=":sSu:dk:q:ri:c:b:o:n:m:e:g:"
while getopts $options opt; do
    case $opt in
        s)  USE_SSH=1 ;;         # make SSH connection to the running QEMU
        S)  USE_SSH=1            # Remove existing SSH keys and make SSH connection to the running QEMU
            RMSSH=1 ;;
        r)  RMSSH=1 ;;          # Remove existing SSH keys 
        u)  UNAME=$OPTARG ;;    # set login user name
        i)  IMG+=($OPTARG) ;;
        d)  G_TERM= ;;
        q)  CUSTOM_QEMU=$OPTARG ;;
        k)  KERNEL_IMAGE=$OPTARG ;;
        c)  CFGFILE=$OPTARG ;;
        b)  USE_UEFI=$OPTARG ;;
        o)  [[ $OPTARG -eq 0 ]] && { USE_NVME=0; } || { USE_NVME=1; [[ $OPTARG -ge 1 ]] && NUM_NS=$OPTARG; } ;;
		n)  NET_T=$OPTARG ;;
		m)  USE_IPMI=$OPTARG ;;
		e)  NVME_BACKEND=$OPTARG ;;
        g)  GRAPHIC=$OPTARG ;;
        h)  usage; exit;;
        *)  usage; exit;;
    esac
done 

shift $(($OPTIND-1)) 

while (($#)); do
    case $1 in 
        *vmlinuz*)  KERNEL_IMAGE=$1 ;;
        *.img*)     IMG+=($1) ;;
        *.qcow2*)   IMG+=($1) ;;
        */dev/*)    IMG+=($1) ;;
        *.iso*)     CDIMG+=($1) ;;
        *.cfg*)     CFGFILE=$1 ;;
        nvme*)      NVME_BACKEND+=($1) ;;
        setup)      setup_qemu; exit 0;;
        * )         break;;
    esac
    shift
done

VMHOME=${VMHOME:-"$HOME/vm"}
CFGFILE=${CFGFILE:-${PWD##*/}.cfg}
[[ -f $CFGFILE ]] && source $CFGFILE

VMNAME=${VMNAME:-${IMG##*/}}
VMNAME=${VMNAME%%.*}
V_UID=$(echo $IMG|md5sum|sed 's/^\(..\).*$/\1/')
_TMP=$(echo ${VMNAME}|sed 's/^\(............\).*$/\1/')
VMPROCID=${VMPROCID:-${_TMP}_${V_UID}}

G_TERM=${G_TERM-"gnome-terminal --"}
echo Virtual machine name: $VMNAME

if ! (waitUntil $VMPROCID 0); then
    [[ -n $CUSTOM_QEMU ]] && QEMU=${QEMU:-"$HOME/$CUSTOM_QEMU/bin/qemu-system-x86_64"}
    QEMU=${QEMU:-"qemu-system-x86_64"};
    (which $QEMU >& /dev/null) || { echo $QEMU was not installed!! ; exit 1; }
    QEMU+=" -name $VMNAME,process=$VMPROCID"
    CMD=($QEMU)

    NUM_CORE=${NUM_CORE:-$(($(nproc)/2))}
    MEM_SIZE=${MEM_SIZE:-"8G"}
    OPT+=" -cpu host -m $MEM_SIZE -smp $NUM_CORE,sockets=1,cores=$NUM_CORE,threads=1 --enable-kvm -monitor stdio -nodefaults"

    M_Q35=${M_Q35-1}
    USE_USB3=${USE_USB3-1}

    set_M_Q35
    set_uefi
    set_kernel
    set_disks
    set_cdrom
    set_nvme
    set_net 1
    set_ipmi
    set_usb3
    CMD+=($OPT $EXT_PARAMS $@)
else
    set_net
fi

echo "${CMD[@]}" 
echo "${CONNECT[@]}" 
if [[ $GDB -eq 1 ]]; then
    sudo gdb -q --args "${CMD[@]}"
else
    (waitUntil $VMPROCID 0) || ($G_TERM sudo "${CMD[@]}")
    (waitUntil $VMPROCID) && ("${CONNECT[@]}")&
fi

