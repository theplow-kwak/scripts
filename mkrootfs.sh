#!/bin/bash

UNLOAD=0
CHROOT=0
FORMAT=0
MKROOT=0
USER=$USERNAME

while getopts ":ucfrn:" opt; do
    case $opt in
        u)  UNLOAD=1 ;;	
        c)  CHROOT=1 ;;
        f)  FORMAT=1 ;;
        r)  MKROOT=1 ;;
        n)  USER=$OPTARG ;;
        \?) echo "Invalid option: -$OPTARG" >&2 
            exit 1 ;;
        :)  echo "Option -$OPTARG requires an argument." >&2 
            exit 1 ;;
    esac
done 

shift $(($OPTIND-1)) 

IMGFILE=${1:-"./image/rootfs.img"}
TARGETDIR=${2:-"./rootfs"}

isEmptyFolder() 
{
    local _count=`find $1 -mindepth 1 -maxdepth 1 | wc -l`
    [ $_count -eq 0 ] && return 0 || return 1
}

FormatDisk() 
{
    local _IMGFILE=$1

    if [ ! -e $_IMGFILE ]; then
        dd if=/dev/zero of=$_IMGFILE bs=1M count=32768
    fi
    if [ -u $_IMGFILE ]; then
        mkfs.ext4 $_IMGFILE
    else
        sudo mkfs.ext4 $_IMGFILE
    fi
}

MakeRootFS()
{
    local _TARGETDIR=$1

    sudo debootstrap --verbose --arch amd64 bionic $_TARGETDIR http://archive.ubuntu.com/ubuntu

    printf "%s\n" \
        "# UNCONFIGURED FSTAB FOR BASE SYSTEM" \
        "#" \
        "/dev/vda        /               ext3    defaults        1 1" \
        "dev             /dev            tmpfs   rw              0 0" \
        "tmpfs           /dev/shm        tmpfs   defaults        0 0" \
        "devpts          /dev/pts        devpts  gid=5,mode=620  0 0" \
        "sysfs           /sys            sysfs   defaults        0 0" \
        "proc            /proc           proc    defaults        0 0" \
        | sudo dd of=$_TARGETDIR/etc/fstab

    pushd $_TARGETDIR
    sudo sh -c 'echo QEMU-OCSSD > ./etc/hostname'
    popd

    printf "%s\n" \
        "network:" \
        "  version: 2" \
        "  renderer: networkd" \
        "  ethernets:" \
        "    ens:" \
        "      match:" \
        "        name: ens*" \
        "      dhcp4: true" \
        | sudo dd of=$_TARGETDIR/etc/netplan/01-network-all.yaml

    printf "%s\n" \
        "deb http://kr.archive.ubuntu.com/ubuntu/ bionic main restricted universe multiverse" \
        "deb-src http://kr.archive.ubuntu.com/ubuntu/ bionic main restricted universe multiverse" \
        "" \
        "deb http://kr.archive.ubuntu.com/ubuntu/ bionic-updates main restricted universe multiverse" \
        "deb-src http://kr.archive.ubuntu.com/ubuntu/ bionic-updates main restricted universe multiverse" \
        "" \
        "deb http://kr.archive.ubuntu.com/ubuntu/ bionic-security main restricted universe multiverse" \
        "deb-src http://kr.archive.ubuntu.com/ubuntu/ bionic-security main restricted universe multiverse" \
        | sudo dd of=$_TARGETDIR/etc/apt/sources.list

    printf "%s\n" \
        "dpkg-reconfigure tzdata" \
        "apt update" \
        "apt install language-pack-ko" \
        "apt install openssh-server" \
        "apt install tasksel net-tools nvme-cli" \
        "tasksel install standard" \
        "apt upgrade" \
        "adduser $USER" \
        "addgroup --system admin" \
        "adduser $USER admin" \
        "passwd root" \
        | sudo dd of=$_TARGETDIR/setupenv.sh
        sudo chmod +x $_TARGETDIR/setupenv.sh
    
    LANG=C.UTF-8 sudo chroot $_TARGETDIR /bin/bash setupenv.sh
    sudo rm $_TARGETDIR/setupenv.sh
}

MountFolder() {
    local _IMGFILE=$1
    local _TARGETDIR=$2

    if (isEmptyFolder $_TARGETDIR ); then
        echo mount $_IMGFILE to $_TARGETDIR
        sudo mount -o loop $_IMGFILE $_TARGETDIR
    else
        echo "$_TARGETDIR was not empty. can't mount $_IMGFILE"
    fi
}

unMountFolder() {
    local _TARGETDIR=$1

    echo umount $_TARGETDIR
    sudo umount $_TARGETDIR
    exit 1
}

ChRoot() {
    local _TARGETDIR=$1
    
    LANG=C.UTF-8 sudo chroot $_TARGETDIR /bin/bash
}

echo source $IMGFILE
echo target $TARGETDIR

[ $UNLOAD -eq 1 ] && unMountFolder $TARGETDIR

[ $FORMAT -eq 1 ] && FormatDisk $IMGFILE $TARGETDIR

MountFolder $IMGFILE $TARGETDIR

[ $MKROOT -eq 1 ] && MakeRootFS $TARGETDIR

[ $CHROOT -eq 1 ] && ChRoot $TARGETDIR

echo " end of work"

