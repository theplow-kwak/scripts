#!/bin/bash

# sudo umount /media/unicorn/Gemini1T9G 
# sudo mount -o defaults,rw,nosuid,nodev,discard /dev/nvme0n1 /media/unicorn/Gemini1T9G
# sudo chmod 777 /media/unicorn/Gemini1T9G

# iostat -t 60 -md /dev/nvme0n1 > disk.log
# watch -n 60 "df /dev/nvme0n1 >> df.log"

Init_LOGDirectory(){
	rm -rf ./LOG

	mkdir LOG
	mkdir ./LOG/32stream_off/
	mkdir ./LOG/32stream_on/
}

Display_TIME_WAI_CAPACITY(){
	date --date=now

	df -a | grep Filesystem
	df -a | grep nvme0n1

	sudo nvme hynix wai-information /dev/nvme0n1
}

# loging NVMe Driver workload
Start_NVMESNOOP(){
		sudo ~/env/scripts/nvmesnoop.py -o $1 &
}

Stop_NVMESNOOP(){
		sleep 3
		TEST_PID=$(ps aux | grep 'nvmesnoop'| grep -v 'grep' | awk '{print $2}')
		echo $TEST_PID
		sudo kill -SIGABRT $TEST_PID
		sleep 3
}

# loging Device Space Usage
Start_MonitorDiskSpace(){
		watch -n1 'df /dev/nvme0n1 | tail -n +2 | tee -a '$1'' &
}

Stop_MonitorDiskSpace(){
		TEST_PID=$(ps aux | grep 'watch -n'| grep -v 'grep' | awk '{print $2}')
		echo $TEST_PID
		sudo kill -SIGKILL $TEST_PID 2>/dev/null
		sleep 1
}

# loging IoStat
Start_IoStat(){
		iostat -t 60 -md /dev/nvme0n1 > $1 &
}

Stop_IoStat(){
		TEST_PID=$(ps aux | grep 'iostat -t'| grep -v 'grep' | awk '{print $2}')
		echo $TEST_PID
		
		sudo kill -SIGKILL $TEST_PID 2>/dev/null
		sleep 1
}


Run_YCSB(){
	echo "=========================================================================================="	
	echo "                             Test Start                                                   "
	echo "=========================================================================================="
	echo "RUN count : $1,  Log_Pos : $2, Thread_Count : $3, Stream_ONOFF : $4, TestDestination : $5 "
	echo "=========================================================================================="

	rm -rf /media/unicorn/$5/*
#	sudo fstrim -v /media/unicorn/$5

	case $4 in
		0)
		sudo -S sh -c 'echo 0 > /sys/module/nvme_core/parameters/streams'
		echo Set Stream off ; cat /sys/module/nvme_core/parameters/streams
		;;
		1)
		sudo -S sh -c 'echo 1 > /sys/module/nvme_core/parameters/streams'
		echo Set Stream on ; cat /sys/module/nvme_core/parameters/streams
		;;
	esac

	Display_TIME_WAI_CAPACITY

	echo "=========================================================================================="

	for i in $( seq 0 $1 )
	do
		case $i in
			0)
			echo "=============================================="
			echo "Load YCSB Data  ***************************"
			echo "=============================================="		
#			Start_NVMESNOOP $2/Load.klog
#			Start_MonitorDiskSpace $2/Load.dlog
#			Start_IoStat $2/Load.iolog
#			echo "check1  ***************************"

			`./bin/ycsb load rocksdb -s -P workloads/workloadx -p rocksdb.dir=/media/unicorn/$5/ycsb-rocksdb-data > $2/Load.log 2>&1`


#			Stop_IoStat
#			Stop_MonitorDiskSpace
#			Stop_NVMESNOOP
#			echo "check2  ***************************"
			
			Display_TIME_WAI_CAPACITY
			;;

			*)
			echo "==============================================" 
			echo "RUN YCSB Data $i ***************************"
			echo "=============================================="		
#			Start_NVMESNOOP $2/Run$i.klog
#			Start_MonitorDiskSpace $2/Run$i.dlog
#			Start_IoStat $2/Run$i.iolog
#			echo "check1  ***************************"

			`./bin/ycsb run rocksdb -s -P workloads/workloadx -threads $3 -p rocksdb.dir=/media/unicorn/$5/ycsb-rocksdb-data > $2/Run$i.log 2>&1`

#			Stop_IoStat
#			Stop_MonitorDiskSpace
#			Stop_NVMESNOOP			
#			echo "check2  ***************************"

			Display_TIME_WAI_CAPACITY
			
			grep OVERALL $2/Run$i.log
			;;
	   	esac

	echo "=============================================="
	done
}

# reset directory
Init_LOGDirectory

# 12 Step Testcount Thread 32, stream off
Run_YCSB 3 ./LOG/32stream_off 32 0 Gemini1T9G

# 12 Step Testcount Thread 32, stream on
Run_YCSB 3 ./LOG/32stream_on 32 1 Gemini1T9G
