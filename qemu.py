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
import functools
from pathlib import Path
from time import sleep


def set_logger(log_name="", log_file=None):
    logger = logging.getLogger(log_name)
    if logger.handlers:
        return logger
    if log_file:
        os.makedirs(str(Path(log_file).parent), exist_ok=True)
        fh = logging.FileHandler(log_file)
        formatter = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    sh = logging.StreamHandler()
    logger.addHandler(sh)
    logger.setLevel(logging.WARNING)
    return logger


mylogger = set_logger("QEMU", f"/tmp/qemu.log")


class QEMU:
    def __init__(self):
        self.vmimages = []
        self.vmcdimages = []
        self.vmnvme = []
        self.params = []
        self.opts = []
        self.KERNEL = []
        self.index = self.use_nvme = 0
        self.home_folder = f"/home/{os.getlogin()}"
        self.memsize = self._calculate_memory_size()

    def _calculate_memory_size(self):
        """Calculate memory size based on physical memory."""
        phy_mem = int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / (1024 * 1024 * 1000))
        return "8G" if phy_mem > 8 else "4G"

    def set_args(self):
        parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
        parser.add_argument("--secboot", default="", action="store_const", const=".secboot", help="Using secureboot of UEFI")
        parser.add_argument("--bios", action="store_true", help="Using legacy BIOS instead of UEFI")
        parser.add_argument("--consol", action="store_true", help="Used the current terminal as the consol I/O")
        parser.add_argument("--noshare", action="store_true", help="Do not support virtiofs")
        parser.add_argument("--nousb", action="store_true", help="Do not support usb port")
        parser.add_argument("--qemu", "-q", action="store_true", help="Use the qemu public distribution")
        parser.add_argument("--rmssh", action="store_true", help="Remove existing SSH key")
        parser.add_argument("--tpm", action="store_true", help="Support TPM device for windows 11")
        parser.add_argument("--arch", "-a", default="x86_64", choices=["x86_64", "aarch64", "arm", "riscv64"], help="The architecture of target VM.",)
        parser.add_argument("--connect", default="spice", choices=["ssh", "spice", "qemu"], help="Connection method - 'spice'(default)",)
        parser.add_argument("--debug", "-d", nargs="?", const="info", default="warning", choices=["cmd", "debug", "info", "warning"], help="Set the logging level. (default: 'warning')")
        parser.add_argument("--ipmi", choices=["internal", "external"], help="IPMI model - 'external', 'internal'")
        parser.add_argument("--machine", default="q35", choices=["q35", "ubuntu-q35", "pc", "ubuntu", "virt", "sifive_u"], help="IPMI model - 'external', 'internal'")
        parser.add_argument("--net", default="bridge", choices=["user", "tap", "bridge", "none"], help="Network interface model - 'user', 'tap', 'bridge'")
        parser.add_argument("--uname", "-u", default=os.getlogin(), help="Set login user name")
        parser.add_argument("--vga", default="qxl", help="Set the type of VGA graphic card. 'virtio', 'qxl'(default)")
        parser.add_argument("--stick", help="Set the USB storage image")
        parser.add_argument("--ip", help="Set local ip")
        parser.add_argument("images", metavar="IMAGES", nargs="*", help="Set the VM images")
        parser.add_argument("--nvme", help="Set the NVMe images")
        parser.add_argument("--vender", help="Set the PC vender")
        parser.add_argument("--kernel", dest="vmkernel", help="Set the Linux Kernel image")
        parser.add_argument("--rootdev", help="Set the rootfs dev")
        parser.add_argument("--initrd", help="Set the initrd image")
        parser.add_argument("--pcihost", help="PCI passthrough")
        parser.add_argument("--numns", type=int, help="Set the numbers of NVMe namespace")
        parser.add_argument("--nssize", type=int, default=1, help="Set the size of NVMe namespace")
        parser.add_argument("--num_queues", type=int, default=32, help="Set the max num of queues")
        parser.add_argument("--vnum", default="", help="Set the vm copies")
        parser.add_argument("--sriov", action="store_true", help="Set to use sriov")
        parser.add_argument("--fdp", action="store_true", help="Set to use fdp")
        parser.add_argument("--hvci", action="store_true", help="Hypervisor-Protected Code Integrity (HVCI).")
        parser.add_argument("--did", type=functools.partial(int, base=0), help="Set the NVMe device ID")
        parser.add_argument("--mn", help="Set the model name")
        parser.add_argument("--ext", help="Set the extra params")
        parser.add_argument("--memsize", help="Set the memory size")
        self.args = parser.parse_args()
        if self.args.debug == "cmd":
            mylogger.setLevel("INFO")
        else:
            mylogger.setLevel(self.args.debug.upper())
        if self.args.nvme:
            _result = self.runshell(f"lsblk -d -o NAME,MODEL,SERIAL --sort NAME -n")
            if _result.returncode == 0:
                _nvme_param = self.args.nvme.lower().split(":")
                _nvme = _nvme_param.pop(0)
                _images = [line.split()[0] for line in _result.stdout.splitlines() if _nvme in line.lower()]
                for _image in _images:
                    _part = _nvme_param.pop(0) if _nvme_param else ""
                    self.args.images.append(f"/dev/{_image}{_part}")
        if self.args.numns:
            self.use_nvme = 1

    def set_images(self):
        for image in self.args.images:
            if Path(image).exists() or "nvme" == image[:4]:
                match image.split("."):
                    case _ if "nvme" in image[:4]:
                        self.vmnvme.append(image)
                        self.use_nvme = 1
                    case [*name, "img" | "IMG"]:
                        self.vmimages.append(image)
                    case [*name, "qcow2" | "QCOW2"]:
                        self.vmimages.append(image)
                    case [*name, "vhdx" | "VHDX"]:
                        self.vmimages.append(image)
                    case [*name, "iso" | "ISO"]:
                        self.vmcdimages.append(image)
                    case _ if "/dev/" in image:
                        self.vmimages.append(image)
                    case _ if "vmlinuz" in image:
                        self.args.vmkernel = image
                    case _:
                        pass

        _boot_dev = self.vmimages + self.vmnvme + self.vmcdimages
        if self.args.vmkernel:
            _boot_dev.append(self.args.vmkernel)
        mylogger.info(f"vmimages {self.vmimages} ")
        mylogger.info(f"vmcdimages {self.vmcdimages} ")
        mylogger.info(f"vmnvme {self.vmnvme} ")
        mylogger.info(f"vmkernel {self.args.vmkernel} ")
        mylogger.info(f"boot_dev {_boot_dev} ")
        if not _boot_dev:
            raise Exception("There is no Boot device!!")
        self.bootype = "1" if self.vmnvme and self.vmnvme[0] == _boot_dev[0] else ""
        boot_0 = Path(_boot_dev[0]).resolve()
        self.vmboot = _boot_dev[0]
        self.vmname = boot_0.stem
        self.vmguid = hashlib.md5(("".join([x for x in _boot_dev if x is not None])).encode()).hexdigest()
        self.vmuid = self.vmguid[0:2]
        self.vmprocid = f"{self.vmname[0:12]}_{self.vmuid}"
        self.G_TERM = [f"gnome-terminal --title={self.vmprocid}"]

    def runshell(self, cmd, _async=False, _consol=False):
        """Run shell commands with optional async and console output."""
        if isinstance(cmd, list):
            cmd = " ".join(cmd)
        _cmd = shlex.split(cmd)
        mylogger.debug(f"runshell {'Async' if _async else ''}: {cmd}")
        if _async:
            completed = subprocess.Popen(_cmd) if not _consol else subprocess.run(_cmd, text=True)
            sleep(1)
        else:
            completed = subprocess.run(_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) if not _consol else subprocess.run(_cmd, text=True)
            if completed.stdout:
                mylogger.debug(f"Return code: {completed.returncode}, stdout: {completed.stdout.rstrip()}")
        return completed

    def set_qemu(self):
        """Set QEMU executable and base parameters."""
        self.sudo = ["sudo"] if os.getuid() else []
        self.qemu_exe = [f"qemu-system-{self.args.arch}"] if self.args.qemu else [f"{self.home_folder}/qemu/bin/qemu-system-{self.args.arch}"]
        self.params = [f"-name {self.vmname},process={self.vmprocid}"]

        arch_params = {
            "riscv64": ["-machine virt -bios none"],
            "arm": ["-machine virt -cpu cortex-a53 -device ramfb"],
            "aarch64": ["-machine virt,virtualization=true -cpu cortex-a72 -device ramfb"],
            "x86_64": self._set_x86_64_params(),
        }
        self._add_param(self.params, *arch_params.get(self.args.arch, []))
        self._add_param(self.params, f"-m {self.memsize} -smp {int(os.cpu_count() / 2)},sockets=1,cores={int(os.cpu_count() / 2)},threads=1 -nodefaults", "-rtc base=localtime")

    def _set_x86_64_params(self):
        """Set parameters specific to x86_64 architecture."""
        params = [f"-machine type={self.args.machine},accel=kvm,usb=on -device intel-iommu"]
        if self.args.hvci:
            params += [
                "-cpu Skylake-Client-v3,hv_stimer,hv_synic,hv_relaxed,hv_reenlightenment,hv_spinlocks=0xfff,hv_vpindex,hv_vapic,hv_time,hv_frequencies,hv_runtime,+kvm_pv_unhalt,+vmx --enable-kvm"
            ]
        else:
            params += ["-cpu host --enable-kvm"]
            if self.args.vender:
                params += [f"-smbios type=1,manufacturer={self.args.vender},product='{self.args.vender} Notebook PC'"]
        params += ["-object rng-random,id=rng0,filename=/dev/urandom -device virtio-rng-pci,rng=rng0"]
        self.opts += [f"-vga {self.args.vga}"]
        return params

    def _add_param(self, param_list, *params):
        """Helper to add parameters to the param list."""
        param_list.extend(params)

    def set_uefi(self):
        _OVMF_PATH = f"{self.home_folder}/qemu/share/qemu"
        match self.args.arch:
            case "x86_64":
                _OVMF_CODE = f"-drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M{self.args.secboot}.fd"
                _OVMF_VAR = f"-drive if=pflash,format=raw,file={self.home_folder}/vm/OVMF_VARS_4M.ms{self.bootype}.fd"
            case "aarch64":
                _OVMF_CODE = f"-drive if=pflash,format=raw,readonly=on,file={_OVMF_PATH}/edk2-aarch64-code.fd"
                _OVMF_VAR = f"-drive if=pflash,format=raw,file={self.home_folder}/vm/edk2-arm-vars.fd"
            case _:
                return
        _UEFI = [f"{_OVMF_CODE}", f"{_OVMF_VAR}"]
        self.params += _UEFI

    def set_usb3(self):
        _USB = ["-device qemu-xhci,id=xhci1"]
        _USB_REDIR = [
            "-chardev spicevmc,name=usbredir,id=usbredirchardev1 -device usb-redir,bus=xhci1.0,chardev=usbredirchardev1,id=usbredirdev1",
            "-chardev spicevmc,name=usbredir,id=usbredirchardev2 -device usb-redir,bus=xhci1.0,chardev=usbredirchardev2,id=usbredirdev2",
            "-chardev spicevmc,name=usbredir,id=usbredirchardev3 -device usb-redir,bus=xhci1.0,chardev=usbredirchardev3,id=usbredirdev3",
        ]
        _USB_PT = ["-device qemu-xhci,id=xhci2", "-device usb-host,bus=xhci2.0,vendorid=0x04e8,productid=0x6860"]
        self.params += _USB + _USB_REDIR + _USB_PT

    def set_usb_storage(self):
        if self.args.stick and Path(self.args.stick).exists():
            _STICK = [
                f"-drive file={self.args.stick},if=none,format=raw,id=stick{self.index}",
                f"-device usb-storage,drive=stick{self.index}",
            ]
            self.index += 1
            self.params += _STICK

    def set_usb_arm(self):
        _USB = ["-device qemu-xhci,id=usb3 -device usb-kbd -device usb-tablet"]
        self.params += _USB

    def set_disks(self):
        if self.args.arch == "riscv64":
            _SCSI = []
        else:
            _SCSI = ["-object iothread,id=iothread0 -device virtio-scsi-pci,id=scsi0,iothread=iothread0"]
        _DISKS = []
        for _image in self.vmimages:
            match _image.split("."):
                case ["wiftest", *ext]:
                    _DISKS += [
                        f"-drive if=none,cache=none,file=blkdebug:blkdebug.conf:{_image},format=qcow2,id=drive-{self.index}",
                        f"-device virtio-blk-pci,drive=drive-{self.index},id=virtio-blk-pci{self.index}",
                    ]
                case [*name, "qcow2" | "QCOW2"]:
                    _DISKS += [f"-drive file={_image},cache=writeback,id=drive-{self.index}"]
                case [*name, "vhdx" | "VHDX"]:
                    _DISKS += [
                        f"-drive file={_image},if=none,id=drive-{self.index}",
                        f"-device nvme,drive=drive-{self.index},serial=nvme-{self.index}",
                    ]
                case _:
                    # _disk_type = 'scsi-hd' if Path(_image).is_block_device and 'nvme' not in _image else 'scsi-hd'
                    _DISKS += [
                        f"-drive file={_image},if=none,format=raw,discard=unmap,aio=native,cache=none,id=drive-{self.index}",
                        f"-device scsi-hd,scsi-id={self.index},drive=drive-{self.index},id=scsi0-{self.index}",
                    ]
            self.index += 1
        if _DISKS:
            self.params += _SCSI + _DISKS

    def set_cdrom(self):
        _IF = "ide" if self.args.arch == "x86_64" else "none"
        _CDROMS = []
        for _image in self.vmcdimages:
            _CDROMS += [f"-drive file={_image},media=cdrom,readonly=on,if={_IF},index={self.index},id=cdrom{self.index}"]
            if self.args.arch != "x86_64":
                _CDROMS += [f"-device usb-storage,drive=cdrom{self.index}"]
            self.index += 1
        if _CDROMS:
            self.params += _CDROMS

    def check_file(self, filename, size):
        if not Path(filename).exists():
            self.runshell(f"qemu-img create -f qcow2 {filename} {size}G")
        if self.runshell(f"lsof -w {filename}").returncode == 0:
            return 0
        return 1

    def set_nvme(self):
        """Set NVMe devices."""
        if not self.use_nvme:
            return

        def add_nvme_drive(_NVME, ns_backend, _ctrl_id, _nsid=None, fdp_nsid=""):
            """Helper to add NVMe drive and namespace."""
            NVME = []
            if self.check_file(ns_backend, _ns_size):
                NVME.append(f"-drive file={ns_backend},id={_NVME}{_nsid or ''},if=none,cache=none")
                if _nsid:
                    NVME.append(f"-device nvme-ns,drive={_NVME}{_nsid},bus={_NVME},nsid={_nsid}{fdp_nsid}")
                else:
                    NVME.append(f"-device nvme,drive={_NVME},serial=beef{_NVME},ocp=on")
            return NVME

        _ns_size = self.args.nssize
        if not self.vmnvme:
            self.vmnvme.append(f"nvme{self.vmuid}")

        NVME = [
            "-device ioh3420,bus=pcie.0,id=root1.0,slot=1",
            "-device x3130-upstream,bus=root1.0,id=upstream1.0",
        ]

        _ctrl_id = 1
        for item in self.vmnvme:
            parts = item.split(":")
            _NVME = parts[0]
            _num_ns = int(parts[1]) if len(parts) > 1 else self.args.numns or 1

            if self.args.qemu:
                ns_backend = f"{_NVME}n1.qcow2"
                NVME += add_nvme_drive(_NVME, ns_backend, _ctrl_id)
            elif self.args.sriov:
                NVME += [
                    f"-device xio3130-downstream,bus=upstream1.0,id=downstream1.{_ctrl_id},chassis={_ctrl_id},multifunction=on",
                    f"-device nvme-subsys,id=nvme-subsys-{_ctrl_id},nqn=subsys{_ctrl_id}",
                    f"-device nvme,serial=beef{_NVME},ocp=on,id={_NVME},subsys=nvme-subsys-{_ctrl_id},bus=downstream1.{_ctrl_id},max_ioqpairs=512,msix_qsize=512,sriov_max_vfs={_num_ns},sriov_vq_flexible=508,sriov_vi_flexible=510",
                ]
                ns_backend = f"{_NVME}n1.qcow2"
                NVME += add_nvme_drive(_NVME, ns_backend, _ctrl_id, _nsid=1, fdp_nsid=",shared=false,detached=true")
                _ctrl_id += 1
            else:
                _did = f",did={self.args.did}" if self.args.did else ""
                _mn = f",mn={self.args.mn}" if self.args.mn else ""
                _fdp = ",fdp=on,fdp.runs=96M,fdp.nrg=1,fdp.nruh=16" if self.args.fdp else ""
                _fdp_nsid = ",fdp.ruhs=1-15" if self.args.fdp else ""
                NVME += [
                    f"-device xio3130-downstream,bus=upstream1.0,id=downstream1.{_ctrl_id},chassis={_ctrl_id},multifunction=on",
                    f"-device nvme-subsys,id=nvme-subsys-{_ctrl_id},nqn=subsys{_ctrl_id}{_fdp}",
                    f"-device nvme,serial=beef{_NVME},ocp=on,id={_NVME},subsys=nvme-subsys-{_ctrl_id},bus=downstream1.{_ctrl_id},max_ioqpairs={self.args.num_queues}{_did}{_mn}",
                ]
                for _nsid in range(1, _num_ns + 1):
                    ns_backend = f"{_NVME}n{_nsid}.qcow2"
                    NVME += add_nvme_drive(_NVME, ns_backend, _ctrl_id, _nsid=_nsid, fdp_nsid=_fdp_nsid if _nsid == 1 else "")
                _ctrl_id += 1

        if Path("./events").exists():
            NVME.append("--trace events=./events")

        self.params.extend(NVME)

    def set_virtiofs(self):
        virtiofsd = (
            self.sudo
            + self.G_TERM
            + ["--geometry=80x24+5+5 --"]
            + [
                (
                    f"{self.home_folder}/qemu/libexec/virtiofsd --socket-path=/tmp/virtiofs_{self.vmuid}.sock -o source={self.home_folder}"
                    if Path(f"{self.home_folder}/qemu/libexec/virtiofsd").exists()
                    else f"/usr/libexec/virtiofsd --socket-path=/tmp/virtiofs_{self.vmuid}.sock --shared-dir={self.home_folder}"
                )
            ]
        )
        if self.args.debug == "cmd":
            print(" ".join(virtiofsd))
        else:
            self.runshell(virtiofsd)
            while not Path(f"/tmp/virtiofs_{self.vmuid}.sock").exists():
                mylogger.debug("wating for /tmp/virtiofs_{self.vmuid}.sock")
                sleep(1)
        _virtiofs = [
            f"-chardev socket,id=char{self.vmuid},path=/tmp/virtiofs_{self.vmuid}.sock",
            f"-device vhost-user-fs-pci,chardev=char{self.vmuid},tag=hostfs",
            f"-object memory-backend-memfd,id=mem,size={self.memsize},share=on -numa node,memdev=mem",
        ]
        self.params += _virtiofs

    def set_ipmi(self):
        match self.args.ipmi:
            case "internal":
                _IPMI = ["-device ipmi-bmc-sim,id=bmc0"]
            case "external":
                _IPMI = [
                    "-chardev socket,id=ipmi0,host=localhost,port=9002,reconnect=10",
                    "-device ipmi-bmc-extern,chardev=ipmi0,id=bmc1",
                    "-device isa-ipmi-kcs,bmc=bmc1",
                ]
        self.params += _IPMI

    def set_spice(self):
        SPICE = [
            f"-spice port={self.SPICEPORT},disable-ticketing=on",
            "-audiodev spice,id=audio0 -device intel-hda -device hda-duplex,audiodev=audio0,mixer=off",
        ]
        SPICE_AGENT = [
            "-chardev spicevmc,id=vdagent,name=vdagent",
            "-device virtio-serial",
            "-device virtserialport,chardev=vdagent,name=com.redhat.spice.0",
        ]
        GUEST_AGENT = [
            "-chardev socket,path=/tmp/qga.sock,server,nowait,id=qga0,name=qga0",
            "-device virtio-serial",
            "-device virtserialport,chardev=qga0,name=org.qemu.guest_agent.0",
        ]
        SHARE0 = [f"-virtfs local,id=fsdev0,path={self.home_folder},security_model=passthrough,writeout=writeout,mount_tag=host"]
        self.params += SPICE + SPICE_AGENT

    def set_tpm(self):
        fn_cancle = f"/tmp/foo-cancel-{self.vmuid}"
        Path(fn_cancle).touch(exist_ok=True)

        TPM = [
            f"-tpmdev passthrough,id=tpm0,path=/dev/tpm0,cancel-path={fn_cancle}",
            "-device tpm-tis,tpmdev=tpm0",
        ]
        self.params += TPM

    def RemoveSSH(self):
        """Remove existing SSH keys for the VM."""
        ssh_file = Path(f"/tmp/{self.vmprocid}_SSH")
        ssh_file.unlink(missing_ok=True)
        ssh_key_cmd = f'ssh-keygen -R "[{self.hostip}]:{self.SSHPORT}"' if self.args.net == "user" else f'ssh-keygen -R "{self.localip}"'
        self.runshell(ssh_key_cmd)

    def set_net(self, _set=False):
        """Configure network settings for the VM."""
        try:
            self.SSHPORT = int(Path(f"/tmp/{self.vmprocid}_SSH").read_text())
        except FileNotFoundError:
            self.SSHPORT = 5900
        self.SPICEPORT = self.SSHPORT + 1
        self.macaddr = f"52:54:00:{self.vmguid[0:2]}:{self.vmguid[2:4]}:{self.vmguid[4:6]}"

        # Get host IP
        _result = self.runshell("ip r g 1.0.0.0")
        self.hostip = _result.stdout.split()[6] if _result.returncode == 0 else "localhost"
        mylogger.info(f"hostip: {self.hostip}")

        # Get local IP from DHCP leases
        _result = self.runshell(f"virsh --quiet net-dhcp-leases default --mac {self.macaddr}")
        dhcp_chk = sorted(_result.stdout.rstrip().split("\n"))[-1] if _result.returncode == 0 and _result.stdout else []
        self.localip = self.args.ip or (dhcp_chk.split()[4].split("/")[0] if dhcp_chk else None)
        mylogger.info(f"localip: {self.localip}")

        if _set:
            # Ensure ports are available
            while not self.runshell(f"lsof -w -i :{self.SPICEPORT}").returncode or not self.runshell(f"lsof -w -i :{self.SSHPORT}").returncode:
                self.SSHPORT += 2
                self.SPICEPORT = self.SSHPORT + 1

            # Configure network based on the selected mode
            net_modes = {
                "user": f"-nic user,model=virtio-net-pci,mac={self.macaddr},smb={self.home_folder},hostfwd=tcp::{self.SSHPORT}-:22",
                "tap": f"-nic tap,model=virtio-net-pci,mac={self.macaddr},script={self.home_folder}/projects/scripts/qemu-ifup",
                "bridge": f"-nic bridge,br=virbr0,model=virtio-net-pci,mac={self.macaddr}",
                "none": "",
            }
            self.params += [net_modes.get(self.args.net, "")]

            # Save SSH port to a file
            try:
                Path(f"/tmp/{self.vmprocid}_SSH").write_text(str(self.SSHPORT))
            except Exception as e:
                mylogger.error(f"Failed to write SSH port: {e}")

    def set_connect(self):
        """Configure connection settings for the VM."""
        connect_modes = {
            "ssh": self._set_ssh_connect,
            "spice": self._set_spice_connect,
            "qemu": self._set_qemu_connect,
        }
        connect_func = connect_modes.get(self.args.connect, lambda: None)
        connect_func()

    def _set_ssh_connect(self):
        """Set SSH connection settings."""
        if f"-vga {self.args.vga}" in self.opts:
            self.opts.remove(f"-vga {self.args.vga}")
        self.opts += ["-nographic -serial mon:stdio"]
        self.SSH_CONNECT = f"{self.hostip} -p {self.SSHPORT}" if self.args.net == "user" else self.localip
        self.CHKPORT = self.SSHPORT
        self.CONNECT = ([] if self.args.consol else self.G_TERM + ["--"]) + [f"ssh {self.args.uname}@{self.SSH_CONNECT}"]

    def _set_spice_connect(self):
        """Set SPICE connection settings."""
        self.opts += ["-monitor stdio"]
        self.CHKPORT = self.SPICEPORT
        self.CONNECT = [f"remote-viewer -t {self.vmprocid} spice://{self.hostip}:{self.SPICEPORT} --spice-usbredir-auto-redirect-filter=0x03,-1,-1,-1,0|-1,-1,-1,-1,1"]

    def _set_qemu_connect(self):
        """Set QEMU connection settings."""
        self.opts += ["-monitor stdio"]
        self.CHKPORT = self.SPICEPORT
        self.CONNECT = None

    def findProc(self, _PROCID, _timeout=10):
        """Wait for a process to start."""
        while self.runshell(f"ps -C {_PROCID}").returncode:
            mylogger.debug(f"findProc timeout {_timeout}")
            _timeout -= 1
            if _timeout < 0:
                return 0
            sleep(1)
        mylogger.debug("findProc return 1")
        return 1

    def checkConn(self, timeout=10):
        """Check if the SSH connection is available."""
        if not self.SSH_CONNECT:
            return 0
        while self.runshell(f"ping -c 1 {self.SSH_CONNECT}").returncode:
            timeout -= 1
            if timeout < 0:
                return 1
            sleep(1)
        return 0

    def set_kernel(self):
        self.KERNEL = [f"-kernel {self.args.vmkernel}"]
        if self.args.arch == "riscv64":
            return
        if self.args.initrd:
            self.KERNEL += [f"-initrd {self.args.initrd}"]
        elif "vmlinuz" in self.args.vmkernel:
            self.KERNEL += [
                "-initrd",
                self.args.vmkernel.replace("vmlinuz", "initrd.img"),
            ]

        if ".img" in self.vmimages[0]:
            _root_dev = "sda"
        else:
            _root_dev = "sda1"
        if self.args.rootdev:
            _root_dev = self.args.rootdev
        if self.args.connect == "ssh":
            self.KERNEL += [f'-append "root=/dev/{_root_dev} console=ttyS0"']
        else:
            self.KERNEL += [f'-append "root=/dev/{_root_dev} vga=0x300"']

    # def set_pcipass(self):
    #     [[ -z self.args.pcihost ]] && return
    #     # unbind 0000:0x:00.0 from xhci_hcd kernel module
    #     _driver_=$(sudo lspci -k -s $args_pcihost | awk '/Kernel driver.*/{print $NF}')
    #     sudo -S sh -c "echo '$args_pcihost' > /sys/bus/pci/drivers/$_driver_/unbind"
    #     # bind 0000:0x:00.0 to vfio-pci kernel module
    #     DEVID=$(sudo lspci -ns $args_pcihost | awk '//{print $NF}' | awk -F: '{print "%s %s", $1, $2}')
    #     sudo -S sh -c "echo '$DEVID' > /sys/bus/pci/drivers/vfio-pci/new-id"

    #     PCIPASS=" -device vfio-pci,host=$args_pcihost,multifunction=on"
    #     self.params+=($PCIPASS)

    def setting(self):
        self.set_args()
        self.set_images()
        if not self.findProc(self.vmprocid, 0):
            self.set_qemu()
            if not self.args.bios:
                self.set_uefi()
            if self.args.vmkernel:
                self.set_kernel()
            # self.set_pcipass()
            if not self.args.nousb:
                self.set_usb3() if self.args.arch == "x86_64" else self.set_usb_arm()
            self.set_disks()
            self.set_cdrom()
            self.set_nvme()
            self.set_usb_storage()
            if not self.args.noshare:
                self.set_virtiofs()
            self.set_net(True)
            if self.args.ipmi:
                self.set_ipmi()
            if self.args.connect == "spice":
                self.set_spice()
            if self.args.tpm:
                self.set_tpm()
            self.set_connect()
        else:
            self.set_net()
            self.set_connect()

        if self.args.rmssh:
            self.RemoveSSH()

    def run(self):
        """Run the QEMU VM."""
        print(f"Boot: {self.vmboot:<15} mac: {self.macaddr}, ip: {self.localip}")
        completed = subprocess.CompletedProcess(0, 0)
        if not self.findProc(self.vmprocid, 0):
            _qemu_command = (
                self.sudo + ([] if self.args.debug == "debug" else [] if self.args.consol else self.G_TERM + ["--"]) + self.qemu_exe + self.params + self.opts + self.KERNEL
            )
            if self.args.debug == "cmd":
                print(" ".join(_qemu_command))
            else:
                completed = self.runshell(_qemu_command, _consol=self.args.consol)
        if self.CONNECT:
            _qemu_connect = self.CONNECT
            if self.args.debug == "cmd":
                print(" ".join(_qemu_connect))
            else:
                if completed.returncode == 0 and self.findProc(self.vmprocid):
                    if self.args.connect == "ssh":
                        self.checkConn(60)
                    self.runshell(_qemu_connect, True, _consol=self.args.consol)


def main():
    qemu = QEMU()
    qemu.setting()
    qemu.run()


import sys
import traceback

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        mylogger.error("Keyboard Interrupted")
    except Exception as e:
        mylogger.error(f"QEMU terminated abnormally. {e}")
        ex_type, ex_value, ex_traceback = sys.exc_info()
        trace_back = traceback.extract_tb(ex_traceback)
        for trace in trace_back[1:]:
            mylogger.error(f"  File {trace[0]}, line {trace[1]}, in {trace[2]}")
