#!/bin/bash

TARGET=${PWD##*/}

while getopts ":p:P:" opt; do
    case $opt in
        p)  TARGET=$OPTARG ;;
        P)  PREFIX=$OPTARG ;;
        *)  usage ;;
    esac
done 

shift $(($OPTIND-1)) 

PREFIX=${PREFIX:-$HOME/$TARGET}

bldenv()
{
    sudo apt install libglib2.0-dev libfdt-dev libpixman-1-dev zlib1g-dev libsnappy-dev
}

config()
{
    TRACE=${1:-"log"}
    
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

distclean()
{
    make distclean && rm -rf *-linux-user *-softmmu
}

$1 $2

