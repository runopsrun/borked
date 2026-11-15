#!/usr/bin/env python3
"""Remove the self-check kernel arguments from an installed disk image."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

NEEDLES = (
    "systemd.run=/usr/bin/borked-selfcheck",
    "systemd.run_success_action=poweroff",
    "systemd.run_failure_action=poweroff",
)


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def strip_text(text: str) -> str:
    for needle in NEEDLES:
        text = text.replace(needle, "")
    return " ".join(text.split()) + ("\n" if text.endswith("\n") or "\n" in text else "")


def rewrite(path: Path) -> None:
    if not path.is_file():
        return
    original = path.read_text(errors="replace")
    updated = original
    for needle in NEEDLES:
        updated = updated.replace(needle, "")
    if updated != original:
        path.write_text(updated)
        print(f"stripped {path}", flush=True)


def main() -> int:
    if os.geteuid() != 0:
        print("strip-selfcheck must run as root", file=sys.stderr)
        return 1
    image = sys.argv[1]
    loop = subprocess.check_output(["losetup", "-fP", "--show", image], text=True).strip()
    root = Path("/run/borked/edit")
    esp = Path("/run/borked/edit-esp")
    try:
        time.sleep(0.5)
        root.mkdir(parents=True, exist_ok=True)
        run(["mount", "-o", "subvol=@", f"{loop}p2", str(root)])
        for path in [root / "etc/kernel/cmdline", root / "boot/grub2/grub.cfg"]:
            rewrite(path)
        entries = root / "boot/loader/entries"
        if entries.is_dir():
            for path in entries.glob("*.conf"):
                rewrite(path)
        esp.mkdir(parents=True, exist_ok=True)
        run(["mount", f"{loop}p1", str(esp)])
        for path in esp.rglob("grub.cfg"):
            rewrite(path)
    finally:
        subprocess.run(["umount", str(esp)], check=False)
        subprocess.run(["umount", str(root)], check=False)
        subprocess.run(["losetup", "-d", loop], check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
