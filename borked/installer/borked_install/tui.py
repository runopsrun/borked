"""Console questionnaire. Unattended installs skip this."""

from __future__ import annotations

import getpass
import os
import re
import subprocess

from borked_install.config import Config, resolve_disk


def _disks() -> list[tuple[str, str]]:
    out = subprocess.check_output(
        ["lsblk", "-dn", "-o", "NAME,SIZE,TYPE"], text=True
    )
    found = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[2] == "disk":
            found.append((f"/dev/{parts[0]}", parts[1]))
    return found


def _ask(label: str, default: str = "", secret: bool = False) -> str:
    prompt = f"{label}"
    if default:
        prompt += f" [{default}]"
    prompt += ": "
    if secret:
        value = getpass.getpass(prompt)
    else:
        value = input(prompt)
    value = value.strip()
    return value or default


def ask(stream: str) -> Config:
    print("\nBorked OS installer\nBeautifully broken.\n", flush=True)
    disks = _disks()
    if not disks:
        raise SystemExit("no disks found")
    print("Disks:")
    for path, size in disks:
        print(f"  {path}  {size}")
    disk = resolve_disk(_ask("Install disk", disks[0][0]))
    luks = _ask("LUKS passphrase (empty to skip)", secret=True)
    username = _ask("Username")
    if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", username):
        raise SystemExit(f"username is not valid: {username}")
    full_name = _ask("Full name", username)
    password = _ask("Password", secret=True)
    again = _ask("Password again", secret=True)
    if not password or password != again:
        raise SystemExit("passwords do not match")
    hostname = _ask("Hostname", "borked")
    timezone = _ask("Timezone", "UTC")
    print(f"\nInstall {stream} onto {disk}\n", flush=True)
    confirm = _ask("Type install to continue")
    if confirm != "install":
        raise SystemExit("not confirmed")
    return Config(
        disk=disk,
        luks_passphrase=luks or None,
        username=username,
        full_name=full_name,
        password=password,
        hostname=hostname,
        timezone=timezone,
        stream=stream,
    )
