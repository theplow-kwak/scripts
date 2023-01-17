#!/bin/bash

usage()
{
cat << EOM
Usage:
 ${0##*/} command [command..]

Command:
 set_mirror     set apt repo as kakao.com
 timeset        Disable UTC and use Local Time
 update         update and install build-essential git python3-pip
 python         update pip modules          
 tools          install net-tools krusader barrier qemu-kvm virt-viewer cifs-utils
 chrome         install chrome
 bcompare       install bcompare
 typora         install typora
 docker         install docker
 scripts        install scripts
 local_cmd      install local_cmd
 gitkraken      install gitkraken
 
Options:
 -a, --all      run all commands

EOM
}

options=$(getopt -n ${0##*/} -o ah \
                --long all,help -- "$@")
[ $? -eq 0 ] || { 
    usage
    exit 1
}
eval set -- "$options"

while true; do
    case "$1" in
        -a | --all )    CMDS="set_mirror update tools chrome bcompare typora docker scripts local_cmd" ;    shift ;;    
        -h | --help )   usage ;         exit ;;
        --)             shift ;         break ;;
    esac
    shift
done 

PREFIX=${PREFIX:-$HOME/$NAME}

tools() {
    echo update
    sudo yum -y install epel-release
    sudo yum -y config-manager --set-enabled powertools
    sudo yum -y update

    sudo yum -y install net-tools qemu-kvm
    sudo yum -y groupinstall "Development tools"
    sudo yum -y install openssl-devel elfutils-libelf-devel ncurses-devel
    sudo yum -y install cmake llvm-devel clang-devel llvm-static libblkid-devel
}

timeset() {
    timedatectl set-local-rtc 1 --adjust-system-clock
}

python() {
    echo install python3
    sudo yum -y update

    sudo yum -y install python3-pip && \
    pip3 install --upgrade pip && \
    pip3 freeze | cut -d'=' -f1 | xargs pip3 install --upgrade
}

chrome() {
    echo install google chrome
    wget --no-check-certificate https://dl.google.com/linux/direct/google-chrome-stable_current_`uname -m`.rpm && \
    sudo yum -y install ./google-chrome-stable_current_`uname -m`.rpm
}

bcompare() {
    echo install byound compare
    wget https://www.scootersoftware.com/bcompare-4.4.2.26348.x86_64.rpm && \
    sudo rpm --import https://www.scootersoftware.com/RPM-GPG-KEY-scootersoftware && \
    sudo yum -y install bcompare-4.4.2.26348.x86_64.rpm
}

gitkraken() {
    echo install gitkraken
    wget https://release.gitkraken.com/linux/gitkraken-amd64.rpm && \
    sudo yum -y install ./gitkraken-amd64.rpm
}

docker()
{
    echo install docker
    sudo yum install -y yum-utils
    sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
    sudo yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    sudo groupadd docker
    sudo usermod -aG docker $USER
    sudo systemctl enable docker.service
    sudo systemctl enable containerd.service
}

pymssql() {
    sudo rpm -Uvh https://download-ib01.fedoraproject.org/pub/epel/7/x86_64/Packages/e/epel-release-7-12.noarch.rpm && \
    sudo yum -y install python2-pymssql
}

local_cmd() {
    [[ -d $HOME/.local/bin ]] || mkdir -p $HOME/.local/bin
    pushd $HOME/.local/bin
	for file in ~/projects/scripts/*.py; do name=${file##*/}; [[ -e ${name%%.*} ]] || ln -s $file ${name%%.*}; done
	for file in ~/projects/scripts/*.sh; do name=${file##*/}; [[ -e ${name%%.*} ]] || ln -s $file ${name%%.*}; done
    popd
}

[[ -d $HOME/temp ]] || mkdir $HOME/temp

if (($#)); then
    CMDS=$@
else
#    CMDS="update chrome scripts local_cmd"
    usage
    exit 1
fi

pushd $HOME/temp &>/dev/null
for _CMD in $CMDS;
do
    $_CMD    
done
popd &>/dev/null
