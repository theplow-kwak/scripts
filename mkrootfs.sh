#!/bin/bash


isEmptyFolder() 
{
    [ -d $1 ] || return 1 
    local _count=`find $1 -mindepth 1 -maxdepth 1 | wc -l`
    [ $_count -eq 0 ] && return 0 || return 1
}

FormatDisk() 
{
    local _IMGFILE=$1

    if [ ! -e $_IMGFILE ]; then
        qemu-img create $_IMGFILE $IMGSIZE
        # dd if=/dev/zero of=$_IMGFILE bs=1M count=32768
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
    local _DESTRO=${DESTRO:-"cosmic"}
    
    if [[ ! $(findmnt $_TARGETDIR) ]]; then
        echo $_TARGETDIR does not mounted !! stop processing !
        exit 1
    fi

    echo debootstrap --verbose --arch amd64 $_DESTRO $_TARGETDIR http://archive.ubuntu.com/ubuntu
    sudo debootstrap --verbose --arch amd64 $_DESTRO $_TARGETDIR http://archive.ubuntu.com/ubuntu

    pushd $_TARGETDIR

    sudo mkdir ./mnt/host
    printf "%s\n" \
        "# UNCONFIGURED FSTAB FOR BASE SYSTEM" \
        "#" \
        "/dev/sda       /               ext4    defaults        1 1" \
        "# sharepoint     /mnt/host       9p      trans=virtio    0 0" \
        | sudo dd of=./etc/fstab

    printf "%s\n" \
        "QEMU-OCSSD" \
        | sudo dd of=./etc/hostname

    printf "%s\n" \
        "network:" \
        "  version: 2" \
        "  renderer: networkd" \
        "  ethernets:" \
        "    ens:" \
        "      match:" \
        "        name: ens*" \
        "      dhcp4: true" \
        | sudo dd of=./etc/netplan/01-network-all.yaml

    printf "%s\n" \
        "deb http://kr.archive.ubuntu.com/ubuntu/ $_DESTRO main restricted universe multiverse" \
        "deb-src http://kr.archive.ubuntu.com/ubuntu/ $_DESTRO main restricted universe multiverse" \
        "" \
        "deb http://kr.archive.ubuntu.com/ubuntu/ $_DESTRO-updates main restricted universe multiverse" \
        "deb-src http://kr.archive.ubuntu.com/ubuntu/ $_DESTRO-updates main restricted universe multiverse" \
        "" \
        "deb http://kr.archive.ubuntu.com/ubuntu/ $_DESTRO-security main restricted universe multiverse" \
        "deb-src http://kr.archive.ubuntu.com/ubuntu/ $_DESTRO-security main restricted universe multiverse" \
        | sudo dd of=./etc/apt/sources.list

    printf "%s\n" \
        "dpkg-reconfigure tzdata" \
        "apt update" \
        "apt install -y language-pack-ko" \
        "apt install -y openssh-server" \
        "apt install -y tasksel net-tools nvme-cli" \
        "tasksel install standard" \
        "apt upgrade" \
        "adduser $UNAME" \
        "addgroup --system admin" \
        "adduser $UNAME admin" \
        "passwd root" \
        | sudo dd of=./setupenv.sh
        sudo chmod +x ./setupenv.sh
    
    LANG=C.UTF-8 sudo chroot $_TARGETDIR /bin/bash setupenv.sh
    sudo rm ./setupenv.sh
    popd
    
    unMountFolder $_TARGETDIR
}

MountFolder() {
    local _IMGFILE=$1
    local _TARGETDIR=$2

    if (isEmptyFolder $_TARGETDIR ); then
        echo mount $_IMGFILE to $_TARGETDIR
        sudo mount -o loop $_IMGFILE $_TARGETDIR
    else
        echo "$_TARGETDIR was not empty. can't mount $_IMGFILE"
        MKROOT=0
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

UNLOAD=0
CHROOT=0
FORMAT=0
MKROOT=0
UNAME=${SUDO_USER:-$USER}
TARGETDIR="$PWD/rootfs"

while getopts ":ucfmn:d:s:t:" opt; do
    case $opt in
        u)  UNLOAD=1 ;;	
        c)  CHROOT=1 ;;
        f)  FORMAT=1 ;;
        m)  MKROOT=1 ;;
        n)  UNAME=$OPTARG ;;
        d)  DESTRO=$OPTARG ;;
        s)  SIZE=$OPTARG ;;
        t)  TARGETDIR=$OPTARG ;;
        \?) echo "Invalid option: -$OPTARG" >&2 
            exit 1 ;;
        :)  echo "Option -$OPTARG requires an argument." >&2 
            exit 1 ;;
    esac
done 

shift $(($OPTIND-1)) 

IMGFILE=${1:-"/dev/nvme1n1p1"}
IMGSIZE=${SIZE:-"16g"}
TARGETDIR=${2:-"$TARGETDIR"}

echo source $IMGFILE
echo target $TARGETDIR

[ $UNLOAD -eq 1 ] && unMountFolder $TARGETDIR

[ $FORMAT -eq 1 ] && FormatDisk $IMGFILE $TARGETDIR

MountFolder $IMGFILE $TARGETDIR

[ $MKROOT -eq 1 ] && MakeRootFS $TARGETDIR

[ $CHROOT -eq 1 ] && ChRoot $TARGETDIR

echo " end of work"

