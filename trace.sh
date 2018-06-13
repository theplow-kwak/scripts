#!/bin/bash

#parserpath=/mnt/hgfs/D/Workspace/nvmeparser/
parserpath=./
getlog=0

while getopts ":vlc" opt; do
	case $opt in
		v)    parserpath=/mnt/hgfs/D/Workspace/traceparser/ ;;
		l)    parserpath=/media/dhkwak/CCE6B6D8E6B6C1CE/Workspace/traceparser/ ;;
		c)    getlog=1 ;;	
		\?)   echo "Invalid option: -$OPTARG" >&2 ;;
		:)    echo "Option -$OPTARG requires an argument." >&2 ;;
	esac
done 

shift $(($OPTIND-1)) 

sudo sh -c 'echo 1 > /sys/kernel/debug/tracing/events/nvme/enable'
sudo sh -c 'echo 1 > /sys/kernel/debug/tracing/tracing_on'
if [ $getlog == 1 ]
then
    sudo cat /sys/kernel/debug/tracing/trace_pipe | tee nvme_tmp.log
else
    sudo cat /sys/kernel/debug/tracing/trace_pipe | python3 ${parserpath}nvmeparser.py $@
fi

