#!/usr/bin/env python3
"""Simple Docker helper with build/run and inspection shortcuts."""

import argparse
import logging
import os
import platform
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def run_command(cmd, *, capture: bool = True, console: bool = False, async_: bool = False) -> str:
    """Run a shell command.

    * ``cmd`` may be a string or sequence.  Returns stripped stdout when
    ``capture`` is True; otherwise returns an empty string.  ``console``
    forwards output to the terminal.  ``async_`` starts the process and
    immediately returns.
    """

    if isinstance(cmd, (list, tuple)):
        args = list(cmd)
    else:
        args = shlex.split(cmd)

    if async_:
        subprocess.Popen(args)
        return ""

    kwargs: dict[str, Any] = {"text": True}
    if capture and not console:
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    proc = subprocess.run(args, **kwargs)
    if capture and proc.stdout:
        output = proc.stdout.strip()
        logger.debug("Return code: %s, stdout: %r", proc.returncode, output)
        return output
    return ""


# -- helpers ---------------------------------------------------------------


def _docker_list(format_str: str, filter_expr: str = "") -> list[str]:
    """Query docker and return sorted lines from ``--format`` output."""

    cmd = f"docker {filter_expr} --format '{format_str}'"
    out = run_command(cmd)
    return sorted(out.splitlines()) if out else []


def get_image(name: str) -> str | None:
    return next((i for i in _docker_list("{{.Repository}}", "images") if i == name), None)


def get_image_id(image_id: str) -> str | None:
    return next((i for i in _docker_list("{{.ID}}", "images") if i == image_id), None)


def get_containers(image: str) -> list[str]:
    return _docker_list("{{.Names}}", f"ps -a --filter 'ancestor={image}'")


def get_container(name: str) -> str | None:
    return next((c for c in _docker_list("{{.Names}}", "ps -a") if c == name), None)


def get_container_id(cid: str) -> str | None:
    return next((i for i in _docker_list("{{.ID}}", "ps -a") if i == cid), None)


