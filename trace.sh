#!/bin/bash

usage()
{
cat << EOM
Usage:
 ${0##*/} [OPTIONS] dockerimage

Options:
 -e, --event        The name of trace event
 -s, --share        Path to the shared folder
 -c, --container    Name of the container what you want to run
 -r, --rm           Remove the container
 -R, --rmi          Remove the docker image and associated containers.

EOM
}

options=$(getopt -n ${0##*/} -o e: \
                --long help,event: -- "$@")
[ $? -eq 0 ] || { usage; exit 1; }
eval set -- "$options"

while true; do
    case $1 in
        -e | --event )      EVENTS+=(${2//,/ }) ;   shift ;;
        -h | --help )       usage ;                 exit ;;
        --)                 shift ;                 break ;;
    esac
    shift
done 

stringContain() { [ -z "${2##*$1*}" ]; }

set()
{
    for EVENT in ${EVENTS[@]};
    do
        sudo sh -c "echo 1 > /sys/kernel/tracing/events/$EVENT/enable"
    done
}

reset()
{
    for EVENT in ${EVENTS[@]};
    do
        sudo sh -c "echo 0 > /sys/kernel/tracing/events/$EVENT/enable"
    done
}

on()
{
    sudo sh -c "echo 0 > /sys/kernel/tracing/trace"
    sudo sh -c "echo 1 > /sys/kernel/tracing/tracing_on"
    sudo cat /sys/kernel/debug/tracing/trace_pipe
}

off()
{
    sudo sh -c "echo 0 > /sys/kernel/tracing/tracing_on"
    sudo sh -c "echo 0 > /sys/kernel/tracing/trace"
}

log()
{
    OUTFILE_NAME=${1:-"tracelog.log"}

    if [[ -z $1 ]]
    then
        echo sudo cat /sys/kernel/tracing/trace_pipe 
        sudo cat /sys/kernel/tracing/trace_pipe 
    else
        echo sudo cat /sys/kernel/tracing/trace_pipe > ${OUTFILE_NAME}
        sudo cat /sys/kernel/tracing/trace_pipe > ${OUTFILE_NAME}
    fi
}

echo $1 $@
$1 $@


