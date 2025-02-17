#!/bin/bash

# sudo apt install debootstrap

isEmptyFolder() 
{
    [ -d $1 ] || return 1 
    local _count=`find $1 -mindepth 1 -maxdepth 1 | wc -l`
    [ $_count -eq 0 ] && return 0 || return 1
}

FormatDisk() 
{
    if [ ! -e $ROOTFS_FILE ]; then
        qemu-img create $ROOTFS_FILE $IMGSIZE
    fi
    if [ -O $ROOTFS_FILE ]; then
        mkfs.ext4 $ROOTFS_FILE
    else
        sudo mkfs.ext4 $ROOTFS_FILE
    fi
}

InstallModules()
{
    echo install kernel module dirvers of $KERNEL
    if [[ ! $(findmnt $MOUNT_PATH) ]]; then
        echo $MOUNT_PATH does not mounted !! stop processing !
        exit 1
    fi
    if [[ -n $KERNEL ]]; then
        kernel_path=$(realpath ~/projects/${KERNEL})
        if [[ -d $kernel_path ]]; then
            pushd $kernel_path
            bldkernel -ihm -t $MOUNT_PATH
            popd
        fi
    fi
}

MakeRootFS()
{
    local _DESTRO=${DESTRO:-"mantic"}
    local _MIRROR=${MIRROR:-"http://mirror.kakao.com/ubuntu/"}
    local _INCLUDE=${INCLUDE:-"--include=build-essential,flex,bison,libssl-dev,libelf-dev,liburing-dev,bc,openssh-server,cifs-utils,net-tools,ca-certificates,gpg,wget,git"}     # ,language-pack-ko
    
    if [[ ! $(findmnt $MOUNT_PATH) ]]; then
        echo $MOUNT_PATH does not mounted !! stop processing !
        exit 1
    fi

    if ! command -v debootstrap &> /dev/null; then echo "debootstrap is not supported!"; return; fi
    echo debootstrap --verbose $_INCLUDE --arch amd64 $_DESTRO $MOUNT_PATH $_MIRROR
    sudo debootstrap --verbose $_INCLUDE --arch amd64 $_DESTRO $MOUNT_PATH $_MIRROR

    pushd $MOUNT_PATH

    sudo mkdir ./mnt/host
    printf "%s\n" \
        "# UNCONFIGURED FSTAB FOR BASE SYSTEM" \
        "#" \
        "/dev/sda       /               ext4    defaults        1 1" \
        "hostfs     /mnt/host       virtiofs      defaults,nofail,comment=cloudconfig    0 2" \
        | sudo dd of=./etc/fstab

    printf "%s\n" \
        "${HOST_NAME}" \
        | sudo dd of=./etc/hostname

    printf "%s\n" \
        "network:" \
        "  version: 2" \
        "  ethernets:" \
        "    id0:" \
        "      match:" \
        "        name: en*" \
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
        "ln -fs /usr/share/zoneinfo/Asia/Seoul /etc/localtime" \
        "dpkg-reconfigure -f noninteractive tzdata" \
        "timedatectl set-local-rtc 1 --adjust-system-clock" \
        "adduser --gecos \"\" --disabled-password $USER_NAME" \
        "echo ${USER_NAME}:1 | chpasswd" \
        "usermod -aG sudo $USER_NAME" \
        | sudo dd of=./setupenv.sh
        sudo chmod +x ./setupenv.sh
    
    LANG=C.UTF-8 sudo chroot $MOUNT_PATH /bin/bash setupenv.sh   
    sudo rm ./setupenv.sh

    sudo cp ~/vm/share/.smb.cred ./etc/
    sudo chmod 600 ./etc/.smb.cred
    sudo mkdir ./home/$USER_NAME/wpc
    sudo chown $USER_NAME:$USER_NAME ./home/$USER_NAME/wpc
    popd

    InstallModules
}

MountFolder() {
    if (isEmptyFolder $MOUNT_PATH ); then
        echo mount $ROOTFS_FILE to $MOUNT_PATH
        sudo mount -o loop $ROOTFS_FILE $MOUNT_PATH
    else
        echo "$MOUNT_PATH was not empty. can't mount $ROOTFS_FILE"
        MKROOT=0
    fi
}

unMountFolder() {
    if [[ ! $(findmnt $MOUNT_PATH) ]]; then
        echo $MOUNT_PATH does not mounted !!
        exit 1
    fi
    echo umount $MOUNT_PATH
    sudo umount $MOUNT_PATH
    exit 1
}

ChRoot() {  
    if [[ ! $(findmnt $MOUNT_PATH) ]]; then
        echo $MOUNT_PATH does not mounted !! stop processing !
        exit 1
    fi
    LANG=C.UTF-8 sudo chroot $MOUNT_PATH /bin/bash
}

usage()
{
cat << EOM
Usage:
 ${0##*/} [OPTIONS]

Options:
 -x, --unmount      unmount the rootfs directory
 -c, --chroot       chroot to the rootfs directory
 -f, --format       format the rootfs file
 -m, --mkroot       make rootfs file
 -M, --module       install kernel modules into the rootfs file
 -k, --kernel       set the kernel version
 -i, --imgname      set the image name
 -u, --user         set the user name
 -d, --distro       set the distro name
 -s, --size         set the rootfs size
 -t, --target       set the rootfs target directory

EOM
}

UNMOUNT=0
CHROOT=0
FORMAT=0
MKROOT=0
MODULE=0
USER_NAME=${SUDO_USER:-$USER}
IMGNAME=${PWD##*/}

while getopts ":xcfmMk:i:u:d:s:t:n:" opt; do
    case $opt in
        x)  UNMOUNT=1 ;;	
        c)  CHROOT=1 ;;
        f)  FORMAT=1 ;;
        m)  MKROOT=1 ;;
        M)  MODULE=1 ;;
        k)	KERNEL=$OPTARG ;;
		i)  IMGNAME=$OPTARG ;;
        u)  USER_NAME=$OPTARG ;;
        d)  DESTRO=$OPTARG ;;
        s)  SIZE=$OPTARG ;;
        t)  MPATH=$OPTARG ;;
        \?) echo "Invalid option: -$OPTARG" >&2 
            usage ; exit 1 ;;
        :)  echo "Option -$OPTARG requires an argument." >&2 
            usage ; exit 1 ;;
    esac
done 

shift $(($OPTIND-1)) 

_TMP=$(echo -n ${IMGNAME} | md5sum)
HOST_NAME=${HOST_NAME:-"${IMGNAME%.*}-VM-${_TMP::2}"}

ROOTFS_FILE=${1:-"./${IMGNAME}.img"}
IMGSIZE=${SIZE:-"16g"}
_MOUNT_PATH=${MPATH:-$PWD/rootfs}
MOUNT_PATH=$(realpath $_MOUNT_PATH)

echo rootfs file: $ROOTFS_FILE
echo rootfs path: $MOUNT_PATH

[ $FORMAT -eq 1 ] && FormatDisk
MountFolder
[ $MKROOT -eq 1 ] && { MakeRootFS; unMountFolder; }
[ $MODULE -eq 1 ] && { InstallModules; unMountFolder; }
[ $CHROOT -eq 1 ] && chroot
[ $UNMOUNT -eq 1 ] && unMountFolder

echo " end of work"

