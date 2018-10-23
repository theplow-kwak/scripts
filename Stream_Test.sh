#!/bin/bash


NVME_DEVICE="/dev/nvme0n1"
YCSB_NVMESNOOP_ID=0
YCSB_IOSTAT_ID=0
YCSB_DISK_ID=0


# Set Stream on/off
Set_Stream(){

	case $1 in
		0)
		sudo -S sh -c 'echo 0 > /sys/module/nvme_core/parameters/streams'
		echo Set Stream off ; cat /sys/module/nvme_core/parameters/streams
		;;
		1)
		sudo -S sh -c 'echo 1 > /sys/module/nvme_core/parameters/streams'
		echo Set Stream on ; cat /sys/module/nvme_core/parameters/streams
		;;
	esac
}

Display_WaiInfo(){
	sudo nvme hynix wai-information $NVME_DEVICE
}

Start_BackgroungMonitoring(){

	sudo ~/env/scripts/nvmesnoop.py -o $1 &
	YCSB_NVMESNOOP_ID=$!
}

Stop_BackgroungMinitoring(){

	sleep 1

	if [ $YCSB_NVMESNOOP_ID -ne 0 ] 
	then		
		sudo kill -SIGABRT $(ps -o pid --no-headers --ppid $YCSB_NVMESNOOP_ID)
		sudo kill -SIGABRT $YCSB_NVMESNOOP_ID
		wait $YCSB_NVMESNOOP_ID 2> /dev/null # remove core-dump message
		YCSB_NVMESNOOP_ID=0
	fi
}

ctrl_c(){
	Stop_BackgroungMinitoring

	exit 2
}

trap ctrl_c INT

######################################################
echo "##################Stream On Test ##################"
date 

Set_Stream 1

Display_WaiInfo

#Start_BackgroungMonitoring ~/BM/TestStream.klog

~/env/scripts/TestStream "/media/unicorn/Gemini1T9G" 1 100000 4

#Stop_BackgroungMinitoring
sleep 2

Display_WaiInfo

date
echo "##################################################"
######################################################
echo "##################Stream Off Test ##################"
date 

Set_Stream 0

Display_WaiInfo

#Start_BackgroungMonitoring ~/BM/TestStream.klog

~/env/scripts/TestStream "/media/unicorn/Gemini1T9G" 0 100000 4

#Stop_BackgroungMinitoring

sleep 2

Display_WaiInfo

date 
echo "##################################################"
