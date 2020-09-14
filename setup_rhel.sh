#!/bin/bash

update() {
    echo update
    sudo yum -y update

    sudo yum -y install net-tools qemu-kvm
    sudo yum -y groupinstall "Development tools"
    sudo yum -y install openssl-devel elfutils-libelf-devel ncurses-devel
    sudo yum -y install cmake llvm-devel clang-devel llvm-static libblkid-devel
}

chrome() {
    echo install google chrome
    wget --no-check-certificate https://dl.google.com/linux/direct/google-chrome-stable_current_`uname -m`.rpm
    sudo yum -y install ./google-chrome-stable_current_`uname -m`.rpm
}

gitkraken() {
    echo install gitkraken
	wget https://release.gitkraken.com/linux/gitkraken-amd64.rpm && \
	sudo yum -y install ./gitkraken-amd64.rpm
}

pymssql() {
    sudo rpm -Uvh https://download-ib01.fedoraproject.org/pub/epel/7/x86_64/Packages/e/epel-release-7-12.noarch.rpm
    sudo yum -y install python2-pymssql
}

scripts() {
    echo install utility scripts
    sudo yum -y install git
    [[ -d $HOME/projects ]] || mkdir $HOME/projects
    pushd $HOME/projects
    git clone http://10.92.159.125/jeongsoon.kwak/scripts.git
    popd
}

local_cmd() {
	[[ -d $HOME/.local/bin ]] || mkdir -p $HOME/.local/bin
	pushd $HOME/.local/bin
	for file in ~/projects/scripts/*.sh; do name=${file##*/}; ln -s $file ${name%%.*}; done
	popd
}

[[ -d $HOME/temp ]] || mkdir $HOME/temp

if (($#)); then
    CMDS=$@
else
    CMDS="update chrome scripts local_cmd"
fi

pushd $HOME/temp
for _CMD in $CMDS;
do
    $_CMD    
done
popd
