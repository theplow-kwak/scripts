#!/bin/bash

MODULE_INSTALL=0
MKCONFIG=0

while getopts ":b:i:t:cC:l:" opt; do
    case $opt in
        b)  [ $OPTARG == 'k' ] && BUILD="$BUILD bzImage"
            [ $OPTARG == 'm' ] && BUILD="$BUILD modules"
            [ $OPTARG == 'd' ] && BUILD="$BUILD bindeb-pkg" ;;
        i)  [ $OPTARG == 'k' ] && INSTALL="$INSTALL bzImage"
            [ $OPTARG == 'm' ] && INSTALL="$INSTALL modules_install"
            [ $OPTARG == 'h' ] && INSTALL="$INSTALL headers_install" ;;
        t)  TARGETDIR=$OPTARG ;;
        l)  LOCALVERSION=$OPTARG ;;
        c)  MKCONFIG=1 ;;
        C)  MKCONFIG=1
            CFG_FILE=$OPTARG ;;
        \?) echo "Invalid option: -$OPTARG" >&2 
            exit 1 ;;
        :)  echo "Option -$OPTARG requires an argument." >&2 
            exit 1 ;;
    esac
done 

shift $(($OPTIND-1)) 

BUILD=${BUILD:-"bzImage"}
CFG_FILE=${CFG_FILE:-"/boot/config-$(uname -r)"}
TARGETDIR=${TARGETDIR:-"$HOME/vm/rootfs"}
LOCALVERSION=${LOCALVERSION:-"ocssd"}

isEmptyFolder() 
{
    local _count=`find $1 -mindepth 1 -maxdepth 1 | wc -l`
    [ $_count -eq 0 ] && return 0 || return 1
}

MakeConfig() {
    make clean
    cp $1 .config
    cp /usr/src/linux-headers-$(uname -r)/Module.symvers .
    make olddefconfig
}

KernelBuild() {
    make prepare
    make scripts
    make -j `getconf _NPROCESSORS_ONLN` $1 LOCALVERSION=-$LOCALVERSION
}

Install()
{
    local _TARGETDIR=$1
    
    if [ -z $_TARGETDIR ]; then
        sudo make $INSTALL
    else
        sudo INSTALL_MOD_PATH=$_TARGETDIR INSTALL_HDR_PATH=$_TARGETDIR make $INSTALL
    fi
}

ModuleInstall()
{
    local _TARGETDIR=$1
    
    if [ -z $_TARGETDIR ]; then
        sudo make modules_install
    else
        sudo INSTALL_MOD_PATH=$_TARGETDIR make modules_install
    fi
}

HeaderInstall()
{
    local _TARGETDIR=$1
    
    if ( isEmptyFolder $_TARGETDIR ); then
        echo empty folder $_TARGETDIR
    else
        sudo INSTALL_HDR_PATH=$_TARGETDIR make headers_install
    fi
}

[ $MKCONFIG -eq 1 ] && MakeConfig $CFG_FILE

KernelBuild $TARGET

[ $MODULE_INSTALL -eq 1 ] && ModuleInstall $TARGETDIR

