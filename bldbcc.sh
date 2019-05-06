#!/bin/bash

TARGET=${PWD##*/}

while getopts ":p:P:" opt; do
    case $opt in
        p)  TARGET=$OPTARG ;;
        P)  PREFIX=$OPTARG ;;
        *)  usage ;;
    esac
done 

shift $(($OPTIND-1)) 

PREFIX=${PREFIX:-$HOME/$TARGET}

config()
{
    TRACE=${1:-"nop"}
    pushd build
    cmake .. -DCMAKE_INSTALL_PREFIX=/usr
    popd
}

bld()
{
    pushd build
    make -j `getconf _NPROCESSORS_ONLN` && sudo make install
    popd
}

cleanall()
{
    sudo rm -rdf ./build
    mkdir build
}

clean()
{
    pushd build
    make clean
    popd
}

$1 $2

