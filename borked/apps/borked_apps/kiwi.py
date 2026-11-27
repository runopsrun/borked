"""Install Cytrence Kiwi into an Ubuntu distrobox.

Fedora is not on Cytrence's list. The current Ubuntu 24.04 deb is.
The zip carries the vendor's own sha256. That is a corruption check,
not a signature.
"""

from __future__ import annotations

import argparse
import grp
import hashlib
import io
import os
import pwd
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

from borked_apps.catalog import App, load
from borked_apps.install import InstallError, invoking_user, user_home
from borked_apps.voice import KIWI_DONE, KIWI_GROUP, KIWI_USAGE, say

PAGE = "https://www.cytrence.com/software"
UA = "borked-apps"
MAX_BYTES = 50 * 1024 * 1024
BOX_PACKAGES = "debconf lsb-release libx11-6 ffmpeg"
DEB_IN_BOX = "/tmp/cytrence-kiwi.deb"
WRAPPER = Path(__file__).with_name("kiwi_wrapper.sh")

_UBUNTU_ZIP = re.compile(
    r"https://www\.cytrence\.com/_files/archives/[A-Za-z0-9_]+\.zip\?dn=CytrenceKiwi-[0-9.]+-ubuntu24_amd64\.zip"
)


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="borked kiwi", description="Install Cytrence Kiwi into distrobox.", add_help=False)
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("--yes", action="store_true", help="Accept the Cytrence EULA without a prompt.")
    args = parser.parse_args(argv)
    if args.help or (not argv and not sys.stdin.isatty()):
        print(KIWI_USAGE, end="")
        return 0 if args.help else 2
    if sys.stdin.isatty() and not args.yes:
        answer = input("Install Cytrence Kiwi into an Ubuntu 24.04 distrobox? That accepts their EULA. [y/N]: ")
        if answer.strip().lower() not in ("y", "yes"):
            print("Left it alone.")
            return 0
    try:
        app = _catalog_app()
        install(app, print)
        return 0
    except InstallError as exc:
        print(f"borked kiwi: {exc}")
        return 1


def install(app: App, log) -> None:
    image, name = _target(app)
    if shutil_which("distrobox") is None or shutil_which("podman") is None:
        raise InstallError("distrobox and podman have to be on the machine. The image ships both.")
    _ensure_box(image, name, log)
    _apt(name, log)
    previous = _enter_text(name, "cat /usr/bin/cytrencekiwi.sh 2>/dev/null || true", log)
    deb_name, deb = _download(log)
    log(f"deb {deb_name} ({len(deb)} bytes)")
    _copy_deb(name, deb, log)
    log("Answering yes to Cytrence's EULA. The package prints the whole thing next.")
    _enter(
        name,
        ["bash", "-lc", f"printf '%s\\n' yes | sudo -n dpkg -i {DEB_IN_BOX} && rm -f {DEB_IN_BOX}"],
        log,
    )
    _install_wrapper(name, previous, log)
    _enter(name, ["distrobox-export", "--app", "cytrencekiwi"], log)
    home = _home()
    bindir = home / ".local" / "bin"
    _enter(
        name,
        ["distrobox-export", "--bin", "/usr/bin/cytrencekiwi.sh", "--export-path", str(bindir)],
        log,
    )
    _enter(name, ["bash", "-lc", "sudo -n usermod -aG dialout \"$(id -un)\""], log)
    _host_dialout(log)
    _brltty(log)
    log(say(KIWI_DONE, name=name, path=str(bindir / "cytrencekiwi.sh")))


def ubuntu_zip_url(page: str) -> str:
    text = page.replace("&amp;", "&").replace("&#63;", "?").replace("\\u003f", "?").replace("\\u003d", "=")
    found = list(dict.fromkeys(_UBUNTU_ZIP.findall(text)))
    if len(found) != 1:
        raise InstallError(f"expected one Ubuntu 24.04 Kiwi link on the Cytrence page, found {len(found)}")
    return found[0]


def verify_deb(name: str, data: bytes, checksums: str) -> None:
    wanted = None
    for line in checksums.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] == name:
            wanted = parts[0]
            break
    if wanted is None:
        raise InstallError(f"the zip has no sha256 line for {name}")
    got = hashlib.sha256(data).hexdigest()
    if got != wanted:
        raise InstallError(f"{name} sha256 is {got}, the zip says {wanted}")


def _catalog_app() -> App:
    for app in load():
        if app.id == "kiwi":
            return app
    raise InstallError("catalog has no kiwi entry")


def _target(app: App) -> tuple[str, str]:
    image, _, name = app.target.partition(" ")
    if not name:
        raise InstallError(f"{app.id} target needs an image and a container name")
    return image, name


def _ensure_box(image: str, name: str, log) -> None:
    current = _box_image(name, log)
    if current is None:
        log(f"Creating {name} from {image}. The first pull is the slow part.")
        _as_user(["distrobox", "create", "--yes", "--image", image, "--name", name], log)
        return
    if image not in current:
        raise InstallError(f"{name} is {current}. It needs to be {image}. Remove that box first.")
    log(f"{name} is already {current}.")


def _box_image(name: str, log) -> str | None:
    done = _as_user(["distrobox", "list", "--no-color"], log, check=False)
    if done.returncode != 0:
        raise InstallError("distrobox list failed")
    for line in done.stdout.splitlines():
        fields = [part.strip() for part in line.split("|")]
        if len(fields) >= 4 and fields[1] == name:
            return fields[3]
    return None


