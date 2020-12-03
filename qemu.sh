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

checkConn()
{
    local _CHKPORT=$1
    local _timeout=${2:-10}
    
    until (lsof -i :$_CHKPORT > /dev/null);  
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
                -drive file=$_IMG,cache=writeback,id=drive-$_index"
          else
              DISKS+=" \
                -drive file=$_IMG,if=none,format=raw,discard=unmap,aio=native,cache=none,id=drive-$_index \
                -device $_disk_type,scsi-id=$_index,drive=drive-$_index,id=scsi0-$_index"
          fi
          ((_index++))
      fi
    done

    CMD+=($SCSI $DISKS)
}

set_cdrom()
{
    [[ $ARCH == "x86_64" ]] && _IF="ide" || _IF="none"
    for _IMG in ${CDIMG[@]};
    do
        if [[ -e $_IMG ]]; then
            CDROMS+=" \
              -drive file=$_IMG,media=cdrom,readonly,if=$_IF,index=$_index,id=cdrom$_index"
            [[ $ARCH == "x86_64" ]] || CDROMS+=" -device usb-storage,drive=cdrom$_index"
            ((_index++))
        fi
    done
    [[ -n $CDROMS ]] && CMD+=($CDROMS)
}

set_net()
{
    local _set=$1
    local _backend=${NET_T-"user"}

    [[ $RMSSH -eq 1 ]] && { rm /tmp/${VMPROCID}*; _set=1; RemoveSSH; }
    [ -f /tmp/${VMPROCID}_SSH ] && read SSHPORT < /tmp/${VMPROCID}_SSH
    SSHPORT=${SSHPORT:-5900}
    SPICEPORT=$(($SSHPORT+1))

    if [[ $_set -eq 1 ]]; then
        while (lsof -i :$SSHPORT > /dev/null) || (lsof -i :$SPICEPORT > /dev/null); do SSHPORT=$(($SSHPORT+2)); SPICEPORT=$(($SSHPORT+1)); done 
        macaddr=$(echo ${IMG[0]}|md5sum|sed 's/^\(..\)\(..\)\(..\).*$/52:54:00:\1:\2:\3/')
		case $_backend in 
		    "user"|"u" )
    	        NET="-nic user,model=virtio-net-pci,mac=$macaddr,smb=$HOME,hostfwd=tcp::${SSHPORT}-:22"
    	        ;;
	        "tap"|"t" )
    	        NET="-nic tap,model=virtio-net-pci,mac=$macaddr,script=$VMHOME/share/qemu-ifup" # ,downscript=$VMHOME/share/qemu-ifdown
    	        ;;
	        "bridge"|"b" )
    	        NET="-nic bridge,br=virbr0,model=virtio-net-pci,mac=$macaddr"
    	        ;;
	    esac
        
        CMD+=($NET)
        echo $SSHPORT > /tmp/${VMPROCID}_SSH
    fi

}

