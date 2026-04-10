#!/bin/bash

install=0
while getopts ":i" opt; do
	case $opt in
        i)    install=1 ;;	
		\?)   echo "Invalid option: -$OPTARG" >&2 ;;
		:)    echo "Option -$OPTARG requires an argument." >&2 ;;
	esac
done 

pushd ../linux-4.15.0/drivers/nvme

make -C /lib/modules/`uname -r`/build M=`pwd` clean modules

if [ $install == 1 ]
then
    sudo make -C /lib/modules/`uname -r`/build M=`pwd` modules_install install
fi

popd
