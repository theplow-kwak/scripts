#!/bin/bash

unload=0
while getopts ":u" opt; do
	case $opt in
		u)    unload=1 ;;	
		\?)   echo "Invalid option: -$OPTARG" >&2 ;;
		:)    echo "Option -$OPTARG requires an argument." >&2 ;;
	esac
done 

pushd ~/linux-4.15.0/drivers/nvme
sudo rmmod nvme
sudo rmmod nvme-core
if [ $unload != 1 ]
then
    sudo insmod host/nvme-core.ko streams=1
    sudo insmod host/nvme.ko
fi
popd
