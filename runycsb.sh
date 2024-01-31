#!/bin/bash

workload="nvme_test"
cmd="run"
nvmepath="/mnt/nvme"

while getopts ":w:p:" opt; do
	case $opt in
		w)	workload=$OPTARG;;
		p)	nvmepath=$OPTARG;;
		:)	echo "Option -$OPTARG requires an argument.";;			
	esac
done 

shift $(($OPTIND-1)) 

opt=$1

pushd ~/projects/ycsb

if [ "$opt" != "" ] && [ "$opt" == "load" ] 
then
    cmd=$opt
fi

echo ./bin/ycsb $cmd rocksdb -s -P workloads/$workload -p rocksdb.dir=$nvmepath/ycsb-rocksdb-data 
./bin/ycsb $cmd rocksdb -s -P workloads/$workload -p rocksdb.dir=$nvmepath/ycsb-rocksdb-data 

popd
