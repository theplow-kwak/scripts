#!/bin/bash

IMGFILE="./image/rootfs.img"
UNLOAD=0
TARGETFOLDER="./rootfs"
CHROOT=0

while getopts ":uci:" opt; do
	case $opt in
		u)    UNLOAD=1 ;;	
		i)    IMGFILE=$OPTARG ;;
		c)    CHROOT=1 ;;
		\?)   echo "Invalid option: -$OPTARG" >&2 ;;
		:)    echo "Option -$OPTARG requires an argument." >&2 ;;
	esac
done 

shift $(($OPTIND-1)) 

if [ ! -d $TARGETFOLDER ]; then
	mkdir $TARGETFOLDER
fi

if [ $UNLOAD == 1 ]; then
	sudo umount ./rootfs
else
	sudo mount -o loop $IMGFILE ./rootfs
	if [ $CHROOT == 1 ]; then
        LANG=C.UTF-8 sudo chroot ./rootfs /bin/bash
    fi
fi
