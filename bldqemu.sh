#!/bin/bash

TARGET=${PWD##*/}

while getopts ":p:P:" opt; do
    case $opt in
        p)  TARGET=$OPTARG ;;     # Specify a new ssh port.
        P)  PREFIX=$OPTARG ;;       # Remove existing SSH keys and specify a new ssh port.
        *)  usage ;;
    esac
done 

shift $(($OPTIND-1)) 

PREFIX=${PREFIX:-$HOME/$TARGET}

config()
{
    TRACE=${1:-"nop"}
    
    CFG=" --enable-kvm --target-list=x86_64-softmmu --enable-linux-aio \
        --disable-werror --disable-xen --prefix=$PREFIX --enable-gtk --enable-spice \
        --enable-virtfs --enable-vhost-net --enable-modules --enable-snappy \
        --enable-debug --extra-cflags="-g3" --extra-ldflags="-g3" --disable-stack-protector \
        --enable-trace-backends=$TRACE"

    echo $CFG
    ./configure $CFG
}

bld()
{
    make -j `getconf _NPROCESSORS_ONLN` && make install
}

clean()
{
    make clean
}

$1 $2

