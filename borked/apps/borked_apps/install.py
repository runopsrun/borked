"""Install one catalog entry. Repos stay gpgcheck=1. Scripts run as the user."""

from __future__ import annotations

import fnmatch
import io
import json
import os
import pwd
import shutil
import subprocess
import tarfile
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


def user_home() -> Path | None:
    user = invoking_user()
    if user is None:
        if os.geteuid() == 0:
            return None
        return Path.home()
    return Path(pwd.getpwnam(user).pw_dir)


def is_installed(app: App) -> bool:
    if app.kind == "distrobox":
        return _distrobox_installed(app)
    if app.kind == "github-bundle":
        return Path(f"/usr/local/bin/{app.check}").is_file()
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
    elif app.kind == "github-bundle":
        _github_bundle(app, log)
    elif app.kind in ("dnf", "dnf-repo", "virt"):
        if app.kind == "dnf-repo":
            _enable_repo(app, log)
        _dnf(app.packages(), log)
        if app.kind == "virt":
            _virt_access(log)
    elif app.kind == "distrobox":
        if app.id != "kiwi":
            raise InstallError(f"{app.id} has no distrobox installer")
        from borked_apps.kiwi import install as install_kiwi

        install_kiwi(app, log)
    else:
        raise InstallError(f"unknown kind {app.kind}")


def _distrobox_installed(app: App) -> bool:
    home = user_home()
    if home is None or shutil.which("distrobox") is None:
        return False
    launcher = home / ".local" / "bin" / app.check
    if not launcher.is_file():
        return False
    _image, _, name = app.target.partition(" ")
    cmd = ["distrobox", "list", "--no-color"]
    if os.geteuid() == 0:
        cmd = ["runuser", "-u", invoking_user() or "", "--", *cmd]
    done = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if done.returncode != 0:
        return False
    for line in done.stdout.splitlines():
        fields = [part.strip() for part in line.split("|")]
        if len(fields) >= 2 and fields[1] == name:
            return True
    return False


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


def _fetch(url: str, timeout: int = 120) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/octet-stream"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
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


def _github_asset(app: App, log) -> dict:
    try:
        owner, repo, pattern = app.target.split("/", 2)
    except ValueError as exc:
        raise InstallError(f"{app.id} target must be owner/repo/glob") from exc
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    log(f"fetch {url}")
    payload = json.loads(_fetch(url).decode())
    matches = [asset for asset in payload.get("assets", []) if fnmatch.fnmatch(asset.get("name", ""), pattern)]
    if len(matches) != 1:
        found = ", ".join(asset.get("name", "") for asset in matches) or "nothing"
        raise InstallError(f"{app.id}: expected one {pattern}, found {found}")
    return matches[0]


def _github_rpm(app: App, log) -> None:
    match = _github_asset(app, log)
    rpm_bytes = _fetch(match["browser_download_url"], timeout=600)
    with tempfile.NamedTemporaryFile(prefix=f"borked-{app.id}-", suffix=".rpm", delete=False) as handle:
        handle.write(rpm_bytes)
        path = handle.name
    try:
        _dnf([path], log)
    finally:
        os.unlink(path)


def _github_bundle(app: App, log) -> None:
    match = _github_asset(app, log)
    name = match["name"]
    blob = _fetch(match["browser_download_url"], timeout=600)
    if name.endswith(".AppImage"):
        _install_appimage(app, blob, log)
    elif name.endswith(".tar.gz"):
        _install_tarball(app, blob, log)
    else:
        raise InstallError(f"{app.id}: {name} is not a tar.gz or an AppImage")


def _install_appimage(app: App, blob: bytes, log) -> None:
    root = Path("/opt/borked") / app.id
    payload = root / f"{app.check}.AppImage"
    wrapper = (
        "#!/bin/sh\n"
        f"exec {payload} --appimage-extract-and-run \"$@\"\n"
    )
    _stage_bytes(payload, blob, 0o755, log)
    _stage_text(Path("/usr/local/bin") / app.check, wrapper, 0o755, log)
    _stage_text(Path("/usr/share/applications") / f"borked-{app.id}.desktop", _desktop(app, terminal=False), 0o644, log)


def _install_tarball(app: App, blob: bytes, log) -> None:
    root = Path("/opt/borked") / app.id
    try:
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as archive:
            members = [_safe_member(app, member) for member in archive.getmembers()]
            bins = [member.name for member in members if Path(member.name).name == app.check and member.isfile()]
            executable = [member.name for member in members if member.isfile() and member.mode & 0o111]
            if len(bins) != 1:
                raise InstallError(f"{app.id}: expected one {app.check} in the archive, found {len(bins)}")
            _run(["rm", "-rf", str(root)], log)
            _run(["mkdir", "-p", str(root)], log)
            with tempfile.TemporaryDirectory(prefix=f"borked-{app.id}-") as temp:
                archive.extractall(temp, members=members, filter="data")
                _run(["cp", "-a", f"{temp}/.", str(root)], log)
    except tarfile.TarError as exc:
        raise InstallError(f"{app.id}: bad tar.gz") from exc
    for name in executable:
        _run(["chmod", "755", str(root / name)], log)
    _run(["ln", "-sfn", str(root / bins[0]), f"/usr/local/bin/{app.check}"], log)
    icon = next(root.rglob(f"{app.check}.png"), None)
    _stage_text(
        Path("/usr/share/applications") / f"borked-{app.id}.desktop",
        _desktop(app, terminal=True, icon=str(icon) if icon else None),
        0o644,
        log,
    )


def _safe_member(app: App, member: tarfile.TarInfo) -> tarfile.TarInfo:
    parts = Path(member.name).parts
    if not member.name or member.name.startswith("/") or ".." in parts:
        raise InstallError(f"{app.id}: unsafe path {member.name}")
    return member


def _desktop(app: App, *, terminal: bool, icon: str | None = None) -> str:
    lines = [
        "[Desktop Entry]",
        f"Name={app.label}",
        f"Comment={app.blurb}",
        f"Exec=/usr/local/bin/{app.check}",
        "Type=Application",
        f"Terminal={'true' if terminal else 'false'}",
        "Categories=Utility;",
    ]
    if icon:
        lines.append(f"Icon={icon}")
    return "\n".join(lines) + "\n"


def _stage_bytes(dest: Path, blob: bytes, mode: int, log) -> None:
    with tempfile.NamedTemporaryFile(prefix="borked-", delete=False) as handle:
        handle.write(blob)
        temp = handle.name
    try:
        _run(["install", "-D", "-m", f"{mode:o}", temp, str(dest)], log)
    finally:
        os.unlink(temp)


def _stage_text(dest: Path, text: str, mode: int, log) -> None:
    _stage_bytes(dest, text.encode(), mode, log)
