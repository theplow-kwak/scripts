#!/bin/bash

setup_qemu()
{
    $SUDO apt install -y qemu-kvm
    $SUDO apt install -y virt-viewer    
}

declare -A log_level=([debug]=1 [cmd]=2 [info]=2 [warning]=3 [error]=4)

set_logger()
{
    [[ -v "log_level[$1]" ]] && current_level=${log_level[$1]} || current_level=${log_level['warning']}
}

mylogger()
{
    _log_level=${log_level[$1]}
    _log_message=$2

    if [[ $_log_level -ge $current_level ]]; then
        echo "${_log_message}"
    fi
}

usage()
{
cat << EOM
Usage:
 ${0##*/} [OPTIONS] [cfg file] [Guest image files..] [CD image files..]

Options:
 --bios                     Using legacy BIOS instead of UEFI
 --consol                   Used the current terminal as the consol I/O
 --qemu | -q                Use the qemu public distribution
 --rmssh                    Remove existing SSH keys 
 --tpm                      Support TPM device for windows 11
 --arch | -a                The architecture of target VM.
 --connect                  Connection method - 'ssh' 'spice'(default)
 --debug                    Set the logging level. (default: 'warning')
 --ipmi <ipmimodel>         IPMI model - 'external', 'internal'
 --net, -n <netmode>        Network card model - 'user', 'tap', 'bridge'(default)
 --uname, -u <UNAME>        Set login user name
 --vga, -g <GRAPHIC>        Set the type of VGA graphic card. 'virtio', 'qxl'(default)
 --stick                    Set the USB storage image
 --image, -i <imagename>    Set the VM images
 --nvme, -e <NVME_BACKEND>  Set the NVMe images ex) 'nvme0'
 --kernel, -k <KERNEL>      Set the Linux Kernel image
 --pci                      PCI passthrough 
 --numns, -o <num_of_ns>    Set the numbers of NVMe namespace
EOM
}

init()
{
    args_uname=${SUDO_USER:-$USER}
    args_rmssh=0
    args_net="bridge"
    args_arch="x86_64"
    args_vga="qxl"
    args_connect="spice"
    args_machine="q35"
    home_folder="/home/$args_uname"
    phy_mem=$(($(awk '/MemTotal/ {print $2}' /proc/meminfo) / (1024*1000)))
    [[ $phy_mem -gt 8 ]] && memsize="8G" || memsize="4G"
}

