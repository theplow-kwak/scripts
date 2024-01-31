#!/bin/bash

TMP=${PWD%/*}
TARGET=${TMP##*/}

while getopts ":p:t:" opt; do
    case $opt in
        t)  TARGET=$OPTARG ;;
        P)  PREFIX=$OPTARG ;;
        *)  usage ;;
    esac
done 

shift $(($OPTIND-1)) 

PREFIX=${PREFIX:-$HOME/$TARGET}

setup_env()
{
    sudo apt install -y flex bison
    sudo apt install -y libglib2.0-dev libfdt-dev libpixman-1-dev zlib1g-dev
    sudo apt install -y libspice-server-dev libspice-server1 libudev-dev libusb-dev libusbredirparser-dev
    sudo apt install -y libaio-dev libbluetooth-dev libbrlapi-dev libbz2-dev
    sudo apt install -y libcap-dev libcap-ng-dev libcurl4-gnutls-dev libgtk-3-dev
    sudo apt install -y libibverbs-dev libjpeg8-dev libncurses5-dev libnuma-dev
    sudo apt install -y librbd-dev librdmacm-dev
    sudo apt install -y libsasl2-dev libsdl1.2-dev libseccomp-dev libsnappy-dev libssh2-1-dev
    sudo apt install -y libvde-dev libvdeplug-dev libvte-2.90-dev libxen-dev liblzo2-dev
    sudo apt install -y valgrind xfslibs-dev 
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
    if [[ -e ./configure ]]; then
        ./configure $CFG
    else
        ../configure $CFG
    fi
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

