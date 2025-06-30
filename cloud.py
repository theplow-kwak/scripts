#!/usr/bin/env python3

import argparse
import hashlib
import logging
import os
import subprocess
import sys
import traceback

from typing import List


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class CloudInitConfig:
    def __init__(self):
        self.cert_files: List[str] = []

    def create_cfgfile(self):
        md5_hash = hashlib.md5(self.img_name.encode()).hexdigest()
        self.host_name = self.host_name or f"{os.path.splitext(self.img_name)[0]}-VM-{md5_hash[:2]}"

        ssh_key_path = os.path.expanduser("~/.ssh/id_rsa.pub")
        ssh_content = ""
        if not os.path.exists(ssh_key_path):
            subprocess.run(["ssh-keygen", "-t", "rsa", "-b", "2048", "-f", ssh_key_path[:-4], "-N", ""], check=True)
        if os.path.exists(ssh_key_path):
            with open(ssh_key_path, "r") as key_file:
                ssh_key = key_file.read().strip()
                ssh_content = f'    ssh-authorized-keys:\n      - "{ssh_key}"\n'

        certs_content = ""
        if self.cert_files:
            certs_content = "ca_certs:\n  trusted:\n"
            for cert_file in self.cert_files:
                with open(cert_file, "r") as cert:
                    certs_content += "    - |\n" + "".join(f"      {line}" for line in cert)

        cloud_config = f"""#cloud-config

preserve_hostname: False
hostname: {self.host_name}
fqdn: {self.host_name}.lo

users:
  - name: {self.user_name}
    lock_passwd: false
    shell: /bin/bash
    sudo: ['ALL=(ALL) NOPASSWD:ALL']
{ssh_content}
chpasswd:
  users:
    - name: root
      password: Passw0rd
      type: text
    - name: {self.user_name}
      password: q
      type: text
  expire: False

write_files:
  - path: /etc/netplan/01-network-all.yaml
    owner: root:root
    permissions: '0600'
    content: |-
      network:
        version: 2
        ethernets:
          id0:
            match:
              name: "en*"
            dhcp4: true
  - path: /etc/ssh/sshd_config.d/90-matchall.conf
    owner: root:root
    permissions: '0644'
    content: |-
      PermitRootLogin yes
      Match All
          PasswordAuthentication yes

ssh_pwauth: true
disable_root: false
runcmd:
  - [ timedatectl, set-local-rtc, 1, --adjust-system-clock ]
  - [ sh, -c, 'touch /etc/cloud/cloud-init.disabled' ]
  - mkdir /host

mounts:
  - [ hostfs, /host, virtiofs ]

mount_default_fields: [ None, None, "auto", "defaults,nofail", "0", "2" ]

power_state:
  delay: 'now'
  mode: poweroff
  message: Bye Bye
  timeout: 30
  condition: True

timezone: Asia/Seoul

"""
        cloud_config += certs_content
        cloud_config += '\nfinal_message: "The system is finally up, after $UPTIME seconds"\n'

        with open(self.cinit_file, "w") as f:
            f.write(cloud_config)

    def parse_args(self):
        parser = argparse.ArgumentParser(description="Cloud-init configuration generator and QEMU launcher.")
        parser.add_argument("-b", "--backing", help="qemu image backing file")
        parser.add_argument("-i", "--image", help="qemu image name")
        parser.add_argument("-q", "--qemu", help="Path to qemu binary", default="qemu")
        parser.add_argument("-n", "--net", help="qemu Network interface model", default="bridge")
        parser.add_argument("-k", "--kernel", help="Set the custom kernel")
        parser.add_argument("-u", "--uname", help="The login USER name", default=os.getenv("USER", "root"))
        parser.add_argument("-H", "--host", help="Set the HOST name")
        parser.add_argument("-f", "--fname", help="The cloud_init file name (default: '_cloud_init.cfg')", default="_cloud_init.cfg")
        parser.add_argument("-c", "--cert", help="Certificate file for cloud-init", action="append")
        parser.add_argument("-s", "--size", help="Size of the qemu image", default="40G")
        parser.add_argument("--nvme", help="Use NVMe instead of SATA", action="store_const", const="--nvme", default="", dest="disk_type")
        parser.add_argument("--uefi", help="Use UEFI instead of bios", action="store_true")
        parser.add_argument("--debug", help="Enable debug mode", action="store_true")
        parser.add_argument("remainder", nargs=argparse.REMAINDER, help="all other args after --")
        args = parser.parse_args()

        self.backing_img = args.backing
        self.img_name = args.image
        self.user_name = args.uname
        self.host_name = args.host
        self.cinit_file = args.fname
        self.image_size = args.size
        if args.cert:
            self.cert_files.extend(args.cert)
        if args.remainder:
            try:
                args.remainder.remove("--")
            except ValueError:
                pass
        self.args = args

    def run(self):
        self.parse_args()
        if self.args.debug:
            print(f"Configuration: {vars(self)}")

        if not self.img_name:
            raise ValueError("Image name is required.")
        img_name_final = f"{self.img_name.split(':')[0]}n1.qcow2" if self.img_name.startswith("nvme") else self.img_name
        cloud_init_iso = ""
        if not os.path.exists(img_name_final):
            if not self.backing_img:
                raise ValueError("Backing image is required to create boot_image.")
            self.create_cfgfile()
            subprocess.run(["cloud-localds", "-v", "cloud_init.iso", self.cinit_file], check=True)
            subprocess.run(["qemu-img", "create", "-f", "qcow2", "-F", "qcow2", "-b", self.backing_img, img_name_final, self.image_size], check=True)
            cloud_init_iso = "cloud_init.iso"

        kernel_option: List[str] = ["--kernel", self.args.kernel] if self.args.kernel else []
        cmd = (
            [self.args.qemu, "" if self.args.uefi else "--bios", "--connect", "ssh", "--net", self.args.net, "--uname", self.user_name]
            + kernel_option
            + [cloud_init_iso, self.args.disk_type, self.img_name]
            + self.args.remainder
        )
        cmd = " ".join(cmd)
        print(cmd)
        subprocess.run(cmd, shell=True, check=True)


if __name__ == "__main__":
    try:
        CloudInitConfig().run()
    except KeyboardInterrupt:
        logging.error("Keyboard Interrupted")
    except Exception as e:
        logging.error(f"Cloud terminated abnormally. {e}")
        ex_type, ex_value, ex_traceback = sys.exc_info()
        trace_back = traceback.extract_tb(ex_traceback)
        for trace in trace_back[1:]:
            logging.error(f"  File {trace[0]}, line {trace[1]}, in {trace[2]}")
