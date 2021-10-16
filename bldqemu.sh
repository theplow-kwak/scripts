#!/bin/bash

TMP=${PWD%/*}
NAME=${TMP##*/}

usage()
{
cat << EOM
Usage:
 ${0##*/} [OPTIONS] command

Command:
 setup_env                  setup build environment
 config                     configuration
 clean                      clean bluid
 distclean                  distclean
 bld                        build
 
Options:
 -n, --name <NAME>          set the executable name
 -a, --arch <architecture>  supported architecture
 -p, --path <PATH>          set the install PATH
EOM
}

options=$(getopt -n ${0##*/} -o n:p:a:h \
                --long name:,path:,arch:,help -- "$@")
[ $? -eq 0 ] || { 
    usage
    exit 1
}
eval set -- "$options"

while true; do
    case "$1" in
        -n | --name )   NAME=$2 ;       shift ;;    # set login user name
        -a | --arch )   ARCH+=(${2//,/ }) ;    shift ;;    
        -p | --path )   PREFIX=$2 ;     shift ;;
        -h | --help )   usage ;         exit ;;
        --)             shift ;         break ;;
    esac
    shift
done 

PREFIX=${PREFIX:-$HOME/$NAME}

setup_env()
{
    sudo apt install -y libglib2.0-dev libfdt-dev libpixman-1-dev zlib1g-dev
    sudo apt install -y libaio-dev libbluetooth-dev libbrlapi-dev libbz2-dev
    sudo apt install -y libcap-dev libcap-ng-dev libcurl4-gnutls-dev libgtk-3-dev
    sudo apt install -y libibverbs-dev libjpeg8-dev libncurses5-dev libnuma-dev
    sudo apt install -y librbd-dev librdmacm-dev libblockdev-mpath-dev
    sudo apt install -y libsasl2-dev libsdl1.2-dev libseccomp-dev libsnappy-dev libssh2-1-dev
    sudo apt install -y libvde-dev libvdeplug-dev libvte-2.91-dev libxen-dev liblzo2-dev
    sudo apt install -y valgrind xfslibs-dev 
    sudo apt install -y flex bison ninja-build 
    sudo apt install -y libspice-server-dev libspice-server1 libudev-dev libusb-dev libusbredirparser-dev libusb-1.0-0-dev
}

config()
{
    TRACE=${1:-"log"}

    ARCH=${ARCH-"x86_64"}
    for _ARCH in ${ARCH[@]};
    do
        [[ -n $TARGET ]] && TARGET+=","
        TARGET+="${_ARCH}-softmmu"
    done
	
    CFG=" \
        --target-list=$TARGET --prefix=$PREFIX --enable-trace-backends=$TRACE \
        --enable-kvm --enable-linux-aio --enable-gtk --enable-spice \
        --enable-virtfs --enable-vhost-net --enable-snappy --enable-mpath \
        --enable-libusb --enable-usb-redir --enable-plugins --enable-user \
        "
    # --disable-xen --enable-modules --sysconfdir=/etc --disable-stack-protector --disable-werror --enable-debug --extra-cflags="-g3" --extra-ldflags="-g3" \

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
