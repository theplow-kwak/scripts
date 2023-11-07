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

set_mirror(){
    sudo sed -i -re 's/([a-z]{2}\.)?archive.ubuntu.com|security.ubuntu.com|extras.ubuntu.com/mirror.kakao.com/g' /etc/apt/sources.list
}

tools() {
    echo update
    sudo apt -y update
    sudo apt -y upgrade

    sudo apt -y install build-essential git python3-pip
    sudo apt -y install net-tools krusader qemu-kvm virt-viewer cifs-utils 
    sudo apt -y install libvirt-daemon-system # barrier
}

timeset() {
    timedatectl set-local-rtc 1 --adjust-system-clock
}

python() {
    echo install python3
    sudo apt -y update
    sudo apt -y upgrade

    sudo apt -y install python3-pip && \
    pip3 install --upgrade pip && \
    pip3 freeze | cut -d'=' -f1 | xargs pip3 install --upgrade
    # pip3 install jupyterlab
}

jenkins() {
    pip install jenkins python-jenkins wcmatch configobj
}

chrome() {
    echo install google chrome
    wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    sudo dpkg -i google-chrome-stable_current_amd64.deb
}

bcompare() {
    echo install byound compare
    wget https://www.scootersoftware.com/bcompare-4.4.4.27058_amd64.deb && \
    sudo apt install ./bcompare-4.4.4.27058_amd64.deb
}

gitkraken() {
    echo install gitkraken
    wget https://release.gitkraken.com/linux/gitkraken-amd64.deb && \
    sudo dpkg -i gitkraken-amd64.deb
}

typora() {
    echo install typora
    wget -qO - https://typora.io/linux/public-key.asc | sudo tee /etc/apt/trusted.gpg.d/typora.asc
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

local_cmd() {
    [[ -d $HOME/.local/bin ]] || mkdir -p $HOME/.local/bin
    find $HOME/.local/bin/ -type l -delete
    pushd $HOME/.local/bin
    for file in ~/projects/scripts/*.py; do name=${file##*/}; [[ -e ${name%%.*} ]] || ln -s $file ${name%%.*}; done
    for file in ~/projects/scripts/*.sh; do name=${file##*/}; [[ -e ${name%%.*} ]] && ln -s $file ${name%%.*}2 || ln -s $file ${name%%.*}; done
    popd
}

[[ -d $HOME/temp ]] || mkdir $HOME/temp

if (($#)); then
    CMDS=$@
else
#    CMDS="tools set_mirror update chrome bcompare typora docker scripts local_cmd"
    usage
    exit 1
fi

pushd $HOME/temp &>/dev/null
for _CMD in $CMDS;
do
    $_CMD    
done
popd &>/dev/null
