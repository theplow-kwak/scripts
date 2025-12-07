#!/usr/bin/python3

import os
import logging
import argparse
import shlex
import subprocess
import sys
from pathlib import Path


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
                logger.debug(f"Return code: {completed.returncode}, stdout: {completed.stdout.rstrip()}\n<<<<\n")
            return completed.stdout.rstrip() if completed.stdout else ""


def _get_docker_items(cmd: str, key: str):
    _result = run_command(cmd)
    items = sorted(_result.split("\n")) if _result else []
    return items


def get_image(image: str):
    images = _get_docker_items("docker images --format '{{.Repository}}'", "Repository")
    return next((item for item in images if item == image), None)


def get_image_id(image: str):
    ids = _get_docker_items("docker images --format '{{.ID}}'", "ID")
    return next((item for item in ids if item == image), None)


def get_containers(image: str):
    return _get_docker_items(f"docker ps -a --filter 'ancestor={image}'" + " --format '{{.Names}}'", "Names")


def get_container(container: str):
    containers = _get_docker_items("docker ps -a --format '{{.Names}}'", "Names")
    return next((item for item in containers if item == container), None)


def get_container_id(container: str):
    ids = _get_docker_items("docker ps -a --format '{{.ID}}'", "ID")
    return next((item for item in ids if item == container), None)


