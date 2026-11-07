"""Shared process helpers for the installer."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=True, **kwargs)


class Cleanup:
    def __init__(self) -> None:
        self._stack: list[Callable[[], None]] = []

    def add(self, fn: Callable[[], None]) -> None:
        self._stack.append(fn)

    def run(self) -> None:
        while self._stack:
            fn = self._stack.pop()
            try:
                fn()
            except Exception as exc:
                print(f"cleanup: {exc}", flush=True)


def mount(source: str, target: str, options: str | None = None) -> None:
    os.makedirs(target, exist_ok=True)
    cmd = ["mount"]
    if options:
        cmd.extend(["-o", options])
    cmd.extend([source, target])
    run(cmd)


def umount(target: str) -> None:
    if not os.path.ismount(target):
        return
    # Bind mounts of /sys pick up efivarfs and stay busy. Detach the tree.
    if subprocess.run(["umount", "-R", target]).returncode == 0:
        return
    subprocess.run(["umount", "-Rl", target], check=False)


def blkid(device: str, tag: str) -> str:
    return subprocess.check_output(
        ["blkid", "-s", tag, "-o", "value", device], text=True
    ).strip()
