#!/bin/bash

info() 
{
    sudo nvme lnvm list
    echo " "
    sudo nvme lnvm id-ns /dev/nvme0
}

init() 
{
    DEVICE=nvme0n1
    sudo nvme lnvm init -d $DEVICE
}

pblk()
{
    DEVICE=nvme0n1
    TARGET_NAME=${3:-"pblk0"}
    TARGET_TYPE=pblk
    LUN_BEGIN=${1:-0}
    LUN_END=${2:-3}
    echo nvme lnvm create -d $DEVICE -n $TARGET_NAME -t $TARGET_TYPE -b $LUN_BEGIN -e $LUN_END
    sudo nvme lnvm create -d $DEVICE -n $TARGET_NAME -t $TARGET_TYPE -b $LUN_BEGIN -e $LUN_END
}

rmpblk() 
{
    TARGET_NAME=${1:-"pblk0"}
    echo nvme lnvm remove -n $TARGET_NAME
    sudo nvme lnvm remove -n $TARGET_NAME
}

mnt()
{
    TARGET_NAME=${1:-"pblk0"}
    DESTDIR="/tmp/$TARGET_NAME"
    SOURCE="/dev/$TARGET_NAME"
  
    rm -rdf $DESTDIR
    mkdir $DESTDIR
  
    sudo mkfs.ext4 $SOURCE
    echo mount $SOURCE $DESTDIR
    sudo mount $SOURCE $DESTDIR
}

umnt()
{
    TARGET_NAME=${1:-"pblk0"}
    DESTDIR="/tmp/$TARGET_NAME"
    sudo umount $DESTDIR
}

[ $1 == "1" ] && { info ; exit 1 ; }
[ $1 == "2" ] && { init ; exit 1 ; }
[ $1 == "3" ] && { pblk $2 $3 $4 ; exit 1 ; }
[ $1 == "4" ] && { mnt $2 ; exit 1 ; }
[ $1 == "5" ] && { umnt $2 ; exit 1 ; }
[ $1 == "6" ] && { rmpblk $2 ; exit 1 ; }

$1 $2 $3 $4
