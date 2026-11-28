"""Load an unattended config, or ask on the console."""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path



# Session Name= from /usr/share/wayland-sessions/*.desktop
DESKTOPS = ("cosmic", "hyprland")
DESKTOP_SESSIONS = {
    "cosmic": "COSMIC",
    "hyprland": "Hyprland",
}


@dataclass
class Config:
    disk: str
    luks_passphrase: str | None
    username: str
    full_name: str
    password: str
    hostname: str
    timezone: str
    stream: str
    poweroff: bool = False
    kernel_extra: str = ""
    locale: str = "en_US.UTF-8"
    keymap: str = "us"
    xkb_layout: str = "us"
    desktop: str = "cosmic"
    interactive: bool = False


def _mount_label(label: str, target: str) -> bool:
    found = subprocess.run(
        ["blkid", "-L", label], text=True, capture_output=True
    )
    device = (found.stdout or "").strip()
    if found.returncode != 0 or not device:
        return False
    os.makedirs(target, exist_ok=True)
    if not os.path.ismount(target):
        subprocess.run(["mount", "-o", "ro", device, target], check=True)
    return True


def find_stream(explicit: str | None) -> str:
    if explicit and Path(explicit).is_file():
        return explicit
    env = os.environ.get("BORKED_STREAM")
    if env and Path(env).is_file():
        return env
    for candidate in (
        Path("/run/iso/borked-root.btrfs.zst"),
        Path("/src/out/borked-root.btrfs.zst"),
    ):
        if candidate.is_file():
            return str(candidate)
    if _mount_label("BORKED_ISO", "/run/iso"):
        candidate = Path("/run/iso/borked-root.btrfs.zst")
        if candidate.is_file():
            return str(candidate)
    raise SystemExit("could not find borked-root.btrfs.zst")


def resolve_disk(disk: str) -> str:
    if disk.startswith("serial:"):
        serial = disk.split(":", 1)[1]
        deadline = time.time() + 20
        while time.time() < deadline:
            by_id = Path("/dev/disk/by-id")
            if by_id.is_dir():
                matches = [
                    path
                    for path in by_id.iterdir()
                    if serial in path.name and "part" not in path.name
                ]
                if matches:
                    return os.path.realpath(matches[0])
            time.sleep(0.5)
        raise SystemExit(f"no disk with serial {serial}")
    if Path(disk).exists():
        return disk
    raise SystemExit(f"disk not found: {disk}")


def _desktop(value: object) -> str:
    name = str(value or "cosmic").strip().lower()
    if name not in DESKTOPS:
        raise SystemExit(f"desktop must be one of {', '.join(DESKTOPS)}")
    return name


def _from_mapping(data: dict, stream: str | None) -> Config:
    passphrase = data.get("luks_passphrase") or None
    return Config(
        disk=resolve_disk(str(data["disk"])),
        luks_passphrase=passphrase,
        username=str(data["username"]),
        full_name=str(data.get("full_name") or data["username"]),
        password=str(data["password"]),
        hostname=str(data.get("hostname") or "borked"),
        timezone=str(data.get("timezone") or "UTC"),
        stream=find_stream(data.get("stream") or stream),
        poweroff=bool(data.get("poweroff", False)),
        kernel_extra=str(data.get("kernel_extra") or ""),
        locale=str(data.get("locale") or "en_US.UTF-8"),
        keymap=str(data.get("keymap") or "us"),
        xkb_layout=str(data.get("xkb_layout") or "us"),
        desktop=_desktop(data.get("desktop")),
    )


def load_config(path: str | None) -> Config:
    if path:
        return _from_mapping(json.loads(Path(path).read_text()), None)
    for directory in (Path("/run/cidata"),):
        pass
    if _mount_label("cidata", "/run/cidata"):
        config = Path("/run/cidata/config.json")
        if config.is_file():
            return _from_mapping(json.loads(config.read_text()), None)
    env = os.environ.get("BORKED_CONFIG")
    if env and Path(env).is_file():
        return _from_mapping(json.loads(Path(env).read_text()), None)
    if os.isatty(0):
        from borked_install.tui import ask

        return ask(find_stream(None))
    raise SystemExit("no installer config. Pass --config or a cidata volume.")
