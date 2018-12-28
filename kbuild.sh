#!/bin/bash

MODULE_INSTALL=0
MKCONFIG=0

while getopts ":kmdiI:cC:" opt; do
    case $opt in
        k)  TARGET="$TARGET bzImage" ;;	
        m)  TARGET="$TARGET modules" ;;
        d)  TARGET="$TARGET bindeb-pkg" ;;
        i)  MODULE_INSTALL=1 ;;
        I)  MODULE_INSTALL=1
            TARGETDIR=$OPTARG ;;
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

[[ -z $TARGET ]] && TARGET="bzImage"
[[ -z $CFG_FILE ]] && CFG_FILE="/boot/config-$(uname -r)"
[[ -z $TARGETDIR ]] && TARGETDIR="$HOME/vm/rootfs"

isEmptyFolder() 
{
    local _count=`find $1 -mindepth 1 -maxdepth 1 | wc -l`
    [ $_count -eq 0 ] && return 0 || return 1
}

MakeConfig() {
    make clean
    cp $1 .config
    make olddefconfig
}

KernelBuild() {
    make prepare
    make scripts
    make -j `getconf _NPROCESSORS_ONLN` $1 LOCALVERSION=-ocssd
}

ModuleInstall()
{
    local _TARGETDIR=$1
    
    if ( isEmptyFolder $_TARGETDIR ); then
        echo empty folder $_TARGETDIR
    else
        sudo INSTALL_MOD_PATH=$_TARGETDIR make modules_install
    fi
}

[ $MKCONFIG -eq 1 ] && MakeConfig $CFG_FILE

KernelBuild $TARGET

[ $MODULE_INSTALL -eq 1 ] && ModuleInstall $TARGETDIR

