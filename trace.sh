#!/bin/bash

#parserpath=/mnt/hgfs/D/Workspace/nvmeparser/
parserpath=./
getlog=0
outfile="nvme_tmp.log"

while getopts ":vlco:" opt; do
	case $opt in
		v)    parserpath=/mnt/hgfs/D/Workspace/traceparser/ ;;
		l)    parserpath=/media/dhkwak/CCE6B6D8E6B6C1CE/Workspace/traceparser/ ;;
		c)    getlog=1 ;;	
		o)    outfile=$OPTARG ;;
		\?)   echo "Invalid option: -$OPTARG" >&2 ;;
		:)    echo "Option -$OPTARG requires an argument." >&2 ;;
	esac
done 

shift $(($OPTIND-1)) 

stringContain() { [ -z "${2##*$1*}" ]; }

set()
{
TARGET=${1:-"scsi block nvme"}

if stringContain "nvme" "$TARGET"; then sudo sh -c 'echo 1 > /sys/kernel/debug/tracing/events/nvme/enable'; fi
if stringContain "scsi" "$TARGET"; then sudo sh -c 'echo 1 > /sys/kernel/debug/tracing/events/scsi/enable'; fi
if stringContain "block" "$TARGET"
then 
  #sudo sh -c 'echo block_rq_insert >> /sys/kernel/debug/tracing/set_event'
  sudo sh -c 'echo block_rq_complete >> /sys/kernel/debug/tracing/set_event'
  sudo sh -c 'echo block_rq_issue >> /sys/kernel/debug/tracing/set_event'
  sudo sh -c 'echo block_rq_remap >> /sys/kernel/debug/tracing/set_event'
  sudo sh -c 'echo block_rq_requeue >> /sys/kernel/debug/tracing/set_event'
fi
}

reset()
{
sudo sh -c 'echo 0 > /sys/kernel/debug/tracing/events/nvme/enable'
sudo sh -c 'echo 0 > /sys/kernel/debug/tracing/events/scsi/enable'
sudo sh -c 'echo > /sys/kernel/debug/tracing/set_event'
}

on()
{
sudo sh -c 'echo 0 > /sys/kernel/debug/tracing/trace'
sudo sh -c 'echo 1 > /sys/kernel/debug/tracing/tracing_on'
}

off()
{
sudo sh -c 'echo 0 > /sys/kernel/debug/tracing/tracing_on'
sudo sh -c 'echo 0 > /sys/kernel/debug/tracing/trace'
}

log()
{
    OUTFILE_NAME=${1:-"tracelog.log"}

    if [[ -z $1 ]]
    then
        echo sudo cat /sys/kernel/debug/tracing/trace_pipe 
        sudo cat /sys/kernel/debug/tracing/trace_pipe 
    else
        echo sudo cat /sys/kernel/debug/tracing/trace_pipe > ${OUTFILE_NAME}
        sudo cat /sys/kernel/debug/tracing/trace_pipe > ${OUTFILE_NAME}
    fi
}

echo $1 "$2"
$1 "$2"


