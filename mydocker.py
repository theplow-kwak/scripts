#!/usr/bin/python3

from genericpath import exists
import os
import logging
import argparse
import shlex
import subprocess
import hashlib
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


mylogger = set_logger("DOCKER", f"/tmp/mydocker.log")


def runshell(cmd, _async=False):
    if isinstance(cmd, list):
        cmd = " ".join(cmd)
    _cmd = shlex.split(cmd)
    if _async:
        completed = subprocess.Popen(_cmd)
    else:
        completed = subprocess.run(_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if completed.stdout:
            mylogger.debug(f"Return code: {completed.returncode}, stdout: {completed.stdout.rstrip()}\n<<<<\n")
    return completed


def get_image(image):
    _result = runshell("docker images --format '{{.Repository}}'")
    images = sorted(_result.stdout.rstrip().split("\n")) if _result.returncode == 0 and _result.stdout else []
    return next((item for item in images if item == image), None)


def get_containers(image):
    _result = runshell(f"docker ps -a --filter 'ancestor={image}'" + " --format '{{.Names}}'")
    containers = sorted(_result.stdout.rstrip().split("\n")) if _result.returncode == 0 and _result.stdout else []
    return containers


def get_container(container):
    _result = runshell("docker ps -a --format '{{.Names}}'")
    containers = sorted(_result.stdout.rstrip().split("\n")) if _result.returncode == 0 and _result.stdout else []
    return next((item for item in containers if item == container), None)


class DockerMaster(object):
    def __init__(self):
        self.parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
        self.parser.add_argument("name", metavar="NAME", nargs="*", help="Set the name of container/image or commands[history|inspect|imports|export|rm|rmi]")
        self.parser.add_argument("--uname", "-u", help="The login USER name")
        self.parser.add_argument("--docker", "-d", help="Path to the docker file")
        self.parser.add_argument("--share", "-s", nargs="*", help="Path to the shared folders")
        self.parser.add_argument("--container", "-c", help="Name of the container what you want to run")
        self.parser.add_argument("--cmd", nargs="+", help="Set extended command")
        self.parser.add_argument("--cert", action="store_true", help="Share the host cert")
        self.parser.add_argument("--force", "-f", action="store_true", help="Do not use cache when building the image")
        self.args = self.parser.parse_args()
        print(self.args)

        self.container = get_container(self.args.container)
        method = self.args.name[0] if self.args.name else ""
        self.method = getattr(self, method, self.default)

    def start(self):
        self.sub_args = self.parser.parse_args(sys.argv[2:])
        self.method()

    def _build(self):
        print(self.sub_args)

    def _run(self):
        print(f"run: {self.sub_args}")

    def history(self):
        print(self.sub_args)

    def inspect(self):
        print(self.sub_args)

    def imports(self):
        REPOSITORY = self.sub_args.name[0]
        if self.args.cmd:
            EXT_CMD = ",".join(f'"{cmd}"' for cmd in self.sub_args.cmd)
            runshell(f"docker import {self.sub_args.docker} {REPOSITORY} --change 'ENTRYPOINT [{EXT_CMD}]'")
        else:
            runshell(f"docker import {self.sub_args.docker} {REPOSITORY}")

    def export(self):
        runshell(f"docker export {self.container} --output {self.sub_args.docker}")

    def rm(self):
        _container = get_container(self.sub_args.name[0])
        if _container is not None:
            print(f"remove container {_container}")
            runshell(f"docker rm {_container}")

    def rmi(self):
        _image = get_image(self.sub_args.name[0])
        if _image is not None:
            _containers = ",".join(get_containers(_image))
            print(f"remove docker image {_image} / {_containers}")
            if _containers:
                runshell(f"docker rm -f {_containers}")
            runshell(f"docker rmi {_image}")

    def default(self):
        print("main")
        print(self.sub_args)


def main():
    mydocker = DockerMaster()
    mydocker.start()


import sys
import traceback

if __name__ == "__main__":
    main()
