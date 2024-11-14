#!/usr/bin/python3

import sys
import argparse
import shlex
import subprocess
from pathlib import Path
from time import sleep


def runshell(cmd, _async=False):
    if isinstance(cmd, list):
        cmd = " ".join(cmd)
    _cmd = shlex.split(cmd)
    if _async:
        completed = subprocess.Popen(_cmd)
    else:
        completed = subprocess.run(_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if completed.returncode:
            print(f"Return code {completed.returncode}: {completed.stdout}")
    return completed


def get_dhcpinfo():
    result = runshell("virsh --quiet net-dhcp-leases default")
    return result.stdout.rstrip().split("\n") if result.returncode == 0 and result.stdout else []


dhcp_leases = get_dhcpinfo()

if len(dhcp_leases) > 0 and len(sys.argv) > 1:
    dhcp_info = dhcp_leases[int(sys.argv[1])].split()
    dest_str = f"<host mac='{dhcp_info[2]}' name='{dhcp_info[5]}' ip='{dhcp_info[4].split('/')[0]}' />"
    cmd = f'virsh net-update default delete ip-dhcp-host "{dest_str}" --live --config'
    print(cmd)
    runshell(cmd)
else:
    for dhcp in dhcp_leases:
        print(dhcp)
