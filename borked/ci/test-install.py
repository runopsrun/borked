#!/usr/bin/env python3
"""Unattended ISO install, then boot the disk and require a self-check PASS."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
DISK = OUT / "test-disk.raw"
CIDATA = OUT / "cidata"
SERIAL_INSTALL = OUT / "serial-install.log"
SERIAL_BOOT = OUT / "serial-test.log"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--desktop", choices=("cosmic", "hyprland"), default="cosmic")
    parser.add_argument("--luks", default=None, help="Optional LUKS passphrase for encrypted install test.")
    parser.add_argument("--skip-boot", action="store_true", help="Only verify unattended install completion.")
    args = parser.parse_args()

    iso = OUT / "borked.iso"
    if not iso.is_file():
        print("missing out/borked.iso. Run just iso.", file=sys.stderr)
        return 1
    if DISK.exists():
        DISK.unlink()
    subprocess.run(["truncate", "-s", "64G", str(DISK)], check=True)
    if CIDATA.exists():
        subprocess.run(["rm", "-rf", str(CIDATA)], check=True)
    CIDATA.mkdir(parents=True)
    (CIDATA / "config.json").write_text(
        json.dumps(
            {
                "disk": "serial:borked-target",
                "luks_passphrase": args.luks,
                "username": "borked",
                "full_name": "Borked User",
                "password": "borkedos",
                "hostname": "borked",
                "timezone": "UTC",
                "desktop": args.desktop,
                "poweroff": True,
                "kernel_extra": " ".join(
                    [
                        "console=ttyS0,115200n8",
                        "systemd.run=/usr/bin/borked-selfcheck",
                        "systemd.run_success_action=poweroff",
                        "systemd.run_failure_action=poweroff",
                    ]
                ),
            },
            indent=2,
        )
        + "\n"
    )
    cidata_iso = OUT / "cidata.iso"
    subprocess.run(
        [
            "xorriso",
            "-as",
            "mkisofs",
            "-o",
            str(cidata_iso),
            "-V",
            "cidata",
            "-J",
            "-r",
            str(CIDATA),
        ],
        check=True,
    )
    qemu = [sys.executable, str(ROOT / "ci/qemuutil.py")]
    subprocess.run(
        qemu
        + [
            "--timeout",
            "2400",
            "iso",
            str(iso),
            str(DISK),
            str(cidata_iso),
            str(SERIAL_INSTALL),
        ],
        check=True,
    )
    install_log = SERIAL_INSTALL.read_text(errors="replace")
    if "borked install: done" not in install_log:
        print(install_log[-4000:], file=sys.stderr)
        print("installer did not finish", file=sys.stderr)
        return 1
    if args.skip_boot:
        print("borked test: install PASS (boot skipped)")
        return 0
    if args.luks:
        # LUKS prompts for a passphrase interactively in initramfs, so assert
        # GRUB loaded the kernel and reached the cryptsetup passphrase prompt.
        subprocess.run(
            qemu
            + [
                "--expect",
                "Please enter passphrase for disk",
                "--timeout",
                "300",
                "disk",
                str(DISK),
                str(SERIAL_BOOT),
            ],
            check=True,
        )
        print("borked test (LUKS): PASS")
        return 0
    subprocess.run(
        qemu
        + [
            "--expect",
            "borked-selfcheck: PASS",
            "--timeout",
            "600",
            "disk",
            str(DISK),
            str(SERIAL_BOOT),
        ],
        check=True,
    )
    print("borked test: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
