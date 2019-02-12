# Bulid your own kernel with NVMe linux kernel driver

This document was written in Ubuntu 18.04 based on linux kernel v.4.15. The kernel build refers to the [BuildYourOwnKernel](https://wiki.ubuntu.com/Kernel/BuildYourOwnKernel) page of the Ubuntu wiki.



Obtaining the source for an Ubuntu release 

```bash
apt source linux-headers-$(uname -r)
sudo apt build-dep linux-headers-$(uname -r)
```



## Modifying the configuration

In order to make your kernel "newer" than the stock Ubuntu kernel from which you are based you should add a local version modifier. Add something like **'.nvme'** to the end of the first version number in the `debian.master/changelog` file, before building.

*"linux (4.15.0-38**.nvme**) bionic; urgency=medium"*

## Patching NVMe kernel tracing related files. 



## Patching NVMe driver code files to support multi-stream.



## Reset build to return Debian build

```bash
make clean
rm .config
rm Module.symvers
rm -rdf include/config
rm -rdf include/generated
rm -rdf arch/*/include/generated
find . -name *.ur-* -type f -delete
```

## Build Kernel by using debian rules

```bash
fakeroot debian/rules clean
DEB_BUILD_OPTIONS=parallel=`getconf _NPROCESSORS_ONLN` AUTOBUILD=1 NOEXTRAS=1 fakeroot debian/rules binary-generic binary-headers skipabi=true
```

If the build is successful, a set of **.deb** binary package files will be produced in the directory above the build root directory.

```
linux-cloud-tools-4.15.0-38-generic_4.15.0-38.nvme_amd64.deb
linux-headers-4.15.0-38-generic_4.15.0-38.nvme_amd64.deb
linux-headers-4.15.0-38_4.15.0-38.nvme_all.deb
linux-image-unsigned-4.15.0-38-generic_4.15.0-38.nvme_amd64.deb
linux-modules-4.15.0-38-generic_4.15.0-38.nvme_amd64.deb
linux-modules-extra-4.15.0-38-generic_4.15.0-38.nvme_amd64.deb
linux-tools-4.15.0-38-generic_4.15.0-38.nvme_amd64.deb
```

## Install new kernel

```bash
sudo dpkg -i linux-*-4.15*.deb
sudo reboot
```







## How to build only the NVMe module driver 

```bash
cd drivers/nvme
make -C /lib/modules/`uname -r`/build M=`pwd` modules
sudo make -C /lib/modules/`uname -r`/build M=`pwd` modules_install install
```


## How to enable kernel trace 
```bash
sudo sh -c 'echo 1 > /sys/kernel/debug/tracing/events/nvme/enable'
sudo sh -c 'echo 1 > /sys/kernel/debug/tracing/tracing_on'
sudo sh -c 'echo 0 > /sys/kernel/debug/tracing/trace'

sudo cat /sys/kernel/debug/tracing/trace_pipe | tee ./nvme.log
```

## How to change stream on and off 
You can turn the stream on or off by changing the module parameter variable 'streams'

```bash
sudo sh -c 'echo 1 > /sys/module/nvme_core/parameters/streams'
sudo sh -c 'echo 0 > /sys/module/nvme_core/parameters/streams'
```

## nvme-cli example 
```bash
sudo nvme id-ctrl /dev/nvme0
sudo nvme dir-receive /dev/nvme0 -D 1 -O 1 -H
sudo nvme smart-log /dev/nvme0
```



# Another way to build the kernel

## Build Kernel by upstream way
```bash
cd linux-xxx
cp /boot/config-$(uname -r) .config
cp /usr/src/linux-headers-$(uname -r)/Module.symvers .

make olddefconfig
make prepare
make scripts
make -j `getconf _NPROCESSORS_ONLN` bindeb-pkg LOCALVERSION=-nvme
make -j `getconf _NPROCESSORS_ONLN` bzImage modules LOCALVERSION=-nvme
sudo make headers_install modules_install install
```

## reference of module-signing 
> https://github.com/Canonical-kernel/Ubuntu-kernel/blob/master/Documentation/module-signing.txt

## reference of kernel build options 
> https://www.linuxsecrets.com/2826-kernel-headers-from-source

