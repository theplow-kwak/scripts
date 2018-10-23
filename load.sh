#!/bin/bash

unload=0
strms=8
while getopts ":us:" opt; do
	case $opt in
		u)    unload=1 ;;	
		s)    strms=$OPTARG;;
		\?)   echo "Invalid option: -$OPTARG" >&2 ;;
		:)    echo "Option -$OPTARG requires an argument." >&2 ;;
	esac
done 

pushd ../linux-4.15.0/drivers/nvme
sudo rmmod nvme
sudo rmmod nvme-core
if [ $unload != 1 ]
then
    sudo insmod host/nvme-core.ko streams=${strms}
    sudo insmod host/nvme.ko
fi
popd
