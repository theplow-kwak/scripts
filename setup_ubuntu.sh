#!/bin/bash

ca_cert() {
    echo setup ca-certfication
    cp *.crt $HOME/temp
    cp setcrt.sh $HOME/temp

    pushd $HOME/temp
    ./setcrt.sh
}

update() {
    echo update
    sudo apt -y update
    sudo apt -y upgrade

    sudo apt -y install net-tools build-essential git krusader barrier qemu-kvm
}

chrome() {
    echo install google chrome
    wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    sudo dpkg -i google-chrome-stable_current_amd64.deb
}

bcompare() {
    echo install byound compare
    wget https://www.scootersoftware.com/bcompare-4.3.1.24438_amd64.deb && \
    sudo dpkg -i bcompare-4.3.1.24438_amd64.deb
}

gitkraken() {
    echo install gitkraken
    wget https://release.gitkraken.com/linux/gitkraken-amd64.deb && \
    sudo dpkg -i gitkraken-amd64.deb
}

typora() {
    echo install typora
    wget -qO - https://typora.io/linux/public-key.asc | sudo apt-key add -
    sudo add-apt-repository 'deb https://typora.io/linux ./'
    sudo apt -y update
    sudo apt -y install typora
}

docker() {
    echo install docker
    sudo apt -y install docker.io docker-compose
    sudo groupadd docker
    sudo usermod -aG docker $USER
}

scripts() {
    echo install utility scripts
    sudo apt -y install git
    [[ -d $HOME/projects ]] || mkdir $HOME/projects
    pushd $HOME/projects
    git clone http://10.92.159.125/jeongsoon.kwak/scripts.git
    popd
}

local_cmd() {
	[[ -d $HOME/.local/bin ]] || mkdir $HOME/.local/bin
	pushd $HOME/.local/bin
	for file in ~/projects/scripts/*.sh; do name=${file##*/}; ln -s $file ${name%%.*}; done
	popd
}

[[ -d $HOME/temp ]] || mkdir $HOME/temp

if (($#)); then
    CMDS=$@
else
    CMDS="ca_cert update chrome bcompare typora docker scripts local_cmd"
fi

pushd $HOME/temp
for _CMD in $CMDS;
do
    $_CMD    
done
popd
