#!/bin/bash

MODULE_INSTALL=0
MKCONFIG=0

while getopts ":b:i:t:cC:l:" opt; do
    case $opt in
        b)  [ $OPTARG == 'k' ] && BUILD+=" bzImage"
            [ $OPTARG == 'm' ] && BUILD+=" modules"
            [ $OPTARG == 'd' ] && BUILD+=" bindeb-pkg" ;;
        i)  [ $OPTARG == 'k' ] && INSTALL+=" bzImage"
            [ $OPTARG == 'm' ] && INSTALL+=" modules_install"
            [ $OPTARG == 'h' ] && INSTALL+=" headers_install" ;;
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

# BUILD=${BUILD:-"bzImage"}
CFG_FILE=${CFG_FILE:-"/boot/config-$(uname -r)"}
TARGETDIR=${TARGETDIR:-"$PWD/rootfs"}
LOCALVERSION=${LOCALVERSION:-"ocssd"}

isEmptyFolder() 
{
    [ -d $1 ] || return 1 
    local _count=`find $1 -mindepth 1 -maxdepth 1 | wc -l`
    [ $_count -eq 0 ] && return 0 || return 1
}

MakeConfig() {
    make clean
    cp $CFG_FILE .config
    # cp /usr/src/linux-headers-$(uname -r)/Module.symvers .
    make olddefconfig
}

KernelBuild() {
    echo $TARGETDIR $1

    make prepare
    make modules_prepare
    make scripts
    echo make -j `getconf _NPROCESSORS_ONLN` $1 LOCALVERSION=-$LOCALVERSION
    make -j `getconf _NPROCESSORS_ONLN` $1 LOCALVERSION=-$LOCALVERSION
}

Install()
{
    local _TARGETDIR=$1
    
    if [ -z $_TARGETDIR ]; then
        echo sudo make $INSTALL
        sudo make $INSTALL
    else
        if ( isEmptyFolder $_TARGETDIR ); then
            echo empty folder $_TARGETDIR
        else
            echo sudo make INSTALL_MOD_PATH=$_TARGETDIR INSTALL_HDR_PATH=$_TARGETDIR/usr/src/$(make kernelversion) $INSTALL
            sudo make INSTALL_MOD_PATH=$_TARGETDIR INSTALL_HDR_PATH=$_TARGETDIR/usr/src/$(make kernelversion) $INSTALL
        fi
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

KernelBuild $BUILD

[[ -z $INSTALL ]] || Install $TARGETDIR

