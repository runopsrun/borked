"""Install one catalog entry. Repos stay gpgcheck=1. Scripts run as the user."""

from __future__ import annotations

import fnmatch
import json
import os
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

from borked_apps.catalog import App, root
from borked_apps.voice import VIRT, say

UA = "borked-apps"


class InstallError(Exception):
    pass


def invoking_user() -> str | None:
    user = os.environ.get("SUDO_USER") or os.environ.get("USER")
    if not user or user == "root":
        return None
    return user


def is_installed(app: App) -> bool:
    if app.kind in ("dnf", "dnf-repo", "virt", "github-rpm"):
        done = subprocess.run(["rpm", "-q", app.check], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return done.returncode == 0
    if shutil.which(app.check):
        return True
    user = invoking_user()
    if user is None:
        return False
    return Path(f"/home/{user}/.local/bin/{app.check}").is_file()


def install(app: App, log) -> None:
    if app.kind == "script":
        _script(app, log)
    elif app.kind == "github-rpm":
        _github_rpm(app, log)
    elif app.kind in ("dnf", "dnf-repo", "virt"):
        if app.kind == "dnf-repo":
            _enable_repo(app, log)
        _dnf(app.packages(), log)
        if app.kind == "virt":
            _virt_access(log)
    else:
        raise InstallError(f"unknown kind {app.kind}")


def _run(cmd: list[str], log, *, root: bool = True, user: str | None = None) -> None:
    if user:
        cmd = ["runuser", "-u", user, "--", *cmd]
    elif root and os.geteuid() != 0:
        cmd = ["sudo", *cmd]
    log(" ".join(cmd))
    done = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if done.stdout:
        log(done.stdout.rstrip())
    if done.returncode != 0:
        raise InstallError(f"exit {done.returncode}")


def _fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/octet-stream"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def _script(app: App, log) -> None:
    user = invoking_user()
    if os.geteuid() == 0 and user is None:
        raise InstallError(f"{app.label} installs into a home directory. Run `borked apps` as your user.")
    log(f"fetch {app.target}")
    body = _fetch(app.target)
    with tempfile.NamedTemporaryFile(prefix=f"borked-{app.id}-", suffix=".sh", delete=False) as handle:
        handle.write(body)
        path = handle.name
    os.chmod(path, 0o755)
    try:
        _run(["bash", path], log, root=False, user=user if os.geteuid() == 0 else None)
    finally:
        os.unlink(path)


def _enable_repo(app: App, log) -> None:
    name = app.repo_name()
    source = root() / "repos" / f"{name}.repo"
    if not source.is_file():
        raise InstallError(f"missing repo file {source.name}")
    dest = Path("/etc/yum.repos.d") / source.name
    text = source.read_text()
    if os.geteuid() == 0:
        dest.write_text(text)
    else:
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            handle.write(text)
            temp = handle.name
        try:
            _run(["install", "-D", "-m", "0644", temp, str(dest)], log)
        finally:
            os.unlink(temp)
    for line in text.splitlines():
        if line.startswith("gpgkey=http"):
            _run(["rpm", "--import", line.split("=", 1)[1].strip()], log)


def _dnf(packages: list[str], log) -> None:
    _run(["dnf", "-y", "--setopt=gpgcheck=1", "install", *packages], log)


def _virt_access(log) -> None:
    _run(["systemctl", "enable", "--now", "libvirtd"], log)
    user = invoking_user()
    if user is None:
        log("libvirtd is on. Add yourself to libvirt, then log out. I'll wait. I won't enjoy it.")
        return
    _run(["usermod", "-aG", "libvirt", user], log)
    log(say(VIRT, user=user))


def _github_rpm(app: App, log) -> None:
    try:
        owner, repo, pattern = app.target.split("/", 2)
    except ValueError as exc:
        raise InstallError(f"{app.id} target must be owner/repo/glob") from exc
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    log(f"fetch {url}")
    payload = json.loads(_fetch(url).decode())
    match = None
    for asset in payload.get("assets", []):
        if fnmatch.fnmatch(asset.get("name", ""), pattern):
            match = asset
            break
    if match is None:
        raise InstallError(f"no {pattern} on the latest {owner}/{repo} release")
    rpm_bytes = _fetch(match["browser_download_url"])
    with tempfile.NamedTemporaryFile(prefix=f"borked-{app.id}-", suffix=".rpm", delete=False) as handle:
        handle.write(rpm_bytes)
        path = handle.name
    try:
        _dnf([path], log)
    finally:
        os.unlink(path)
