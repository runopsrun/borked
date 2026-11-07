"""Per-machine files: user, hostname, fstab, machine-id."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from borked_install.config import Config
from borked_install.partition import Layout
from borked_install.util import run


def _write(path: str, text: str, mode: int = 0o644) -> None:
    Path(path).write_text(text)
    os.chmod(path, mode)


def configure(root: str, cfg: Config, layout: Layout, fs_uuid: str) -> None:
    zone = Path(root) / "usr/share/zoneinfo" / cfg.timezone
    if not zone.exists():
        raise SystemExit(f"timezone not in the image: {cfg.timezone}")
    os.symlink(f"/usr/share/zoneinfo/{cfg.timezone}", os.path.join(root, "etc/localtime.tmp"))
    os.replace(os.path.join(root, "etc/localtime.tmp"), os.path.join(root, "etc/localtime"))

    _write(os.path.join(root, "etc/hostname"), cfg.hostname + "\n")
    _write(
        os.path.join(root, "etc/hosts"),
        "127.0.0.1 localhost\n::1 localhost\n"
        f"127.0.1.1 {cfg.hostname}\n",
    )
    _write(os.path.join(root, "etc/locale.conf"), "LANG=C.UTF-8\n")
    _write(
        os.path.join(root, "etc/sudoers.d/wheel"),
        "%wheel ALL=(ALL) ALL\n",
        mode=0o440,
    )

    fstab = [
        f"UUID={fs_uuid} / btrfs subvol=@,compress=zstd:3 0 0",
        f"UUID={fs_uuid} /home btrfs subvol=@home,compress=zstd:3 0 0",
        f"UUID={layout.esp_uuid} /boot/efi vfat umask=0077,shortname=winnt 0 2",
    ]
    if layout.luks_uuid:
        _write(
            os.path.join(root, "etc/crypttab"),
            f"borked UUID={layout.luks_uuid} none luks,discard\n",
        )
    _write(os.path.join(root, "etc/fstab"), "\n".join(fstab) + "\n")

    machine_id = os.path.join(root, "etc/machine-id")
    Path(machine_id).write_text("")
    dbus = Path(root) / "var/lib/dbus/machine-id"
    if dbus.is_symlink() or dbus.exists():
        dbus.unlink()
    run(["systemd-machine-id-setup", "--root", root])

    run(
        [
            "chroot",
            root,
            "useradd",
            "-m",
            "-U",
            "-G",
            "wheel",
            "-c",
            cfg.full_name,
            cfg.username,
        ]
    )
    subprocess.run(
        ["chroot", root, "chpasswd"],
        input=f"{cfg.username}:{cfg.password}\n",
        text=True,
        check=True,
    )
    run(["chroot", root, "passwd", "-l", "root"])
    # systemd-run-generator redirects default.target from /run, but
    # set-default's /etc symlink wins, so systemd.run= never starts.
    # A conditioned unit still runs, and get-default stays graphical.
    unit = os.path.join(root, "etc/systemd/system/borked-selfcheck.service")
    _write(
        unit,
        "[Unit]\n"
        "Description=Borked install self-check\n"
        "ConditionKernelCommandLine=systemd.run=/usr/bin/borked-selfcheck\n"
        "DefaultDependencies=no\n"
        "After=local-fs.target\n"
        "Before=display-manager.service\n"
        "SuccessAction=poweroff\n"
        "FailureAction=poweroff\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        "ExecStart=/usr/bin/borked-selfcheck\n"
        "StandardOutput=journal+console\n"
        "StandardError=journal+console\n",
    )
    wants = os.path.join(root, "etc/systemd/system/sysinit.target.wants")
    os.makedirs(wants, exist_ok=True)
    link = os.path.join(wants, "borked-selfcheck.service")
    if os.path.lexists(link):
        os.remove(link)
    os.symlink("../borked-selfcheck.service", link)
