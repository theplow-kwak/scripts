#!/bin/bash

NS=${NS:-"1"}

info() 
{
    sudo nvme lnvm list
    echo " "
    sudo nvme lnvm id-ns /dev/nvme0
}

init() 
{
    NS=${1:-$NS}
    DEVICE=nvme0n$NS
    echo nvme lnvm init -d $DEVICE
    sudo nvme lnvm init -d $DEVICE
}

pblk()
{
    NS=${1:-$NS}
    DEVICE=nvme0n$NS
    PN=${2:-$NS}
    TARGET_NAME="pblk$PN"
    TARGET_TYPE=pblk
    LUN_BEGIN=${3:-0}
    LUN_END=${4:-63}
    echo nvme lnvm create -d $DEVICE -n $TARGET_NAME -t $TARGET_TYPE -b $LUN_BEGIN -e $LUN_END
    sudo nvme lnvm create -d $DEVICE -n $TARGET_NAME -t $TARGET_TYPE -b $LUN_BEGIN -e $LUN_END
}

rmpblk() 
{
    PN=${1:-$NS}
    TARGET_NAME="pblk$PN"
    echo nvme lnvm remove -n $TARGET_NAME
    sudo nvme lnvm remove -n $TARGET_NAME
}

fmt()
{
    TARGET_NAME=${1:-"pblk$NS"}
    DESTDIR="/tmp/$TARGET_NAME"
    SOURCE="/dev/$TARGET_NAME"
  
    echo mkfs.ext4 $SOURCE
    sudo mkfs.ext4 $SOURCE
}

mnt()
{
    TARGET_NAME=${1:-"pblk$NS"}
    DESTDIR="/tmp/$TARGET_NAME"
    SOURCE="/dev/$TARGET_NAME"

    mkdir $DESTDIR
    echo mount $SOURCE $DESTDIR
    sudo mount $SOURCE $DESTDIR
}

umnt()
{
    TARGET_NAME=${1:-"pblk$NS"}
    DESTDIR="/tmp/$TARGET_NAME"
    echo umount $DESTDIR
    sudo umount $DESTDIR
    rm -rdf $DESTDIR
}

[ $1 == "1" ] && { info $2  exit 1 ; }
[ $1 == "2" ] && { init $2 ; exit 1 ; }
[ $1 == "3" ] && { pblk $2 $3 $4 ; exit 1 ; }
[ $1 == "4" ] && { mnt $2 ; exit 1 ; }
[ $1 == "5" ] && { umnt $2 ; exit 1 ; }
[ $1 == "6" ] && { rmpblk $2 ; exit 1 ; }

$1 $2 $3 $4
