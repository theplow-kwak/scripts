#!/bin/bash

while getopts ":f:r:s:" opt; do
    case $opt in
        f)  FILENAME=$OPTARG ;;
        r)  RWMIX=$OPTARG ;;
        s)  FSYNC=$OPTARG ;;
        \?) echo "Invalid option: -$OPTARG" >&2 
            exit 1 ;;
        :)  echo "Option -$OPTARG requires an argument." >&2 
            exit 1 ;;
    esac
done 

shift $(($OPTIND-1)) 

FILENAME=${FILENAME:-"/mnt/nvme/test"}
RWMIX=${RWMIX:-"100"}
FSYNC=${FSYNC:-"0"}

#
echo "fio --direct=1 --randrepeat=1 --ioengine=libaio --gtod_reduce=1 --name=test --filename=$FILENAME --bs=4k --iodepth=128 --size=40G --readwrite=randrw --rwmixread=$RWMIX --fsync=$FSYNC"
sudo fio --direct=1 --randrepeat=1 --ioengine=libaio --gtod_reduce=1 --name=test --filename=$FILENAME --bs=4k --iodepth=128 --size=40G --readwrite=randrw --rwmixread=$RWMIX 

