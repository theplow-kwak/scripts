#!/bin/bash

case $1 in 
    "5")    REL_VER="7.5.1804" ;;
    "6")    REL_VER="7.6.1810" ;;
    "7")    REL_VER="7.7.1908" ;;
    *)      REL_VER=$1 ;;
esac

REL_VER=${REL_VER:-"7"}
MIRROR='http://mirror.navercorp.com/centos/'
echo $REL_VER
echo $MIRROR

printf "%s\n" \
"[base]
name=CentOS-\$releasever - Base
baseurl=$MIRROR\$releasever/os/\$basearch/
gpgcheck=1

#released updates
[update]
name=CentOS-\$releasever - Updates
baseurl=$MIRROR\$releasever/updates/\$basearch/
gpgcheck=1" \
| sudo dd of=/etc/yum.repos.d/centos.repo

sudo rpm --import $MIRROR/7/os/x86_64/RPM-GPG-KEY-CentOS-7
sudo yum clean all
sudo sh -c "echo $REL_VER > /etc/yum/vars/releasever"
sudo yum repolist all

