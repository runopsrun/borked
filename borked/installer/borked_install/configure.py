"""Per-machine files: user, hostname, fstab, machine-id."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from borked_install.config import DESKTOP_SESSIONS, Config
from borked_install.partition import Layout
from borked_install.util import run


# Same entry the image writes over cosmic-bg's Fedora default, so the
# account keeps the site background if that package is updated later.
_WALLPAPER = """(
    output: "all",
    source: Path("/usr/share/backgrounds/borked/default.png"),
    filter_by_theme: false,
    rotation_frequency: 3600,
    filter_method: Lanczos,
    scaling_mode: Zoom,
    sampling_method: Alphanumeric,
)
"""


def _token(value: str) -> bool:
    return bool(value) and all(ch.isalnum() or ch in "_.@-" for ch in value)


def _user_uid(root: str, username: str) -> int:
    for line in Path(root, "etc/passwd").read_text().splitlines():
        parts = line.split(":")
        if len(parts) >= 3 and parts[0] == username:
            return int(parts[2])
    raise SystemExit(f"no uid for {username}")


def _seed_greeter_session(root: str, cfg: Config) -> None:
    # cosmic-greeter remembers last_session per UID. Seed it so the first
    # login opens the desktop the installer asked for.
    session = DESKTOP_SESSIONS.get(cfg.desktop, "COSMIC")
    uid = _user_uid(root, cfg.username)
    greeter = Path(root) / "var/lib/cosmic-greeter/.config/cosmic/com.system76.CosmicGreeter/v1"
    greeter.mkdir(parents=True, exist_ok=True)
    (greeter / "users").write_text(
        "{\n"
        f"  {uid}: (\n"
        f"    uid: {uid},\n"
        f'    last_session: Some("{session}"),\n'
        "  ),\n"
        "}\n"
    )
    (greeter / "last_user").write_text(f"Some({uid})\n")
    run(
        [
            "chroot",
            root,
            "chown",
            "-R",
            "cosmic-greeter:cosmic-greeter",
            "/var/lib/cosmic-greeter",
        ]
    )


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
    locale = cfg.locale if _token(cfg.locale) else "en_US.UTF-8"
    keymap = cfg.keymap if _token(cfg.keymap) else "us"
    xkb = cfg.xkb_layout if _token(cfg.xkb_layout) else "us"
    _write(os.path.join(root, "etc/locale.conf"), f"LANG={locale}\n")
    _write(os.path.join(root, "etc/vconsole.conf"), f"KEYMAP={keymap}\n")
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
        stderr=subprocess.DEVNULL if os.environ.get("BORKED_QUIET") == "1" else None,
    )
    run(["chroot", root, "passwd", "-l", "root"])
    # cosmic-initial-setup lists locales and ignores C.UTF-8. With no
    # language pack the page is empty and Next never enables. The
    # installer already chose the locale, so mark that wizard finished.
    config_dir = os.path.join(root, "home", cfg.username, ".config")
    os.makedirs(config_dir, exist_ok=True)
    Path(os.path.join(config_dir, "cosmic-initial-setup-done")).write_text("")
    locale = cfg.locale if _token(cfg.locale) else "en_US.UTF-8"
    xkb = cfg.xkb_layout if _token(cfg.xkb_layout) else "us"
    comp = os.path.join(config_dir, "cosmic/com.system76.CosmicComp/v1")
    settings = os.path.join(config_dir, "cosmic/com.system76.CosmicSettings/v1")
    os.makedirs(comp, exist_ok=True)
    os.makedirs(settings, exist_ok=True)
    Path(os.path.join(comp, "xkb_config")).write_text(
        f'(rules:"",model:"",layout:"{xkb}",variant:"",'
        f"options:None,repeat_delay:600,repeat_rate:25)\n"
    )
    Path(os.path.join(settings, "system_locales")).write_text(f'["{locale}"]\n')
    background = os.path.join(config_dir, "cosmic/com.system76.CosmicBackground/v1")
    os.makedirs(background, exist_ok=True)
    Path(os.path.join(background, "all")).write_text(_WALLPAPER)
    if cfg.desktop == "hyprland":
        hypr = os.path.join(config_dir, "hypr")
        os.makedirs(hypr, exist_ok=True)
        for name in ("hyprland.conf", "hyprpaper.conf"):
            src = Path(root) / "usr/share/borked/hypr" / name
            if src.is_file():
                Path(hypr, name).write_text(src.read_text())
    run(
        [
            "chroot",
            root,
            "chown",
            "-R",
            f"{cfg.username}:{cfg.username}",
            f"/home/{cfg.username}/.config",
        ]
    )
    _seed_greeter_session(root, cfg)
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
