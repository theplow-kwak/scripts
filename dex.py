#!/usr/bin/python3

import subprocess
import sys
import time
import logging
import argparse
import shlex
from typing import Optional, Dict
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class DexManager:
    ADB_COMMAND = "adb"
    SCRCPY_COMMAND = "scrcpy"
    DEFAULT_SCREEN_SIZE = "2400x1440"
    DEFAULT_SCREEN_DENSITY = "210"
    DEFAULT_DISPLAY_MODE = "2560x1440/240"

    def __init__(self):
        self.check_device_connected()

    def run_command(self, command: str, capture_output: bool = False, demon_mode: bool = False) -> Optional[str]:
        """Run a shell command and optionally capture its output or run in background."""
        try:
            cmd_list = shlex.split(command)
            if demon_mode:
                subprocess.Popen(cmd_list, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return None
            else:
                result = subprocess.run(cmd_list, check=True, text=True, stdout=subprocess.PIPE if capture_output else None)
                return result.stdout.strip() if capture_output else None
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {e}")
            sys.exit(1)

    def check_device_connected(self) -> None:
        """Check if any devices are connected via adb."""
        output = self.run_command(f"{self.ADB_COMMAND} devices", capture_output=True)
        if not output or not any("device" in line and "unauthorized" not in line for line in output.splitlines()[1:]):
            logger.error("There is no device connected!")
            sys.exit(1)

    def get_display(self, verbose: bool = False) -> Optional[int]:
        """Get the ID of the last available display."""
        output = self.run_command(f"{self.SCRCPY_COMMAND} --list-displays", capture_output=True)
        if not output:
            logger.error("No output from scrcpy --list-displays")
            return None
        display_ids = [int(match.group(1)) for match in re.finditer(r"--display-id=(\d+)", output)]
        if verbose:
            logger.info("\n".join([f"display-id={display_id}" for display_id in display_ids]))
        return max(display_ids, default=None)

    def get_apps(self, verbose: bool = False) -> dict[str, str]:
        """Retrieve a list of installed apps."""
        output = self.run_command(f"{self.SCRCPY_COMMAND} --list-apps", capture_output=True)
        app_list: dict[str, str] = {}
        if output:
            for line in output.splitlines():
                line = line.strip()
                if line.startswith(("*", "-")):
                    parts = line.lstrip("*-").strip().split()
                    package = parts[-1]
                    name = "".join(parts[:-1]).strip()
                    if name:
                        app_list[name] = package
        if verbose:
            for name, pkg in app_list.items():
                logger.info(f"{name} - {pkg}")
        return app_list

    def get_package(self, app_list: Dict[str, str], name: str) -> str:
        """Find the package name for a given app name."""
        if name:
            for key, package in app_list.items():
                if name.lower() in key.lower():
                    return package
        logger.warning(f"No package found for {name}")
        return ""

    def run_app(self, package: str) -> None:
        """Run an app using scrcpy."""
        _package = f" --start-app={package}" if package else ""
        self.run_command(f"{self.SCRCPY_COMMAND} --new-display={self.DEFAULT_DISPLAY_MODE} --stay-awake --keyboard=uhid {_package} --window-title='DexOnLinux'", demon_mode=True)

    def adb_ssh(self) -> None:
        """Forward ports and start an SSH session."""
        self.run_command(f"{self.ADB_COMMAND} forward tcp:8022 tcp:8022")
        self.run_command(f"{self.ADB_COMMAND} forward tcp:8080 tcp:8080")
        self.run_command("ssh localhost -p 8022")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage Dex mode and related operations.")
    parser.add_argument("command", type=str, nargs="?", default=None, help="Command to execute (e.g., 'list', 'applist', or app name).")
    args = parser.parse_args()

    dex_manager = DexManager()

    if args.command == "list":
        dex_manager.get_display(verbose=True)
    elif args.command == "applist":
        dex_manager.get_apps(verbose=True)
    elif args.command == "adbssh":
        dex_manager.adb_ssh()
    else:
        app_list = dex_manager.get_apps()
        package = dex_manager.get_package(app_list, args.command)
        dex_manager.run_app(package)