set_args()
{
    options=$(getopt --name ${0##*/} --options qa:d:n:u:i:h \
                    --long bios,consol,noshare,nousb,qemu,rmssh,tpm,arch:,connect:,debug:,ipmi:,machine:,net:,uname:,vga:,stick:,images:,nvme:,kernel:,pci:,numns:,help -- "$@")
    [ $? != 0 ] && { 
        usage
        exit 1
    }
    eval set -- "$options"

    while true; do
        case "$1" in
            # Command line argment parsing
            --bios )        args_bios=1 ;;                          # Using legacy BIOS instead of UEFI
            --consol )      args_consol=1 ;;                        # Used the current terminal as the consol I/O
            --noshare )     args_noshare=1 ;;                       # Do not support virtiofs
            --nousb )       args_nousb=1 ;;                         # Do not support usb port
            --qemu | -q )   args_qemu=1 ;;                          # Use the qemu public distribution
            --rmssh )       args_rmssh=1 ;;                         # Remove existing SSH key 
            --tpm )         args_tpm=1 ;;                           # Support TPM device for windows 11
            --arch | -a )   args_arch="$2" ;      shift ;;          # The architecture of target VM.
            --connect )     args_connect="$2" ;   shift ;;          # Connection method - 'ssh' 'spice'(default)
            --debug | -d )  args_debug="$2" ;     shift ;;          # Set the logging level. (default: 'warning')
            --ipmi)         args_ipmi="$2" ;      shift ;;          # IPMI model - 'external', 'internal'
            --machine )     args_machine="$2" ;   shift ;;          # Machine type for x86_64
            --net | -n )    args_net="$2" ;       shift ;;          # Network interface model - 'user', 'tap', 'bridge'
            --uname | -u )  args_uname="$2" ;     shift ;;          # Set login user name
            --vga )         args_vga="$2" ;       shift ;;          # Set the type of VGA graphic card. 'virtio', 'qxl'(default)
            --stick )       args_stick="$2" ;     shift ;;          # Set the USB storage image
            --images | -i ) vmimages+=("$2") ;    shift ;;          # Set the VM images
            --nvme )        vmnvme=("$2") ;       shift ;;          # Set the NVMe images
            --kernel )      vmkernel="$2" ;       shift ;;          # Set the Linux Kernel image
            --pcihost )     args_pcihost="$2" ;   shift ;;          # PCI passthrough 
            --numns )                                               # Set the numbers of NVMe namespace
                [[ $2 -eq 0 ]] && { use_nvme=0; } || { use_nvme=1; [[ $2 -ge 1 ]] && arg_numns=$2; } ; shift ;;
            -h | --help )   usage ;             exit;;
            --)             shift ;             break ;;
        esac
        shift
    done 

    while (($#)); do
        args_images+=($1)
        shift
    done
    set_logger $args_debug
}

set_images()
{
    for image in ${args_images[@]}; do
        if [[ -e $image ]] || [[ 'nvme' == ${image::4} ]]; then
            case $image in 
                *.img | *.IMG)          vmimages+=($image) ;;
                *.qcow2 | *.QCOW2)      vmimages+=($image) ;;
                *.vhdx | *.VHDX)        vmimages+=($image) ;;
                *.iso | *.ISO)          vmcdimages+=($image) ;;
                /dev/*)                 vmimages+=($image) ;;
                nvme*)                  
                                        vmnvme+=($image) 
                                        use_nvme=1 ;;
                *vmlinuz*)              vmkernel=$image ;;
                * )                     break;;
            esac
        fi
    done
    
    _boot_dev=("${vmimages[@]}" "${vmnvme[@]}" "${vmcdimages[@]}" "${vmkernel[@]}")
    mylogger info "vmimages: ${vmimages[*]}"
    mylogger info "vmcdimages: ${vmcdimages[*]}"
    mylogger info "vmnvme: ${vmnvme[*]}"
    mylogger info "vmkernel: ${vmkernel[*]}"
    mylogger info "boot_dev: ${_boot_dev[*]}"
    if [[ -z $_boot_dev ]] && [[ -z $vmkernel ]]; then
        mylogger error "There is no Boot device!!" ; exit 1
    fi
    boot_0=$(realpath ${_boot_dev[0]})
    vmname=${boot_0##*/} ; vmname=${vmname%.*}
    vmguid=$(echo -n ${boot_0} | md5sum)
    vmuid=${vmguid::2}
    vmprocid=${vmname::12}_${vmuid}
    G_TERM="gnome-terminal --title=$vmprocid"
    _index=0
}

runshell()
{
    cmd=$1
    if [[ $2 == 'True' ]]; then
        mylogger debug "runshell Async: ${cmd[@]}"
        (${cmd[@]})& 
        returncode=0
        sleep 1
    else
        mylogger debug "runshell: ${cmd[@]}"
        completed_stdout=$(${cmd[@]}); returncode=$?
        mylogger debug "Return code: $returncode, stdout: $completed_stdout"
    fi
    return $returncode
}

set_qemu()
{
    [[ $UID > 0 ]] && SUDO="sudo" || SUDO=
    [[ $args_qemu -eq 1 ]] && qemu_exe=("qemu-system-$args_arch") || qemu_exe=("$home_folder/qemu/bin/qemu-system-$args_arch")
    (which $qemu_exe >& /dev/null) || { mylogger error "$qemu_exe was not installed!!" ; exit 1; }

    params=(-name $vmname,process=$vmprocid)
    case $args_arch in
        "arm" )
            params+=(-machine virt -cpu cortex-a53 -device ramfb) ;;
        "aarch64" )
            params+=(-machine virt -cpu cortex-a72 -device ramfb) ;;
        "x86_64" )
            params+=(-machine type=${args_machine},accel=kvm,usb=on -device intel-iommu)
            params+=(-cpu host --enable-kvm)
            params+=(-object rng-random,id=rng0,filename=/dev/urandom -device virtio-rng-pci,rng=rng0)
			opts+=(-vga $args_vga) ;;
    esac
    _numcore=$(($(nproc)/2))
    params+=(
        -m ${memsize} -smp ${_numcore},sockets=1,cores=${_numcore},threads=1 -nodefaults
        -rtc base=localtime)
}

