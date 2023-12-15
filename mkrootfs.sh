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
    local _ROOTFS_FILE=$1

    if [ ! -e $_ROOTFS_FILE ]; then
        qemu-img create $_ROOTFS_FILE $IMGSIZE
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
    local _DESTRO=${DESTRO:-"mantic"}
    local _MIRROR=${MIRROR:-"http://mirror.kakao.com/ubuntu/"}
    local _INCLUDE=${INCLUDE:-"--include=build-essential,flex,bison,libssl-dev,libelf-dev,liburing-dev,bc,openssh-server,cifs-utils,net-tools,ca-certificates,gpg,wget,git"}     # ,language-pack-ko
    
    if [[ ! $(findmnt $_MOUNT_PATH) ]]; then
        echo $_MOUNT_PATH does not mounted !! stop processing !
        exit 1
    fi

    echo debootstrap --verbose $_INCLUDE --arch amd64 $_DESTRO $_MOUNT_PATH $_MIRROR
    sudo debootstrap --verbose $_INCLUDE --arch amd64 $_DESTRO $_MOUNT_PATH $_MIRROR

    pushd $_MOUNT_PATH

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
    
    LANG=C.UTF-8 sudo chroot $_MOUNT_PATH /bin/bash setupenv.sh   
    sudo rm ./setupenv.sh

    sudo cp ~/vm/share/.smb.cred ./etc/
    sudo chmod 600 ./etc/.smb.cred
    sudo mkdir ./home/$USER_NAME/wpc
    sudo chown $USER_NAME:$USER_NAME ./home/$USER_NAME/wpc
    popd

    if [[ -n $KERNEL ]]; then
        kernel_path=$(realpath ~/projects/${KERNEL})
        pushd $kernel_path
        bldkernel -i m -t $_MOUNT_PATH
        popd
    fi

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

usage()
{
cat << EOM
Usage:
 ${0##*/} [OPTIONS]

Options:
 -d, --docker       Path to the docker file
 -s, --share        Path to the shared folder
 -c, --container    Name of the container what you want to run
 -r, --rm           Remove the container
 -R, --rmi          Remove the docker image and associated containers.

EOM
}

UNLOAD=0
CHROOT=0
FORMAT=0
MKROOT=0
USER_NAME=${SUDO_USER:-$USER}
IMGNAME=${PWD##*/}

while getopts ":xu:cfmn:d:s:t:i:k:" opt; do
    case $opt in
        x)  UNLOAD=1 ;;	
        c)  CHROOT=1 ;;
        f)  FORMAT=1 ;;
        m)  MKROOT=1 ;;
        k)	KERNEL=$OPTARG ;;
		i)  IMGNAME=$OPTARG ;;
        u)  USER_NAME=$OPTARG ;;
        d)  DESTRO=$OPTARG ;;
        s)  SIZE=$OPTARG ;;
        t)  MPATH=$OPTARG ;;
        \?) echo "Invalid option: -$OPTARG" >&2 
            exit 1 ;;
        :)  echo "Option -$OPTARG requires an argument." >&2 
            exit 1 ;;
    esac
done 

shift $(($OPTIND-1)) 

_TMP=$(echo -n ${IMGNAME} | md5sum)
HOST_NAME=${HOST_NAME:-"${IMGNAME%.*}-VM-${_TMP::2}"}

ROOTFS_FILE=${1:-"./${IMGNAME}.img"}
IMGSIZE=${SIZE:-"16g"}
MOUNT_PATH=${MPATH:-$(realpath $PWD/rootfs)}

echo source $ROOTFS_FILE
echo target $MOUNT_PATH

[ $UNLOAD -eq 1 ] && unMountFolder $MOUNT_PATH

[ $FORMAT -eq 1 ] && FormatDisk $ROOTFS_FILE $MOUNT_PATH

MountFolder $ROOTFS_FILE $MOUNT_PATH

[ $MKROOT -eq 1 ] && MakeRootFS $MOUNT_PATH

[ $CHROOT -eq 1 ] && ChRoot $MOUNT_PATH

echo " end of work"

