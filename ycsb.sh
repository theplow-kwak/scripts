#!/bin/bash

workload="nvme_test"
cmd="run"

while getopts ":w:" opt; do
	case $opt in
		w)	workload=$OPTARG;;
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

echo ./bin/ycsb $cmd rocksdb -s -P workloads/$workload -p rocksdb.dir=/mnt/nvme/ycsb-rocksdb-data 
./bin/ycsb $cmd rocksdb -s -P workloads/$workload -p rocksdb.dir=/mnt/nvme/ycsb-rocksdb-data 

popd
