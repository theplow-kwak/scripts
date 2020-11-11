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

REL_VER=${REL_VER:-"7"}
ARCH=${ARCH:-"x86_64"}
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

sudo yum clean all
sudo sh -c "echo $REL_VER > /etc/yum/vars/releasever"
sudo yum repolist all

