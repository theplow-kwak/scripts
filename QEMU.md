# Virtual Open-Channel SSD

## pre-install tools 
```bash
sudo apt install make 
sudo apt install make-guile gcc g++ curl git dpkg-dev 
sudo apt install python python3 python-pip python3-pip python-tk python3-tk bison
sudo apt install libgflags-dev

sudo apt install openjdk-8-jdk
sudo apt install maven
sudo apt install vagrant

sudo apt install libglib2.0-dev libpixman-1-dev libxen-dev libgtk-3-dev
```

## Compiling & Installing
```bash
git clone https://github.com/OpenChannelSSD/qemu-nvme.git

cd qemu-nvme
./configure --enable-kvm --target-list=x86_64-softmmu --enable-linux-aio --disable-werror --disable-xen --prefix=$HOME/qemu-nvme --enable-gtk

make -j12
make install
```

## Configuring the virtual open-channel SSD drive
```bash
dd if=/dev/zero of=ocssd_backend.img bs=1M count=16384

sudo $HOME/qemu-nvme/bin/qemu-system-x86_64 -m 4G -smp 8 -s \
-drive file={path to vm image},id=diskdrive,format=raw,if=none \
-device virtio-blk-pci,drive=diskdrive,scsi=off,config-wce=off,x-data-plane=on \
-drive file={path to ocssd backend file},id=myocssd,format=raw,if=none \
-device nvme,drive=myocssd,serial=deadbeef,lnum_pu=4,lstrict=1,meta=16,mc=3
```

```bash
sudo $HOME/qemu-nvme/bin/qemu-system-x86_64 -m 4G -smp 4 -s \
-cdrom ubuntu-18.04.1-desktop-amd64.iso \
-drive file=ocssd_backend.img,id=myocssd,format=raw,if=none \
-device nvme,drive=myocssd,serial=deadbeef,lnum_pu=4,lstrict=1,meta=16,mc=3
```