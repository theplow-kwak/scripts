#!/usr/bin/python3

from genericpath import exists
import os
import logging
import argparse
import shlex
import subprocess
import platform
import hashlib
import getpass
from pathlib import Path
from time import sleep


def set_logger(log_name='', log_file=None):
    logger = logging.getLogger(log_name)
    if logger.handlers:
        return logger
    if log_file:
        os.makedirs(str(Path(log_file).parent), exist_ok=True)
        fh = logging.FileHandler(log_file)
        formatter = logging.Formatter(
            '%(asctime)s [%(name)s] %(levelname)s: %(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    sh = logging.StreamHandler()
    logger.addHandler(sh)
    logger.setLevel(logging.WARNING)
    return logger


CJQ_RESULT = '.'
mylogger = set_logger('QEMU', f'{CJQ_RESULT}/qemu.log')


class QEMU():
    def __init__(self):
        self.vmimages = []
        self.vmcdimages = []
        self.vmnvme = []
        self.params = []
        self.opts = []
        self.index = self.use_nvme = 0

    def set_qemu(self):
        self.sudo = ["sudo"] if os.getuid() else []
        self.qemu_exe = [f"qemu-system-{self.args.arch}"] if self.args.qemu else [f"{str(Path.home())}/qemu/bin/qemu-system-{self.args.arch}"]
        self.params = [f"-name {self.vmname},process={self.vmprocid}"]

        match self.args.arch:
            case 'arm':
                self.params += ["-M virt -cpu cortex-a53 -device ramfb"]
            case 'aarch64':
                self.params += ["-M virt -cpu cortex-a72 -device ramfb"]
            case 'x86_64':
                self.params += ["-cpu host --enable-kvm"]
        _numcore = int(os.cpu_count() / 2)
        self.params += [
            f"-m 8G -smp {_numcore},sockets=1,cores={_numcore},threads=1 -nodefaults"]
        self.opts += ["-monitor stdio"]

    def set_M_Q35(self):
        self.opts += ["-machine type=q35,accel=kvm,usb=on -device intel-iommu"]
        self.params += ["-object rng-random,id=rng0,filename=/dev/urandom -device virtio-rng-pci,rng=rng0"]

    def set_images(self):
        for image in self.args.image:
            if Path(image).exists() or 'nvme' in image[:4]:
                match image.split('.'):
                    case [*name, 'img' | 'IMG']:        self.vmimages.append(image)
                    case [*name, 'qcow2' | 'QCOW2']:    self.vmimages.append(image)
                    case [*name, 'vhdx' | 'VHDX']:      self.vmimages.append(image)
                    case [*name, 'iso' | 'ISO']:        self.vmcdimages.append(image)
                    case _ if '/dev/' in image:         self.vmimages.append(image)
                    case _ if 'nvme' in image[:4]:
                        self.vmnvme.append(image)
                        self.use_nvme = 1
                    case _:
                        pass
            else:
                mylogger.debug(f"File not found! {image}")

        _boot_dev = self.vmimages + self.vmnvme + self.vmcdimages
        if not _boot_dev:
            raise Exception("There is no Boot device!!")
        boot_0 = Path(_boot_dev[0]).resolve()
        self.vmname = boot_0.stem
        self.vmguid = hashlib.md5(str(boot_0).encode()).hexdigest()
        self.vmuid = self.vmguid[0:2]
        self.vmprocid = f"{self.vmname[0:12]}_{self.vmuid}"
        self.G_TERM = [f"gnome-terminal --title={self.vmname} --"]

        mylogger.info(f"vmimages {self.vmimages} ")
        mylogger.info(f"vmcdimages {self.vmcdimages} ")
        mylogger.info(f"vmnvme {self.vmnvme} ")

    def set_args(self):
        parser = argparse.ArgumentParser(
            formatter_class=argparse.RawTextHelpFormatter)
        parser.add_argument('image', metavar='IMAGE', nargs='+',
                            help='the set of VM image')
        parser.add_argument('--arch', '-a', default='x86_64', choices=['x86_64', 'aarch64', 'arm'],
                            help="The architecture of target VM.")
        parser.add_argument("--debug", '-d', nargs='?', const='info', default='warning', choices=['cmd', 'debug', 'info', 'warning', 'error', 'critical'],
                            help="Set the logging level. (default: 'warning')")
        parser.add_argument("--qemu", '-q', action='store_true',
                            help="Used dist qemu package")
        parser.add_argument("--bios", action='store_true',
                            help="boot from MBR BIOS")
        parser.add_argument("--rmssh", action='store_true',
                            help="Remove existing SSH keys")
        parser.add_argument("--tpm", action='store_true',
                            help="Remove existing SSH keys")
        parser.add_argument("--ipmi", choices=['internal', 'external'],
                            help="IPMI model - 'external', 'internal'")
        parser.add_argument("--net", default='bridge', choices=['user', 'u', 'tap', 't', 'bridge', 'b'],
                            help="network interface model - 'user', 'tap', 'bridge'")
        parser.add_argument("--vga", default='qxl', choices=['qxl', 'virtio'],
                            help="set the type of VGA graphic card. 'virtio', 'qxl'(default)")
        parser.add_argument("--uname", '-u', default=getpass.getuser(),
                            help="set login user name")
        parser.add_argument("--connect", default='spice', choices=['ssh', 'spice'],
                            help="connection method - 'ssh' 'spice'(default)")
        parser.add_argument("--stick",
                            help="Set the USB storage image")
        self.args = parser.parse_args()
        if self.args.debug != 'cmd':
            mylogger.setLevel(self.args.debug.upper())

    def set_uefi(self):
        match self.args.arch:
            case 'x86_64':
                _OVMF_PATH = "/usr/share/OVMF"
                _OVMF_CODE = f"{_OVMF_PATH}/OVMF_CODE.fd"
            case 'aarch64':
                _OVMF_PATH = "/usr/share/qemu-efi-aarch64"
                _OVMF_CODE = f"{_OVMF_PATH}/QEMU_EFI.fd"
            case _:
                return

        _UEFI = [
            f"-bios {_OVMF_CODE}"]
        self.params += _UEFI

    def set_usb3(self):
        _USB = ["-device qemu-xhci,id=usb3"]
        _USB_REDIR = [
            "-chardev spicevmc,name=usbredir,id=usbredirchardev1 -device usb-redir,chardev=usbredirchardev1,id=usbredirdev1",
            "-chardev spicevmc,name=usbredir,id=usbredirchardev2 -device usb-redir,chardev=usbredirchardev2,id=usbredirdev2",
            "-chardev spicevmc,name=usbredir,id=usbredirchardev3 -device usb-redir,chardev=usbredirchardev3,id=usbredirdev3",
            "-chardev spicevmc,name=usbredir,id=usbredirchardev4 -device usb-redir,chardev=usbredirchardev4,id=usbredirdev4"]
        _USB_PT = ["-device usb-host,hostbus=3,hostport=1"]
        self.params += _USB + _USB_REDIR

    def set_usb_storage(self):
        if self.args.stick and Path(self.args.stick).exists():
            _STICK = [
                f"-drive file={self.args.stick},if=none,format=raw,id=stick{self.index}",
                f"-device usb-storage,drive=stick{self.index}"]
            self.index += 1
            self.params += _STICK

    def set_usb_arm(self):
        _USB = [
            "-device qemu-xhci,id=usb3 -device usb-kbd -device usb-tablet"]
        self.params += _USB

    def set_disks(self):
        _SCSI = [
            "-object iothread,id=iothread0 -device virtio-scsi-pci,id=scsi0,iothread=iothread0"]
        _DISKS = []
        for _image in self.vmimages:
            match _image.split('.'):
                case [*name, 'qcow2' | 'QCOW2']:
                    _DISKS += [
                        f"-drive file={_image},cache=writeback,id=drive-{self.index}"]
                case [*name, 'vhdx' | 'VHDX']:
                    _DISKS += [
                        f"-drive file={_image},if=none,id=drive-{self.index}",
                        f"-device nvme,drive=drive-{self.index},serial=nvme-{self.index}"]
                case _:
                    # _disk_type = 'scsi-hd' if Path(_image).is_block_device and 'nvme' not in _image else 'scsi-hd'
                    _DISKS += [
                        f"-drive file={_image},if=none,format=raw,discard=unmap,aio=native,cache=none,id=drive-{self.index}",
                        f"-device scsi-hd,scsi-id={self.index},drive=drive-{self.index},id=scsi0-{self.index}"]
            self.index += 1
        if _DISKS:
            self.params += _SCSI + _DISKS

    def set_cdrom(self):
        _IF = "ide" if self.args.arch == 'x86_64' else "none"
        _CDROMS = ""
        for _image in self.vmcdimages:
            _CDROMS += [
                f"-drive file={_image},media=cdrom,readonly=on,if={_IF},index={self.index},id=cdrom{self.index}"]
            if self.args.arch != 'x86_64':
                _CDROMS += [
                    f"-device usb-storage,drive=cdrom{self.index}"]
            self.index += 1
        if _CDROMS:
            self.params += _CDROMS

    def check_file(self, filename, size):
        if not Path(filename).exists():
            self.runshell(f"qemu-img create -f raw {filename} {size}G")
        if self.runshell(f"lsof -w {filename}").returncode == 0:
            return 0
        return 1

    def set_nvme(self):
        if not self.use_nvme:
            return
        _num_ns = 4
        _ns_size = 1
        if not self.vmnvme:
            self.vmnvme.append(f"nvme{self.vmuid}")

        _ctrl_id = 1
        NVME = [
            "-device ioh3420,bus=pcie.0,id=root1.0,slot=1",
            "-device x3130-upstream,bus=root1.0,id=upstream1.0"]

        for _NVME in self.vmnvme:
            if self.args.qemu:
                ns_backend = f"{_NVME}n1.img"
                if self.check_file(ns_backend, _ns_size):
                    NVME += [
                        f"-drive file={ns_backend},id={_NVME},format=raw,if=none,cache=none",
                        f"-device nvme,drive={_NVME},serial=beef{_NVME}"]
            else:
                NVME += [
                        f"-device xio3130-downstream,bus=upstream1.0,id=downstream1.{_ctrl_id},chassis={_ctrl_id},multifunction=on",
                        f"-device nvme-subsys,id=nvme-subsys-{_ctrl_id},nqn=subsys{_ctrl_id}",
                        f"-device nvme,serial=beef{_NVME},id={_NVME},subsys=nvme-subsys-{_ctrl_id},bus=downstream1.{_ctrl_id}"]
                _ctrl_id += 1
                for _nsid in range(1, _num_ns+1):
                    ns_backend = f"{_NVME}n{_nsid}.img"
                    if self.check_file(ns_backend, _ns_size):
                        NVME += [
                            f"-drive file={ns_backend},id={_NVME}{_nsid},format=raw,if=none,cache=none",
                            f"-device nvme-ns,drive={_NVME}{_nsid},bus={_NVME},nsid={_nsid}"]
        if Path("./events").exists():
            NVME += ["--trace events=./events"]
        if NVME:
            self.params += NVME

    def runshell(self, cmd, _async=False):
        if isinstance(cmd, list): cmd = ' '.join(cmd)
        mylogger.debug(f"runshell: {cmd}")
        _cmd = shlex.split(cmd)
        if _async:
            completed = subprocess.Popen(_cmd)
            # _cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        else:
            completed = subprocess.run(
                _cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        mylogger.debug(
            f"Return code {completed.returncode}: {completed.stdout}")
        return completed

    def set_ipmi(self):
        match self.args.ipmi:
            case "internal":
                _IPMI = ["-device ipmi-bmc-sim,id=bmc0"]
            case "external":
                _IPMI = [
                    "-chardev socket,id=ipmi0,host=localhost,port=9002,reconnect=10",
                    "-device ipmi-bmc-extern,chardev=ipmi0,id=bmc1",
                    "-device isa-ipmi-kcs,bmc=bmc1"]
        self.params += _IPMI

    def set_spice(self):
        SPICE = [
            f"-spice port={self.SPICEPORT},disable-ticketing=on",
            "-device intel-hda -device hda-duplex"]
        SPICE_AGENT = [
            "-chardev spicevmc,id=vdagent,name=vdagent",
            "-device virtio-serial",
            "-device virtserialport,chardev=vdagent,name=com.redhat.spice.0"]
        GUEST_AGENT = [
            "-chardev socket,path=/tmp/qga.sock,server,nowait,id=qga0,name=qga0",
            "-device virtio-serial",
            "-device virtserialport,chardev=qga0,name=org.qemu.guest_agent.0"]
        SHARE0 = [
            f"-virtfs local,id=fsdev0,path={str(Path.home())},security_model=passthrough,writeout=writeout,mount_tag=host"]
        self.params += SPICE + SPICE_AGENT

    def set_tpm(self):
        fn_cancle = f"/tmp/foo-cancel-{self.vmuid}"
        Path(fn_cancle).touch(exist_ok=True)

        TPM = [
            f"-tpmdev passthrough,id=tpm0,path=/dev/tpm0,cancel-path={fn_cancle}",
            "-device tpm-tis,tpmdev=tpm0"]
        self.params += TPM

    def RemoveSSH(self):
        Path(f"/tmp/{self.vmprocid}_SSH").unlink(missing_ok=True)
        if self.args.net == "user":
            self.runshell(f'ssh-keygen -R "[{self.hostip}]:{self.SSHPORT}"')
        else:
            self.runshell(f'ssh-keygen -R "{self.localip}"')

    def set_net(self, _set=False):
        try:
            self.SSHPORT = int(Path(f"/tmp/{self.vmprocid}_SSH").read_text())
        except:
            self.SSHPORT = 5900
        self.SPICEPORT = self.SSHPORT + 1
        self.macaddr = f"52:54:00:{self.vmguid[0:2]}:{self.vmguid[2:4]}:{self.vmguid[4:6]}"
        self.hostip = self.runshell("ip r g 1.0.0.0").stdout.split()[6]
        dhcp_chk = self.runshell(f"virsh --quiet net-dhcp-leases default --mac {self.macaddr}")
        self.localip = dhcp_chk.stdout.split()[4].split('/')[0] if dhcp_chk.stdout else None

        if _set:
            while not self.runshell(f"lsof -w -i :{self.SPICEPORT}").returncode or not self.runshell(f"lsof -w -i :{self.SSHPORT}").returncode:
                self.SSHPORT += 2
                self.SPICEPORT = self.SSHPORT + 1
            match self.args.net:
                case "user" | "u":
                    NET = [
                        f"-nic user,model=virtio-net-pci,mac={self.macaddr},smb={str(Path.home())},hostfwd=tcp::{self.SSHPORT}-:22"]
                case "tap" | "t":
                    NET = [
                        f"-nic tap,model=virtio-net-pci,mac={self.macaddr},script={str(Path.home())}/vm/share/qemu-ifup"]
                    # ,downscript=$VMHOME/share/qemu-ifdown
                case "bridge" | "b":
                    NET = [
                        f"-nic bridge,br=virbr0,model=virtio-net-pci,mac={self.macaddr}"]
            self.params += NET
            Path(f"/tmp/{self.vmprocid}_SSH").write_text(str(self.SSHPORT))

    def set_connect(self):
        if self.args.arch != "aarch64":
            self.opts += [f"-vga {self.args.vga}"]
        match self.args.connect:
            case "ssh":
                if "-monitor stdio" in self.opts: self.opts.remove("-monitor stdio")
                if f"-vga {self.args.vga}" in self.opts: self.opts.remove(f"-vga {self.args.vga}")
                self.opts += ["-nographic -serial mon:stdio"]
                self.SSH_CONNECT = self.localip if self.args.net != "user" else f"{self.hostip} -p {self.SSHPORT}"
                self.CHKPORT = self.SSHPORT
                T_TITLE = f"{self.vmname}:{self.CHKPORT}"
                self.CONNECT = self.G_TERM + \
                    [f"ssh {self.args.uname}@{self.SSH_CONNECT}"]
            case "spice":
                self.CHKPORT = self.SPICEPORT
                T_TITLE = f"{self.vmname}:{self.CHKPORT}"
                self.CONNECT = [
                    f"remote-viewer -t {T_TITLE} spice://{self.hostip}:{self.SPICEPORT} --spice-usbredir-auto-redirect-filter=0x03,-1,-1,-1,0|-1,-1,-1,-1,1"]
        #        CONNECT=(remote-viewer -t {T_TITLE} spice://localhost:{self.SPICEPORT} --spice-usbredir-redirect-on-connect="0x03,-1,-1,-1,0|-1,-1,-1,-1,1" --spice-usbredir-auto-redirect-filter="0x03,-1,-1,-1,0|-1,-1,-1,-1,1")
        #        CONNECT=(virt-viewer -c qemu:///system --spice-usbredir-redirect-on-connect="0x03,-1,-1,-1,0|-1,-1,-1,-1,1" --spice-usbredir-auto-redirect-filter="0x03,-1,-1,-1,0|-1,-1,-1,-1,1")
        mylogger.info(T_TITLE)
        mylogger.info(self.CONNECT)

    def findProc(self, _PROCID, _timeout=10):
        while self.runshell(f"ps -C {_PROCID}").returncode:
            _timeout -= 1
            if _timeout < 0:
                return 0
            sleep(1)
        return 1

    def setting(self):
        self.set_args()
        self.set_images()
        if not self.findProc(self.vmprocid, 0):
            self.set_qemu()
            if self.args.arch == 'x86_64':
                self.set_M_Q35()
            if not self.args.bios:
                self.set_uefi()
            self.set_usb3() if self.args.arch == 'x86_64' else self.set_usb_arm()
            self.set_disks()
            self.set_cdrom()
            self.set_nvme()
            self.set_usb_storage()
            self.set_net(True)
            if self.args.ipmi:
                self.set_ipmi()
            if self.args.connect == 'spice':
                self.set_spice()
            if self.args.tpm:
                self.set_tpm()
            self.set_connect()
        else:
            self.set_net()
            self.set_connect()

        if self.args.rmssh:
            self.RemoveSSH()

    def checkConn(self, timeout=10):
        if self.SSH_CONNECT is None:
            return 0
        while self.runshell(f"ping -c 1 {self.SSH_CONNECT}").returncode:
            timeout -= 1
            if timeout < 0:
                return 1
            sleep(1)
        return 0

    def run(self):
        if not self.findProc(self.vmprocid, 0):
            _qemu_command = self.sudo + self.G_TERM + \
                self.qemu_exe + self.params + self.opts
            if self.args.debug == 'cmd':
                print(' '.join(_qemu_command))
            completed = self.runshell(_qemu_command)
        if self.CONNECT:
            if self.findProc(self.vmprocid):
                _qemu_connect = self.CONNECT
                if self.args.debug == 'cmd':
                    print(' '.join(_qemu_connect))
                if self.args.connect == 'ssh':
                    self.checkConn(60)
                self.runshell(_qemu_connect, True)


def main():
    qemu = QEMU()
    qemu.setting()
    qemu.run()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        mylogger.error(f"QEMU terminated abnormally. {e}")