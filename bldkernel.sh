#!/bin/bash

MODULE_INSTALL=0
MKCONFIG=0

while getopts ":b:i:t:cC:l:" opt; do
    case $opt in
        b)  [[ $OPTARG =~ 'k' ]] && BUILD+=" bzImage"
            [[ $OPTARG =~ 'm' ]] && BUILD+=" modules"
            [[ $OPTARG =~ 'd' ]] && BUILD+=" deb-pkg"
            [[ $OPTARG =~ 'b' ]] && BUILD+=" bindeb-pkg" ;;
        i)  [[ $OPTARG =~ 'h' ]] && INSTALL+=" headers_install"
            [[ $OPTARG =~ 'm' ]] && INSTALL+=" modules_install"
            [[ $OPTARG =~ 'k' ]] && INSTALL+=" install" ;;
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
LOCALVERSION=${LOCALVERSION:-"custom"}
KVER=$(make kernelversion)-$LOCALVERSION
# KSRC="-C $PWD"
# export KBUILD_OUTPUT=$TARGETDIR/usr/src/$KVER

isEmptyFolder() 
{
    [[ -d $1 ]] || return 1 
    local _count=`find $1 -mindepth 1 -maxdepth 1 | wc -l`
    [[ $_count -eq 0 ]] && return 0 || return 1
}

MakeConfig()
{
    sudo make $KSRC clean
    cp $CFG_FILE .config
    cp /usr/src/linux-headers-$(uname -r)/Module.symvers .
    make $KSRC olddefconfig
}

KernelBuild()
{
    echo $TARGETDIR $BUILD

    make $KSRC prepare && make $KSRC modules_prepare && make $KSRC scripts
    local _CMD="make $KSRC -j `getconf _NPROCESSORS_ONLN` $BUILD LOCALVERSION=-$LOCALVERSION"
    echo $_CMD
    $_CMD
}

Install()
{
    local _TARGETDIR=$1
    
    if [[ -z $_TARGETDIR ]]; then
        echo sudo make $INSTALL
        sudo make $INSTALL
    else
        if ( isEmptyFolder $_TARGETDIR ); then
            echo empty folder $_TARGETDIR
        else
            local _CMD="make $KSRC INSTALL_PATH=$_TARGETDIR/boot INSTALL_MOD_PATH=$_TARGETDIR INSTALL_HDR_PATH=$_TARGETDIR/usr/src/$KVER $INSTALL"
            echo $_CMD
            sudo $_CMD && { 
                            sudo rm $_TARGETDIR/lib/modules/$KVER/build ;
                            sudo rm $_TARGETDIR/lib/modules/$KVER/source ;
                            sudo ln -s /usr/src/$KVER $_TARGETDIR/lib/modules/$KVER/build ;
                            sudo ln -s /usr/src/$KVER $_TARGETDIR/lib/modules/$KVER/source ; }
        fi
    fi
}

kpkgBuild()
{
    fakeroot make-kpkg -j `getconf _NPROCESSORS_ONLN` --append-to-version "-$LOCALVERSION" "$INSTALL"
}

kpkgInstall()
{
    echo kpkgInstall
}


[[ $MKCONFIG -eq 1 ]] && MakeConfig $CFG_FILE

[[ ! -z $BUILD ]] && KernelBuild  

[[ ! -z $INSTALL ]] && Install $TARGETDIR

