#!/usr/bin/python3

import sys
import shlex
import subprocess
from typing import List


def runshell(cmd: str | List[str], _async: bool = False):
    if isinstance(cmd, list):
        cmd = " ".join(cmd)
    _cmd = shlex.split(cmd)
    if _async:
        return subprocess.Popen(_cmd)
    else:
        completed = subprocess.run(_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if completed.returncode:
            print(f"Return code {completed.returncode}: {completed.stdout}")
        return completed


def get_dhcpinfo() -> List[str]:
    result = runshell("virsh --quiet net-dhcp-leases default")
    if result.returncode == 0 and result.stdout:
        return str(result.stdout).rstrip().split("\n")
    return []


dhcp_leases = get_dhcpinfo()

if len(dhcp_leases) > 0 and len(sys.argv) > 1:
    try:
        idx = int(sys.argv[1])
        dhcp_info = dhcp_leases[idx].split()
        dest_str = f"<host mac='{dhcp_info[2]}' name='{dhcp_info[5]}' ip='{dhcp_info[4].split('/')[0]}' />"
        cmd = f'virsh net-update default delete ip-dhcp-host "{dest_str}" --live --config'
        print(cmd)
        runshell(cmd)
    except (IndexError, ValueError) as e:
        print(f"Error: {e}. Check the index and input.")
    except Exception as e:
        print(f"Unexpected error: {e}")
else:
    for dhcp in dhcp_leases:
        print(dhcp)
