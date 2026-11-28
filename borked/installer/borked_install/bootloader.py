"""Install Fedora's signed shim and make the received system bootable."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from borked_install.config import Config
from borked_install.partition import Layout
from borked_install.util import mount, run, umount


def _find(root: str, name: str) -> str | None:
    for dirpath, _dirs, files in os.walk(root):
        if name in files and "efi-payload" not in dirpath:
            return os.path.join(dirpath, name)
    return None


def _copy_named(src: str, dest_dir: str) -> None:
    os.makedirs(dest_dir, exist_ok=True)
    shutil.copy2(src, os.path.join(dest_dir, os.path.basename(src)))


def _bind(root: str) -> list[str]:
    mounted = []
    for name in ("dev", "proc", "sys", "run"):
        target = os.path.join(root, name)
        os.makedirs(target, exist_ok=True)
        run(["mount", "--bind", f"/{name}", target])
        mounted.append(target)
    efi = os.path.join(root, "sys/firmware/efi/efivars")
    if os.path.isdir("/sys/firmware/efi/efivars"):
        os.makedirs(efi, exist_ok=True)
        try:
            run(["mount", "--bind", "/sys/firmware/efi/efivars", efi])
            mounted.append(efi)
        except Exception:
            pass
    return mounted


def _only_invalid_argument(err: str) -> bool:
    lines = [line.strip() for line in err.splitlines() if line.strip()]
    return bool(lines) and all("Invalid argument" in line for line in lines)


def _grub_stub(layout: Layout, fs_uuid: str) -> str:
    if layout.boot_uuid:
        return (
            "search --no-floppy --fs-uuid --set=root "
            f"{layout.boot_uuid}\n"
            "set prefix=($root)/grub2\n"
            "export prefix\n"
            "configfile $prefix/grub.cfg\n"
        )
    return (
        "search --no-floppy --fs-uuid --set=root "
        f"{fs_uuid}\n"
        "set prefix=($root)/@/boot/grub2\n"
        "export prefix\n"
        "configfile $prefix/grub.cfg\n"
    )


def _clear_dir(path: str) -> None:
    if not os.path.isdir(path):
        return
    for entry in os.listdir(path):
        full = os.path.join(path, entry)
        if os.path.isdir(full) and not os.path.islink(full):
            shutil.rmtree(full)
        else:
            os.unlink(full)


def _should_register_efi_entry(disk: str) -> bool:
    name = os.path.basename(os.path.realpath(disk))
    return not name.startswith("loop")


def _register_efi_entry(root: str, layout: Layout) -> None:
    if not _should_register_efi_entry(layout.disk):
        return
    if not os.path.isdir("/sys/firmware/efi/efivars"):
        return
    subprocess.run(
        [
            "chroot",
            root,
            "efibootmgr",
            "--create",
            "--disk",
            layout.disk,
            "--part",
            "1",
            "--label",
            "Borked",
            "--loader",
            r"\EFI\fedora\shimx64.efi",
        ],
        check=False,
        stdout=subprocess.DEVNULL if os.environ.get("BORKED_QUIET") == "1" else None,
        stderr=subprocess.DEVNULL if os.environ.get("BORKED_QUIET") == "1" else None,
    )


def install_bootloader(root: str, layout: Layout, fs_uuid: str, cfg: Config) -> None:
    payload = root + ".efi-payload"
    boot_payload = root + ".boot-payload"
    boot_dir = os.path.join(root, "boot")
    efi_src = os.path.join(root, "boot/efi")
    try:
        if os.path.isdir(efi_src):
            shutil.copytree(efi_src, payload, dirs_exist_ok=True)
        if layout.boot and os.path.isdir(boot_dir):
            shutil.copytree(
                boot_dir,
                boot_payload,
                ignore=shutil.ignore_patterns("efi"),
                dirs_exist_ok=True,
            )
            _clear_dir(boot_dir)
        # grub2-probe only accepts / when the chroot root is itself a mount.
        run(["mount", "--bind", root, root])
        try:
            if layout.boot:
                os.makedirs(boot_dir, exist_ok=True)
                mount(layout.boot, boot_dir)
                if os.path.isdir(boot_payload):
                    shutil.copytree(boot_payload, boot_dir, dirs_exist_ok=True)
            try:
                os.makedirs(efi_src, exist_ok=True)
                mount(layout.esp, efi_src)
                try:
                    _fill_esp(root, efi_src, payload, layout, fs_uuid, cfg)
                finally:
                    umount(efi_src)
            finally:
                if layout.boot:
                    umount(boot_dir)
        finally:
            umount(root)
    finally:
        shutil.rmtree(payload, ignore_errors=True)
        shutil.rmtree(boot_payload, ignore_errors=True)

    # The live ISO kernel matches the image policy. A host that is one
    # release behind can refuse a type with EINVAL; keep going so `just qemu`
    # on that host still boots.
    cmd = [
        "chroot",
        root,
        "setfiles",
        "-F",
        "/etc/selinux/targeted/contexts/files/file_contexts",
        "/",
    ]
    print("+", " ".join(cmd), flush=True)
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        if err:
            print(err, flush=True)
        if not _only_invalid_argument(err):
            raise SystemExit(err or f"setfiles failed ({result.returncode})")
        print("borked: setfiles hit a label the host kernel does not know; continuing", flush=True)


def _fill_esp(root: str, efi_src: str, payload: str, layout: Layout, fs_uuid: str, cfg: Config) -> None:
    wanted = ("shimx64.efi", "mmx64.efi", "grubx64.efi", "grub.efi")
    found: dict[str, str] = {}
    search_root = payload if os.path.isdir(payload) else root
    for name in wanted:
        path = _find(search_root, name) or _find(root, name)
        if path:
            found[name] = path
    if "shimx64.efi" not in found or "grubx64.efi" not in found:
        raise SystemExit(f"signed EFI binaries missing from the image: {sorted(found)}")

    for directory in ("EFI/fedora", "EFI/BOOT"):
        dest = os.path.join(efi_src, directory)
        for name in ("shimx64.efi", "mmx64.efi", "grubx64.efi"):
            if name in found:
                _copy_named(found[name], dest)
    shutil.copy2(found["shimx64.efi"], os.path.join(efi_src, "EFI/BOOT/BOOTX64.EFI"))

    extra = f" {cfg.kernel_extra.strip()}" if cfg.kernel_extra.strip() else ""
    luks = f" rd.luks.uuid={layout.luks_uuid}" if layout.luks_uuid else ""
    cmdline = (
        f"root=UUID={fs_uuid} rootflags=subvol=@ rw selinux=1"
        f"{luks} console=tty0{extra}\n"
    )
    os.makedirs(os.path.join(root, "etc/kernel"), exist_ok=True)
    Path(os.path.join(root, "etc/kernel/cmdline")).write_text(cmdline)
    # Written before cmdline so kernel-install does not treat grub as newer
    # and replace the command line. OS prober would scan the build machine.
    Path(os.path.join(root, "etc/default/grub")).write_text(
        "GRUB_TIMEOUT=1\n"
        "GRUB_DISABLE_OS_PROBER=true\n"
        "GRUB_ENABLE_BLSCFG=true\n"
        "GRUB_DISABLE_SUBMENU=true\n"
        f"GRUB_CMDLINE_LINUX=\"{cmdline.strip()}\"\n"
        "GRUB_CMDLINE_LINUX_DEFAULT=\"\"\n"
    )
    Path(os.path.join(root, "etc/dracut.conf.d/99-borked.conf")).write_text(
        'hostonly="no"\nhostonly_cmdline="no"\n'
    )

    mounted = _bind(root)
    try:
        entries = Path(root) / "boot/loader/entries"
        if entries.is_dir():
            for entry in entries.glob("*.conf"):
                entry.unlink()
        kvers = sorted(path.name for path in Path(root, "lib/modules").iterdir() if path.is_dir())
        if not kvers:
            raise SystemExit("no kernel modules in the received image")
        for kver in kvers:
            vmlinuz = f"/lib/modules/{kver}/vmlinuz"
            if not os.path.exists(os.path.join(root, vmlinuz.lstrip("/"))):
                vmlinuz = f"/boot/vmlinuz-{kver}"
            initrd = f"/boot/initramfs-{kver}.img"
            if not os.path.exists(os.path.join(root, initrd.lstrip("/"))):
                run(
                    [
                        "chroot",
                        root,
                        "dracut",
                        "--force",
                        "--no-hostonly",
                        initrd,
                        kver,
                    ]
                )
            run(["chroot", root, "kernel-install", "add", kver, vmlinuz, initrd])
        run(["chroot", root, "grub2-mkconfig", "-o", "/boot/grub2/grub.cfg"])
        # grub's BLS helper can drop back to a short root= line. Put the
        # command line we wrote back onto every entry.
        for entry in Path(root, "boot/loader/entries").glob("*.conf"):
            lines = []
            for line in entry.read_text().splitlines():
                if line.startswith("options "):
                    lines.append("options " + cmdline.strip())
                else:
                    lines.append(line)
            entry.write_text("\n".join(lines) + "\n")
        _register_efi_entry(root, layout)
    finally:
        for target in reversed(mounted):
            umount(target)

    stub = _grub_stub(layout, fs_uuid)
    for directory in ("EFI/fedora", "EFI/BOOT"):
        Path(os.path.join(efi_src, directory, "grub.cfg")).write_text(stub)
