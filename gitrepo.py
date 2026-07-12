#!/usr/bin/env python3
"""Manage simple local Git repository workflows from the command line.

This script preserves the original shell interface and adds a more robust
Python implementation for:
- initializing a bare remote repository on a local Git server
- initializing a local working repository from that remote
- attaching a remote to an existing repository
- creating an archive of selected files between commits
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence

DEFAULT_REMOTE_NAME = "origin"
DEFAULT_SERVER_ROOT = "/home/git"
DEFAULT_REMOTE_URL_TEMPLATE = "git@localhost:/home/git/{repo}.git"


class GitRepoError(RuntimeError):
    """Raised when repository operations fail."""


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manage local and remote Git repositories",
    )
    parser.add_argument("-s", "--server", action="store_true", help="Initialize a remote repository")
    parser.add_argument("-l", "--local", action="store_true", help="Initialize a local repository")
    parser.add_argument("-r", "--remote", dest="remote", help="Remote repository URL or path")
    parser.add_argument("-n", "--name", dest="repo_name", default=DEFAULT_REMOTE_NAME, help="Remote name")
    parser.add_argument("--patch", action="store_true", help="Create an archive from changes between commits")
    parser.add_argument("--commit1", default="HEAD~1", help="First commit for patch generation")
    parser.add_argument("--commit2", default="HEAD", help="Second commit for patch generation")
    parser.add_argument("--folder", default="", help="Optional folder to include in the archive")
    parser.add_argument("--archive", default="../archive.zip", help="Archive output path")
    parser.add_argument("repo", nargs="?", help="Repository name or path")
    return parser.parse_args(argv)


def build_remote_url(repo: str, remote: Optional[str] = None) -> str:
    if remote:
        return remote
    normalized = repo.strip().strip("/")
    return DEFAULT_REMOTE_URL_TEMPLATE.format(repo=normalized)


def run_command(command: Sequence[str], cwd: Optional[Path] = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        list(command),
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and completed.returncode != 0:
        stderr = completed.stderr.strip() or completed.stdout.strip()
        raise GitRepoError(f"Command failed: {' '.join(command)}\n{stderr}")
    return completed


def ensure_git_repo(path: Path) -> None:
    if not path.exists():
        raise GitRepoError(f"Local repository {path} does not exist")
    if not (path / ".git").exists():
        run_command(["git", "init"], cwd=path)


def detect_default_branch(repo_path: Path, remote_name: str) -> Optional[str]:
    completed = run_command(["git", "ls-remote", "--symref", remote_name, "HEAD"], cwd=repo_path, check=False)
    if completed.returncode != 0:
        return None
    for line in completed.stdout.splitlines():
        if line.startswith("ref:") and "HEAD" in line:
            parts = line.split("refs/heads/")
            if len(parts) > 1:
                return parts[1].split()[0]
    return None


def set_upstream(repo_path: Path, remote_name: str, default_branch: Optional[str]) -> None:
    if not default_branch:
        return
    current_branch = run_command(["git", "branch", "--show-current"], cwd=repo_path, check=False).stdout.strip()
    if not current_branch:
        current_branch = "master"
    run_command(["git", "reset", "--mixed", f"{remote_name}/{default_branch}", "--no-refresh"], cwd=repo_path)
    run_command(["git", "branch", "--set-upstream-to", f"{remote_name}/{default_branch}", current_branch], cwd=repo_path)


def init_local_repo(repository: str, repo_name: str = DEFAULT_REMOTE_NAME, remote: Optional[str] = None) -> None:
    repo_path = Path(repository)
    ensure_git_repo(repo_path)
    remotes = run_command(["git", "remote"], cwd=repo_path).stdout.splitlines()
    if repo_name not in remotes:
        remote_url = build_remote_url(repository, remote)
        run_command(["git", "remote", "add", repo_name, remote_url], cwd=repo_path)
    else:
        remote_url = build_remote_url(repository, remote)
        if remote:
            run_command(["git", "remote", "set-url", repo_name, remote_url], cwd=repo_path)
    run_command(["git", "fetch", repo_name], cwd=repo_path)
    default_branch = detect_default_branch(repo_path, repo_name)
    if default_branch:
        set_upstream(repo_path, repo_name, default_branch)
    else:
        print("No remote branches were found; skipping upstream setup.")


def init_server_repo(repository: str) -> None:
    server_path = Path(DEFAULT_SERVER_ROOT) / f"{repository}.git"
    if server_path.exists():
        print(f"Repository {server_path} already exists")
        return
    if os.geteuid() != 0:
        run_command(["sudo", "-H", "-u", "git", "mkdir", "-p", str(server_path)])
        run_command(["sudo", "-H", "-u", "git", "git", "init", "--bare", str(server_path)])
    else:
        server_path.parent.mkdir(parents=True, exist_ok=True)
        run_command(["git", "init", "--bare", str(server_path)])


def add_remote_repo(repository: str, repo_name: str = DEFAULT_REMOTE_NAME, remote: Optional[str] = None) -> None:
    repo_path = Path(repository)
    if not (repo_path / ".git").exists():
        raise GitRepoError(f"fatal: not a git repository (or any of the parent directories): .git")
    remotes = run_command(["git", "remote"], cwd=repo_path).stdout.splitlines()
    if repo_name not in remotes:
        remote_url = build_remote_url(repository, remote)
        run_command(["git", "remote", "add", repo_name, remote_url], cwd=repo_path)
    else:
        remote_url = build_remote_url(repository, remote)
        if remote:
            run_command(["git", "remote", "set-url", repo_name, remote_url], cwd=repo_path)
    run_command(["git", "fetch", repo_name], cwd=repo_path)
    default_branch = detect_default_branch(repo_path, repo_name)
    if default_branch:
        set_upstream(repo_path, repo_name, default_branch)


def patch_archive(commit1: str, commit2: str, folder_path: str = "", archive_path: str = "../archive.zip") -> None:
    completed = run_command(["git", "diff", "--diff-filter=ACMRT", "--name-only", commit1, commit2])
    files = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if folder_path:
        files = [path for path in files if path.startswith(f"{folder_path}/")]
    if not files:
        print("No files to archive.")
        return
    run_command(["git", "archive", "--worktree-attributes", "--output", archive_path, commit2, "--", *files])
    print(f"{archive_path} has been created.")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.patch:
        patch_archive(args.commit1, args.commit2, args.folder, args.archive)
        return 0

    if not args.repo:
        print("Repository argument is required", file=sys.stderr)
        return 2

    if args.server:
        init_server_repo(args.repo)
    if args.local:
        init_local_repo(args.repo, repo_name=args.repo_name, remote=args.remote)
    if not args.server and not args.local:
        add_remote_repo(args.repo, repo_name=args.repo_name, remote=args.remote)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except GitRepoError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
