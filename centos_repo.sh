#!/bin/bash

case $1 in 
    "5")    REL_VER="7.5.1804" ;;
    "6")    REL_VER="7.6.1810" ;;
    "7")    REL_VER="7.7.1908" ;;
    *)      REL_VER=$1 ;;
esac

REL_VER=${REL_VER:-"7.6.1810"}
echo $REL_VER

sudo sh -c 'cat > /etc/yum.repos.d/centos.repo <<EOL
[base]
name=CentOS-\$releasever - Base
baseurl=http://mirror.kakao.com/centos/\$releasever/os/\$basearch/
gpgcheck=1

#released updates
[update]
name=CentOS-\$releasever - Updates
baseurl=http://mirror.kakao.com/centos/\$releasever/updates/\$basearch/
gpgcheck=1
EOL'

sudo rpm --import http://mirror.kakao.com/centos/7/os/x86_64/RPM-GPG-KEY-CentOS-7
sudo sh -c "echo $REL_VER > /etc/yum/vars/releasever"
sudo yum repolist all