set_connect()
{
    T_TITLE="${VMNAME}:${CHKPORT}"
    
    OPT+=" -vga $GRAPHIC"
    if [[ $M_CONNECT == "ssh" ]]; then
        OPT=${OPT/"-monitor stdio"/""}
        OPT=${OPT/"-vga $GRAPHIC"/""}
        OPT+=" -nographic -serial mon:stdio"
        CONNECT=(gnome-terminal --title=$T_TITLE -- ssh $UNAME@localhost -p $SSHPORT)
        CHKPORT=$SSHPORT
    fi
    if [[ $M_CONNECT == "spice" ]]; then
        CONNECT=(remote-viewer -t ${T_TITLE} spice://localhost:$SPICEPORT --spice-usbredir-redirect-on-connect="0x03,-1,-1,-1,0|-1,-1,-1,-1,1" --spice-usbredir-auto-redirect-filter="0x03,-1,-1,-1,0|-1,-1,-1,-1,1")
        CHKPORT=$SPICEPORT
    fi
}

set_spice()
{
    SPICE="\
      -spice port=$SPICEPORT,disable-ticketing \
      -device intel-hda -device hda-duplex"
    SPICE_AGENT="\
      -chardev spicevmc,id=vdagent,name=vdagent \
      -device virtio-serial \
      -device virtserialport,chardev=vdagent,name=com.redhat.spice.0"
    GUEST_AGENT="\
      -chardev socket,path=/tmp/qga.sock,server,nowait,id=qga0,name=qga0 \
      -device virtio-serial \
      -device virtserialport,chardev=qga0,name=org.qemu.guest_agent.0"
    SHARE0="-virtfs local,id=fsdev0,path=$HOME,security_model=passthrough,writeout=writeout,mount_tag=host"
    CMD+=($SPICE $SPICE_AGENT)
}

set_kernel() 
{
    [[ -n $KERNEL_IMAGE ]] || return
    KERNEL="-kernel ${KERNEL_IMAGE:="$HOME/projects/linux-ocssd/arch/x86_64/boot/bzImage"}"
    [[ $KERNEL_IMAGE == *vmlinuz* ]] && INITRD="-initrd ${KERNEL_IMAGE/"vmlinuz"/"initrd.img"}"
    
    if [[ $GUI_BOOT -eq 1 ]]; then
        OPT+=" -vga $GRAPHIC"
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
    case $ARCH in
        "x86_64" )
            OVMF_PATH=${OVMF_PATH:-"/usr/share/OVMF"}
            OVMF_CODE="$OVMF_PATH/OVMF_CODE.fd"
            if [[ ! -f ${OVMF_VARS:="OVMF_${VMNAME}.fd"} ]]; then
                (cp $OVMF_PATH/OVMF_VARS.fd $OVMF_VARS) || return
            fi
            UEFI=${UEFI-"-drive file=$OVMF_CODE,if=pflash,format=raw,readonly,unit=0 \
                  -drive file=$OVMF_VARS,if=pflash,format=raw,unit=1"}
            ;;
        "aarch64" )
            UEFI=${UEFI-"-bios ../bios/QEMU_EFI.fd"}
            ;;
    esac
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

    _CTRL_ID=1
    for _NVME in ${NVME_BACKEND[@]};
    do
        case $CUSTOM_QEMU in
            "qemu-nvme"|"qemu" )   
                NVME+=" \
                    -device nvme,serial=beef${_NVME},id=${_NVME}"
                ((_CTRL_ID++))
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
                ns_backend=${_NVME}n1.img
                if (check_file $ns_backend 40); then
                    NVME+=" \
                        -drive file=$ns_backend,id=${_NVME},format=raw,if=none,cache=none"
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
      -device qemu-xhci,id=usb3"
    USB_REDIR="\
      -chardev spicevmc,name=usbredir,id=usbredirchardev1 \
      -device usb-redir,chardev=usbredirchardev1,id=usbredirdev1 \
      -chardev spicevmc,name=usbredir,id=usbredirchardev2 \
      -device usb-redir,chardev=usbredirchardev2,id=usbredirdev2 \
      -chardev spicevmc,name=usbredir,id=usbredirchardev3 \
      -device usb-redir,chardev=usbredirchardev3,id=usbredirdev3"
    USB_PT="-device usb-host,hostbus=3,hostport=1"
    CMD+=($USB $USB_REDIR)
}

set_usb_arm()
{
    USB="\
      -device qemu-xhci,id=usb3 \
      -device usb-kbd -device usb-tablet"
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

set_QEMU()
{
    [[ -n $CUSTOM_QEMU ]] && QEMU=${QEMU:-"$HOME/$CUSTOM_QEMU/bin/qemu-system-$ARCH"}
    QEMU=${QEMU:-"qemu-system-$ARCH"};
    (which $QEMU >& /dev/null) || { echo $QEMU was not installed!! ; exit 1; }
    
    QEMU+=" -name $VMNAME,process=$VMPROCID"
    case $ARCH in
        "arm" )
            QEMU+=" -M virt -cpu cortex-a53 -device ramfb"
            ;;
        "aarch64" )
            QEMU+=" -M virt -cpu cortex-a53 -device ramfb"
            ;;
        "x86_64" )
            QEMU+=" -cpu host --enable-kvm"
            ;;
    esac
    NUM_CORE=${NUM_CORE:-$(($(nproc)/2))}
    MEM_SIZE=${MEM_SIZE:-"8G"}
    QEMU+=" -m $MEM_SIZE -smp $NUM_CORE,sockets=1,cores=$NUM_CORE,threads=1 -nodefaults"
    OPT+=" -monitor stdio"

    CMD=($QEMU)
}

RemoveSSH()
{
    ssh-keygen -R "[localhost]:$SSHPORT"
}

usage()
{
cat << EOM
Usage:
 ${0##*/} [OPTIONS] [cfg file] [Guest image files..] [CD image files..]

Options:
 -s                         make SSH connection to the running QEMU
 -S                         Remove existing SSH keys and make SSH connection to the running QEMU
 -r                         Remove existing SSH keys 
 -e, --nvme <NVME_BACKEND>  set NVME_BACKEND. ex) 'nvme0'
 -n, --net <netmode>        Network card model - 'user'(default), 'tap', 'bridge'
 -u, --uname <UNAME>        set login user name
 -i, --image <imagename>    disk images
 -q, --qemu <QEMU>          use custom qemu
 -c, --config <cfg_file>    read configurations from cfg_file
 -k, --kernel <KERNEL>      kernel image
 -o, --num_ns <num_of_ns>   0 - do not use nvme, gt 1 - set numbers of multi name space
 -g, --vga <GRAPHIC>        set the type of VGA graphic card. 'virtio', 'qxl'(default)
 --bios <0|1>               0 - boot from MBR BIOS, 1 - boot from UEFI
 --ipmi <ipmimodel>         IPMI model - 'external', 'internal'
 --debug                    debug mode
EOM
}

