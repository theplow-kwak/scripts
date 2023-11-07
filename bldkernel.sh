#!/bin/bash

isEmptyFolder() 
{
    [[ -d $1 ]] || return 1 
    local _count=`find $1 -mindepth 1 -maxdepth 1 | wc -l`
    [[ $_count -eq 0 ]] && return 0 || return 1
}

getOsVersion()
{
    if [ -f /etc/os-release ]; then
        # freedesktop.org and systemd
        . /etc/os-release
        _OS=$NAME
        _VER=$VERSION_ID
    elif type lsb_release >/dev/null 2>&1; then
        # linuxbase.org
        _OS=$(lsb_release -si)
        _VER=$(lsb_release -sr)
    elif [ -f /etc/lsb-release ]; then
        # For some versions of Debian/Ubuntu without lsb_release command
        . /etc/lsb-release
        _OS=$DISTRIB_ID
        _VER=$DISTRIB_RELEASE
    else
        # Fall back to uname, e.g. "Linux <version>", also works for BSD, etc.
        _OS=$(uname -s)
        _VER=$(uname -r)
    fi
}

MakeConfig()
{
    sudo make $KSRC clean
    cp $CFG_FILE .config
    getOsVersion
    if [[ $_OS == Ubuntu ]]; then
        cp /usr/src/linux-headers-$(uname -r)/Module.symvers .
    else
        cp /usr/src/kernels/$(uname -r)/Module.symvers .
    fi
    make $KSRC olddefconfig
    make $KSRC prepare && make $KSRC modules_prepare && make $KSRC scripts && return 0
    return 1
}

KernelBuild()
{
    local _CMD="make $KSRC -j `getconf _NPROCESSORS_ONLN` $BUILD LOCALVERSION=-$LOCALVERSION"
    echo $_CMD
    $_CMD
}

Install()
{
    if [[ -z $TARGETDIR ]]; then
        read -n 1 -p "Do you really want to install a new kernel on this machine? [y|n] " ans
        echo ""
        if [[ "$ans" == "y" ]]; then   
            echo sudo make $INSTALL
            sudo make $INSTALL
        fi
    else
        read -n 1 -p "Do you want to install a new kernel to the \"$TARGETDIR\"? [y|n] " ans
        echo ""
        [[ "$ans" != "y" ]] && return   
        if ( isEmptyFolder $TARGETDIR ); then
            echo empty folder $TARGETDIR
            echo please verify target folder \"$TARGETDIR\"
        else
            local _CMD="make $KSRC INSTALL_PATH=$TARGETDIR/boot INSTALL_MOD_PATH=$TARGETDIR INSTALL_HDR_PATH=$TARGETDIR/usr/src/$KVER $INSTALL"
            echo $_CMD
            sudo $_CMD && { 
                            sudo rm $TARGETDIR/lib/modules/$KVER/build ;
                            sudo rm $TARGETDIR/lib/modules/$KVER/source ;
                            sudo ln -s /usr/src/$KVER $TARGETDIR/lib/modules/$KVER/build ;
                            sudo ln -s /usr/src/$KVER $TARGETDIR/lib/modules/$KVER/source ; }
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

removeKernel()
{
    echo removeKernel $KVER
    sudo updatedb --prunepaths=/var/lib/dpkg
    locate -b -e $KVER
    echo
    locate -b -e $KVER | xargs -p sudo rm -r
    getOsVersion
    if [[ $_OS == *Ubuntu* ]]; then
        sudo update-grub
    else
        sudo grub2-mkconfig -o /boot/grub2/grub.cfg
    fi
}

MODULE_INSTALL=0
MKCONFIG=0

while getopts ":b:i:t:cC:l:r" opt; do
    case $opt in
        b)  [[ $OPTARG =~ 'b' ]] && BUILD+=" bindeb-pkg"
            [[ $OPTARG =~ 'k' ]] && BUILD+=" bzImage"
            [[ $OPTARG =~ 'm' ]] && BUILD+=" modules"
            [[ $OPTARG =~ 'd' ]] && BUILD+=" deb-pkg" ;;
        i)  [[ $OPTARG =~ 'h' ]] && INSTALL+=" headers_install"
            [[ $OPTARG =~ 'm' ]] && INSTALL+=" modules_install"
            [[ $OPTARG =~ 'k' ]] && INSTALL+=" install" ;;
        t)  TARGETDIR=$OPTARG ;;
        l)  LOCALVERSION=$OPTARG ;;
        c)  MKCONFIG=1 ;;
        C)  MKCONFIG=1
            CFG_FILE=$OPTARG ;;
        r)  RMKERNEL=1 ;;
        \?) echo "Invalid option: -$OPTARG" >&2 
            exit 1 ;;
        :)  echo "Option -$OPTARG requires an argument." >&2 
            exit 1 ;;
    esac
done 

shift $(($OPTIND-1)) 

# BUILD=${BUILD:-"bzImage"}
# TARGETDIR=${TARGETDIR:-"$PWD/rootfs"}
CFG_FILE=${CFG_FILE:-"/boot/config-$(uname -r)"}
LOCALVERSION=${LOCALVERSION:-"custom"}
KVER=$(make kernelversion)-$LOCALVERSION
# KSRC="-C $PWD"
# export KBUILD_OUTPUT=$TARGETDIR/usr/src/$KVER

echo $KVER

[[ $RMKERNEL -eq 1 ]] && removeKernel
[[ $MKCONFIG -eq 1 ]] && { MakeConfig || exit; }
[[ ! -z $BUILD ]] && KernelBuild  
[[ ! -z $INSTALL ]] && Install

