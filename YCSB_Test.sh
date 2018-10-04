#!/bin/bash

# sudo umount /media/unicorn/Gemini1T9G 
# sudo mount -o defaults,rw,nosuid,nodev,discard /dev/nvme0n1 /media/unicorn/Gemini1T9G
# sudo chmod 777 /media/unicorn/Gemini1T9G

# iostat -t 60 -md /dev/nvme0n1 > disk.log
# watch -n 60 "df /dev/nvme0n1 >> df.log"

NVME_DEVICE="/dev/nvme0n1"
DISK_ID=0
# Clean DB Output & Init
Clean_Device(){
	echo Clean Device $1 | tee -a $2
	
	rm $1/*
#	sudo fstrim -v $1
}

# Set Stream on/off
Set_Stream(){

	case $1 in
		0)
		sudo -S sh -c 'echo 0 > /sys/module/nvme_core/parameters/streams'
		echo Set Stream off | tee -a $2 ; cat /sys/module/nvme_core/parameters/streams | tee -a $2
		;;
		1)
		sudo -S sh -c 'echo 1 > /sys/module/nvme_core/parameters/streams'
		echo Set Stream on | tee -a $2 ; cat /sys/module/nvme_core/parameters/streams | tee -a $2
		;;
	esac
}

# output usage of disk, WAI
Display_TIME_WAI_CAPACITY(){
	date '+%Y-%m-%d %H:%M:%S' 					| tee -a $1

	df -a | grep Filesystem 					| tee -a $1
	df -a | grep $NVME_DEVICE 					| tee -a $1

	sudo nvme hynix wai-information $NVME_DEVICE 			| tee -a $1
}

Run_DiskSpaceMonitoring(){

	while true
	do
		df $NVME_DEVICE | tail -n +2 >> $1
		sleep $2
	done
}

Start_BackgroungMonitoring(){

	sudo ~/env/scripts/nvmesnoop.py -o $1 &

	iostat -t 60 -md $NVME_DEVICE > $2 &

	Run_DiskSpaceMonitoring $3 1 &

	DISK_ID=$!
}

Stop_BackgroungMinitoring(){
	NVMESNOOP_PID=$(ps aux | grep 'nvmesnoop'| grep -v 'grep' | awk '{print $2}')
	sudo kill -SIGABRT $NVMESNOOP_PID
	sleep 1
		
	IOSTAT_PID=$(ps aux | grep 'iostat -t'| grep -v 'grep' | awk '{print $2}')
	sudo kill -SIGABRT $IOSTAT_PID
	sleep 1

#	WORK_PID=`jobs -l | awk '{print $2}'`
#	echo "JOBS = $WORK_PID"

	sudo kill -SIGABRT $DISK_ID
	sleep 1
}

# Parameter
#     $1	   $2	       $3		$4		$5		$6
# Stream offon | RUN Count |Thread count | RockDB Directory | RecordCount | Operation Count
#
Run_YCSB(){

# Init Variable
	LOG_DIR=$(date '+%Y%m%d-%H%M%S')
	STREAM=$1
	RUNCNT=$2
	THREADCNT=$3
	ROCKSDB_DIR=/media/unicorn/$4/YCSBRocksDB
	ROCKSDB_LOG_DIR=./$LOG_DIR/$STREAM-Detail
	RECCNT=$5
	OPCNT=$6
	MAIN_LOG=./$LOG_DIR/$LOG_DIR-$STREAM-$RUNCNT.log

# Make LOG
	mkdir $LOG_DIR	

	mkdir $ROCKSDB_LOG_DIR

# Test Start
	echo "=========================================================================================="	| tee -a $MAIN_LOG
	echo "                             Test Start                                                   "	| tee -a $MAIN_LOG
	echo "=========================================================================================="	| tee -a $MAIN_LOG
	echo "Environment 1: Stream_ONOFF : $STREAM, RUN count : $RUNCNT,  Thread_Count : $THREADCNT  "		| tee -a $MAIN_LOG
	echo "Environment 2: TestDestination : $ROCKSDB_DIR, Log_Pos : $ROCKSDB_LOG_DIR "			| tee -a $MAIN_LOG
	echo "Environment 3: Record Count= $RECCNT,  Operation Count=$OPCNT "					| tee -a $MAIN_LOG
	echo "=========================================================================================="	| tee -a $MAIN_LOG

	Clean_Device $ROCKSDB_DIR $MAIN_LOG

	Set_Stream $STREAM $MAIN_LOG

	Display_TIME_WAI_CAPACITY $MAIN_LOG

	echo "=========================================================================================="	| tee -a $MAIN_LOG

	for i in $( seq 0 $RUNCNT )
	do
		case $i in
			0)
			echo "=============================================="					| tee -a $MAIN_LOG
			echo "Load YCSB Data  ***************************"					| tee -a $MAIN_LOG
			echo "=============================================="					| tee -a $MAIN_LOG
			Start_BackgroungMonitoring $ROCKSDB_LOG_DIR/Load.klog $ROCKSDB_LOG_DIR/Load.slog $ROCKSDB_LOG_DIR/Load.dlog

			`./bin/ycsb load rocksdb -s -P workloads/workloadx -p recordcount=$RECCNT -p rocksdb.dir=$ROCKSDB_DIR > $ROCKSDB_LOG_DIR/Load.log 2>&1`

			Stop_BackgroungMinitoring
			
			Display_TIME_WAI_CAPACITY $MAIN_LOG
			;;

			*)
			echo "==============================================" 					| tee -a $MAIN_LOG
			echo "RUN YCSB Data $i ***************************"					| tee -a $MAIN_LOG
			echo "=============================================="					| tee -a $MAIN_LOG
			Start_BackgroungMonitoring $ROCKSDB_LOG_DIR/Run$i.klog $ROCKSDB_LOG_DIR/Run$i.slog $ROCKSDB_LOG_DIR/Run$i.dlog

			`./bin/ycsb run rocksdb -s -P workloads/workloadx -threads $THREADCNT -p recordcount=$RECCNT -p operationcount=$OPCNT -p rocksdb.dir=$ROCKSDB_DIR > $ROCKSDB_LOG_DIR/Run$i.log 2>&1`

			Stop_BackgroungMinitoring

			Display_TIME_WAI_CAPACITY $MAIN_LOG
			
			grep OVERALL $ROCKSDB_LOG_DIR/Run$i.log							| tee -a $MAIN_LOG
			;;
	   	esac

	echo "=============================================="							| tee -a $MAIN_LOG
	done
}

# Parameter
#     $1	   $2	       $3		$4		$5		$6
# Stream offon | RUN Count |Thread count | RockDB Directory | RecordCount | Operation Count
Run_YCSB 0 1 32 Gemini1T9G 300000 200000

Run_YCSB 1 1 32 Gemini1T9G 300000 200000


