#!/usr/bin/env python3
"""Lightweight QEMU VM launcher with convenient CLI options."""

from __future__ import annotations

import argparse
import functools
import getpass
import hashlib
import logging
import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from time import sleep
from typing import Sequence

# ---------------------------------------------------------------------------
# logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

Command = str | Sequence[str]
IMAGE_EXTS = {".img", ".qcow2", ".vhdx"}
DEFAULT_SSH_PORT = 5900
VIRTIOFSD_TIMEOUT = 15


@dataclass(frozen=True)
class NvmeBackend:
    nvme_id: str
    namespace_id: str
    extension: str
    namespace_count: int
    is_physical: bool

    def backend_for_namespace(self, namespace: int) -> str:
        ns_id = self.namespace_id
        if namespace != 1 and not self.is_physical:
            ns_id = f"n{int(ns_id[1:]) + namespace - 1}" if ns_id else f"n{namespace}"
        return f"{self.nvme_id}{ns_id}{self.extension}"


@dataclass(frozen=True)
class NvmeOptions:
    max_ioqpairs: int
    controller: str = ""
    namespace: str = ""


def split_command(cmd: Command) -> list[str]:
    """Convert a command string or command fragments into subprocess argv."""
    if isinstance(cmd, str):
        return shlex.split(cmd)

    argv: list[str] = []
    for fragment in cmd:
        argv.extend(shlex.split(str(fragment)))
    return argv


def command_text(cmd: Command) -> str:
    return shlex.join(split_command(cmd))


def default_home_folder() -> str:
    user = os.environ.get("SUDO_USER") or getpass.getuser()
    candidate = Path("/home") / user
    return str(candidate) if candidate.exists() else str(Path.home())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--secboot", default="", action="store_const", const=".ms", help="UEFI secure boot")
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
    parser.add_argument("--usbredir", action="store_true", help="Enable SPICE USB redirection in remote-viewer")
    parser.add_argument("--usbredir-filter", default="", help="SPICE USB redirect filter string")
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
    parser.add_argument("--serial", action="store_true", help="Enable USB serial")
    parser.add_argument("--blkdbg", action="store_true", help="Enable block debug")
    parser.add_argument("--demon", action="store_true", help="Run in daemon mode (no console, no auto-connect)")
    return parser


def get_available_memory_gb() -> int:
    """Get available memory in GB.

    Returns:
        int: Available memory in GB, or 0 if unable to read.
    """
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    # Extract the number (in kB) and convert to bytes
                    mem_available_kb = int(line.split()[1])
                    return mem_available_kb // (1024 * 1024)
    except (FileNotFoundError, ValueError, IndexError):
        pass

    # Fallback to the original method if /proc/meminfo is not available
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        avail_phys_pages = os.sysconf("SC_PHYS_PAGES")
        return (page_size * avail_phys_pages) // (1024 * 1024 * 1024)
    except (ValueError, OSError):
        return 0


# ---------------------------------------------------------------------------
# QEMU class
# ---------------------------------------------------------------------------