def _apt(name: str, log) -> None:
    script = (
        "sudo -n apt-get update && "
        f"sudo -n env DEBIAN_FRONTEND=noninteractive apt-get install -y {BOX_PACKAGES}"
    )
    _enter(name, ["bash", "-lc", script], log)


def _download(log) -> tuple[str, bytes]:
    log(f"fetch {PAGE}")
    page = _fetch(PAGE).decode("utf-8", "replace")
    url = ubuntu_zip_url(page)
    log(f"fetch {url}")
    blob = _fetch(url)
    if len(blob) > MAX_BYTES:
        raise InstallError("the Kiwi zip is larger than expected")
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            debs = [item for item in archive.namelist() if item.endswith(".deb") and not item.endswith("/")]
            sums = [item for item in archive.namelist() if Path(item).name == "sha256_checksums.txt"]
            if len(debs) != 1 or len(sums) != 1:
                raise InstallError("the zip should hold one deb and sha256_checksums.txt")
            deb = archive.read(debs[0])
            checksums = archive.read(sums[0]).decode()
    except zipfile.BadZipFile as exc:
        raise InstallError("the download is not a zip") from exc
    if len(deb) > MAX_BYTES:
        raise InstallError("the Kiwi deb is larger than expected")
    verify_deb(Path(debs[0]).name, deb, checksums)
    return Path(debs[0]).name, deb


def _fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise InstallError("download is larger than expected")
    return data


def _copy_deb(name: str, deb: bytes, log) -> None:
    _enter(name, ["bash", "-c", f"cat > {DEB_IN_BOX}"], log, input_bytes=deb)


def _enter_text(name: str, script: str, log) -> str:
    return _as_user(["distrobox", "enter", name, "--", "bash", "-lc", script], log).stdout


def _install_wrapper(name: str, previous: str, log) -> None:
    if "SDL_AUDIO_DRIVER=dummy" in previous or "SDL_AUDIODRIVER=dummy" in previous:
        _keep_dummy_audio(log)
    wrapper = WRAPPER.read_text()
    _enter(name, ["bash", "-c", "sudo -n tee /usr/bin/cytrencekiwi.sh >/dev/null"], log, input_text=wrapper)
    _enter(name, ["sudo", "-n", "chmod", "755", "/usr/bin/cytrencekiwi.sh"], log)


def _keep_dummy_audio(log) -> None:
    path = _home() / ".config" / "borked" / "kiwi.env"
    if path.is_file():
        log(f"{path} already has the local Kiwi overrides.")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Kept from the previous Kiwi launcher. nouveau HDMI can blank a display.\n"
        "SDL_AUDIO_DRIVER=dummy\n"
        "SDL_AUDIODRIVER=dummy\n"
    )
    user = invoking_user()
    if os.geteuid() == 0 and user is not None:
        record = pwd.getpwnam(user)
        os.chown(path.parent, record.pw_uid, record.pw_gid)
        os.chown(path, record.pw_uid, record.pw_gid)
    log(f"Wrote {path} so the old audio workaround stays.")


def _host_dialout(log) -> None:
    user = invoking_user()
    if user is None:
        log("Add your user to dialout, then log out. The serial device stays shut until you do.")
        return
    _as_user(["usermod", "-aG", "dialout", user], log, as_user=False)
    try:
        in_session = grp.getgrnam("dialout").gr_gid in os.getgroups()
    except KeyError:
        in_session = False
    if os.geteuid() != 0 and in_session:
        log(f"{user} already has dialout in this session.")
        return
    log(say(KIWI_GROUP, user=user))


def _brltty(log) -> None:
    done = subprocess.run(["rpm", "-q", "brltty"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if done.returncode == 0:
        log("brltty is installed. It can claim the Kiwi serial device. Remove it if the dongle never shows up.")


def _enter(name: str, args: list[str], log, *, input_bytes: bytes | None = None, input_text: str | None = None) -> None:
    _as_user(["distrobox", "enter", name, "--", *args], log, input_bytes=input_bytes, input_text=input_text)


def _as_user(
    cmd: list[str],
    log,
    *,
    input_bytes: bytes | None = None,
    input_text: str | None = None,
    check: bool = True,
    as_user: bool = True,
) -> subprocess.CompletedProcess:
    kwargs: dict = {}
    if as_user and os.geteuid() == 0:
        user = invoking_user()
        if user is None:
            raise InstallError("distrobox belongs to a user. Run `borked kiwi` as yourself.")
        record = pwd.getpwnam(user)
        env = os.environ.copy()
        env["HOME"] = record.pw_dir
        env["USER"] = user
        env["LOGNAME"] = user
        env["XDG_RUNTIME_DIR"] = f"/run/user/{record.pw_uid}"
        kwargs["user"] = record.pw_uid
        kwargs["group"] = record.pw_gid
        kwargs["env"] = env
    elif not as_user and os.geteuid() != 0:
        cmd = ["sudo", "-n", *cmd]
    log(" ".join(cmd))
    if input_bytes is not None:
        done = subprocess.run(cmd, input=input_bytes, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs)
        output = done.stdout.decode("utf-8", "replace")
    else:
        done = subprocess.run(
            cmd,
            input=input_text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            **kwargs,
        )
        output = done.stdout or ""
    if output:
        log(output.rstrip())
    if check and done.returncode != 0:
        raise InstallError(f"{cmd[0]} exited {done.returncode}")
    done.stdout = output
    return done


def _home() -> Path:
    home = user_home()
    if home is None:
        raise InstallError("distrobox belongs to a user. Run `borked kiwi` as yourself.")
    return home


def shutil_which(name: str) -> str | None:
    return shutil.which(name)
