"""Partition the target disk."""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass

from borked_install.util import Cleanup, blkid, run


@dataclass
class Layout:
    disk: str
    esp: str
    root_dev: str
    esp_uuid: str
    luks_uuid: str | None
    boot: str | None = None
    boot_uuid: str | None = None


def _part(disk: str, number: int) -> str:
    if disk[-1].isdigit():
        return f"{disk}p{number}"
    return f"{disk}{number}"


def _wait(path: str) -> None:
    for _ in range(50):
        if os.path.exists(path):
            return
        time.sleep(0.1)
    raise SystemExit(f"partition did not appear: {path}")


def _sfdisk_script(encrypted: bool) -> str:
    if encrypted:
        return "label: gpt\n, 1GiB, U\n, 1GiB, L\n, , L\n"
    return "label: gpt\n, 1GiB, U\n, , L\n"


def partition(disk: str, passphrase: str | None, cleanup: Cleanup) -> Layout:
    encrypted = bool(passphrase)
    run(["wipefs", "-a", disk])
    run(["sfdisk", disk], input=_sfdisk_script(encrypted), text=True)
    subprocess.run(["blockdev", "--rereadpt", disk], check=False)
    subprocess.run(["udevadm", "settle", "--timeout=10"], check=False)
    esp = _part(disk, 1)
    boot = _part(disk, 2) if encrypted else None
    root = _part(disk, 3) if encrypted else _part(disk, 2)
    _wait(esp)
    if boot:
        _wait(boot)
    _wait(root)
    run(["mkfs.vfat", "-F", "32", "-n", "EFI", esp])
    boot_uuid = None
    if boot:
        run(["mkfs.ext4", "-F", "-L", "borked-boot", boot])
        boot_uuid = blkid(boot, "UUID")
    luks_uuid = None
    root_dev = root
    if passphrase:
        run(
            [
                "cryptsetup",
                "luksFormat",
                "--type",
                "luks2",
                "--batch-mode",
                "--key-file",
                "-",
                root,
            ],
            input=passphrase.encode(),
        )
        run(["cryptsetup", "open", "--key-file", "-", root, "borked"], input=passphrase.encode())
        root_dev = "/dev/mapper/borked"
        luks_uuid = blkid(root, "UUID")
        cleanup.add(lambda: run(["cryptsetup", "close", "borked"]))
    return Layout(
        disk=disk,
        esp=esp,
        root_dev=root_dev,
        esp_uuid=blkid(esp, "UUID"),
        luks_uuid=luks_uuid,
        boot=boot,
        boot_uuid=boot_uuid,
    )