class QEMU:
    NVME_INPUT_PATTERN = re.compile(r"^(?P<nvme_id>[^:]+):?(?P<num_ns>\d+)?$")
    NVME_STEM_PATTERN = re.compile(r"^(?P<nvme>.+?)(?P<ns_id>n\d+)?$")

    def __init__(self) -> None:
        self.args: argparse.Namespace
        self.vmimages: list[str] = []
        self.vmcdimages: list[str] = []
        self.vmnvme: list[str] = []
        self.params: list[str] = []
        self.opts: list[str] = []
        self.kernel: list[str] = []
        self.connect: list[str] | None = []
        self.ssh_connect: str | None = None
        self.ssh_host: str | None = None
        self.localip: str | None = None
        self.hostip = "localhost"
        self.macaddr = ""
        self.ssh_port = DEFAULT_SSH_PORT
        self.spiceport = DEFAULT_SSH_PORT + 1
        self.vmprocid = ""
        self.index = 0
        self._memsize: str | None = None
        self.sudo = ["sudo"] if os.getuid() else []
        self.G_TERM: list[str] = []

    # properties -------------------------------------------------------------

    @property
    def home_folder(self) -> str:
        return default_home_folder()

    @property
    def memsize(self) -> str:
        if self._memsize is None:
            gb = get_available_memory_gb()
            self._memsize = f"{min(max(gb, 6), 16)}G"
        return self._memsize

    # command execution -----------------------------------------------------

    def run_command(
        self,
        cmd: Command,
        sudo: bool = False,
        async_: bool = False,
        consol: bool = False,
    ) -> subprocess.CompletedProcess[str] | subprocess.Popen[str]:
        """Run a shell command with optional sudo/async/console output.

        The former `sudo_run` method is now implemented as a shim that calls
        this routine with ``sudo=True``.  The helper exists primarily for
        backwards compatibility with any external code or scripts that might
        be invoking ``qemu.sudo_run`` directly.
        """
        cmd_list = split_command(cmd)
        if sudo and os.getuid():
            cmd_list = self.sudo + cmd_list

        logger.debug("exec: %s", shlex.join(cmd_list))
        try:
            if consol:
                return subprocess.run(cmd_list, text=True)
            if async_:
                proc = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                sleep(1)
                return proc
            completed = subprocess.run(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        except FileNotFoundError as exc:
            logger.debug("command not found: %s", cmd_list[0])
            return subprocess.CompletedProcess(cmd_list, 127, stdout=str(exc), stderr=None)

        if completed.stdout:
            logger.debug(f"Return code: {completed.returncode}, Output: {completed.stdout.rstrip()}")
        return completed

    # keep a thin compatibility wrapper
    def sudo_run(self, cmd: Command, *, async_: bool = False, consol: bool = False):
        """Legacy helper: run a command with sudo privileges."""
        return self.run_command(cmd, sudo=True, async_=async_, consol=consol)

    # argument and image parsing -------------------------------------------

    def set_args(self) -> None:
        self.args = build_parser().parse_args()

        # logging and derived arguments
        logger.setLevel("INFO" if self.args.debug == "cmd" else self.args.debug.upper())
        if self.args.disk:
            self.parse_disks()
        if self.args.nvme:
            self.vmnvme.extend(self.args.nvme)
        if self.args.memsize:
            self._memsize = self.args.memsize
        if os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_CLIENT"):
            self.args.demon = True

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
                if p.is_block_device() or p.suffix.lower() in IMAGE_EXTS:
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
        self.bootype = "p" if Path(self.vmboot).is_block_device() else "n" if self.vmnvme and self.vmnvme[0] == self.vmboot else ""
        self.G_TERM = [] if self.args.demon else [f"gnome-terminal --title={self.vmprocid}", "--"]
        logger.info("vmimages %s vmcd %s vmnvme %s vmkernel %s", self.vmimages, self.vmcdimages, self.vmnvme, self.args.vmkernel)

    # qemu initialization --------------------------------------------------

    def set_qemu(self) -> None:
        exe = f"qemu-system-{self.args.arch}"
        self.qemu_exe = [exe] if self.args.qemu else [f"{self.home_folder}/qemu/bin/{exe}"]
        self.params = [f"-name {self.vmname},process={self.vmprocid}"]
        self.params += self._arch_params()
        self.params += self._machine_resources()

    def _arch_params(self) -> list[str]:
        arch_switch: dict[str, list[str]] = {
            "riscv64": ["-machine virt -bios none"],
            "arm": ["-machine virt -cpu cortex-a53 -device ramfb"],
            "aarch64": ["-machine virt,highmem=on,virtualization=true -cpu cortex-a72 -device ramfb"],
            "x86_64": self._set_x86_64_params(),
        }
        return arch_switch.get(self.args.arch, [])

    def _machine_resources(self) -> list[str]:
        cpu = self.args.cpus or int((os.cpu_count() or 2) / 2)
        return [f"-m {self.memsize}", f"-smp {cpu},sockets=1,cores={cpu},threads=1", "-nodefaults", "-rtc base=localtime"]

    def _set_x86_64_params(self) -> list[str]:
        base = [
            f"-machine type={self.args.machine},accel=kvm,usb=on -device intel-iommu",
            (
                "-cpu Skylake-Client-v3,hv_stimer,hv_synic,hv_relaxed,hv_reenlightenment,hv_spinlocks=0xfff,hv_vpindex,hv_vapic,hv_time,hv_frequencies,hv_runtime,+kvm_pv_unhalt,+vmx --enable-kvm"
                if self.args.hvci
                else "-cpu host,arch_capabilities=off --enable-kvm"
            ),
            "-device virtio-rng-pci,rng=rng0" if self.args.hvci else "-object rng-random,id=rng0,filename=/dev/urandom -device virtio-rng-pci,rng=rng0",
        ]
        if not self.args.hvci and self.args.vender:
            base.append(f"-smbios type=1,manufacturer={self.args.vender},product='{self.args.vender} Notebook PC'")
        if self.args.connect != "ssh" and self.args.arch != "aarch64":
            self.opts.append(f"-vga {self.args.vga}")
        return base

    def configure_uefi(self) -> None:
        if self.args.bios:
            return
        varfile = Path(f"./OVMF_VARS_4M{self.args.secboot}{self.bootype}.fd")
        if not varfile.exists():
            try:
                self.run_command(["cp", f"/usr/share/OVMF/OVMF_VARS_4M{self.args.secboot}.fd", str(varfile)])
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
            self.params += ["-device qemu-xhci,id=usb3", "-device usb-kbd", "-device usb-tablet"]

    def configure_usb_storage(self) -> None:
        if self.args.stick and Path(self.args.stick).exists():
            self.params += [f"-drive file={self.args.stick},if=none,format=raw,id=stick{self.index}", f"-device usb-storage,drive=stick{self.index}"]
            self.index += 1

    def configure_usb_serial(self) -> None:
        if not self.args.serial:
            return
        if self.args.nousb:
            return

        base_port = 60000 + int(self.vmguid[:2], 16)
        bus = "xhci1.0" if self.args.arch == "x86_64" else "usb3.0"
        self.params += [
            f"-chardev socket,id=usbserial0,host=127.0.0.1,port={base_port},server=on,wait=off",
            f"-device usb-serial,chardev=usbserial0,id=usbserialdev0,bus={bus}",
            f"-chardev socket,id=usbserial1,host=127.0.0.1,port={base_port},server=off",
            f"-device usb-serial,chardev=usbserial1,id=usbserialdev1,bus={bus}",
        ]

    def configure_disks(self) -> None:
        scsi_params = [] if self.args.arch == "riscv64" else ["-object iothread,id=iothread0", "-device virtio-scsi-pci,id=scsi0,iothread=iothread0"]
        disk_params: list[str] = []
        for img in self.vmimages:
            disk_params += self._disk_params(img, self.index)
            self.index += 1
        if disk_params:
            self.params += scsi_params + disk_params

    def _disk_params(self, img: str, index: int) -> list[str]:
        ext = Path(img).suffix.lower()
        drive_id = f"drive-{index}"

        if img.startswith("wiftest"):
            return [
                f"-drive if=none,cache=none,file=blkdebug:blkdebug.conf:{img},format=qcow2,id={drive_id}",
                f"-device virtio-blk-pci,drive={drive_id},id=virtio-blk-pci{index}",
            ]
        if ext == ".qcow2":
            return [
                f"-drive file={img},if=none,cache=writeback,id={drive_id}",
                f"-device virtio-blk-pci,drive={drive_id},id=virtio-blk-pci{index}",
            ]
        if ext == ".vhdx":
            return [
                f"-drive file={img},if=none,id={drive_id}",
                f"-device nvme,drive={drive_id},serial=nvme-{index}",
            ]
        return [
            f"-drive file={img},if=none,format=raw,discard=unmap,aio=native,cache=none,id={drive_id}",
            f"-device scsi-hd,scsi-id={index},drive={drive_id},id=scsi0-{index}",
        ]

    def configure_cdrom(self) -> None:
        iface = "none"
        for iso in self.vmcdimages:
            self.params.append(f"-drive file={iso},media=cdrom,readonly=on,if={iface},index={self.index},id=cdrom{self.index}")
            bus = "xhci1.0" if self.args.arch == "x86_64" else "xhci.0"
            if self.args.arch != "x86_64":
                self.params.append("-device qemu-xhci,id=xhci")
            self.params.append(f"-device usb-storage,drive=cdrom{self.index},bus={bus}")
            self.index += 1

    def check_file(self, filename: str, size: int, raw: bool = False) -> bool:
        if not Path(filename).exists():
            self.run_command(f"qemu-img create -f {'raw' if raw else 'qcow2'} {filename} {size}G")
        return self.run_command(f"lsof -w {filename}").returncode != 0

    def configure_nvme(self) -> None:
        if not self.vmnvme:
            return

        nvme_opts = self._nvme_options()
        blkdbg = self._blkdebug_prefix()
        params = ["-device ioh3420,bus=pcie.0,id=root1.0,slot=1", "-device x3130-upstream,bus=root1.0,id=upstream1.0"]
        ctrl = 0
        for nvme in self.vmnvme:
            backend = self._parse_nvme_backend(nvme)
            if backend is None:
                continue

            params += [
                f"-device xio3130-downstream,bus=upstream1.0,id=downstream1.{ctrl},chassis={ctrl},multifunction=on",
                f"-device nvme-subsys,id=nvme-subsys-{ctrl},nqn=subsys{ctrl}",
                f"-device nvme,serial=beefnvme{ctrl},id=nvme{ctrl},subsys=nvme-subsys-{ctrl},bus=downstream1.{ctrl},max_ioqpairs={nvme_opts.max_ioqpairs}{nvme_opts.controller}",
            ]

            for ns in range(1, backend.namespace_count + 1):
                filename = backend.backend_for_namespace(ns)
                if self.check_file(filename, self.args.nssize, backend.extension == ".img"):
                    params += [
                        f"-drive file={blkdbg}{filename},id=nvme{ctrl}n{ns},if=none{',format=raw' if backend.extension != '.qcow2' else ''},cache=none",
                        f"-device nvme-ns,drive=nvme{ctrl}n{ns},bus=nvme{ctrl},nsid={ns}{nvme_opts.namespace if ns == 1 else ''}",
                    ]
            ctrl += 1
        if Path("./events").exists():
            params.append("--trace events=./events")
        self.params += params

    def _parse_nvme_backend(self, token: str) -> NvmeBackend | None:
        match = self.NVME_INPUT_PATTERN.match(token)
        if not match:
            logger.warning("ignore invalid nvme backend: %s", token)
            return None

        filename = match.group("nvme_id")
        namespace_count = int(match.group("num_ns") or self.args.numns or 1)
        if token.startswith("/dev/"):
            return NvmeBackend(filename, "", "", namespace_count, True)

        path = Path(filename)
        extension = path.suffix or ".qcow2"
        stem_match = self.NVME_STEM_PATTERN.match(path.stem)
        if not stem_match:
            logger.warning("ignore invalid nvme backend: %s", token)
            return None

        nvme_id = stem_match.group("nvme")
        namespace_id = (stem_match.group("ns_id") or "") if path.suffix else "n1"
        return NvmeBackend(nvme_id, namespace_id, extension, namespace_count, False)

    def _nvme_options(self) -> NvmeOptions:
        did = f",did={self.args.did}" if self.args.did else ""
        mn = f",mn={self.args.mn}" if self.args.mn else ""
        ocp = "" if self.args.qemu else ",ocp=on"
        fdp = ",fdp=on" if self.args.fdp else ""

        if not self.args.sriov:
            return NvmeOptions(self.args.num_queues, f"{did}{mn}{ocp}{fdp}")

        sriov_max_vfs = 64
        sriov_vq = sriov_max_vfs * 2
        sriov_vi = sriov_max_vfs
        msix = sriov_vi + 1
        controller = f",msix_qsize={msix},sriov_max_vfs={sriov_max_vfs}," f"sriov_vq_flexible={sriov_vq},sriov_vi_flexible={sriov_vi}{did}{mn}{ocp}{fdp}"
        return NvmeOptions(sriov_vq + 2, controller, ",shared=false,detached=true")

    def _blkdebug_prefix(self) -> str:
        return "blkdebug:blkdebug.conf:" if self.args.blkdbg and Path("blkdebug.conf").exists() else ""

    def configure_virtiofs(self) -> None:
        if self.args.noshare:
            return
        candidates = [Path("/usr/libexec/virtiofsd"), Path(self.home_folder) / "qemu/libexec/virtiofsd"]
        virtiofsd = next((str(p) for p in candidates if p.exists()), None)
        if not virtiofsd:
            return
        sock = f"/tmp/virtiofs_{self.vmuid}.sock"
        cmd = [f"{virtiofsd} --socket-path={sock}", f"--shared-dir={self.home_folder}" if virtiofsd.startswith("/usr") else f"-o source={self.home_folder}"]
        if self.args.debug == "cmd":
            print(command_text(cmd))
        else:
            result = self.run_command(cmd, sudo=True, async_=True)
            if isinstance(result, subprocess.CompletedProcess) and result.returncode != 0:
                raise RuntimeError(f"virtiofsd failed: {result.stdout}")
            if not self.wait_for_path(Path(sock), VIRTIOFSD_TIMEOUT):
                raise RuntimeError(f"virtiofsd socket was not created: {sock}")
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
            "external": ["-chardev socket,id=ipmi0,host=localhost,port=9002,reconnect=10", "-device ipmi-bmc-extern,chardev=ipmi0,id=bmc1", "-device isa-ipmi-kcs,bmc=bmc1"],
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
            self.params += [f"-tpmdev passthrough,id=tpm0,path=/dev/tpm0,cancel-path={cancel}", "-device tpm-tis,tpmdev=tpm0"]

    def RemoveSSH(self) -> None:
        ssh_file = Path(f"/tmp/{self.vmprocid}_SSH")
        ssh_file.unlink(missing_ok=True)
        cmd = f'ssh-keygen -R "[{self.hostip}]:{self.ssh_port}"' if self.args.net == "user" else f'ssh-keygen -R "{self.localip}"'
        self.run_command(cmd)

    def configure_net(self, set_ports: bool = False) -> None:
        """Compute networking parameters and optionally reserve ports."""
        fh = Path(f"/tmp/{self.vmprocid}_SSH")
        self.ssh_port = self._read_ssh_port(fh)
        self.spiceport = self.ssh_port + 1
        self.macaddr = self._macaddr()
        self.hostip = self._host_ip()
        self.localip = self.args.ip or self._dhcp_guest_ip()

        if not set_ports:
            return

        self._reserve_ports()
        net_param = self._network_param()
        if net_param:
            self.params.append(net_param)
        try:
            fh.write_text(str(self.ssh_port))
        except Exception as e:
            logger.error("can't save ssh port: %s", e)

    def _read_ssh_port(self, path: Path) -> int:
        try:
            return int(path.read_text())
        except Exception:
            return DEFAULT_SSH_PORT

    def _macaddr(self) -> str:
        return f"52:54:00:{self.vmguid[:2]}:{self.vmguid[2:4]}:{self.vmguid[4:6]}"

    def _host_ip(self) -> str:
        out = self.run_command("ip r g 1.0.0.0")
        fields = (out.stdout or "").split()
        return fields[6] if out.returncode == 0 and len(fields) > 6 else "localhost"

    def _dhcp_guest_ip(self) -> str | None:
        result = self.run_command(f"virsh --quiet net-dhcp-leases default --mac {self.macaddr}")
        if result.returncode != 0:
            return None

        leases = result.stdout or ""
        lines = leases.strip().splitlines()
        match = next((ln for ln in lines if self.vmname in ln), None)
        last = match if match else (sorted(lines)[-1] if lines else "")
        fields = last.split()
        return fields[4].split("/")[0] if len(fields) > 4 else None

    def _reserve_ports(self) -> None:
        while self._port_in_use(self.spiceport) or self._port_in_use(self.ssh_port):
            self.ssh_port += 2
            self.spiceport = self.ssh_port + 1

    def _port_in_use(self, port: int) -> bool:
        return self.run_command(f"lsof -w -i :{port}", sudo=True).returncode == 0

    def _network_param(self) -> str:
        net_map = {
            "user": f"-nic user,model=virtio-net-pci,mac={self.macaddr},smb={self.home_folder},hostfwd=tcp::{self.ssh_port}-:22",
            "tap": f"-nic tap,model=virtio-net-pci,mac={self.macaddr},script={self.home_folder}/projects/scripts/qemu-ifup",
            "bridge": f"-nic bridge,br=virbr0,model=virtio-net-pci,mac={self.macaddr}",
            "none": "",
        }
        return net_map[self.args.net]

    def configure_connect(self) -> None:
        modes = {"ssh": self._set_ssh_connect, "spice": self._set_spice_connect, "qemu": self._set_qemu_connect}
        modes.get(self.args.connect, lambda: None)()
        if self.args.rmssh:
            self.RemoveSSH()

    def _set_ssh_connect(self) -> None:
        self.opts += ["-nographic -serial mon:stdio"]
        host = self.hostip or "localhost"
        self.ssh_host = host if self.args.net == "user" else self.localip
        self.ssh_connect = f"{host} -p {self.ssh_port}" if self.args.net == "user" else self.localip
        self.chkport, self.connect = self.ssh_port, ([] if self.args.consol else self.G_TERM) + [f"ssh {self.args.uname}@{self.ssh_connect}"]

    def _set_spice_connect(self) -> None:
        self.opts += ["-monitor stdio"]
        cmd = [f"remote-viewer -t {self.vmprocid} spice://{self.hostip}:{self.spiceport}"]
        if self.args.usbredir or self.args.usbredir_filter:
            filter_str = self.args.usbredir_filter or "0x03,-1,-1,-1,0|-1,-1,-1,-1,1"
            cmd.append(f"--spice-usbredir-redirect-on-connect={filter_str}")
        self.chkport, self.connect = self.spiceport, cmd

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
        if not self.ssh_host:
            return False
        port = self.ssh_port if self.args.net == "user" else 22
        while self.run_command(["nc", "-z", "-w", "1", self.ssh_host, str(port)]).returncode:
            timeout -= 1
            if timeout < 0:
                return False
            sleep(1)
        return True

    def wait_for_path(self, path: Path, timeout: int) -> bool:
        while timeout >= 0:
            if path.exists():
                return True
            logger.debug("waiting for %s", path)
            timeout -= 1
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

    def configure_extra(self) -> None:
        if self.args.ext:
            self.params.append(self.args.ext)

    def qemu_command(self) -> list[str]:
        prefix = [] if self.args.debug == "debug" or self.args.consol else self.G_TERM
        return [*prefix, *self.qemu_exe, *self.params, *self.opts, *self.kernel]

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
        self.configure_usbs()
        self.configure_cdrom()
        self.configure_nvme()
        self.configure_net(True)
        self.configure_spice()
        self.configure_virtiofs()
        self.configure_tpm()
        self.configure_usb_storage()
        self.configure_ipmi()
        self.configure_usb_serial()
        self.configure_extra()
        self.set_qmp()
        # self.set_pcipass()
        self.configure_connect()

    def run(self) -> None:
        print(f"Boot: {self.vmboot:<15}, memsize: {self.memsize}, mac: {self.macaddr}, ip: {self.localip}")
        completed: subprocess.CompletedProcess[str] | subprocess.Popen[str] = subprocess.CompletedProcess(args=[], returncode=0)
        if not self.findProc(self.vmprocid, 0):
            qcmd = self.qemu_command()
            if self.args.debug == "cmd":
                print(command_text(qcmd))
            else:
                if self.args.demon and self.connect:
                    print(command_text(self.connect))
                completed = self.run_command(qcmd, sudo=bool(self.sudo), consol=self.args.consol or self.args.demon)
        if self.connect:
            if self.args.debug == "cmd":
                print(command_text(self.connect))
            elif completed.returncode == 0 and self.findProc(self.vmprocid):
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
