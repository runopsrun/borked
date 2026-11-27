"""Configure Cisco Duo Unix after `borked apps` installs it."""

from __future__ import annotations

import argparse
import getpass
import grp
import os
import pwd
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from borked_apps.catalog import load
from borked_apps.install import InstallError, install, is_installed
from borked_apps.voice import DUO_DONE, DUO_MISS, DUO_SSH, DUO_START, DUO_USAGE, say

CONF = Path("/etc/duo/login_duo.conf")
SSHD_DROPIN = Path("/etc/ssh/sshd_config.d/50-borked-duo.conf")
LOGIN_DUO = "/usr/sbin/login_duo"

# Fedora ships login_duo.conf as sshd:root mode 0600. login_duo has
# cap_dac_read_search so ForceCommand can still read the secret key.
CONF_OWNER = "sshd"
CONF_GROUP = "root"
CONF_MODE = 0o600

_KEY_RE = re.compile(r"^[A-Za-z0-9]{20,64}$")
_HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]+\.duosecurity\.com$")


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="borked duo",
        description="Write Duo Unix keys. Optionally wire SSH.",
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("--ikey")
    parser.add_argument("--skey")
    parser.add_argument("--host")
    parser.add_argument("--failmode", choices=("safe", "secure"), default="safe")
    parser.add_argument(
        "--ssh",
        action="store_true",
        help="Force SSH logins through login_duo (drop-in under sshd_config.d).",
    )
    parser.add_argument(
        "--no-ssh",
        action="store_true",
        help="Skip the SSH drop-in even when asked interactively.",
    )
    args = parser.parse_args(argv)
    if args.help or (not argv and not sys.stdin.isatty()):
        print(DUO_USAGE, end="")
        return 0 if args.help else 2

    try:
        _ensure_installed()
        ikey = (args.ikey or "").strip() or _ask("Integration key (ikey)")
        skey = (args.skey or "").strip() or _ask_secret("Secret key (skey)")
        host = (args.host or "").strip() or _ask("API hostname (api-XXXX.duosecurity.com)")
        _validate(ikey, skey, host)
        _write_conf(ikey, skey, host, args.failmode)
        print(say(DUO_DONE, path=str(CONF)))

        want_ssh = args.ssh
        if not args.ssh and not args.no_ssh and sys.stdin.isatty():
            want_ssh = _ask_yes("Wire SSH through login_duo now?")
        if want_ssh:
            _enable_ssh()
            print(say(DUO_SSH, path=str(SSHD_DROPIN)))
        else:
            print("SSH is untouched. Run `borked duo --ssh` when you're ready to regret that.")
        return 0
    except InstallError as exc:
        print(f"borked duo: {exc}")
        return 1
    except DuoError as exc:
        print(f"borked duo: {exc}")
        return 2
    except OSError as exc:
        print(f"borked duo: {exc}")
        return 1


class DuoError(Exception):
    pass


def _ensure_installed() -> None:
    apps = {app.id: app for app in load()}
    app = apps.get("duo")
    if app is None:
        raise DuoError("catalog has no duo entry. The image is the wrong kind of broken.")
    if is_installed(app):
        return
    print(say(DUO_MISS))
    print(say(DUO_START))
    install(app, print)


def _ask(prompt: str) -> str:
    if not sys.stdin.isatty():
        raise DuoError("need --ikey --skey --host when stdin is not a terminal")
    value = input(f"{prompt}: ").strip()
    if not value:
        raise DuoError("empty answer. Duo needs all three.")
    return value


def _ask_secret(prompt: str) -> str:
    if not sys.stdin.isatty():
        raise DuoError("need --ikey --skey --host when stdin is not a terminal")
    value = getpass.getpass(f"{prompt}: ").strip()
    if not value:
        raise DuoError("empty secret. That would be a short career.")
    return value


def _ask_yes(prompt: str) -> bool:
    answer = input(f"{prompt} [y/N]: ").strip().lower()
    return answer in ("y", "yes")


def _validate(ikey: str, skey: str, host: str) -> None:
    if not _KEY_RE.fullmatch(ikey):
        raise DuoError("ikey looks wrong. Paste the integration key from the Duo admin panel.")
    if not _KEY_RE.fullmatch(skey):
        raise DuoError("skey looks wrong. Paste the secret key from the Duo admin panel.")
    if not _HOST_RE.fullmatch(host):
        raise DuoError("host must look like api-XXXX.duosecurity.com")


def _write_conf(ikey: str, skey: str, host: str, failmode: str) -> None:
    text = (
        "[duo]\n"
        f"ikey = {ikey}\n"
        f"skey = {skey}\n"
        f"host = {host}\n"
        f"failmode = {failmode}\n"
    )
    _root_write(CONF, text, CONF_MODE, owner=CONF_OWNER, group=CONF_GROUP)


def _enable_ssh() -> None:
    text = (
        "# Written by `borked duo --ssh`. Remove this file to undo.\n"
        f"ForceCommand {LOGIN_DUO}\n"
        "PermitTunnel no\n"
        "AllowTcpForwarding no\n"
    )
    _root_write(SSHD_DROPIN, text, 0o644)
    _run(["sshd", "-t"])
    _run(["systemctl", "reload", "sshd"])


def _root_write(
    path: Path,
    text: str,
    mode: int,
    *,
    owner: str | None = None,
    group: str | None = None,
) -> None:
    if os.geteuid() == 0:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        os.chmod(path, mode)
        if owner or group:
            uid = pwd.getpwnam(owner).pw_uid if owner else -1
            gid = grp.getgrnam(group).gr_gid if group else -1
            os.chown(path, uid, gid)
        return

    with tempfile.NamedTemporaryFile("w", delete=False) as handle:
        handle.write(text)
        temp = handle.name
    try:
        cmd = ["install", "-D", "-m", f"{mode:o}"]
        if owner:
            cmd.extend(["-o", owner])
        if group:
            cmd.extend(["-g", group])
        cmd.extend([temp, str(path)])
        _run(cmd)
    finally:
        os.unlink(temp)


def _run(cmd: list[str]) -> None:
    full = cmd if os.geteuid() == 0 else ["sudo", *cmd]
    print(" ".join(full))
    done = subprocess.run(full, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if done.stdout:
        print(done.stdout.rstrip())
    if done.returncode != 0:
        raise InstallError(f"{cmd[0]} exited {done.returncode}")
