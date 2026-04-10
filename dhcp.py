#!/usr/bin/python3

import logging
import sys
import shlex
import subprocess
from typing import List

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def run_command(cmd: str | list[str], _async: bool = False, _consol: bool = False) -> str:
    if isinstance(cmd, list):
        cmd = " ".join(cmd)
    _cmd = shlex.split(cmd)
    if _async:
        subprocess.Popen(_cmd)
        return ""
    else:
        if _consol:
            completed = subprocess.run(_cmd, text=True)
            return ""
        else:
            completed = subprocess.run(_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if completed.stdout:
                logger.debug(f"Return code: {completed.returncode}, stdout: {completed.stdout.rstrip()}")
            return completed.stdout.rstrip() if completed.stdout else ""


def get_dhcpinfo() -> List[str]:
    result = run_command("virsh --quiet net-dhcp-leases default")
    if result:
        return result.split("\n")
    return []


dhcp_leases = get_dhcpinfo()

if len(dhcp_leases) > 0 and len(sys.argv) > 1:
    try:
        idx = int(sys.argv[1])
        dhcp_info = dhcp_leases[idx].split()
        dest_str = f"<host mac='{dhcp_info[2]}' name='{dhcp_info[5]}' ip='{dhcp_info[4].split('/')[0]}' />"
        cmd = f'virsh net-update default delete ip-dhcp-host "{dest_str}" --live --config'
        print(cmd)
        run_command(cmd)
    except (IndexError, ValueError) as e:
        print(f"Error: {e}. Check the index and input.")
    except Exception as e:
        print(f"Unexpected error: {e}")
else:
    for dhcp in dhcp_leases:
        print(dhcp)
