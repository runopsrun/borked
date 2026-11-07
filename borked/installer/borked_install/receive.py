"""Receive the golden btrfs stream onto the new filesystem."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from borked_install.util import Cleanup, blkid, mount, run, umount

MNT = "/run/borked/mnt"


def _stream(path: str) -> subprocess.Popen:
    magic = Path(path).read_bytes()[:4]
    if magic == b"\x28\xb5\x2f\xfd":
        cmd = ["zstd", "-dc", "--stdout", path]
    else:
        cmd = ["cat", path]
    print("+", " ".join(cmd), flush=True)
    return subprocess.Popen(cmd, stdout=subprocess.PIPE)


def receive(root_dev: str, stream: str, cleanup: Cleanup) -> tuple[str, str]:
    run(["mkfs.btrfs", "-f", "-L", "borked", root_dev])
    os.makedirs(MNT, exist_ok=True)
    mount(root_dev, MNT, "compress=zstd:3")
    cleanup.add(lambda: umount(MNT))
    sender = _stream(stream)
    print("+ btrfs receive", MNT, flush=True)
    received = subprocess.run(["btrfs", "receive", MNT], stdin=sender.stdout, check=False)
    if sender.stdout:
        sender.stdout.close()
    sender.wait()
    if received.returncode != 0 or sender.returncode not in (0, None):
        raise SystemExit(
            f"btrfs receive failed (btrfs {received.returncode}, stream {sender.returncode})"
        )
    subvol = os.path.join(MNT, "@")
    if not os.path.isdir(subvol):
        listing = subprocess.check_output(["btrfs", "subvolume", "list", MNT], text=True)
        raise SystemExit(f"received stream has no @ subvolume:\n{listing}")
    run(["btrfs", "property", "set", "-f", subvol, "ro", "false"])
    run(["btrfs", "filesystem", "resize", "max", MNT])
    home = os.path.join(subvol, "home")
    os.makedirs(home, exist_ok=True)
    run(["btrfs", "subvolume", "create", os.path.join(MNT, "@home")])
    mount(root_dev, home, "subvol=@home,compress=zstd:3")
    cleanup.add(lambda: umount(home))
    fs_uuid = blkid(root_dev, "UUID")
    print(f"btrfs uuid {fs_uuid}", flush=True)
    return subvol, fs_uuid
