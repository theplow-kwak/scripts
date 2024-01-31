#!/bin/bash

while getopts ":ed" opt; do
	case $opt in
		e)    sudo sh -c 'echo 1 > /sys/module/nvme_core/parameters/streams' ;;
		d)    sudo sh -c 'echo 0 > /sys/module/nvme_core/parameters/streams' ;;
		\?)   echo "Invalid option: -$OPTARG" >&2 ;;
		:)    echo "Option -$OPTARG requires an argument." >&2 ;;
	esac
done 

cat /sys/module/nvme_core/parameters/streams 
