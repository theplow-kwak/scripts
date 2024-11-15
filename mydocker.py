#!/usr/bin/python3

import os
import logging
import argparse
import shlex
import subprocess
from pathlib import Path


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


def runshell(cmd, _async=False, _consol=False):
    if isinstance(cmd, list):
        cmd = " ".join(cmd)
    _cmd = shlex.split(cmd)
    if _async:
        completed = subprocess.Popen(_cmd)
    else:
        if _consol:
            completed = subprocess.run(_cmd, text=True)
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
        self.method_list = [func for func in dir(self) if callable(getattr(self, func)) and not func.startswith("__") and not func.startswith("_")]
        self.parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
        self.parser.add_argument("name", metavar="NAME", nargs="*", help=f"Set the name of container/image\n or commands [{'|'.join(self.method_list)}]")
        self.parser.add_argument("--uname", "-u", default=os.getlogin(), help="Set login user name")
        self.parser.add_argument("--docker", "-d", help="Path to the docker file")
        self.parser.add_argument("--share", "-s", nargs="+", help="Path to the shared folders")
        self.parser.add_argument("--container", "-c", help="Name of the container what you want to run")
        self.parser.add_argument("--extcmd", nargs="+", help="Set extended command")
        self.parser.add_argument("--cert", action="store_true", help="Share the host cert")
        self.parser.add_argument("--force", "-f", action="store_true", help="Do not use cache when building the image")
        self.args = self.parser.parse_args()

        _method = self.args.name[0] if self.args.name else ""
        self.name = self.args.name[-1] if self.args.name else ""
        self.method = getattr(self, _method, self._default)

    def _start(self):
        if self.args.docker:
            _DOCKERPATH = Path(self.args.docker).resolve()
            if _DOCKERPATH.is_file():
                self.docker_dir = _DOCKERPATH.parent
                self.docker_file = _DOCKERPATH.name
            else:
                self.docker_dir = _DOCKERPATH
                self.docker_file = ""
            if not self.name:
                self.name = self.docker_dir.name
        self.container = get_container(self.args.container) if self.args.container else get_container(self.name)
        self.image = get_image(self.name)
        if not self.image and self.container:
            self.image = runshell(f"docker ps -a --filter 'name=^/{self.container}$'" + " --format '{{.Image}}'").stdout.rsplit()[0]
        print(f"Image    : {self.image}")
        print(f"Container: {self.container}")
        print(f"Name     : {self.name}\n")
        self.method()

    def _build(self):
        if not self.args.docker:
            mylogger.error("Docker build: A dockerfile must be specified. Specify it using '--docker' or '-d'.")
            return
        docker_cmd = [f"docker build -t {self.name} --network=host"]
        if self.args.force:
            docker_cmd += ["--no-cache"]
        if os.getlogin() != "root":
            docker_cmd += [f"--build-arg NEWUSER={os.getlogin()} --build-arg NEWUID={os.getuid()}"]
        docker_cmd += [f"{self.docker_dir}"]
        if self.docker_file:
            docker_cmd += [f"-f {self.docker_dir}/{self.docker_file}"]
        print(" ".join(docker_cmd))
        runshell(docker_cmd, _consol=True)

    def _run(self):
        _CONTAINER = self.args.container if not self.container and self.args.container else self.name
        WORKDIR = ""
        docker_cmd = [f"docker run -it --user {self.args.uname}", "-v /etc/timezone:/etc/timezone:ro", "-e TZ=Asia/Seoul", f"--hostname {_CONTAINER}"]
        if self.args.cert:
            if Path("/etc/ssl/certs").exists():
                docker_cmd += ["-v /etc/ssl/certs:/etc/ssl/certs:ro"]
            if Path("/etc/pki/ca-trust").exists():
                docker_cmd += ["-v /etc/pki/ca-trust:/etc/pki/ca-trust:ro"]
        HOME_FOLDER = "/root" if self.args.uname == "root" else f"/home/{self.args.uname}"
        if self.args.share:
            for share in self.args.share:
                _share = share.split(":")
                _path = Path(_share[0])
                if _path.exists():
                    docker_cmd += [f"--mount type=bind,source='{_path.resolve()}',target='{HOME_FOLDER}/{_share[1] if len(_share) > 1 else _path.name}'"]
                    if not WORKDIR:
                        WORKDIR = _share[1] if len(_share) > 1 else _path.name
        docker_cmd += [f"--workdir '{HOME_FOLDER}/{WORKDIR}'"]
        docker_cmd += [f"--name {_CONTAINER} {self.image}"]
        _EXT_CMD = " ".join(self.args.extcmd) if self.args.extcmd else "/bin/bash"
        docker_cmd += [f"{_EXT_CMD}"]
        print(" ".join(docker_cmd))
        runshell(docker_cmd, _consol=True)

    def history(self):
        print(runshell("docker history --human --format '{{.CreatedBy}}: {{.Size}}'" + f" {self.image}").stdout.rstrip())

    def inspect(self):
        print(runshell("docker inspect --format 'User:       {{.Config.User}}'" + f" {self.container}").stdout.rstrip())
        print(runshell("docker inspect --format 'Args:       {{.Path}} {{join .Args \" \"}}'" + f" {self.container}").stdout.rstrip())
        print(runshell("docker inspect --format 'WorkingDir: {{.Config.WorkingDir}}'" + f" {self.container}").stdout.rstrip())
        print("Mounts:")
        print(runshell('docker inspect --format \'{{range .Mounts}}{{println " " .Source "\t-> " .Destination}}{{end}}\'' + f" {self.container}").stdout.rstrip())

    def imports(self):
        if self.args.extcmd:
            _EXT_CMD = ",".join(f'"{cmd}"' for cmd in self.args.extcmd)
            runshell(f"docker import {self.args.docker} {self.name} --change 'ENTRYPOINT [{_EXT_CMD}]'", _consol=True)
        else:
            runshell(f"docker import {self.args.docker} {self.name}", _consol=True)

    def export(self):
        runshell(f"docker export {self.container} --output {self.args.docker}", _consol=True)

    def rm(self):
        if self.container:
            print(f"remove container {self.container}")
            runshell(f"docker rm {self.container}", _consol=True)

    def rmi(self):
        if self.image is not None:
            _containers = " ".join(get_containers(self.image))
            print(f"remove docker image {self.image} / {_containers}")
            if _containers:
                runshell(f"docker rm -f {_containers}", _consol=True)
            runshell(f"docker rmi {self.image}", _consol=True)

    def _default(self):
        if len(sys.argv) < 2:
            print(runshell("docker images").stdout)
            print(runshell("docker ps -a").stdout)
            return
        if not self.image:  # or not runshell(f"docker images -q --filter reference={self.name}").stdout
            self._build()
            return
        has_container = runshell(f"docker ps -a --filter 'name=^/{self.args.container}$'" + " --format '{{.Names}}'").stdout
        if not self.container and not has_container:
            self._run()
            return
        is_started = runshell(f"docker ps --filter 'name=^/{self.container}$'" + " --format '{{.Names}}'").stdout
        if not is_started:
            print(f"docker start {self.container}")
            runshell(f"docker start {self.container}")
        print(f"docker attach {self.container}")
        runshell(f"docker attach {self.container}", _consol=True)


def main():
    mydocker = DockerMaster()
    mydocker._start()


import sys
import traceback

if __name__ == "__main__":
    main()