class DockerMaster(object):
    def __init__(self):
        self.method_list = [func for func in dir(self) if callable(getattr(self, func)) and not func.startswith("__") and not func.startswith("_")]
        self.parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
        self.parser.add_argument("name", metavar="NAME", nargs="*", help=f"Set the name of container/image\n or commands [{'|'.join(self.method_list)}]")
        self.parser.add_argument("--uname", "-u", default=os.getlogin(), help="Set login user name")
        self.parser.add_argument("--uid", "-U", default=os.getuid(), help="Set login user id")
        self.parser.add_argument("--docker", "-d", help="Path to the docker file")
        self.parser.add_argument("--share", "-s", nargs="+", help="Path to the shared folders")
        self.parser.add_argument("--container", "-c", help="Name of the container what you want to run")
        self.parser.add_argument("--extcmd", nargs="+", help="Set extended command")
        self.parser.add_argument("--cert", action="store_true", help="Share the host cert")
        self.parser.add_argument("--force", "-f", action="store_true", help="Do not use cache when building the image")
        self.args = self.parser.parse_args()

        _method = self.args.name.pop(0) if self.args.name and self.args.name[0] in self.method_list else ""
        self.name = self.args.name[0] if self.args.name else ""
        self.method = getattr(self, _method, self._default)

    def start(self):
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
        if not self.container:
            self.container = get_container_id(self.name)
        self.image = get_image(self.name)
        if not self.image:
            self.image = get_image_id(self.name)
        if not self.image and self.container:
            self.image = run_command(f"docker ps -a --filter 'name=^/{self.container}$'" + " --format '{{.Image}}'")
        print(f"Image    : {self.image}")
        print(f"Container: {self.container}")
        print(f"Name     : {self.name}\n")
        self.method()

    def _build(self):
        if not self.args.docker:
            logger.error("Docker build: A dockerfile must be specified. Specify it using '--docker' or '-d'.")
            return
        docker_cmd = [f"docker build -t {self.name} --network=host"]
        if self.args.force:
            docker_cmd += ["--no-cache"]
        if self.args.uname != "root":
            docker_cmd += [f"--build-arg NEWUSER={self.args.uname} --build-arg NEWUID={self.args.uid}"]
        docker_cmd += [f"{self.docker_dir}"]
        if self.docker_file:
            docker_cmd += [f"-f {self.docker_dir}/{self.docker_file}"]
        print(" ".join(docker_cmd))
        run_command(docker_cmd, _consol=True)

    def _run(self):
        _container = self.args.container if not self.container and self.args.container else self.name
        workdir = ""
        docker_cmd = [f"docker run -it --user {self.args.uname}", "-v /etc/timezone:/etc/timezone:ro", "-e TZ=Asia/Seoul", f"--hostname {_container}"]
        if self.args.cert:
            if Path("/etc/ssl/certs").exists():
                docker_cmd += ["-v /etc/ssl/certs:/etc/ssl/certs:ro"]
            if Path("/etc/pki/ca-trust").exists():
                docker_cmd += ["-v /etc/pki/ca-trust:/etc/pki/ca-trust:ro"]
        home_folder = "/root" if self.args.uname == "root" else f"/home/{self.args.uname}"
        if self.args.share:
            for share in self.args.share:
                _share = share.split(":")
                _path = Path(_share[0])
                if _path.exists():
                    docker_cmd += [f"--mount type=bind,source='{_path.resolve()}',target='{home_folder}/{_share[1] if len(_share) > 1 else _path.name}'"]
                    if not workdir:
                        workdir = _share[1] if len(_share) > 1 else _path.name
        docker_cmd += [f"--workdir '{home_folder}/{workdir}'"]
        docker_cmd += [f"--name {_container} {self.image}"]
        _EXT_CMD = " ".join(self.args.extcmd) if self.args.extcmd else "/bin/bash"
        docker_cmd += [f"{_EXT_CMD}"]
        print(" ".join(docker_cmd))
        run_command(docker_cmd, _consol=True)

    def history(self):
        if self.image:
            print(run_command("docker history --human --format '{{.CreatedBy}}: {{.Size}}'" + f" {self.image}"))

    def inspect(self):
        if self.container:
            print(run_command("docker inspect --format 'User:       {{.Config.User}}'" + f" {self.container}"))
            print(run_command('docker inspect --format \'Entrypoint: {{join .Config.Entrypoint " "}} {{join .Config.Cmd " "}}\'' + f" {self.container}"))
            print(run_command("docker inspect --format 'WorkingDir: {{.Config.WorkingDir}}'" + f" {self.container}"))
            print("Mounts:")
            print(run_command('docker inspect --format \'{{range .Mounts}}{{println " " .Source "\t-> " .Destination}}{{end}}\'' + f" {self.container}"))
        elif self.image:
            print(run_command("docker inspect --format 'User:       {{.Config.User}}'" + f" {self.image}"))
            print(run_command("docker inspect --format 'Cmd:        {{join .Config.Cmd \" \"}}'" + f" {self.image}"))
            print(run_command("docker inspect --format 'Entrypoint: {{join .Config.Entrypoint \" \"}}'" + f" {self.image}"))

    def imports(self):
        if not self.args.docker:
            logger.error("Docker import: A dockerfile must be specified. Specify it using '--docker' or '-d'.")
            return
        _name = self.args.name[0] if self.args.name else self.docker_file.split(".")[0]
        docker_cmd = [f"docker import {self.args.docker} {_name}"]
        if self.args.extcmd:
            _EXT_CMD = ",".join(f'"{cmd}"' for cmd in self.args.extcmd)
            docker_cmd += [f"--change 'ENTRYPOINT [{_EXT_CMD}]'"]
        print(" ".join(docker_cmd))
        run_command(docker_cmd, _consol=True)

    def export(self):
        if not self.args.docker:
            logger.error("Docker export: A dockerfile must be specified. Specify it using '--docker' or '-d'.")
            return
        run_command(f"docker export {self.container} --output {self.args.docker}", _consol=True)

    def rm(self):
        if self.container:
            print(f"remove container {self.container}")
            run_command(f"docker rm {self.container}", _consol=True)

    def rmi(self):
        if self.image:
            _containers = " ".join(get_containers(self.image))
            print(f"remove docker image {self.image} / {_containers}")
            if _containers:
                run_command(f"docker rm -f {_containers}", _consol=True)
            run_command(f"docker rmi {self.image}", _consol=True)

    def status(self):
        run_command("systemctl status docker.service", _consol=True)

    def restart(self):
        run_command("systemctl stop docker", _consol=True)
        run_command("sudo rm -rf /var/lib/docker/network", _consol=True)
        run_command("systemctl start docker", _consol=True)

    def restart_network(self):
        run_command("virsh net-destroy default", _consol=True)
        run_command("virsh net-edit default", _consol=True)
        run_command("virsh net-start default", _consol=True)
        run_command("virsh net-autostart default", _consol=True)
        run_command("systemctl restart docker", _consol=True)

    def _default(self):
        if len(sys.argv) < 2:
            print(run_command("docker images") + "\n")
            print(run_command("docker ps -a") + "\n")
            return
        if not self.image:  # or not runshell(f"docker images -q --filter reference={self.name}")
            self._build()
            return
        has_container = run_command(f"docker ps -a --filter 'name=^/{self.args.container}$'" + " --format '{{.Names}}'")
        if not self.container and not has_container:
            self._run()
            return
        is_started = run_command(f"docker ps --filter 'name=^/{self.container}$'" + " --format '{{.Image}}'")
        if not is_started:
            print(f"docker start {self.container}")
            run_command(f"docker start {self.container}")
        print(f"docker attach {self.container}")
        run_command(f"docker attach {self.container}", _consol=True)


def main():
    mydocker = DockerMaster()
    mydocker.start()


if __name__ == "__main__":
    main()
