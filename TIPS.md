
# pre-install tools 

```bash
sudo apt install make 
sudo apt install make-guile gcc g++ curl git dpkg-dev bison flex ncurses-dev libelf-dev
sudo apt install python python3 python-pip python3-pip python-tk python3-tk 
sudo apt install libgflags-dev

sudo apt install openjdk-8-jdk
sudo apt install maven
sudo apt install vagrant

sudo apt install libglib2.0-dev libpixman-1-dev libxen-dev libgtk-3-dev
```


# kernel tracing on ubuntu
> https://wiki.ubuntu.com/Kernel/BuildYourOwnKernel#Obtaining_the_source_for_an_Ubuntu_release

## get kernel source 

```bash
apt source linux-headers-$(uname -r)
sudo apt build-dep linux-headers-$(uname -r)
```

## Depackage the kernel source

```
dpkg-source -x linux_4.15.0-38.41.dsc
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



# Example of fio test

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



# wine 설치

```
sudo apt install wine-stable ttf-mscorefonts-installer --install-recommends
sudo apt install fonts-nanum fonts-nanum-extra fonts-nanum-coding
sudo apt install wine64
```



# fix GitKraken invalid collation character error

added ```LC_ALL=C``` to the ```Exec=env``` line, in the file ```/var/lib/snapd/desktop/applications/gitkraken_gitkraken.desktop```

```
Exec=env LC_ALL=C BAMF_DESKTOP_FILE_HINT=/var/lib/snapd/desktop/applications/gitkraken_gitkraken.desktop /snap/bin/gitkraken %U
```



# OS disk 이동

 ```
mkdir src dest
sudo mkfs.ext4 /dev/nvme1n1p2
sudo mount -o loop /dev/nvme0n1p2 src/
sudo mount -o loop /dev/nvme1n1p2 dest/
cd dest/
sudo cp -av ../src/* .
cd ..
sudo umount src dest
 ```





# Deleting a git commit

## Example git log

| Number | Hash    | Commit Message                                         | Author       |
| ------ | ------- | ------------------------------------------------------ | ------------ |
| 1      | 2c6a45b | (HEAD) Adding public method to access protected method | Tom          |
| 2      | ae45fab | Updates to database interface                          | Contractor 1 |
| 3      | 77b9b82 | Improving database interface                           | Contractor 2 |
| 4      | 3c9093c | Merged develop branch into master                      | Tom          |
| 5      | b3d92c5 | Adding new Event CMS Module                            | Paul         |
| 6      | 7feddbb | Adding CMS class and files                             | Tom          |
| 7      | a809379 | Adding project to Git                                  | Tom          |

## Using Cherry Pick

**Step 1:** Find the commit before the commit you want to remove `git log`

**Step 2:** Checkout that commit `git checkout <commit hash>`

**Step 3:** Make a new branch using your current checkout commit `git checkout -b <new branch>`

**Step 4:** Now you need to add the commit after the removed commit `git cherry-pick <commit hash>`

**Step 5:** Now repeat Step 4 for all other commits you want to keep.

**Step 6:** Once all commits have been added to your new branch and have been commited. Check that everything is in the correct state and working as intended. Double check everything has been commited: `git status`

**Step 7:** Switch to your broken branch `git checkout <broken branch>`

**Step 8:** Now perform a hard reset on the broken branch to the commit prior to the one your want to remove `git reset --hard <commit hash>`

**Step 9:** Merge your fixed branch into this branch `git merge <branch name>`

**Step 10:** Push the merged changes back to origin. **WARNING: This will overwrite the remote repo!** `git push --force origin <branch name>`

You can do the process without creating a new branch by replacing **Step 2 & 3** with **Step 8** then not carry out **Step 7 & 9.**

### **Example**

Say we want to remove commits 2 & 4 from the repo.

1. `git checkout b3d92c5` Checkout the last usable commit.
2. `git checkout -b repair` Create a new branch to work on.
3. `git cherry-pick 77b9b82` Run through commit 3.
4. `git cherry-pick 2c6a45b` Run through commit 1.
5. `git checkout master` Checkout master.
6. `git reset --hard b3d92c5` Reset master to last usable commit.
7. `git merge repair` Merge our new branch onto master.
8. `git push --hard origin master` Push master to the remote repo.