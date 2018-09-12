
# pre-install tools 
```bash
sudo apt install make 
sudo apt install make-guile gcc g++ curl git dpkg-dev 
sudo apt install python python3 python-pip python3-pip python-tk python3-tk bison
sudo apt install libgflags-dev

sudo apt install openjdk-8-jdk
sudo apt install maven
sudo apt install vagrant
```


# kernel tracing on ubuntu
> https://wiki.ubuntu.com/Kernel/BuildYourOwnKernel#Obtaining_the_source_for_an_Ubuntu_release

## get kernel source 
```bash
sudo apt install ncurses-dev
apt source linux-headers-$(uname -r)
sudo apt build-dep linux-headers-$(uname -r)
```

## kernel tracing patch
download nvme_driver.diff to ~/
```bash
cd ~/linux-4.15.0
patch -p1 < ../nvme_driver.diff

diff -urN nvme_u1804_org/drivers/nvme linux-4.15.0/drivers/nvme > nvme_driver.diff
```

## build NVMe module driver 
> https://wiki.ubuntu.com/KernelCustomBuild

```bash
cd drivers/nvme
make -C /lib/modules/`uname -r`/build M=`pwd` modules
sudo make -C /lib/modules/`uname -r`/build M=`pwd` modules_install install

#make M=./drivers/nvme modules
#sudo make M=./drivers/nvme modules_install install

sudo depmod -a
```

## build kernel 
```bash
fakeroot debian/rules clean
(fakeroot debian/rules editconfigs) 
debian/rules build
fakeroot debian/rules binary-headers binary-generic binary-perarch
```

## enable kernel trace  
```bash
sudo sh -c 'echo 1 > /sys/kernel/debug/tracing/events/nvme/enable'
sudo sh -c 'echo 1 > /sys/kernel/debug/tracing/tracing_on'
sudo cat /sys/kernel/debug/tracing/trace_pipe | tee ./nvme.log
```


# nvme-cli
```bash
sudo nvme id-ctrl /dev/nvme0
sudo nvme dir-receive /dev/nvme0 -D 1 -O 1 -H
sudo nvme smart-log /dev/nvme0
```

# bcc 
```bash
sudo apt install cmake clang libedit-dev llvm libclang-dev luajit libfl-dev
sudo apt install luajit luajit-5.1-dev
sudo apt install netperf iperf 

git clone https://github.com/iovisor/bcc.git
mkdir bcc/build; cd bcc/build
cmake .. -DCMAKE_INSTALL_PREFIX=/usr -DPYTHON_CMD=python3
make
sudo make install
```


# fio test
```bash
fio --randrepeat=1 --ioengine=libaio --direct=1 --gtod_reduce=1 --name=test --filename=/mnt/nvme/test --bs=4k --iodepth=64 --size=4G --readwrite=randrw --rwmixread=75
fio --randrepeat=1 --ioengine=libaio --direct=1 --gtod_reduce=1 --name=test --filename=/mnt/nvme/test --bs=4k --iodepth=64 --size=4G --readwrite=randread 
```


# iol_interact-8.0 
```bash
sudo apt-get install runit
sudo apt-get install libxml++2.6-dev 
sudo apt-get install libboost-all-dev
sudo apt-get install doxygen
sudo apt-get install linux-headers-$(uname -r)
```
dnvme.ko build시에 gcc version이 맞지 않으면 insmod에서 error 발생 (kernel patch와 연관) -> ppa:ubuntu-toolchain-r/test 사용하면 안됨


# vmdk to vhdx
```
ConvertTo-MvmcVirtualHardDisk -SourceLiteralPath "D:\VMPC\Ubuntu 1804 64-bit\Ubuntu 1804 64-bit.vmdk" -DestinationLiteralPath u1804 -VhdType DynamicHarddisk -VhdFormat vhdx
```

# How to do Screen Sharing on Ubuntu 18.04

Now you need to install dconf-editor with this command:

sudo apt-get install dconf-editor

Now open a terminal and type

dconf-editor

Now navigate to:

ORG > GNOME > DESKTOP > REMOTE ACCESS

Then find the “Require Encryption” setting and toggle it off
Now you can open your favorite VNC client and view your remote screen!


# wine 설치
```
sudo apt install wine-stable ttf-mscorefonts-installer --install-recommends
sudo apt install fonts-nanum fonts-nanum-extra fonts-nanum-coding
sudo apt install wine64

```