set_uefi()
{
    case $args_arch in
        "x86_64" )
            _OVMF_PATH="/usr/share/OVMF"
            _OVMF_CODE="${_OVMF_PATH}/OVMF_CODE.fd" ;;
        "aarch64" )
            _OVMF_PATH="/usr/share/qemu-efi-aarch64"
            _OVMF_CODE="${_OVMF_PATH}/QEMU_EFI.fd" ;;
        * )
            return ;;
    esac
    _UEFI=(
        -bios $_OVMF_CODE)
    params+=(${_UEFI[@]})
}

set_usb3()
{
    _USB=(-device qemu-xhci,id=usb3)
    _USB_REDIR=(
        -chardev spicevmc,name=usbredir,id=usbredirchardev1 -device usb-redir,chardev=usbredirchardev1,id=usbredirdev1
        -chardev spicevmc,name=usbredir,id=usbredirchardev2 -device usb-redir,chardev=usbredirchardev2,id=usbredirdev2
        -chardev spicevmc,name=usbredir,id=usbredirchardev3 -device usb-redir,chardev=usbredirchardev3,id=usbredirdev3
        -chardev spicevmc,name=usbredir,id=usbredirchardev4 -device usb-redir,chardev=usbredirchardev4,id=usbredirdev4)
    _USB_PT=(-device usb-host,hostbus=3,hostport=1)
    params+=(${_USB[@]} ${_USB_REDIR[@]})
}

set_usb_storage()
{
    if [[ $args_stick ]] && [[ -e $args_stick ]]; then
        _STICK=(
            -drive file=$args_stick,if=none,format=raw,id=stick$_index
            -device usb-storage,drive=stick$_index)
        ((_index++))
        params+=(${_STICK[@]})
    fi
}

set_usb_arm()
{
    _USB=(
        -device qemu-xhci,id=usb3 -device usb-kbd -device usb-tablet)
    params+=(${_USB[@]})
}

set_disks()
{
    _SCSI=(
        -object iothread,id=iothread0 -device virtio-scsi-pci,id=scsi0,iothread=iothread0)
    _DISKS=()
    for _image in ${vmimages[@]}; do
        case $_image in
            *.qcow2 | *.QCOW2)
                _DISKS+=(
                    -drive file=$_image,cache=writeback,id=drive-$_index)   ;;
            *.vhdx | *.VHDX)
                _DISKS+=(
                    -drive file=$_image,if=none,id=drive-$_index
                    -device nvme,drive=drive-$_index,serial=nvme-$_index)   ;;
            * )
                # if [[ -b $_image ]] && [[ $_image != *nvme* ]]; then _disk_type="scsi-hd"; else _disk_type="scsi-hd"; fi
                _DISKS+=(
                    -drive file=$_image,if=none,format=raw,discard=unmap,aio=native,cache=none,id=drive-$_index
                    -device scsi-hd,scsi-id=$_index,drive=drive-$_index,id=scsi0-$_index)   ;;
        esac
        ((_index++))
    done
    [[ -n $_DISKS ]] && params+=(${_SCSI[@]} ${_DISKS[@]})
}

set_cdrom()
{
    [[ $args_arch == "x86_64" ]] && _IF="ide" || _IF="none"
    _CDROMS=()
    for _image in ${vmcdimages[@]}; do
        _CDROMS+=(
            -drive file=$_image,media=cdrom,readonly=on,if=$_IF,index=$_index,id=cdrom$_index)
        if [[ $args_arch != "x86_64" ]]; then
            _CDROMS+=(
                -device usb-storage,drive=cdrom$_index) ; fi
        ((_index++))
    done
    [[ -n $_CDROMS ]] && params+=(${_CDROMS[@]})
}

