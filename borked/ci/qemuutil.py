"""Boot a Borked disk or installer ISO in qemu."""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

CODE = Path("/usr/share/edk2/ovmf/OVMF_CODE.fd")
VARS = Path("/usr/share/edk2/ovmf/OVMF_VARS.fd")


def qmp_powerdown(sock: Path) -> None:
    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(5)
        client.connect(str(sock))
        client.sendall(b'{"execute":"qmp_capabilities"}\n')
        client.sendall(b'{"execute":"system_powerdown"}\n')
        client.close()
    except OSError as exc:
        print(f"qmp powerdown failed: {exc}", flush=True)


def boot(cmd: list[str], serial: Path, timeout: int, qmp: Path, expect: str | None = None) -> None:
    serial.parent.mkdir(parents=True, exist_ok=True)
    print("+", " ".join(cmd), flush=True)
    with serial.open("w") as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + timeout
        code = None
        try:
            while True:
                code = proc.poll()
                if expect:
                    try:
                        if expect in serial.read_text(errors="replace"):
                            # The greeter ignores the ACPI power button, so
                            # quit the VM once the serial log has the marker.
                            qmp_powerdown(qmp)
                            try:
                                proc.wait(timeout=15)
                            except subprocess.TimeoutExpired:
                                proc.kill()
                                proc.wait(timeout=30)
                            print(f"qemu saw {expect!r}", flush=True)
                            return
                    except OSError:
                        pass
                if code is not None:
                    break
                if time.monotonic() >= deadline:
                    qmp_powerdown(qmp)
                    try:
                        proc.wait(timeout=90)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=30)
                    raise SystemExit(f"qemu timed out after {timeout}s; serial is {serial}")
                time.sleep(0.5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=30)
            raise SystemExit(f"qemu did not exit after powerdown; serial is {serial}")
    print(f"qemu exit {code}", flush=True)


def firmware(var_copy: Path) -> list[str]:
    if not CODE.is_file() or not VARS.is_file():
        raise SystemExit(f"OVMF firmware missing ({CODE}, {VARS})")
    shutil.copyfile(VARS, var_copy)
    return [
        "-drive",
        f"if=pflash,unit=0,format=raw,readonly=on,file={CODE}",
        "-drive",
        f"if=pflash,unit=1,format=raw,file={var_copy}",
    ]


def base_cmd(qmp: Path, gui: bool) -> list[str]:
    kvm = os.access("/dev/kvm", os.R_OK | os.W_OK)
    cmd = [
        "qemu-system-x86_64",
        "-machine",
        "q35,accel=kvm" if kvm else "q35,accel=tcg",
        "-cpu",
        "host" if kvm else "qemu64",
        "-m",
        "4096",
        "-smp",
        "2",
        "-no-reboot",
        "-serial",
        "stdio",
        "-monitor",
        "none",
        "-qmp",
        f"unix:{qmp},server,nowait",
    ]
    if gui:
        cmd.extend(["-device", "virtio-vga", "-display", "vnc=127.0.0.1:99"])
    else:
        cmd.extend(["-display", "none", "-vga", "none"])
    return cmd


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expect", help="substring that must appear in the serial log")
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--timeout", type=int, required=True)
    sub = parser.add_subparsers(dest="mode", required=True)
    disk = sub.add_parser("disk")
    disk.add_argument("image")
    disk.add_argument("serial")
    iso = sub.add_parser("iso")
    iso.add_argument("iso")
    iso.add_argument("image")
    iso.add_argument("cidata")
    iso.add_argument("serial")
    args = parser.parse_args()

    stamp = int(time.time())
    qmp = Path(f"/tmp/borked-qmp-{stamp}.sock")
    var_copy = Path(args.serial).with_suffix(".vars.fd")
    cmd = base_cmd(qmp, args.gui) + firmware(var_copy)
    if args.mode == "disk":
        cmd += [
            "-drive",
            f"file={args.image},if=none,id=disk,format=raw",
            "-device",
            "virtio-blk-pci,drive=disk,bootindex=1,serial=borked-target",
        ]
    else:
        cmd += [
            "-drive",
            f"file={args.iso},if=none,id=cd0,format=raw,media=cdrom",
            "-device",
            "ide-cd,drive=cd0,bus=ide.0,bootindex=1",
            "-drive",
            f"file={args.cidata},if=none,id=cd1,format=raw,media=cdrom",
            "-device",
            "ide-cd,drive=cd1,bus=ide.1",
            "-drive",
            f"file={args.image},if=none,id=disk,format=raw",
            "-device",
            "virtio-blk-pci,drive=disk,bootindex=2,serial=borked-target",
        ]
    boot(cmd, Path(args.serial), args.timeout, qmp, args.expect)
    if args.expect:
        text = Path(args.serial).read_text(errors="replace")
        if args.expect not in text:
            print(f"serial log missing {args.expect!r}", file=sys.stderr)
            tail = "\n".join(text.splitlines()[-80:])
            print(tail, file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
