#!/bin/bash

usage()
{
cat << EOM
Usage:
 ${0##*/} [OPTIONS]

Options:
 -v, --ver <VER NUM>            release version
 -a, --arch <architecture>      architecture
 -m, --mirror <mirror site>     URL of the mirror site
EOM
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

repo_7_o()
{
case $ARCH in
    "x86_64" )  MIRROR=${MIRROR:-'http://mirror.navercorp.com/centos/'} ;;
    "aarch64" ) MIRROR=${MIRROR:-'http://mirror.centos.org/altarch/'} ;;
    * )         break ;;
esac
echo $MIRROR $REL_VER $ARCH 

printf "%s\n" \
"[base]
name=CentOS-\$releasever - Base
baseurl=$MIRROR\$releasever/os/\$basearch/
gpgcheck=1

#released updates
[update]
name=CentOS-\$releasever - Updates
baseurl=$MIRROR\$releasever/updates/\$basearch/
gpgcheck=1

#additional packages that may be useful
[extras]
name=CentOS-\$releasever - Extras
baseurl=$MIRROR\$releasever/extras/\$basearch/
gpgcheck=1
" \
| sudo dd of=/etc/yum.repos.d/centos.repo

sudo rpm --import $MIRROR/$REL_VER/os/$ARCH/RPM-GPG-KEY-CentOS-7
[[ $ARCH == "aarch64" ]] && sudo rpm --import https://www.centos.org/keys/RPM-GPG-KEY-CentOS-7-aarch64
[[ $ARCH == "arm32" ]] && sudo rpm --import https://www.centos.org/keys/RPM-GPG-KEY-CentOS-SIG-AltArch-Arm32
}

repo_7()
{
echo $MIRROR $REL_VER $ARCH 

printf "%s\n" \
"
[base]
name=CentOS-\$releasever - Base
mirrorlist=http://mirrorlist.centos.org/?release=\$releasever&arch=\$basearch&repo=os&infra=\$infra
gpgcheck=1
enabled=1

[updates]
name=CentOS-\$releasever - AppStream
mirrorlist=http://mirrorlist.centos.org/?release=\$releasever&arch=\$basearch&repo=updates&infra=\$infra
gpgcheck=1
enabled=1

[extras]
name=CentOS-\$releasever - Extras
mirrorlist=http://mirrorlist.centos.org/?release=\$releasever&arch=\$basearch&repo=extras&infra=\$infra
gpgcheck=1
enabled=1

" \
| sudo dd of=/etc/yum.repos.d/centos.repo

sudo rpm --import https://www.centos.org/keys/RPM-GPG-KEY-CentOS-7
[[ $ARCH == "aarch64" ]] && sudo rpm --import https://www.centos.org/keys/RPM-GPG-KEY-CentOS-7-aarch64
[[ $ARCH == "arm32" ]] && sudo rpm --import https://www.centos.org/keys/RPM-GPG-KEY-CentOS-SIG-AltArch-Arm32
}

repo_8()
{
echo $MIRROR $REL_VER $ARCH 

printf "%s\n" \
"
[BaseOS]
name=CentOS-\$releasever - Base
mirrorlist=http://mirrorlist.centos.org/?release=\$releasever&arch=\$basearch&repo=BaseOS&infra=\$infra
gpgcheck=1
enabled=1

[AppStream]
name=CentOS-\$releasever - AppStream
mirrorlist=http://mirrorlist.centos.org/?release=\$releasever&arch=\$basearch&repo=AppStream&infra=\$infra
gpgcheck=1
enabled=1

[extras]
name=CentOS-\$releasever - Extras
mirrorlist=http://mirrorlist.centos.org/?release=\$releasever&arch=\$basearch&repo=extras&infra=\$infra
gpgcheck=1
enabled=1

[PowerTools]
name=CentOS-\$releasever - PowerTools
mirrorlist=http://mirrorlist.centos.org/?release=\$releasever&arch=\$basearch&repo=PowerTools&infra=\$infra
gpgcheck=1
enabled=1

" \
| sudo dd of=/etc/yum.repos.d/centos.repo

sudo rpm --import https://www.centos.org/keys/RPM-GPG-KEY-CentOS-Official
}


options=$(getopt -n ${0##*/} -o v:m:a:h \
                --long ver:,mirror:,arch:,help -- "$@")
[ $? -eq 0 ] || { usage ; exit 1 ; }
eval set -- "$options"

while true; do
    case "$1" in
        -v | --ver )    REL_VER=$2 ;    shift ;;    
        -a | --arch )   ARCH=$2 ;       shift ;;    
        -m | --mirror ) MIRROR=$2 ;     shift ;;
        -h | --help )   usage ;         exit ;;
        --)             shift ;         break ;;
    esac
    shift
done 

getOsVersion
_ARCH=$(uname -i)

REL_VER=${REL_VER:-${_VER:0:1}}
ARCH=${ARCH:-$_ARCH}

case $REL_VER in
    '7' )   repo_7 ;;
    '8' )   repo_8 ;;
    * )     usage ; exit ;;
esac

[[ -e /etc/yum/vars/releasever ]] || sudo sh -c "echo $REL_VER > /etc/yum/vars/releasever"
sudo yum clean all
sudo yum repolist all