check_file()
{
    local filename=$1
    local size=$2
    
    [[ -e $filename ]] || (runshell "qemu-img create -f raw ${filename} ${size}G")
    if ! (runshell "lsof -w $filename"); then
        return 0; fi
    return 1
}

set_nvme()
{   
    [[ $use_nvme -eq 1 ]] || return
    _num_ns=${arg_numns:-4}
    _ns_size=1
    vmnvme=${vmnvme:-"nvme${vmuid}"}

    _ctrl_id=1
    NVME=(
        -device ioh3420,bus=pcie.0,id=root1.0,slot=1
        -device x3130-upstream,bus=root1.0,id=upstream1.0)
        
    for _NVME in ${vmnvme[@]}; do
        if [[ $args_qemu -eq 1 ]] ; then
            ns_backend=${_NVME}n1.img
            if (check_file $ns_backend $_ns_size); then
                NVME+=(
                    -drive file=$ns_backend,id=${_NVME},format=raw,if=none,cache=none
                    -device nvme,drive=${_NVME},serial=beef${_NVME}); fi
        else
            NVME+=(
                -device xio3130-downstream,bus=upstream1.0,id=downstream1.$_ctrl_id,chassis=$_ctrl_id,multifunction=on
                -device nvme-subsys,id=nvme-subsys-$_ctrl_id,nqn=subsys$_ctrl_id
                -device nvme,serial=beef${_NVME},id=${_NVME},subsys=nvme-subsys-$_ctrl_id,bus=downstream1.$_ctrl_id)
            ((_ctrl_id++))
            for ((_nsid=1;_nsid<=$_num_ns;_nsid++)); do
                ns_backend=${_NVME}n${_nsid}.img
                if (check_file $ns_backend $_ns_size); then
                    NVME+=(
                        -drive file=$ns_backend,id=${_NVME}${_nsid},format=raw,if=none,cache=none
                        -device nvme-ns,drive=${_NVME}${_nsid},bus=${_NVME},nsid=${_nsid}); fi
            done
        fi
    done
    [[ -f ./events ]] && NVME+=(--trace events=./events)
    [[ -n $NVME ]] && params+=(${NVME[@]})
}

set_virtiofs()
{
    virtiofsd=($SUDO $G_TERM --geometry=80x24+5+5 -- 
        $home_folder/qemu/libexec/virtiofsd --socket-path=/tmp/virtiofs_${vmuid}.sock -o source=$home_folder)
    if [[ $args_debug == 'cmd' ]]; then
        echo "${virtiofsd[*]}"
    else
        (runshell "${virtiofsd[*]}" 'True')
        until [[ -e "/tmp/virtiofs_${vmuid}.sock" ]]; do 
            sleep 1
            mylogger debug "wating for /tmp/virtiofs_${vmuid}.sock"; done
    fi
    _virtiofs=(-chardev socket,id=char${vmuid},path=/tmp/virtiofs_${vmuid}.sock
        -device vhost-user-fs-pci,chardev=char${vmuid},tag=hostfs
        -object memory-backend-memfd,id=mem,size=${memsize},share=on -numa node,memdev=mem)
    params+=(${_virtiofs[@]})
}

set_ipmi()
{
    case $args_ipmi in
        "internal" )
            _IPMI=(-device ipmi-bmc-sim,id=bmc0) ;;
        "external" )
            _IPMI=(
                -chardev socket,id=ipmi0,host=localhost,port=9002,reconnect=10
                -device ipmi-bmc-extern,chardev=ipmi0,id=bmc1
                -device isa-ipmi-kcs,bmc=bmc1) ;;
    esac
    [[ -n $_IPMI ]] && params+=(${_IPMI[@]})   
}

