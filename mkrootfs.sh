#!/bin/bash


isEmptyFolder() 
{
    [ -d $1 ] || return 1 
    local _count=`find $1 -mindepth 1 -maxdepth 1 | wc -l`
    [ $_count -eq 0 ] && return 0 || return 1
}

FormatDisk() 
{
    local _ROOTFS_FILE=$1

    if [ ! -e $_ROOTFS_FILE ]; then
        qemu-img create $_ROOTFS_FILE $IMGSIZE
        # dd if=/dev/zero of=$_ROOTFS_FILE bs=1M count=32768
    fi
    if [ -O $_ROOTFS_FILE ]; then
        mkfs.ext4 $_ROOTFS_FILE
    else
        sudo mkfs.ext4 $_ROOTFS_FILE
    fi
}

MakeRootFS()
{
    local _MOUNT_PATH=$1
    local _DESTRO=${DESTRO:-"kinetic"}
    local _MIRROR=${MIRROR:-"http://mirror.kakao.com/ubuntu/"}
    
    if [[ ! $(findmnt $_MOUNT_PATH) ]]; then
        echo $_MOUNT_PATH does not mounted !! stop processing !
        exit 1
    fi

    echo debootstrap --verbose --arch amd64 $_DESTRO $_MOUNT_PATH $_MIRROR
    sudo debootstrap --verbose --arch amd64 $_DESTRO $_MOUNT_PATH $_MIRROR

    pushd $_MOUNT_PATH

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
        "deb $_MIRROR $_DESTRO main restricted universe multiverse" \
        "deb-src $_MIRROR $_DESTRO main restricted universe multiverse" \
        "" \
        "deb $_MIRROR $_DESTRO-updates main restricted universe multiverse" \
        "deb-src $_MIRROR $_DESTRO-updates main restricted universe multiverse" \
        "" \
        "deb $_MIRROR $_DESTRO-security main restricted universe multiverse" \
        "deb-src $_MIRROR $_DESTRO-security main restricted universe multiverse" \
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
    
    LANG=C.UTF-8 sudo chroot $_MOUNT_PATH /bin/bash setupenv.sh
    sudo rm ./setupenv.sh
    popd
    
    unMountFolder $_MOUNT_PATH
}

MountFolder() {
    local _ROOTFS_FILE=$1
    local _MOUNT_PATH=$2

    if (isEmptyFolder $_MOUNT_PATH ); then
        echo mount $_ROOTFS_FILE to $_MOUNT_PATH
        sudo mount -o loop $_ROOTFS_FILE $_MOUNT_PATH
    else
        echo "$_MOUNT_PATH was not empty. can't mount $_ROOTFS_FILE"
        MKROOT=0
    fi
}

unMountFolder() {
    local _MOUNT_PATH=$1

    echo umount $_MOUNT_PATH
    sudo umount $_MOUNT_PATH
    exit 1
}

ChRoot() {
    local _MOUNT_PATH=$1
    
    LANG=C.UTF-8 sudo chroot $_MOUNT_PATH /bin/bash
}

UNLOAD=0
CHROOT=0
FORMAT=0
MKROOT=0
UNAME=${SUDO_USER:-$USER}
MOUNT_PATH="$PWD/rootfs"

while getopts ":ucfmn:d:s:t:" opt; do
    case $opt in
        u)  UNLOAD=1 ;;	
        c)  CHROOT=1 ;;
        f)  FORMAT=1 ;;
        m)  MKROOT=1 ;;
        n)  UNAME=$OPTARG ;;
        d)  DESTRO=$OPTARG ;;
        s)  SIZE=$OPTARG ;;
        t)  MOUNT_PATH=$OPTARG ;;
        \?) echo "Invalid option: -$OPTARG" >&2 
            exit 1 ;;
        :)  echo "Option -$OPTARG requires an argument." >&2 
            exit 1 ;;
    esac
done 

shift $(($OPTIND-1)) 

ROOTFS_FILE=${1:-"./rootfs.img"}
IMGSIZE=${SIZE:-"16g"}
MOUNT_PATH=${2:-"$MOUNT_PATH"}

echo source $ROOTFS_FILE
echo target $MOUNT_PATH

[ $UNLOAD -eq 1 ] && unMountFolder $MOUNT_PATH

[ $FORMAT -eq 1 ] && FormatDisk $ROOTFS_FILE $MOUNT_PATH

MountFolder $ROOTFS_FILE $MOUNT_PATH

[ $MKROOT -eq 1 ] && MakeRootFS $MOUNT_PATH

[ $CHROOT -eq 1 ] && ChRoot $MOUNT_PATH

echo " end of work"

