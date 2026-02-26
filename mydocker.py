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
    """Run a shell command; return stdout when ``capture`` is True."""

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
    """Return sorted output for docker query."""

    out = run_command(f"docker {filter_expr} --format '{format_str}'")
    return sorted(out.splitlines()) if out else []


def _lookup(fmt: str, filter_expr: str, match: str) -> str | None:
    """Find *match* in ``_docker_list`` results."""
    return next((i for i in _docker_list(fmt, filter_expr) if i == match), None)


def get_image(name: str) -> str | None:
    return _lookup("{{.Repository}}", "images", name)


def get_image_id(image_id: str) -> str | None:
    return _lookup("{{.ID}}", "images", image_id)


def get_containers(image: str) -> list[str]:
    return _docker_list("{{.Names}}", f"ps -a --filter 'ancestor={image}'")


def get_container(name: str) -> str | None:
    return _lookup("{{.Names}}", "ps -a", name)


def get_container_id(cid: str) -> str | None:
    return _lookup("{{.ID}}", "ps -a", cid)


class DockerMaster:
    """CLI driver for docker operations."""

    COMMANDS = (
        "build",
        "run",
        "history",
        "inspect",
        "imports",
        "export",
        "rm",
        "rmi",
        "pull",
        "status",
        "restart",
        "restart_network",
    )

    def __init__(self) -> None:
        parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
        for args, kwargs in (
            (("command",), dict(nargs="?", help="Operation to perform")),
            (("name",), dict(nargs="?", help="container/image name or dockerfile path")),
            (("--uname", "-n"), dict(default=os.getlogin(), help="login user name")),
            (("--uid", "-U"), dict(type=int, default=self._get_uid(), help="login user id")),
            (("--docker", "-d"), dict(help="Path to dockerfile or image tarball")),
            (("--alias", "-a"), dict(help="local name/tag to give pulled image")),
            (("--share", "-s"), dict(nargs="+", help="bind mount(s) in the form src[:dest]; use quoting on Windows to avoid splitting drive letters")),
            (("--container", "-c"), dict(help="container name to operate on")),
            (("--extcmd",), dict(nargs="+", help="extra command/entrypoint")),
            (("--cert",), dict(action="store_true", help="mount host certificates")),
            (("--force", "-f"), dict(action="store_true", help="disable build cache")),
        ):
            parser.add_argument(*args, **kwargs)  # pyright: ignore[reportArgumentType]
        self.args = parser.parse_args()

        # if first arg isn't a known command, use it as name
        if (cmd := self.args.command) and cmd not in self.COMMANDS:
            self.name, self.command = cmd, "default"
        else:
            self.name, self.command = self.args.name or "", cmd or "default"

    def _get_uid(self) -> int:
        # fall back to 1000 on platforms without os.getuid
        return getattr(os, "getuid", lambda: 1000)()  # pyright: ignore[reportAttributeAccessIssue]

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
        self.container = get_container(cname := self.args.container or self.name) or get_container_id(self.name)
        self.image = (
            get_image(name := self.name)
            or get_image_id(name)
            or (run_command(f"docker ps -a --filter 'name=^/{self.container}$' --format '{{{{.Image}}}}'") if self.container else "")
        )

        # display basic metadata
        for k, v in ("Image", self.image), ("Container", self.container), ("Name", self.name):
            print(f"{k:9}: {v}")
        print()

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
                parsed = self._parse_share(s)
                if not parsed:
                    continue
                srcp, target = parsed
                src_str = str(srcp.resolve()) if platform.system() == "Windows" else srcp.resolve().as_posix()
                target_path = join_container(home, target)
                cmd += ["--mount", f"type=bind,source={src_str},target={target_path}"]
                if not workdir:
                    workdir = target

        if not is_win:
            cmd += ["--user", self.args.uname, "-v", "/etc/timezone:/etc/timezone:ro"]
        if workdir:
            cmd += ["--workdir", join_container(home, workdir)]

        cmd += ["--name", container, self.image or ""]

        ext = " ".join(self.args.extcmd) if self.args.extcmd else ("powershell.exe" if is_win else "/bin/bash")
        if ext:
            cmd.append(ext)

        print(" ".join(cmd))
        run_command(cmd, console=True)

    def _is_windows_container(self) -> bool:
        """Return True if image OS is Windows (empty image -> False)."""
        if not self.image:
            return False
        return run_command(f"docker inspect --format '{{{{.Os}}}}' {self.image}").strip().lower() == "windows"

    def _parse_share(self, spec: str) -> tuple[Path, str] | None:
        """Parse ``src[:dest]`` share spec, ignoring drive-letter colon."""

        # find last colon that's not the Windows drive-letter
        sep = spec.rfind(":")
        if sep > 1:
            src, dst = spec[:sep], spec[sep + 1 :]
        else:
            src, dst = spec, ""

        srcp = Path(src)
        if not srcp.exists():
            return None
        return srcp, dst or srcp.name

    def _container_paths(self) -> tuple[bool, str, Any]:
        """Return is_win flag, home dir and join func for container."""

        is_win = self._is_windows_container()
        home = f"C:\\Users\\{self.args.uname}" if is_win else ("/root" if self.args.uname == "root" else f"/home/{self.args.uname}")
        join = (lambda b, s: f"{b}\\{s}") if is_win else (lambda b, s: f"{b}/{s}")
        return is_win, home, join

    def history(self) -> None:
        self.image and print(run_command(f"docker history --human --format '{{{{.CreatedBy}}}}: {{.Size}}' {self.image}"))  # pyright: ignore[reportUnusedExpression]

    def inspect(self) -> None:
        target = self.container or self.image
        if not target:
            return
        if self.container:
            for f in (
                "User:       {{.Config.User}}",
                'Entrypoint: {{join .Config.Entrypoint " "}} {{join .Config.Cmd " "}}',
                "WorkingDir: {{.Config.WorkingDir}}",
            ):
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
            return logger.error("--docker/-d required for import")
        name = self.args.name or self.docker_file.split(".")[0]
        cmd = ["docker", "import", self.args.docker, name]
        if self.args.extcmd:
            extcmd = ",".join(f'"{c}"' for c in self.args.extcmd)
            cmd += ["--change", f"ENTRYPOINT [{extcmd}]"]
        print(" ".join(cmd))
        run_command(cmd, console=True)

    def export(self) -> None:
        if not self.args.docker:
            return logger.error("--docker/-d required for export")
        run_command(f"docker export {self.container} --output {self.args.docker}", console=True)

    def rm(self) -> None:
        if self.container:
            print(f"remove container {self.container}")
            run_command(f"docker rm {self.container}", console=True)

    def rmi(self) -> None:
        if self.image:
            conts = " ".join(get_containers(self.image))
            print(f"remove docker image {self.image} / {conts}")
            conts and run_command(f"docker rm -f {conts}", console=True)  # pyright: ignore[reportUnusedExpression]
            run_command(f"docker rmi {self.image}", console=True)

    def status(self) -> None:
        run_command("systemctl status docker.service", console=True)

    def restart(self) -> None:
        for cmd in ("systemctl stop docker", "sudo rm -rf /var/lib/docker/network", "systemctl start docker"):
            run_command(cmd, console=True)

    def restart_network(self) -> None:
        for cmd in (
            "virsh net-destroy default",
            "virsh net-edit default",
            "virsh net-start default",
            "virsh net-autostart default",
            "systemctl restart docker",
        ):
            run_command(cmd, console=True)

    def pull(self) -> None:
        """Pull an image from a registry, optionally tagging it locally.

        If ``--alias`` was supplied, the image will be re-tagged after pulling.
        """
        image = self.name
        if not image:
            logger.error("Specify an image name to pull")
            return
        alias = self.args.alias
        print(f"docker pull {image}")
        run_command(f"docker pull {image}", console=True)
        if alias:
            print(f"docker tag {image} {alias}")
            run_command(f"docker tag {image} {alias}", console=True)

    def _default(self) -> None:
        # no arguments: show list
        if self.command == "default" and not self.name:
            for cmd in ("docker images", "docker ps -a"):
                print(run_command(cmd) + "\n")
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