set_spice()
{
    SPICE=(
        -spice port=$SPICEPORT,disable-ticketing=on
        -device intel-hda -device hda-duplex)
    SPICE_AGENT=(
        -chardev spicevmc,id=vdagent,name=vdagent
        -device virtio-serial
        -device virtserialport,chardev=vdagent,name=com.redhat.spice.0)
    GUEST_AGENT=(
        -chardev socket,path=/tmp/qga.sock,server,nowait,id=qga0,name=qga0
        -device virtio-serial
        -device virtserialport,chardev=qga0,name=org.qemu.guest_agent.0)
    SHARE0=(
        -virtfs local,id=fsdev0,path=$home_folder,security_model=passthrough,writeout=writeout,mount_tag=host)
    params+=(${SPICE[@]} ${SPICE_AGENT[@]})
}

set_tpm()
{
    fn_cancle="/tmp/foo-cancel-${vmuid}"
    [[ -e $fn_cancle ]] || touch $fn_cancle

    TPM=(
        -tpmdev passthrough,id=tpm0,path=/dev/tpm0,cancel-path=$fn_cancle
        -device tpm-tis,tpmdev=tpm0)
    params+=(${TPM[@]})
}

RemoveSSH()
{
    [[ -e /tmp/${vmprocid}_SSH ]] && { rm /tmp/${vmprocid}_SSH ; }
    if [[ $args_net == "user" ]]; then
        ssh-keygen -R "[${hostip}]:${SSHPORT}"
    else
        ssh-keygen -R "${localip}"
    fi
}