class DockerMaster:
    """Command-line driver for various docker operations."""

    COMMANDS = (
        "build",
        "run",
        "history",
        "inspect",
        "imports",
        "export",
        "rm",
        "rmi",
        "status",
        "restart",
        "restart_network",
    )

    def __init__(self) -> None:
        parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
        parser.add_argument("command", nargs="?", help="Operation to perform")
        parser.add_argument("name", nargs="?", help="container/image name or dockerfile path")
        parser.add_argument("--uname", "-n", default=os.getlogin(), help="login user name")
        parser.add_argument("--uid", "-U", type=int, default=self._get_uid(), help="login user id")
        parser.add_argument("--docker", "-d", help="Path to dockerfile or image tarball")
        parser.add_argument("--share", "-s", nargs="+", help="bind mount(s) in the form src[:dest]; use quoting on Windows to avoid splitting drive letters")
        parser.add_argument("--container", "-c", help="container name to operate on")
        parser.add_argument("--extcmd", nargs="+", help="extra command/entrypoint")
        parser.add_argument("--cert", action="store_true", help="mount host certificates")
        parser.add_argument("--force", "-f", action="store_true", help="disable build cache")
        self.args = parser.parse_args()

        # if the first positional argument is not a known command then treat it
        # as the "name" instead and default the command to "default".
        if self.args.command and self.args.command not in self.COMMANDS:
            self.name = self.args.command
            self.command = "default"
        else:
            self.name = self.args.name or ""
            self.command = self.args.command or "default"

    def _get_uid(self) -> int:
        try:
            return os.getuid()  # pyright: ignore[reportAttributeAccessIssue]
        except AttributeError:
            return 1000

    def start(self) -> None:
        # resolve dockerfile / image name
        if self.args.docker:
            path = Path(self.args.docker).resolve()
            if path.is_file():
                self.docker_dir = path.parent
                self.docker_file = path.name
            else:
                self.docker_dir = path
                self.docker_file = ""
            self.name = self.name or self.docker_dir.name

        # look up container/image metadata
        self.container = get_container(self.args.container or self.name) or get_container_id(self.name)
        self.image = (
            get_image(self.name)
            or get_image_id(self.name)
            or (run_command(f"docker ps -a --filter 'name=^/{self.container}$' --format '{{{{.Image}}}}'") if self.container else "")
        )

        print(f"Image    : {self.image}")
        print(f"Container: {self.container}")
        print(f"Name     : {self.name}\n")

        getattr(self, f"{self.command}", self._default)()

    def _build(self) -> None:
        if not self.args.docker:
            logger.error("Specify a Dockerfile with --docker/-d.")
            return
        cmd = ["docker", "build", "-t", self.name, "--network=host"]
        if self.args.force:
            cmd.append("--no-cache")
        if self.args.uname != "root":
            cmd += ["--build-arg", f"NEWUSER={self.args.uname}", "--build-arg", f"NEWUID={self.args.uid}"]
        cmd.append(str(self.docker_dir))
        if getattr(self, "docker_file", ""):
            cmd += ["-f", str(self.docker_dir / self.docker_file)]
        print(" ".join(cmd))
        run_command(cmd, console=True)

    def _run(self) -> None:
        container = self.args.container or self.name
        is_win, home, join_container = self._container_paths()
        cmd = ["docker", "run", "-it", "-e", "TZ=Asia/Seoul", "--hostname", container]

        if not is_win and self.args.cert:
            for path in ("/etc/ssl/certs", "/etc/pki/ca-trust"):
                if Path(path).exists():
                    cmd += ["-v", f"{path}:{path}:ro"]

        workdir = ""
        if self.args.share:
            for s in self.args.share:
                parts = s.rsplit(":", 1)
                src = parts[0]
                dst = parts[1] if len(parts) > 1 else ""
                srcp = Path(src)
                if not srcp.exists():
                    continue
                target = dst if dst else srcp.name

                # build source path string appropriate for the host
                if platform.system() == "Windows":
                    src_str = str(srcp.resolve())
                else:
                    # convert to posix style for linux/docker compatibility
                    src_str = srcp.resolve().as_posix()

                # build target path inside container based on container_os
                target_path = join_container(home, target)

                cmd += ["--mount", f"type=bind,source={src_str},target={target_path}"]
                if not workdir:
                    workdir = target

        if not is_win:
            cmd += ["--user", self.args.uname, "-v", "/etc/timezone:/etc/timezone:ro"]
        if workdir:
            cmd += ["--workdir", join_container(home, workdir)]

        cmd += ["--name", container, self.image or ""]

        if self.args.extcmd:
            ext = " ".join(self.args.extcmd)
        else:
            ext = "powershell.exe" if is_win else "/bin/bash"

        if ext:
            cmd.append(ext)

        print(" ".join(cmd))
        run_command(cmd, console=True)

    def _is_windows_container(self) -> bool:
        """Return True if the current image/container appears to be Windows.

        Falls back to False when the image is unknown or inspection fails.
        """

        if not self.image:
            return False
        os_val = run_command(f"docker inspect --format '{{{{.Os}}}}' {self.image}")
        return os_val.strip().lower() == "windows" if os_val else False

    def _container_paths(self) -> tuple[bool, str, Any]:
        """Helper returning (is_windows, home, join_func) for the container.

        The join_func takes (base, sub) and constructs a platform-appropriate
        path inside the container.
        """

        is_win = self._is_windows_container()
        if is_win:
            home = f"C:\\Users\\{self.args.uname}"
            join = lambda base, sub: f"{base}\\{sub}"
        else:
            home = "/root" if self.args.uname == "root" else f"/home/{self.args.uname}"
            join = lambda base, sub: f"{base}/{sub}"
        return is_win, home, join

    def history(self) -> None:
        if self.image:
            print(run_command(f"docker history --human --format '{{{{.CreatedBy}}}}: {{.Size}}' {self.image}"))

    def inspect(self) -> None:
        target = self.container or self.image
        if not target:
            return
        if self.container:
            fmt = [
                "User:       {{.Config.User}}",
                'Entrypoint: {{join .Config.Entrypoint " "}} {{join .Config.Cmd " "}}',
                "WorkingDir: {{.Config.WorkingDir}}",
            ]
            for f in fmt:
                print(run_command(f"docker inspect --format '{f}' {self.container}"))
            print("Mounts:")
            print(run_command('docker inspect --format \'{{range .Mounts}}{{println "-" .Source "\t-> " .Destination}}{{end}}\'' + f" {self.container}"))
        else:
            for f in (
                "User:       {{.Config.User}}",
                'Cmd:        {{join .Config.Cmd " "}}',
                'Entrypoint: {{join .Config.Entrypoint " "}}',
            ):
                print(run_command(f"docker inspect --format '{f}' {self.image}"))

    def imports(self) -> None:
        if not self.args.docker:
            logger.error("--docker/-d required for import")
            return
        name = self.args.name or self.docker_file.split(".")[0]
        cmd = ["docker", "import", self.args.docker, name]
        if self.args.extcmd:
            ext = ",".join(f'"{c}"' for c in self.args.extcmd)
            cmd += ["--change", f"ENTRYPOINT [{ext}]"]
        print(" ".join(cmd))
        run_command(cmd, console=True)

    def export(self) -> None:
        if not self.args.docker:
            logger.error("--docker/-d required for export")
            return
        run_command(f"docker export {self.container} --output {self.args.docker}", console=True)

    def rm(self) -> None:
        if self.container:
            print(f"remove container {self.container}")
            run_command(f"docker rm {self.container}", console=True)

    def rmi(self) -> None:
        if self.image:
            conts = " ".join(get_containers(self.image))
            print(f"remove docker image {self.image} / {conts}")
            if conts:
                run_command(f"docker rm -f {conts}", console=True)
            run_command(f"docker rmi {self.image}", console=True)

    def status(self) -> None:
        run_command("systemctl status docker.service", console=True)

    def restart(self) -> None:
        run_command("systemctl stop docker", console=True)
        run_command("sudo rm -rf /var/lib/docker/network", console=True)
        run_command("systemctl start docker", console=True)

    def restart_network(self) -> None:
        for cmd in (
            "virsh net-destroy default",
            "virsh net-edit default",
            "virsh net-start default",
            "virsh net-autostart default",
            "systemctl restart docker",
        ):
            run_command(cmd, console=True)

    def _default(self) -> None:
        # no arguments: show list
        if self.command == "default" and not self.name:
            print(run_command("docker images") + "\n")
            print(run_command("docker ps -a") + "\n")
            return

        if not self.image:
            self._build()
            return

        has_ct = run_command(f"docker ps -a --filter 'name=^/{self.args.container}$' --format '{{{{.Names}}}}'")
        if not self.container and not has_ct:
            self._run()
            return

        started = run_command(f"docker ps --filter 'name=^/{self.container}$' --format '{{{{.Image}}}}'")
        if not started:
            print(f"docker start {self.container}")
            run_command(f"docker start {self.container}")
        print(f"docker attach {self.container}")
        run_command(f"docker attach {self.container}", console=True)


def main():
    mydocker = DockerMaster()
    mydocker.start()


if __name__ == "__main__":
    main()
