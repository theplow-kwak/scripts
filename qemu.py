#!/usr/bin/env python3

import argparse
import functools
import getpass
import hashlib
import logging
import os
import shlex
import subprocess
from pathlib import Path
from time import sleep
from typing import Optional


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class QEMU:
    ssh_connect: Optional[str] = None  # Explicit type annotation
    hostip: str  # Explicit type annotation for hostip

    def __init__(self):
        self.vmimages: list[str] = []
        self.vmcdimages: list[str] = []
        self.vmnvme: list[str] = []
        self.params: list[str] = []
        self.opts: list[str] = []
        self.kernel: list[str] = []
        self.index = self.use_nvme = 0
        self.home_folder = f"/home/{os.getlogin()}"
        self.memsize = self._calculate_memory_size()
        self.sudo = ["sudo"] if os.getuid() else []

    def _calculate_memory_size(self):
        """Calculate memory size based on physical memory."""
        phy_mem = int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / (1024 * 1024 * 1000))
        return "8G" if phy_mem > 8 else "4G"

    def run_command(self, cmd: str | list[str], _async: bool = False, _consol: bool = False):
        """Run shell commands with optional async and console output."""
        if isinstance(cmd, list):
            cmd = " ".join(cmd)
        _cmd = shlex.split(cmd)
        logger.debug(f"runshell {'Async' if _async else ''}: {cmd}")
        if _consol:
            completed = subprocess.run(_cmd, text=True)
        elif _async:
            completed = subprocess.Popen(_cmd, text=True)
            sleep(1)
        else:
            completed = subprocess.run(_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if completed.stdout:
                logger.debug(f"Return code: {completed.returncode}, stdout: {completed.stdout.rstrip()}")
        return completed

    def sudo_run(self, cmd: str | list[str], _async: bool = False, _consol: bool = False):
        """Run shell commands with sudo."""
        if isinstance(cmd, str):
            cmd = shlex.split(cmd)
        cmd = self.sudo + cmd
        return self.run_command(cmd, _async, _consol)

    def set_args(self):
        parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
        parser.add_argument("--secboot", default="", action="store_const", const=".secboot", help="Using secureboot of UEFI")
        parser.add_argument("--bios", action="store_true", help="Using legacy BIOS instead of UEFI")
        parser.add_argument("--consol", action="store_true", help="Use current terminal as console I/O")
        parser.add_argument("--noshare", action="store_true", help="Disable virtiofs sharing")
        parser.add_argument("--nousb", action="store_true", help="Disable USB port")
        parser.add_argument("--qemu", "-q", action="store_true", help="Use public QEMU distribution")
        parser.add_argument("--rmssh", action="store_true", help="Remove existing SSH key")
        parser.add_argument("--tpm", action="store_true", help="Enable TPM device for Windows 11")
        parser.add_argument("--arch", "-a", default="x86_64", choices=["x86_64", "aarch64", "arm", "riscv64"], help="Target VM architecture")
        parser.add_argument("--connect", default="spice", choices=["ssh", "spice", "qemu"], help="Connection method")
        parser.add_argument("--debug", "-d", nargs="?", const="info", default="warning", choices=["cmd", "debug", "info", "warning"], help="Set logging level")
        parser.add_argument("--ipmi", choices=["internal", "external"], help="IPMI model")
        parser.add_argument("--machine", default="q35", choices=["q35", "ubuntu-q35", "pc", "ubuntu", "virt", "sifive_u"], help="Machine type")
        parser.add_argument("--net", default="bridge", choices=["user", "tap", "bridge", "none"], help="Network interface model")
        parser.add_argument("--uname", "-u", default=getpass.getuser(), help="Login user name")
        parser.add_argument("--vga", default="qxl", help="Type of VGA graphic card")
        parser.add_argument("--stick", help="Set USB storage image")
        parser.add_argument("--ip", help="Set local IP")
        parser.add_argument("images", metavar="IMAGES", nargs="*", help="Set VM images")
        parser.add_argument("--nvme", help="Set NVMe images")
        parser.add_argument("--disk", help="Set disk image")
        parser.add_argument("--vender", help="Set PC vendor")
        parser.add_argument("--kernel", dest="vmkernel", help="Set Linux Kernel image")
        parser.add_argument("--rootdev", help="Set root filesystem device")
        parser.add_argument("--initrd", help="Set initrd image")
        parser.add_argument("--pcihost", help="PCI passthrough")
        parser.add_argument("--numns", type=int, help="Set number of NVMe namespaces")
        parser.add_argument("--nssize", type=int, default=1, help="Set size of NVMe namespace")
        parser.add_argument("--num_queues", type=int, default=32, help="Set max number of queues")
        parser.add_argument("--vnum", default="", help="Set VM copies")
        parser.add_argument("--sriov", action="store_true", help="Enable SR-IOV")
        parser.add_argument("--fdp", action="store_true", help="Enable FDP")
        parser.add_argument("--hvci", action="store_true", help="Enable Hypervisor-Protected Code Integrity (HVCI)")
        parser.add_argument("--did", type=functools.partial(int, base=0), help="Set NVMe device ID")
        parser.add_argument("--mn", help="Set model name")
        parser.add_argument("--ext", help="Set extra parameters")
        parser.add_argument("--memsize", help="Set memory size")
        self.args = parser.parse_args()
        if self.args.debug == "cmd":
            logger.setLevel("INFO")
        else:
            logger.setLevel(self.args.debug.upper())
        if self.args.disk:
            _result = self.run_command(f"lsblk -d -o NAME,MODEL,SERIAL --sort NAME -n -e7")
            if _result.returncode == 0 and _result.stdout:
                _disk_param = self.args.disk.lower().split(":")
                _disk = _disk_param.pop(0)
                stdout_str: str = _result.stdout.decode() if isinstance(_result.stdout, bytes) else str(_result.stdout)
                lines: list[str] = stdout_str.splitlines()
                _images: list[str] = [line.split()[0] for line in lines if _disk in line.lower()]
                for _image in _images:
                    _part = _disk_param.pop(0) if _disk_param else ""
                    self.args.images.append(f"/dev/{_image}{_part}")
        if self.args.numns:
            self.use_nvme = 1

    def set_images(self):
        image_extensions = {".img", ".qcow2", ".vhdx"}
        for image in self.args.images:
            image_path = Path(image)
            if image.startswith("nvme"):
                self.vmnvme.append(image)
            elif image_path.exists() or image_path.is_block_device():
                self.vmimages.append(image)
            elif image_path.exists():
                _, ext = os.path.splitext(image)
                ext = ext.lower()
                if ext in image_extensions:
                    self.vmimages.append(image)
                elif ext == ".iso":
                    self.vmcdimages.append(image)
            elif "vmlinuz" in image and not self.args.vmkernel:
                self.args.vmkernel = image

        _boot_dev = self.vmimages + self.vmnvme + self.vmcdimages
        if self.args.vmkernel:
            _boot_dev.append(self.args.vmkernel)
        logger.info(f"vmimages {self.vmimages} ")
        logger.info(f"vmcdimages {self.vmcdimages} ")
        logger.info(f"vmnvme {self.vmnvme} ")
        logger.info(f"vmkernel {self.args.vmkernel} ")
        logger.info(f"boot_dev {_boot_dev} ")
        if not _boot_dev:
            raise Exception("There is no Boot device!!")
        self.bootype = "1" if self.vmnvme and self.vmnvme[0] == _boot_dev[0] else ""
        boot_0 = Path(_boot_dev[0]).resolve()
        self.vmboot = _boot_dev[0]
        self.vmname = boot_0.stem
        self.vmguid = hashlib.md5(("".join([x for x in _boot_dev])).encode()).hexdigest()
        self.vmuid = self.vmguid[0:2]
        self.vmprocid = f"{self.vmname[0:12]}_{self.vmuid}"
        self.G_TERM = [f"gnome-terminal --title={self.vmprocid}"]

    def set_qemu(self):
        """Set QEMU executable and base parameters."""
        self.qemu_exe = [f"qemu-system-{self.args.arch}"] if self.args.qemu else [f"{self.home_folder}/qemu/bin/qemu-system-{self.args.arch}"]
        self.params = [f"-name {self.vmname},process={self.vmprocid}"]

        arch_params = {
            "riscv64": ["-machine virt -bios none"],
            "arm": ["-machine virt -cpu cortex-a53 -device ramfb"],
            "aarch64": ["-machine virt,virtualization=true -cpu cortex-a72 -device ramfb"],
            "x86_64": self._set_x86_64_params(),
        }
        self.params.extend(arch_params.get(self.args.arch, []))
        cpu_count = os.cpu_count() or 2
        self.params.extend([f"-m {self.memsize}", f"-smp {cpu_count // 2},sockets=1,cores={cpu_count // 2},threads=1", "-nodefaults", "-rtc base=localtime"])

    def _set_x86_64_params(self):
        """Set parameters specific to x86_64 architecture."""
        params = [
            f"-machine type={self.args.machine},accel=kvm,usb=on -device intel-iommu",
            (
                "-cpu Skylake-Client-v3,hv_stimer,hv_synic,hv_relaxed,hv_reenlightenment,hv_spinlocks=0xfff,hv_vpindex,hv_vapic,hv_time,hv_frequencies,hv_runtime,+kvm_pv_unhalt,+vmx --enable-kvm"
                if self.args.hvci
                else "-cpu host --enable-kvm"
            ),
            "-object rng-random,id=rng0,filename=/dev/urandom -device virtio-rng-pci,rng=rng0",
        ]
        if not self.args.hvci and self.args.vender:
            params.append(f"-smbios type=1,manufacturer={self.args.vender},product='{self.args.vender} Notebook PC'")
        if self.args.connect != "ssh":
            self.opts.append(f"-vga {self.args.vga}")
        return params

    def configure_uefi(self):
        """Configure UEFI firmware for the VM."""
        if self.args.bios:
            return
        ovmf_path = f"{self.home_folder}/qemu/share/qemu"
        uefi_params = {
            "x86_64": [
                f"-drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M{self.args.secboot}.fd",
                f"-drive if=pflash,format=raw,file={self.home_folder}/vm/OVMF_VARS_4M.ms{self.bootype}.fd",
            ],
            "aarch64": [
                f"-drive if=pflash,format=raw,readonly=on,file={ovmf_path}/edk2-aarch64-code.fd",
                f"-drive if=pflash,format=raw,file={self.home_folder}/vm/edk2-arm-vars.fd",
            ],
        }
        self.params += uefi_params.get(self.args.arch, [])

    def configure_usbs(self):
        if self.args.nousb:
            return
        if self.args.arch == "x86_64":
            USB_PARAMS = ["-device qemu-xhci,id=xhci1"]
            USB_REDIR = [f"-chardev spicevmc,name=usbredir,id=usbredirchardev{i} -device usb-redir,bus=xhci1.0,chardev=usbredirchardev{i},id=usbredirdev{i}" for i in range(1, 4)]
            USB_PT = ["-device qemu-xhci,id=xhci2", "-device usb-host,bus=xhci2.0,vendorid=0x04e8,productid=0x6860"]
            self.params += USB_PARAMS + USB_REDIR + USB_PT
        else:
            self.params.append("-device qemu-xhci,id=usb3 -device usb-kbd -device usb-tablet")

    def configure_usb_storage(self):
        if not (self.args.stick and Path(self.args.stick).exists()):
            return
        self.params += [
            f"-drive file={self.args.stick},if=none,format=raw,id=stick{self.index}",
            f"-device usb-storage,drive=stick{self.index}",
        ]
        self.index += 1

    def configure_disks(self):
        if self.args.arch == "riscv64":
            scsi_params = []
        else:
            scsi_params = ["-object iothread,id=iothread0 -device virtio-scsi-pci,id=scsi0,iothread=iothread0"]
        disks_params: list[str] = []
        for _image in self.vmimages:
            match _image.split("."):
                case ["wiftest", *_]:
                    disks_params += [
                        f"-drive if=none,cache=none,file=blkdebug:blkdebug.conf:{_image},format=qcow2,id=drive-{self.index}",
                        f"-device virtio-blk-pci,drive=drive-{self.index},id=virtio-blk-pci{self.index}",
                    ]
                case [*_, "qcow2" | "QCOW2"]:
                    disks_params += [f"-drive file={_image},cache=writeback,id=drive-{self.index}"]
                case [*_, "vhdx" | "VHDX"]:
                    disks_params += [
                        f"-drive file={_image},if=none,id=drive-{self.index}",
                        f"-device nvme,drive=drive-{self.index},serial=nvme-{self.index}",
                    ]
                case _:
                    # _disk_type = 'scsi-hd' if Path(_image).is_block_device and 'nvme' not in _image else 'scsi-hd'
                    disks_params += [
                        f"-drive file={_image},if=none,format=raw,discard=unmap,aio=native,cache=none,id=drive-{self.index}",
                        f"-device scsi-hd,scsi-id={self.index},drive=drive-{self.index},id=scsi0-{self.index}",
                    ]
            self.index += 1
        if disks_params:
            self.params += scsi_params + disks_params

    def configure_cdrom(self):
        """Configure CD-ROM drives for the VM."""
        _IF = "ide" if self.args.arch == "x86_64" else "none"
        for _image in self.vmcdimages:
            self.params.append(f"-drive file={_image},media=cdrom,readonly=on,if={_IF},index={self.index},id=cdrom{self.index}")
            if self.args.arch != "x86_64":
                self.params.append(f"-device usb-storage,drive=cdrom{self.index}")
            self.index += 1

    def check_file(self, filename: str, size: int) -> int:
        if not Path(filename).exists():
            self.run_command(f"qemu-img create -f qcow2 {filename} {size}G")
        if self.run_command(f"lsof -w {filename}").returncode == 0:
            return 0
        return 1

    def configure_nvme(self):
        """Set NVMe devices."""
        if not self.vmnvme:
            return

        def add_nvme_drive(_NVME: str, ns_backend: str, _ctrl_id: int, _nsid: Optional[int] = None, fdp_nsid: str = "") -> list[str]:
            """Helper to add NVMe drive and namespace."""
            NVME: list[str] = []
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

        nvme_params = [
            "-device ioh3420,bus=pcie.0,id=root1.0,slot=1",
            "-device x3130-upstream,bus=root1.0,id=upstream1.0",
        ]

        _ctrl_id = 1
        for item in self.vmnvme:
            parts = item.split(":")
            _NVME = parts[0]
            _num_ns = int(parts[1]) if len(parts) > 1 else self.args.numns or 1
            ns_backend = f"{_NVME}n1.qcow2"

            if self.args.qemu:
                nvme_params += add_nvme_drive(_NVME, ns_backend, _ctrl_id)
            elif self.args.sriov:
                nvme_params += [
                    f"-device xio3130-downstream,bus=upstream1.0,id=downstream1.{_ctrl_id},chassis={_ctrl_id},multifunction=on",
                    f"-device nvme-subsys,id=nvme-subsys-{_ctrl_id},nqn=subsys{_ctrl_id}",
                    f"-device nvme,serial=beef{_NVME},ocp=on,id={_NVME},subsys=nvme-subsys-{_ctrl_id},bus=downstream1.{_ctrl_id},max_ioqpairs=512,msix_qsize=512,sriov_max_vfs={_num_ns},sriov_vq_flexible=508,sriov_vi_flexible=510",
                ]
                nvme_params += add_nvme_drive(_NVME, ns_backend, _ctrl_id, _nsid=1, fdp_nsid=",shared=false,detached=true")
                _ctrl_id += 1
            else:
                _did = f",did={self.args.did}" if self.args.did else ""
                _mn = f",mn={self.args.mn}" if self.args.mn else ""
                _fdp = ",fdp=on,fdp.runs=96M,fdp.nrg=1,fdp.nruh=16" if self.args.fdp else ""
                _fdp_nsid = ",fdp.ruhs=1-15,mcl=2048,mssrl=256,msrc=7" if self.args.fdp else ""
                nvme_params += [
                    f"-device xio3130-downstream,bus=upstream1.0,id=downstream1.{_ctrl_id},chassis={_ctrl_id},multifunction=on",
                    f"-device nvme-subsys,id=nvme-subsys-{_ctrl_id},nqn=subsys{_ctrl_id}{_fdp}",
                    f"-device nvme,serial=beef{_NVME},ocp=on,id={_NVME},subsys=nvme-subsys-{_ctrl_id},bus=downstream1.{_ctrl_id},max_ioqpairs={self.args.num_queues}{_did}{_mn}",
                ]
                for _nsid in range(1, _num_ns + 1):
                    ns_backend = ns_backend.replace("n1", f"n{_nsid}")
                    nvme_params += add_nvme_drive(_NVME, ns_backend, _ctrl_id, _nsid=_nsid, fdp_nsid=_fdp_nsid if _nsid == 1 else "")
                _ctrl_id += 1

        if Path("./events").exists():
            nvme_params.append("--trace events=./events")

        self.params.extend(nvme_params)

    def configure_virtiofs(self):
        if self.args.noshare:
            return
        virtiofsd_path = f"{self.home_folder}/qemu/libexec/virtiofsd" if Path(f"{self.home_folder}/qemu/libexec/virtiofsd").exists() else "/usr/libexec/virtiofsd"
        virtiofsd_cmd = (
            self.G_TERM
            + ["--geometry=80x24+5+5 --"]
            + [
                (
                    f"{virtiofsd_path} --socket-path=/tmp/virtiofs_{self.vmuid}.sock " f"-o source={self.home_folder}"
                    if "libexec" in virtiofsd_path
                    else f"--shared-dir={self.home_folder}"
                )
            ]
        )
        if self.args.debug == "cmd":
            print(" ".join(virtiofsd_cmd))
        else:
            self.sudo_run(virtiofsd_cmd)
            while not Path(f"/tmp/virtiofs_{self.vmuid}.sock").exists():
                logger.debug(f"Waiting for /tmp/virtiofs_{self.vmuid}.sock")
                sleep(1)

        self.params += [
            f"-chardev socket,id=char{self.vmuid},path=/tmp/virtiofs_{self.vmuid}.sock",
            f"-device vhost-user-fs-pci,chardev=char{self.vmuid},tag=hostfs",
            f"-object memory-backend-memfd,id=mem,size={self.memsize},share=on -numa node,memdev=mem",
        ]

    def configure_ipmi(self):
        if self.args.ipmi:
            ipmi_options = {
                "internal": ["-device ipmi-bmc-sim,id=bmc0"],
                "external": ["-chardev socket,id=ipmi0,host=localhost,port=9002,reconnect=10", "-device ipmi-bmc-extern,chardev=ipmi0,id=bmc1", "-device isa-ipmi-kcs,bmc=bmc1"],
            }
            self.params += ipmi_options.get(self.args.ipmi, [])

    def configure_spice(self):
        if self.args.connect != "spice":
            return
        SPICE_PARAMS = [
            f"-spice port={self.spiceport},disable-ticketing=on",
            "-audiodev spice,id=audio0 -device intel-hda -device hda-duplex,audiodev=audio0,mixer=off",
        ]
        SPICE_AGENT = [
            "-chardev spicevmc,id=vdagent,name=vdagent",
            "-device virtio-serial",
            "-device virtserialport,chardev=vdagent,name=com.redhat.spice.0",
        ]
        _GUEST_AGENT = [
            "-chardev socket,path=/tmp/qga.sock,server,nowait,id=qga0,name=qga0",
            "-device virtio-serial",
            "-device virtserialport,chardev=qga0,name=org.qemu.guest_agent.0",
        ]
        _SHARE0 = [f"-virtfs local,id=fsdev0,path={self.home_folder},security_model=passthrough,writeout=writeout,mount_tag=host"]
        self.params += SPICE_PARAMS + SPICE_AGENT

    def configure_tpm(self):
        """Configure TPM device for the VM."""
        if self.args.tpm:
            cancel_path = Path(f"/tmp/foo-cancel-{self.vmuid}")
            cancel_path.touch(exist_ok=True)
            self.params += [f"-tpmdev passthrough,id=tpm0,path=/dev/tpm0,cancel-path={cancel_path}", "-device tpm-tis,tpmdev=tpm0"]

    def RemoveSSH(self):
        """Remove existing SSH keys for the VM."""
        ssh_file = Path(f"/tmp/{self.vmprocid}_SSH")
        ssh_file.unlink(missing_ok=True)
        ssh_key_cmd = f'ssh-keygen -R "[{self.hostip}]:{self.ssh_port}"' if self.args.net == "user" else f'ssh-keygen -R "{self.localip}"'
        self.run_command(ssh_key_cmd)

    def configure_net(self, _set: bool = False):
        """Configure network settings for the VM."""
        # Set SSH port from file or default
        ssh_port_file = Path(f"/tmp/{self.vmprocid}_SSH")
        try:
            self.ssh_port = int(ssh_port_file.read_text())
        except Exception:
            self.ssh_port = 5900
        self.spiceport = self.ssh_port + 1
        self.macaddr = f"52:54:00:{self.vmguid[:2]}:{self.vmguid[2:4]}:{self.vmguid[4:6]}"

        # Get host IP
        _result = self.run_command("ip r g 1.0.0.0")
        stdout = _result.stdout.decode() if isinstance(_result.stdout, bytes) else str(_result.stdout or "")
        self.hostip = stdout.split()[6] if _result.returncode == 0 and len(stdout.split()) > 6 else "localhost"
        logger.info(f"hostip: {self.hostip}")

        # Get local IP from DHCP leases
        _result = self.run_command(f"virsh --quiet net-dhcp-leases default --mac {self.macaddr}")
        dhcp_stdout = _result.stdout.decode() if isinstance(_result.stdout, bytes) else str(_result.stdout or "")
        dhcp_lines = dhcp_stdout.rstrip().split("\n") if dhcp_stdout.strip() else []
        dhcp_chk = sorted(dhcp_lines)[-1] if dhcp_lines else ""
        self.localip = self.args.ip or (dhcp_chk.split()[4].split("/")[0] if dhcp_chk and len(dhcp_chk.split()) > 4 else None)
        logger.info(f"localip: {self.localip}")

        if _set:
            # Ensure ports are available
            while not self.run_command(f"lsof -w -i :{self.spiceport}").returncode or not self.run_command(f"lsof -w -i :{self.ssh_port}").returncode:
                self.ssh_port += 2
                self.spiceport = self.ssh_port + 1

            # Configure network based on the selected mode
            net_modes = {
                "user": f"-nic user,model=virtio-net-pci,mac={self.macaddr},smb={self.home_folder},hostfwd=tcp::{self.ssh_port}-:22",
                "tap": f"-nic tap,model=virtio-net-pci,mac={self.macaddr},script={self.home_folder}/projects/scripts/qemu-ifup",
                "bridge": f"-nic bridge,br=virbr0,model=virtio-net-pci,mac={self.macaddr}",
                "none": "",
            }
            net_param = net_modes.get(self.args.net, "")
            if net_param:
                self.params.append(net_param)

            # Save SSH port to a file
            try:
                ssh_port_file.write_text(str(self.ssh_port))
            except Exception as e:
                logger.error(f"Failed to write SSH port: {e}")

    def configure_connect(self):
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
        self.opts += ["-nographic -serial mon:stdio"]
        hostip = self.hostip if self.hostip else "localhost"
        self.ssh_connect = f"{hostip} -p {self.ssh_port}" if self.args.net == "user" else self.localip
        self.chkport = self.ssh_port
        self.connect = ([] if self.args.consol else self.G_TERM + ["--"]) + [f"ssh {self.args.uname}@{self.ssh_connect}"]

    def _set_spice_connect(self):
        """Set SPICE connection settings."""
        self.opts += ["-monitor stdio"]
        self.chkport = self.spiceport
        self.connect = [f"remote-viewer -t {self.vmprocid} spice://{self.hostip}:{self.spiceport} --spice-usbredir-auto-redirect-filter=0x03,-1,-1,-1,0|-1,-1,-1,-1,1"]

    def _set_qemu_connect(self):
        """Set QEMU connection settings."""
        self.opts += ["-monitor stdio"]
        self.chkport = self.spiceport
        self.connect = None

    def findProc(self, _PROCID: str, _timeout: int = 10) -> bool:
        """Wait for a process to start."""
        while self.run_command(f"ps -C {_PROCID}").returncode:
            logger.debug(f"findProc timeout {_timeout}")
            _timeout -= 1
            if _timeout < 0:
                return False
            sleep(1)
        logger.debug("findProc return 1")
        return True

    def checkConn(self, timeout: int = 10):
        """Check if the SSH connection is available."""
        if not self.ssh_connect:
            return 0
        while self.run_command(f"ping -c 1 {self.ssh_connect}").returncode:
            timeout -= 1
            if timeout < 0:
                return True
            sleep(1)
        return False

    def configure_kernel(self):
        """Configure the kernel and its parameters."""
        if not self.args.vmkernel:
            return
        self.kernel.append(f"-kernel {self.args.vmkernel}")
        if self.args.arch != "riscv64":
            initrd = self.args.initrd or self.args.vmkernel.replace("vmlinuz", "initrd.img")
            if Path(initrd).exists():
                self.kernel += ["-initrd", initrd]
            root_dev = self.args.rootdev or ("sda" if ".img" in self.vmimages[0] else "sda1")
            console = "console=ttyS0" if self.args.connect == "ssh" else "vga=0x300"
            self.kernel.append(f'-append "root=/dev/{root_dev} {console}"')

    def set_pcipass(self):
        """PCI Passthrough: Unbind device from current driver and bind to vfio-pci, then add QEMU param."""
        if not self.args.pcihost:
            return

        pcihost = self.args.pcihost
        # Get current driver
        try:
            lspci_out = subprocess.check_output(["lspci", "-k", "-s", pcihost], text=True)
            driver_line = next((line for line in lspci_out.splitlines() if "Kernel driver in use:" in line), None)
            if not driver_line:
                logger.error(f"Could not find kernel driver for {pcihost}")
                return
            driver = driver_line.split(":")[-1].strip()
        except Exception as e:
            logger.error(f"Failed to get kernel driver for {pcihost}: {e}")
            return

        # Unbind from current driver
        try:
            with open(f"/sys/bus/pci/drivers/{driver}/unbind", "w") as f:
                f.write(pcihost)
        except Exception as e:
            logger.error(f"Failed to unbind {pcihost} from {driver}: {e}")
            return

        # Bind to vfio-pci
        try:
            # Get vendor and device id
            lspci_n_out = subprocess.check_output(["lspci", "-ns", pcihost], text=True)
            devid = lspci_n_out.split()[2]  # Format: "8086:10ed"
            with open("/sys/bus/pci/drivers/vfio-pci/new_id", "w") as f:
                f.write(devid)
        except Exception as e:
            logger.error(f"Failed to bind {pcihost} to vfio-pci: {e}")
            return

        # Add QEMU param
        self.params.append(f"-device vfio-pci,host={pcihost},multifunction=on")

    def setting(self):
        self.set_args()
        self.set_images()
        if self.findProc(self.vmprocid, 0):
            self.configure_net()
            self.configure_connect()
        else:
            self.set_qemu()
            self.configure_uefi()
            self.configure_kernel()
            self.configure_disks()
            self.configure_cdrom()
            self.configure_nvme()
            self.configure_net(True)
            self.configure_spice()
            self.configure_virtiofs()
            self.configure_tpm()
            self.configure_usbs()
            self.configure_usb_storage()
            self.configure_ipmi()
            # self.set_pcipass()
            self.configure_connect()

        if self.args.rmssh:
            self.RemoveSSH()

    def run(self):
        """Run the QEMU VM."""
        print(f"Boot: {self.vmboot:<15} mac: {self.macaddr}, ip: {self.localip}")
        completed: subprocess.CompletedProcess[str] | subprocess.Popen[str] = subprocess.CompletedProcess(args=[], returncode=0)
        if not self.findProc(self.vmprocid, 0):
            qemu_command = ([] if self.args.debug == "debug" else [] if self.args.consol else self.G_TERM + ["--"]) + self.qemu_exe + self.params + self.opts + self.kernel
            if self.args.debug == "cmd":
                print(" ".join(qemu_command))
            else:
                completed = self.sudo_run(qemu_command, _consol=self.args.consol)
        if self.connect:
            qemu_connect = self.connect
            if self.args.debug == "cmd":
                print(" ".join(qemu_connect))
            else:
                if completed.returncode == 0 and self.findProc(self.vmprocid):
                    if self.args.connect == "ssh":
                        self.checkConn(60)
                    self.run_command(qemu_connect, True, _consol=self.args.consol)


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
        logger.error("Keyboard Interrupted")
    except Exception as e:
        logger.error(f"QEMU terminated abnormally. {e}")
        ex_type, ex_value, ex_traceback = sys.exc_info()
        trace_back = traceback.extract_tb(ex_traceback)
        for trace in trace_back[1:]:
            logger.error(f"  File {trace[0]}, line {trace[1]}, in {trace[2]}")