set_net()
{
    local _set=$1
    [ -f /tmp/${vmprocid}_SSH ] && SSHPORT=$(< /tmp/${vmprocid}_SSH) || SSHPORT=5900
    SPICEPORT=$(($SSHPORT+1))
    macaddr="52:54:00:${vmguid::2}:${vmguid:2:2}:${vmguid:4:2}"
    runshell "ip r g 1.0.0.0"
    _result=($completed_stdout); [[ ${#_result[@]} ]] && hostip=${_result[6]} || hostip='localhost'
    mylogger info "hostip: ${hostip}"
    runshell "virsh --quiet net-dhcp-leases default --mac ${macaddr}"; _result=$completed_stdout
    SAVEIFS=$IFS; IFS=$'\n'; dhcp_leases=($_result); IFS=$SAVEIFS ; [[ $dhcp_leases ]] && dhcp_chk=(${dhcp_leases[-1]})
    [[ -n $dhcp_chk ]] && localip=${dhcp_chk[4]%/*}
    mylogger info "localip: ${localip}"

    if [[ $_set -eq 1 ]]; then
        while (runshell "lsof -w -i :$SPICEPORT") || (runshell "lsof -w -i :$SSHPORT"); do 
            SSHPORT=$(($SSHPORT+2))
            SPICEPORT=$(($SSHPORT+1)); done 
        case $args_net in 
            "user"|"u" )
                NET=(
                    -nic user,model=virtio-net-pci,mac=$macaddr,smb=$home_folder,hostfwd=tcp::${SSHPORT}-:22) ;;
            "tap"|"t" )
                NET=(
                    -nic tap,model=virtio-net-pci,mac=$macaddr,script=$home_folder/projects/scripts/qemu-ifup) ;;
                    # ,downscript=$home_folder/vm/share/qemu-ifdown  ;;
            "bridge"|"b" )
                NET=(
                    -nic bridge,br=virbr0,model=virtio-net-pci,mac=$macaddr) ;;
        esac
        params+=(${NET[@]})
        echo $SSHPORT > /tmp/${vmprocid}_SSH
    fi
}

set_connect()
{
    case $args_connect in
        "ssh" )
            { opts=(${opts[@]/"-vga"}) ; opts=(${opts[@]/"$args_vga"}) ; }
            opts+=(-nographic -serial mon:stdio)
            [[ $args_net == "user" ]] && SSH_CONNECT="${hostip} -p $SSHPORT" || { [[ -n $localip ]] && SSH_CONNECT=$localip ; }
            CHKPORT=$SSHPORT
            CONNECT=($G_TERM --
				ssh $args_uname@${SSH_CONNECT}) ;;
        "spice" )
            opts+=(-monitor stdio)
            CHKPORT=$SPICEPORT
            CONNECT=(
                remote-viewer -t $vmprocid spice://${hostip}:$SPICEPORT --spice-usbredir-auto-redirect-filter="0x03,-1,-1,-1,0|-1,-1,-1,-1,1") ;;
        "qemu" )
            opts+=(-monitor stdio)
            CHKPORT=$SPICEPORT
            CONNECT=("")
    esac
    mylogger info "${CONNECT[*]}"
}

findProc()
{
    local _PROCID=$1
    local _timeout=${2:-10}
    
    until (runshell "ps -C $_PROCID"); do 
        mylogger debug "findProc timeout ${_timeout}"
        ((_timeout--))
        [[ $_timeout < 0 ]] && return 1
        sleep 1
    done
    mylogger debug "findProc return 1"
    return 0
}

checkConn()
{
    local _timeout=${1:-10}
    [[ -n $SSH_CONNECT ]] || return 0
    until (runshell "ping -c 1 $SSH_CONNECT"); do
        ((_timeout--))
        [[ $_timeout < 0 ]] && return 1
        sleep 1
    done 
    return 0
}

set_kernel() 
{
    KERNEL=(-kernel ${vmkernel})
    [[ $vmkernel == *vmlinuz* ]] && KERNEL+=(-initrd ${vmkernel/"vmlinuz"/"initrd.img"})
    
    if [[ $args_connect -eq "ssh" ]]; then
        PARAM=(-append "root=/dev/sda console=ttyS0")
    else
        PARAM=(-append "root=/dev/sda vga=0x300")
    fi
}

set_pcipass()
{
    [[ -z $args_pcihost ]] && return 
    # unbind 0000:0x:00.0 from xhci_hcd kernel module
    _driver_=$($SUDO lspci -k -s $args_pcihost | awk '/Kernel driver.*/{print $NF}')
    $SUDO -S sh -c "echo '$args_pcihost' > /sys/bus/pci/drivers/$_driver_/unbind"
    # bind 0000:0x:00.0 to vfio-pci kernel module
    DEVID=$($SUDO lspci -ns $args_pcihost | awk '//{print $NF}' | awk -F: '{print "%s %s", $1, $2}')
    $SUDO -S sh -c "echo '$DEVID' > /sys/bus/pci/drivers/vfio-pci/new-id"
    
    PCIPASS=" -device vfio-pci,host=$args_pcihost,multifunction=on"
    params+=($PCIPASS)
}

# main
setting()
{
    set_images
    if ! (findProc $vmprocid 0); then
        set_qemu
        [[ $args_bios != 1 ]] && set_uefi
        [[ $vmkernel ]] && set_kernel
        # set_pcipass
        [[ $args_nousb != 1 ]] && { [[ $args_arch == "x86_64" ]] && set_usb3 || set_usb_arm ; }
        set_disks
        set_cdrom
        set_nvme
        set_usb_storage
        [[ $args_noshare != 1 ]] && set_virtiofs
        set_net 1
        set_ipmi
        [[ $args_connect == "spice" ]] && set_spice
        [[ $args_tpm ]] && set_tpm
        set_connect
    else
        set_net
        set_connect
    fi

    [[ $args_rmssh -eq 1 ]] && RemoveSSH
}

run()
{
    if ! (findProc $vmprocid 0); then
        _qemu_command=($SUDO $( [[ $args_debug != 'debug' ]] && echo $G_TERM -- )
            $qemu_exe ${params[@]} ${opts[@]} ${KERNEL[@]} "${PARAM[@]}")
        if [[ $args_debug == 'cmd' ]]; then
            (IFS=' '; echo "${_qemu_command[*]}")
        else
            completed=$("${_qemu_command[@]}"); fi
    fi
    if [[ -n $CONNECT ]]; then
        _qemu_connect=(${CONNECT[*]})
        if [[ $args_debug == 'cmd' ]]; then
            (IFS=' '; echo "${_qemu_connect[*]}")
        else
            if [[ -z ${completed} ]] && (findProc $vmprocid); then
                if [[ $args_connect == 'ssh' ]]; then
                    checkConn 60; fi
                (runshell "${_qemu_connect[*]}" 'True')
            fi
        fi
    fi
}

# main
init
set_args "$@"
setting
run
