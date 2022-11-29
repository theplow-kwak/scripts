#!/bin/bash

BACKIMG="../cd/CentOS-Stream-GenericCloud-8-20220913.0.x86_64.qcow2"
IMGNAME="centos-8.3.qcow2"
QEMU="qemu2"
NET="bridge"

while getopts ":b:i:q:n:" opt; do
	case $opt in
		b)    BACKIMG=$OPTARG ;;
		i)    IMGNAME=$OPTARG ;;
		q)    QEMU=$OPTARG ;;	
		n)    NET=$OPTARG ;;	
		\?)   echo "Invalid option: -$OPTARG" >&2 ;;
		:)    echo "Option -$OPTARG requires an argument." >&2 ;;
	esac
done 
shift $(($OPTIND-1))

if [[ ! -e $IMGNAME ]]; then
    qemu-img create -f qcow2 $IMGNAME -F qcow2 -b $BACKIMG
    qemu-img resize $IMGNAME 30G
    CLOUD_INIT="cloud_init.iso"
fi

if [[ -e $IMGNAME ]]; then
    echo $QEMU --bios --connect ssh --net $NET --uname test $IMGNAME $CLOUD_INIT $@
    $QEMU --bios --connect ssh --net $NET --uname test $IMGNAME $CLOUD_INIT $@
fi