# main

UNAME=${SUDO_USER:-$USER}
RMSSH=0
USE_UEFI=1

options=$(getopt -n ${0##*/} -o sSu:k:q:ri:c:o:n:e:g:h \
                --long nvme:,net:,uname:,image:,qemu:,config:,kernel:,num_ns:,vga:,bios:,ipmi:,debug,help,arch:,connect: -- "$@")
[ $? -eq 0 ] || { 
    usage
    exit 1
}
eval set -- "$options"

while true; do
    case "$1" in
        -s )            USE_SSH=1 ;;                    # make SSH connection to the running QEMU
        -S )            USE_SSH=1 ; RMSSH=1 ;;          # Remove existing SSH keys and make SSH connection to the running QEMU
        -r )            RMSSH=1 ;;                      # Remove existing SSH keys 
        --debug )       G_TERM= ;;
        --connect )     M_CONNECT=$2 ;      shift ;;
        --arch )        ARCH=$2 ;           shift ;;    
        --bios )        USE_UEFI=$2 ;       shift ;;
        --ipmi)         USE_IPMI=$2 ;       shift ;;
        -u | --uname )  UNAME=$2 ;          shift ;;    # set login user name
        -i | --image )  IMG+=($2) ;         shift ;;
        -q | --qemu )   CUSTOM_QEMU=$2 ;    shift ;;
        -k | --kernel ) KERNEL_IMAGE=$2 ;   shift ;;
        -c | --config ) CFGFILE=$2 ;        shift ;;
        -n | --net)     NET_T=$2 ;          shift ;;
        -e | --nvme )   NVME_BACKEND=$2 ;   shift ;;
        -g | --vga )    GRAPHIC=$2 ;        shift ;;
        -o | --num_ns )  
            [[ $2 -eq 0 ]] && { USE_NVME=0; } || { USE_NVME=1; [[ $2 -ge 1 ]] && NUM_NS=$2; } ; shift ;;
        -h | --help )   usage ;             exit;;
        --)             shift ;             break ;;
    esac
    shift
done 

while (($#)); do
    case $1 in 
        *vmlinuz*)              KERNEL_IMAGE=$1 ;;
        *.img* | *.IMG*)        IMG+=($1) ;;
        *.qcow2* | *.QCOW2*)    IMG+=($1) ;;
        */dev/*)                IMG+=($1) ;;
        *.iso* | *.ISO*)        CDIMG+=($1) ;;
        *.cfg*)                 CFGFILE=$1 ;;
        nvme*)                  USE_NVME=1
                                NVME_BACKEND+=($1) ;;
        setup)                  setup_qemu; exit 0;;
        * )                     break;;
    esac
    shift
done

VMHOME=${VMHOME:-"$HOME/vm"}
CFGFILE=${CFGFILE:-${PWD##*/}.cfg}
[[ -f $CFGFILE ]] && source $CFGFILE

BOOT_DEV=(${IMG[@]} ${NVME_BACKEND[@]} ${CDIMG[@]})

VMNAME=${VMNAME:-${BOOT_DEV##*/}}
VMNAME=${VMNAME%%.*}
V_UID=$(echo $IMG|md5sum|sed 's/^\(..\).*$/\1/')
_TMP=$(echo ${VMNAME}|sed 's/^\(............\).*$/\1/')
VMPROCID=${VMPROCID:-${_TMP}_${V_UID}}

M_Q35=${M_Q35-1}
USE_USB3=${USE_USB3-1}
ARCH=${ARCH:-"x86_64"}
GRAPHIC=${GRAPHIC:-"qxl"}
M_CONNECT=${M_CONNECT:-"spice"}

G_TERM=${G_TERM-"gnome-terminal --title=$VMNAME --"}
printf "Virtual machine name: $VMNAME \n\n"

if ! (waitUntil $VMPROCID 0); then
    set_QEMU
    [[ $ARCH == "x86_64" ]] && set_M_Q35
    set_uefi
    set_kernel
    [[ $ARCH == "x86_64" ]] && set_usb3 || set_usb_arm
    set_disks
    set_cdrom
    set_nvme
    set_net 1
    set_ipmi
    [[ $M_CONNECT == "spice" ]] && set_spice
    set_connect
    CMD+=($OPT $EXT_PARAMS $@)
else
    set_net
    set_connect
fi

printf '%s\n\n' "${CMD[*]}" 
printf '%s\n\n' "${CONNECT[*]}" 
if [[ $GDB -eq 1 ]]; then
    sudo gdb -q --args "${CMD[@]}"
else
    (waitUntil $VMPROCID 0) || (sudo $G_TERM "${CMD[@]}")
    [[ -n $CONNECT ]] && (waitUntil $VMPROCID) && ("${CONNECT[@]}")&
    [[ -n $CONNECT ]] && (checkConn $CHKPORT 5) 
fi

