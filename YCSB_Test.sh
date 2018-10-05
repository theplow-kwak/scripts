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
	
	rm $1/* 2> /dev/null
#	sudo fstrim -v $1
}

Copy_RocksdbLOG(){
	cp $1/LOG*.* $2/ 
	cp $1/OPTIONS* $2/
	cp $1/MANIFEST* $2/
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
	date '+%Y-%m-%d %H:%M:%S %Z' 					| tee -a $1

	df -a | grep Filesystem 					| tee -a $1
	df -a | grep $NVME_DEVICE 					| tee -a $1

	sudo nvme hynix wai-information $NVME_DEVICE 			| tee -a $1
}

Run_DiskSpaceMonitoring(){

	TIMEINDEX=$(date '+%Y-%m-%d-%H:%M:%S')

	while true
	do 
		df $NVME_DEVICE | tail -n +2 | awk '{print "'$TIMEINDEX' : ",$0}' >> $1
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
	wait $NVMESNOOP_PID 2> /dev/null # remove core-dump message
		
	IOSTAT_PID=$(ps aux | grep 'iostat -t'| grep -v 'grep' | awk '{print $2}')
	sudo kill -SIGABRT $IOSTAT_PID
	wait $IOSTAT_PID 2> /dev/null # remove core-dump message

	if [ $DISK_ID -ne 0 ] 
	then
		sudo kill -SIGABRT $DISK_ID
		wait $DISK_ID 2> /dev/null # remove core-dump message
		DISK_ID=0
	fi

	sleep 2
}

# Parameter
#     $1	   $2	       $3		$4		$5		$6
# Stream offon | RUN Count |Thread count | RockDB Directory | RecordCount | Operation Count
#
Run_YCSB(){

# Init Variable
	STARTTIME=$(date '+%Y%m%d-%H%M%S')
	LOG_ROOT=./LOG
	
	STREAM=$1
	RUNCNT=$2
	THREADCNT=$3	
	LOG_DIR=$LOG_ROOT/$STARTTIME-$STREAM-$RUNCNT
	ROCKSDB_DIR=/media/unicorn/$4/YCSBRocksDB
	DETAIL_LOG_DIR=$LOG_DIR/Detail-$STREAM-$RUNCNT
	ROCKSDB_LOG_DIR=$LOG_DIR/ROCKSDB_LOG
	RECCNT=$5
	OPCNT=$6
	MAIN_LOG=$LOG_DIR/$STARTTIME-$STREAM-$RUNCNT.log
	

# Make LOG

	mkdir $LOG_ROOT 2> /dev/null # remove error message although already made LOG ROOT
	
	mkdir $LOG_DIR

	mkdir $DETAIL_LOG_DIR

	mkdir $ROCKSDB_LOG_DIR

# Test Start
	echo "=========================================================================================="				| tee -a $MAIN_LOG
	echo "                             Test Start                                                   "				| tee -a $MAIN_LOG
	echo "=========================================================================================="				| tee -a $MAIN_LOG
	echo "Stream ONOFF : $STREAM, RUN count : $RUNCNT, Thread Count : $THREADCNT, Record Count : $RECCNT, Operation Count : $OPCNT"	| tee -a $MAIN_LOG
	echo "DB Data Position : $ROCKSDB_DIR"												| tee -a $MAIN_LOG
        echo "Log Data Pos Position : $LOG_DIR "											| tee -a $MAIN_LOG
	echo "=========================================================================================="				| tee -a $MAIN_LOG

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
			Start_BackgroungMonitoring $DETAIL_LOG_DIR/Load.klog $DETAIL_LOG_DIR/Load.slog $DETAIL_LOG_DIR/Load.dlog

			`./bin/ycsb load rocksdb -s -P workloads/workloadx -p recordcount=$RECCNT -p rocksdb.dir=$ROCKSDB_DIR > $DETAIL_LOG_DIR/Load.log 2>&1`

			Stop_BackgroungMinitoring
			
			Display_TIME_WAI_CAPACITY $MAIN_LOG
			;;

			*)
			echo "==============================================" 					| tee -a $MAIN_LOG
			echo "RUN YCSB Data : $i ***************************"					| tee -a $MAIN_LOG
			echo "=============================================="					| tee -a $MAIN_LOG
			Start_BackgroungMonitoring $DETAIL_LOG_DIR/Run$i.klog $DETAIL_LOG_DIR/Run$i.slog $DETAIL_LOG_DIR/Run$i.dlog

			`./bin/ycsb run rocksdb -s -P workloads/workloadx -threads $THREADCNT -p recordcount=$RECCNT -p operationcount=$OPCNT -p rocksdb.dir=$ROCKSDB_DIR > $DETAIL_LOG_DIR/Run$i.log 2>&1`

			Stop_BackgroungMinitoring

			Display_TIME_WAI_CAPACITY $MAIN_LOG
			
			grep OVERALL $DETAIL_LOG_DIR/Run$i.log							| tee -a $MAIN_LOG
			;;
	   	esac

	echo "=============================================="							| tee -a $MAIN_LOG
	done

	Copy_RocksdbLOG $ROCKSDB_DIR $ROCKSDB_LOG_DIR
}

# Parameter
#     $1	   $2	       $3		$4		$5		$6
# Stream offon | RUN Count |Thread count | RockDB Directory | RecordCount | Operation Count
Run_YCSB 0 6 32 Gemini1T9G 300000 100000

Run_YCSB 1 6 32 Gemini1T9G 300000 100000


