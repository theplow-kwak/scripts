#!/usr/bin/env python3
"""Lightweight QEMU VM launcher with convenient CLI options.

The original implementation contained many repetitive patterns and
imperative code.  This refactor keeps the same behaviour but is
shorter, uses more Python idioms, and breaks complex routines into
smaller helpers.
"""

import argparse
import functools
import getpass
import hashlib
import logging
import os
import re
import shlex
import subprocess
from pathlib import Path
from time import sleep
from typing import List, Optional, Union

# ---------------------------------------------------------------------------
# logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def sh(cmd: Union[str, List[str]]) -> List[str]:
    """Split a command string into a list for subprocess."""
    return shlex.split(cmd) if isinstance(cmd, str) else list(cmd)


# ---------------------------------------------------------------------------
# QEMU class
# ---------------------------------------------------------------------------


class QEMU:
    IMAGE_EXTS = {".img", ".qcow2", ".vhdx"}

    def __init__(self) -> None:
        self.args: argparse.Namespace
        self.vmimages: List[str] = []
        self.vmcdimages: List[str] = []
        self.vmnvme: List[str] = []
        self.params: List[str] = []
        self.opts: List[str] = []
        self.kernel: List[str] = []
        self.vmprocid = ""
        self.index = 0
        self._memsize: Optional[str] = None
        self.sudo = ["sudo"] if os.getuid() else []

    # properties -------------------------------------------------------------

    @property
    def home_folder(self) -> str:
        return f"/home/{os.getlogin()}"

    @property
    def memsize(self) -> str:
        if self._memsize is None:
            pages = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
            gb = int(pages / (1024**3) / 2)
            self._memsize = f"{min(gb, 16)}G"
        return self._memsize

    # command execution -----------------------------------------------------

    def run_command(
        self,
        cmd: Union[str, List[str]],
        *,
        sudo: bool = False,
        async_: bool = False,
        consol: bool = False,
    ) -> Union[subprocess.CompletedProcess[str], subprocess.Popen[str]]:
        """Run a shell command with optional sudo/async/console output."""
        cmd_list = (self.sudo + sh(cmd)) if sudo and os.getuid() else sh(cmd)
        logger.debug("exec: %s", " ".join(cmd_list))
        if consol:
            return subprocess.run(cmd_list, text=True)
        if async_:
            proc = subprocess.Popen(cmd_list, text=True)
            sleep(1)
            return proc
        return subprocess.run(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    # argument and image parsing -------------------------------------------

    def set_args(self) -> None:
        parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
        parser.add_argument("--secboot", default="", action="store_const", const=".secboot", help="UEFI secure boot")
        parser.add_argument("--bios", action="store_true", help="Use BIOS instead of UEFI")
        parser.add_argument("--consol", action="store_true", help="Use current tty for VM")
        parser.add_argument("--noshare", action="store_true", help="Disable virtiofs share")
        parser.add_argument("--nousb", action="store_true", help="Disable USB")
        parser.add_argument("--qemu", "-q", action="store_true", help="Use system qemu binaries")
        parser.add_argument("--rmssh", action="store_true", help="Remove VM SSH key")
        parser.add_argument("--tpm", action="store_true", help="Enable TPM (Win11)")
        parser.add_argument("--arch", "-a", default="x86_64", choices=["x86_64", "aarch64", "arm", "riscv64"], help="VM architecture")
        parser.add_argument("--connect", default="spice", choices=["ssh", "spice", "qemu"], help="How to connect")
        parser.add_argument("--debug", "-d", nargs="?", const="info", default="warning", choices=["cmd", "debug", "info", "warning"], help="Logging level")
        parser.add_argument("--ipmi", choices=["internal", "external"], help="IPMI model")
        parser.add_argument("--machine", default="q35", choices=["q35", "ubuntu-q35", "pc", "ubuntu", "virt", "sifive_u"], help="Machine type")
        parser.add_argument("--net", default="bridge", choices=["user", "tap", "bridge", "none"], help="Network mode")
        parser.add_argument("--uname", "-u", default=getpass.getuser(), help="Remote username")
        parser.add_argument("--vga", default="qxl", help="VGA card")
        parser.add_argument("--stick", help="USB stick image")
        parser.add_argument("--ip", help="Fixed guest IP")
        parser.add_argument("images", metavar="IMAGES", nargs="*", help="VM disk/iso images")
        parser.add_argument("--nvme", nargs="+", action="extend", help="NVMe backend(s)")
        parser.add_argument("--disk", nargs="+", action="extend", help="Additional disks (lsblk)\nexample: sda:1")
        parser.add_argument("--vender", help="SMBIOS vendor string")
        parser.add_argument("--kernel", dest="vmkernel", help="Kernel image")
        parser.add_argument("--rootdev", help="Root device (e.g. sda1)")
        parser.add_argument("--initrd", help="initrd image")
        parser.add_argument("--pcihost", help="PCI passthrough PCI address")
        parser.add_argument("--numns", type=int, help="NVMe namespace count")
        parser.add_argument("--nssize", type=int, default=40, help="NVMe namespace size (GB)")
        parser.add_argument("--num_queues", type=int, default=32, help="NVMe queue count")
        parser.add_argument("--vnum", default="", help="VM copy suffix")
        parser.add_argument("--sriov", action="store_true", help="Enable SR-IOV")
        parser.add_argument("--fdp", action="store_true", help="Enable FDP extensions")
        parser.add_argument("--hvci", action="store_true", help="Enable HVCI CPU features")
        parser.add_argument("--did", type=functools.partial(int, base=0), help="NVMe device ID (hex)")
        parser.add_argument("--mn", help="NVMe model name")
        parser.add_argument("--ext", help="Extra parameters")
        parser.add_argument("--memsize", help="Override memory size")
        parser.add_argument("--cpus", type=int, default=0, help="vCPU count")
        parser.add_argument("--blkdbg", action="store_true", help="Enable block debug")
        self.args = parser.parse_args()

        # logging and derived arguments
        logger.setLevel("INFO" if self.args.debug == "cmd" else self.args.debug.upper())
        if self.args.disk:
            self.parse_disks()
        if self.args.nvme:
            self.vmnvme.extend(self.args.nvme)
        if self.args.memsize:
            self._memsize = self.args.memsize

    def parse_disks(self) -> None:
        """Translate --disk arguments into block device paths using lsblk."""
        out = self.run_command("lsblk -d -o NAME,MODEL,SERIAL --sort NAME -n -e7")
        if out.returncode != 0 or not out.stdout:
            return
        lines = out.stdout.splitlines()
        for token in self.args.disk:
            parts = token.lower().split(":")
            name = parts.pop(0)
            matches = [ln.split()[0] for ln in lines if name in ln.lower()]
            for dev in matches:
                part = parts.pop(0) if parts else ""
                self.args.images.append(f"/dev/{dev}{part}")

    def set_images(self) -> None:
        """Inspect provided image strings and classify them."""
        for image in self.args.images:
            p = Path(image)
            if re.match(r"^(nvme\d+):?(\d+)?$", image):
                self.vmnvme.append(image)
                continue
            if p.exists():
                if p.is_block_device() or p.suffix.lower() in self.IMAGE_EXTS:
                    self.vmimages.append(image)
                elif p.suffix.lower() == ".iso":
                    self.vmcdimages.append(image)
            elif "vmlinuz" in image and not self.args.vmkernel:
                self.args.vmkernel = image

        boot_devs = self.vmimages + self.vmnvme + self.vmcdimages
        if self.args.vmkernel:
            boot_devs.append(self.args.vmkernel)
        if not boot_devs:
            raise RuntimeError("There is no boot device!")
        self.vmboot = boot_devs[0]
        self.vmname = Path(self.vmboot).stem
        guid = hashlib.md5("".join(boot_devs).encode()).hexdigest()
        self.vmguid, self.vmuid = guid, guid[:2]
        self.vmprocid = f"{self.vmname[:12]}_{self.vmuid}"
        self.bootype = "1" if self.vmnvme and self.vmnvme[0] == self.vmboot else ""
        self.G_TERM = [f"gnome-terminal --title={self.vmprocid}"]
        logger.info("vmimages %s vmcd %s vmnvme %s vmkernel %s", self.vmimages, self.vmcdimages, self.vmnvme, self.args.vmkernel)

    # qemu initialization --------------------------------------------------

    def set_qemu(self) -> None:
        exe = f"qemu-system-{self.args.arch}"
        self.qemu_exe = [exe] if self.args.qemu else [f"{self.home_folder}/qemu/bin/{exe}"]
        self.params = [f"-name {self.vmname},process={self.vmprocid}"]

        arch_switch = {
            "riscv64": ["-machine virt -bios none"],
            "arm": ["-machine virt -cpu cortex-a53 -device ramfb"],
            "aarch64": ["-machine virt,highmem=on,virtualization=true -cpu cortex-a72 -device ramfb"],
            "x86_64": self._set_x86_64_params(),
        }
        self.params += arch_switch.get(self.args.arch, [])
        cpu = self.args.cpus or int((os.cpu_count() or 2) / 2)
        self.params += [f"-m {self.memsize}", f"-smp {cpu},sockets=1,cores={cpu},threads=1", "-nodefaults", "-rtc base=localtime"]

    def _set_x86_64_params(self) -> List[str]:
        base = [
            f"-machine type={self.args.machine},accel=kvm,usb=on -device intel-iommu",
            "-device virtio-rng-pci,rng=rng0" if self.args.hvci else "-object rng-random,id=rng0,filename=/dev/urandom -device virtio-rng-pci,rng=rng0",
            (
                "-cpu Skylake-Client-v3,hv_stimer,hv_synic,hv_relaxed,hv_reenlightenment,hv_spinlocks=0xfff,hv_vpindex,hv_vapic,hv_time,hv_frequencies,hv_runtime,+kvm_pv_unhalt,+vmx --enable-kvm"
                if self.args.hvci
                else "-cpu host,arch_capabilities=off --enable-kvm"
            ),
        ]
        if not self.args.hvci and self.args.vender:
            base.append(f"-smbios type=1,manufacturer={self.args.vender},product='{self.args.vender} Notebook PC'")
        if self.args.connect != "ssh" and self.args.arch != "aarch64":
            self.opts.append(f"-vga {self.args.vga}")
        return base

    def configure_uefi(self) -> None:
        if self.args.bios:
            return
        varfile = Path(f"./OVMF_VARS_4M.ms{self.bootype}.fd")
        if not varfile.exists():
            try:
                self.run_command(["cp", "/usr/share/OVMF/OVMF_VARS_4M.ms.fd", str(varfile)])
            except Exception as e:
                logger.error("copy failed: %s", e)
                raise
        common = []
        if self.args.arch == "x86_64":
            common = [
                f"-drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M{self.args.secboot}.fd",
                f"-drive if=pflash,format=raw,file={varfile.absolute()}",
            ]
        elif self.args.arch == "aarch64":
            common = [
                f"-drive if=pflash,format=raw,readonly=on,file={self.home_folder}/qemu/share/qemu/edk2-aarch64-code.fd",
                f"-drive if=pflash,format=raw,file={self.home_folder}/vm/edk2-arm-vars.fd",
            ]
        self.params += common

    # peripheral configuration ------------------------------------------------

    def configure_usbs(self) -> None:
        if self.args.nousb:
            return
        if self.args.arch == "x86_64":
            self.params += ["-device qemu-xhci,id=xhci1"]
            self.params += [
                f"-chardev spicevmc,name=usbredir,id=usbredirchardev{i} -device usb-redir,bus=xhci1.0,chardev=usbredirchardev{i},id=usbredirdev{i}" for i in range(1, 4)
            ]
            self.params += ["-device qemu-xhci,id=xhci2", "-device usb-host,bus=xhci2.0,vendorid=0x04e8,productid=0x6860"]
        else:
            self.params += ["-device qemu-xhci,id=usb3 -device usb-kbd -device usb-tablet"]

    def configure_usb_storage(self) -> None:
        if self.args.stick and Path(self.args.stick).exists():
            self.params += [
                f"-drive file={self.args.stick},if=none,format=raw,id=stick{self.index}",
                f"-device usb-storage,drive=stick{self.index}",
            ]
            self.index += 1

    def configure_disks(self) -> None:
        scsi = (
            []
            if self.args.arch == "riscv64"
            else [
                "-object iothread,id=iothread0",
                "-device virtio-scsi-pci,id=scsi0,iothread=iothread0",
            ]
        )
        for idx, img in enumerate(self.vmimages):
            ext = Path(img).suffix.lower()
            if img.startswith("wiftest"):
                self.params += [
                    f"-drive if=none,cache=none,file=blkdebug:blkdebug.conf:{img},format=qcow2,id=drive-{idx}",
                    f"-device virtio-blk-pci,drive=drive-{idx},id=virtio-blk-pci{idx}",
                ]
            elif ext == ".qcow2":
                self.params.append(f"-drive file={img},cache=writeback,id=drive-{idx}")
            elif ext == ".vhdx":
                self.params += [
                    f"-drive file={img},if=none,id=drive-{idx}",
                    f"-device nvme,drive=drive-{idx},serial=nvme-{idx}",
                ]
            else:
                self.params += [
                    f"-drive file={img},if=none,format=raw,discard=unmap,aio=native,cache=none,id=drive-{idx}",
                    f"-device scsi-hd,scsi-id={idx},drive=drive-{idx},id=scsi0-{idx}",
                ]
        if scsi:
            self.params = scsi + self.params

    def configure_cdrom(self) -> None:
        iface = "ide" if self.args.arch == "x86_64" else "none"
        for idx, iso in enumerate(self.vmcdimages):
            self.params.append(f"-drive file={iso},media=cdrom,readonly=on,if={iface},index={idx},id=cdrom{idx}")
            if self.args.arch != "x86_64":
                self.params += ["-device qemu-xhci,id=xhci", f"-device usb-storage,drive=cdrom{idx},bus=xhci.0"]

    def check_file(self, filename: str, size: int) -> bool:
        if not Path(filename).exists():
            self.run_command(f"qemu-img create -f qcow2 {filename} {size}G")
        return self.run_command(f"lsof -w {filename}").returncode != 0

    def configure_nvme(self) -> None:
        if not self.vmnvme:
            return
        params = [
            "-device ioh3420,bus=pcie.0,id=root1.0,slot=1",
            "-device x3130-upstream,bus=root1.0,id=upstream1.0",
        ]
        ctrl = 0
        for nvme in self.vmnvme:
            m = re.match(r"^(?P<nvme_id>[^:]+):?(?P<num_ns>\d+)?$", nvme)
            if not m:
                continue
            nvme_id = m.group("nvme_id")
            num_ns = int(m.group("num_ns") or 1)
            fname, ext = nvme_id.split(".", 1) if "." in nvme_id else (nvme_id, "")
            is_phys = nvme.startswith("nvme")

            # build dynamic options
            did = f",did={self.args.did}" if self.args.did else ""
            mn = f",mn={self.args.mn}" if self.args.mn else ""
            ocp = "" if self.args.qemu else ",ocp=on"
            blkdbg = "blkdebug:blkdebug.conf:" if self.args.blkdbg and Path("blkdebug.conf").exists() else ""

            if self.args.sriov:
                sriov_max_vfs = 64
                sriov_vq = sriov_max_vfs * 2
                sriov_vi = sriov_max_vfs
                max_ioqpairs = sriov_vq + 2
                msix = sriov_vi + 1
                sriov_params = f",msix_qsize={msix},sriov_max_vfs={sriov_max_vfs},sriov_vq_flexible={sriov_vq},sriov_vi_flexible={sriov_vi}"
                sriov_nsid = ",shared=false,detached=true"
            else:
                max_ioqpairs = self.args.num_queues
                sriov_params = sriov_nsid = ""

            params += [
                f"-device xio3130-downstream,bus=upstream1.0,id=downstream1.{ctrl},chassis={ctrl},multifunction=on",
                f"-device nvme-subsys,id=nvme-subsys-{ctrl},nqn=subsys{ctrl}",
                f"-device nvme,serial=beefnvme{ctrl},id=nvme{ctrl},subsys=nvme-subsys-{ctrl},bus=downstream1.{ctrl},max_ioqpairs={max_ioqpairs}{sriov_params}{did}{mn}{ocp}",
            ]

            for ns in range(1, num_ns + 1):
                tail = "" if not ext or (not is_phys and ns == 1) else f"n{ns}"
                backend = f"{fname}{tail}{'.' if ext else ''}{ext}"
                if self.check_file(backend, self.args.nssize):
                    params += [
                        f"-drive file={blkdbg}{backend},id=nvme{ctrl}n{ns},if=none,cache=none",
                        f"-device nvme-ns,drive=nvme{ctrl}n{ns},bus=nvme{ctrl},nsid={ns}{sriov_nsid if ns == 1 else ''}",
                    ]
            ctrl += 1
        if Path("./events").exists():
            params.append("--trace events=./events")
        self.params += params

    def configure_virtiofs(self) -> None:
        if self.args.noshare:
            return
        virtiofsd = Path(f"{self.home_folder}/qemu/libexec/virtiofsd")
        virtiofsd = str(virtiofsd) if virtiofsd.exists() else "/usr/libexec/virtiofsd"
        sock = f"/tmp/virtiofs_{self.vmuid}.sock"
        cmd = self.G_TERM + ["--", f"{virtiofsd} --socket-path={sock} -o source={self.home_folder}" if "libexec" in virtiofsd else f"--shared-dir={self.home_folder}"]
        if self.args.debug == "cmd":
            print(" ".join(cmd))
        else:
            self.run_command(cmd, sudo=True)
            while not Path(sock).exists():
                logger.debug("waiting for %s", sock)
                sleep(1)
        self.params += [
            f"-chardev socket,id=char{self.vmuid},path={sock}",
            f"-device vhost-user-fs-pci,chardev=char{self.vmuid},tag=hostfs",
            f"-object memory-backend-memfd,id=mem,size={self.memsize},share=on -numa node,memdev=mem",
        ]

    def configure_ipmi(self) -> None:
        if not self.args.ipmi:
            return
        mapping = {
            "internal": ["-device ipmi-bmc-sim,id=bmc0"],
            "external": [
                "-chardev socket,id=ipmi0,host=localhost,port=9002,reconnect=10",
                "-device ipmi-bmc-extern,chardev=ipmi0,id=bmc1",
                "-device isa-ipmi-kcs,bmc=bmc1",
            ],
        }
        self.params += mapping.get(self.args.ipmi, [])

    def configure_spice(self) -> None:
        if self.args.connect != "spice":
            return
        self.params += [
            f"-spice port={self.spiceport},disable-ticketing=on",
            "-audiodev spice,id=audio0 -device intel-hda -device hda-duplex,audiodev=audio0,mixer=off",
            "-chardev spicevmc,id=vdagent,name=vdagent",
            "-device virtio-serial",
            "-device virtserialport,chardev=vdagent,name=com.redhat.spice.0",
        ]

    def configure_tpm(self) -> None:
        if self.args.tpm:
            cancel = Path(f"/tmp/foo-cancel-{self.vmuid}")
            cancel.touch(exist_ok=True)
            self.params += [
                f"-tpmdev passthrough,id=tpm0,path=/dev/tpm0,cancel-path={cancel}",
                "-device tpm-tis,tpmdev=tpm0",
            ]

    def RemoveSSH(self) -> None:
        ssh_file = Path(f"/tmp/{self.vmprocid}_SSH")
        ssh_file.unlink(missing_ok=True)
        cmd = f'ssh-keygen -R "[{self.hostip}]:{self.ssh_port}"' if self.args.net == "user" else f'ssh-keygen -R "{self.localip}"'
        self.run_command(cmd)

    def configure_net(self, set_ports: bool = False) -> None:
        """Compute networking parameters and optionally reserve ports."""
        fh = Path(f"/tmp/{self.vmprocid}_SSH")
        try:
            self.ssh_port = int(fh.read_text())
        except Exception:
            self.ssh_port = 5900
        self.spiceport = self.ssh_port + 1
        self.macaddr = f"52:54:00:{self.vmguid[:2]}:{self.vmguid[2:4]}:{self.vmguid[4:6]}"

        out = self.run_command("ip r g 1.0.0.0")
        text = out.stdout or ""
        self.hostip = text.split()[6] if out.returncode == 0 and len(text.split()) > 6 else "localhost"

        # dhcp: virsh can return multiple lines; we pick the last
        leases = self.run_command(f"virsh --quiet net-dhcp-leases default --mac {self.macaddr}").stdout or ""
        lines = leases.strip().splitlines()
        last = sorted(lines)[-1] if lines else ""
        self.localip = self.args.ip or (last.split()[4].split("/")[0] if last and len(last.split()) > 4 else None)

        if not set_ports:
            return

        # pick unused ports
        while not self.run_command(f"lsof -w -i :{self.spiceport}").returncode or not self.run_command(f"lsof -w -i :{self.ssh_port}").returncode:
            self.ssh_port += 2
            self.spiceport = self.ssh_port + 1

        net_map = {
            "user": f"-nic user,model=virtio-net-pci,mac={self.macaddr},smb={self.home_folder},hostfwd=tcp::{self.ssh_port}-:22",
            "tap": f"-nic tap,model=virtio-net-pci,mac={self.macaddr},script={self.home_folder}/projects/scripts/qemu-ifup",
            "bridge": f"-nic bridge,br=virbr0,model=virtio-net-pci,mac={self.macaddr}",
            "none": "",
        }
        if net_map[self.args.net]:
            self.params.append(net_map[self.args.net])
        try:
            fh.write_text(str(self.ssh_port))
        except Exception as e:
            logger.error("can't save ssh port: %s", e)

    def configure_connect(self) -> None:
        modes = {
            "ssh": self._set_ssh_connect,
            "spice": self._set_spice_connect,
            "qemu": self._set_qemu_connect,
        }
        modes.get(self.args.connect, lambda: None)()

    def _set_ssh_connect(self) -> None:
        self.opts += ["-nographic -serial mon:stdio"]
        host = self.hostip or "localhost"
        self.ssh_connect = f"{host} -p {self.ssh_port}" if self.args.net == "user" else self.localip
        self.chkport, self.connect = self.ssh_port, ([] if self.args.consol else self.G_TERM + ["--"]) + [f"ssh {self.args.uname}@{self.ssh_connect}"]

    def _set_spice_connect(self) -> None:
        self.opts += ["-monitor stdio"]
        self.chkport, self.connect = self.spiceport, [
            f"remote-viewer -t {self.vmprocid} spice://{self.hostip}:{self.spiceport} --spice-usbredir-auto-redirect-filter=0x03,-1,-1,-1,0|-1,-1,-1,-1,1"
        ]

    def _set_qemu_connect(self) -> None:
        self.opts += ["-monitor stdio"]
        self.chkport, self.connect = self.spiceport, None

    # runtime helpers -------------------------------------------------------

    def findProc(self, proc: str, timeout: int = 10) -> bool:
        while self.run_command(f"ps -C {proc}").returncode:
            timeout -= 1
            if timeout < 0:
                return False
            sleep(1)
        return True

    def checkConn(self, timeout: int = 10) -> bool:
        if not self.ssh_connect:
            return False
        while self.run_command(f"ping -c 1 {self.ssh_connect}").returncode:
            timeout -= 1
            if timeout < 0:
                return True
            sleep(1)
        return False

    def configure_kernel(self) -> None:
        if not self.args.vmkernel:
            return
        self.kernel.append(f"-kernel {self.args.vmkernel}")
        if self.args.arch == "riscv64":
            return
        initrd = self.args.initrd or self.args.vmkernel.replace("vmlinuz", "initrd.img")
        if Path(initrd).exists():
            self.kernel += ["-initrd", initrd]
        root_dev = self.args.rootdev or ("sda" if ".img" in self.vmimages[0] else "sda1")
        console = "console=ttyS0" if self.args.connect == "ssh" else "vga=0x300"
        self.kernel.append(f'-append "root=/dev/{root_dev} {console}"')

    def set_pcipass(self) -> None:
        if not self.args.pcihost:
            return
        pcihost = self.args.pcihost
        try:
            drv = next(l for l in subprocess.check_output(["lspci", "-k", "-s", pcihost], text=True).splitlines() if "Kernel driver in use" in l)
            drv = drv.split(":")[-1].strip()
        except Exception as e:
            logger.error("pciinfo: %s", e)
            return
        try:
            with open(f"/sys/bus/pci/drivers/{drv}/unbind", "w") as f:
                f.write(pcihost)
        except Exception as e:
            logger.error("unbind: %s", e)
            return
        try:
            devid = subprocess.check_output(["lspci", "-ns", pcihost], text=True).split()[2]
            with open("/sys/bus/pci/drivers/vfio-pci/new_id", "w") as f:
                f.write(devid)
        except Exception as e:
            logger.error("vfio bind: %s", e)
            return
        self.params.append(f"-device vfio-pci,host={pcihost},multifunction=on")

    def set_qmp(self) -> None:
        self.params.append("-qmp unix:/tmp/qmp-sock,server=on,wait=off")

    # orchestration --------------------------------------------------------

    def setting(self) -> None:
        self.set_args()
        self.set_images()
        if self.findProc(self.vmprocid, 0):
            self.configure_net()
            self.configure_connect()
            return
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
        self.set_qmp()
        # self.set_pcipass()
        self.configure_connect()
        if self.args.rmssh:
            self.RemoveSSH()

    def run(self) -> None:
        print(f"Boot: {self.vmboot:<15} mac: {self.macaddr}, ip: {self.localip}")
        completed = None
        if not self.findProc(self.vmprocid, 0):
            qcmd = [] if self.args.debug == "debug" else []
            if not self.args.consol:
                qcmd = self.G_TERM + ["--"]
            qcmd += self.qemu_exe + self.params + self.opts + self.kernel
            if self.args.debug == "cmd":
                print(" ".join(qcmd))
            else:
                completed = self.run_command(qcmd, sudo=bool(self.sudo), consol=self.args.consol)
        if self.connect and completed and completed.returncode == 0 and self.findProc(self.vmprocid):
            if self.args.connect == "ssh":
                self.checkConn(60)
            self.run_command(self.connect, async_=True, consol=self.args.consol)


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


def main() -> None:
    q = QEMU()
    q.setting()
    q.run()


if __name__ == "__main__":
    import sys, traceback

    try:
        main()
    except KeyboardInterrupt:
        logger.error("Keyboard Interrupted")
    except Exception as e:
        logger.error("QEMU terminated abnormally. %s", e)
        for trace in traceback.extract_tb(sys.exc_info()[2])[1:]:
            logger.error("  File %s, line %s, in %s", trace[0], trace[1], trace[2])
