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

def runshell(cmd, _async=False):
    if isinstance(cmd, list): cmd = ' '.join(cmd)
    _cmd = shlex.split(cmd)
    if _async:
        completed = subprocess.Popen(_cmd)
    else:
        completed = subprocess.run(
            _cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if completed.returncode:
            print(f"Return code {completed.returncode}: {completed.stdout}")
    return completed

def get_dhcpinfo():
    result = runshell("virsh --quiet net-dhcp-leases default")
    if result.returncode == 0:
        print(result.stdout)
        for line in result.stdout.strip().split('\n'):
            dhcp_info = line.split()
            dhcp_leases.append({'mac':dhcp_info[2], 'name':dhcp_info[5], 'ip':dhcp_info[4].split('/')[0]})

dhcp_leases = []
get_dhcpinfo()
print(dhcp_leases) 


# virsh net-update default delete ip-dhcp-host "<host mac='52:54:00:b7:f1:59' name='QEMU-OCSSD' ip='192.168.122.36' />" --live --config
