"""Catalog shape. Does not install anything."""

import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps"))
sys.path.insert(0, str(ROOT / "installer"))

from borked_apps import duo, install as apps_install  # noqa: E402
from borked_apps.__main__ import main  # noqa: E402
from borked_apps.catalog import App, load  # noqa: E402
from borked_apps.install import InstallError  # noqa: E402
from borked_apps.kiwi import ubuntu_zip_url, verify_deb  # noqa: E402
from borked_apps.voice import OK  # noqa: E402
from borked_install import bootloader, partition, receive, tui as install_tui  # noqa: E402


class CatalogTest(unittest.TestCase):
    def test_groups_and_kinds(self) -> None:
        apps = load()
        by_id = {app.id: app for app in apps}
        self.assertEqual(
            list(by_id),
            [
                "codex",
                "claude",
                "antigravity",
                "opencode",
                "t3",
                "hermes",
                "vscode",
                "cursor",
                "rambox",
                "virt",
                "duo",
                "kiwi",
                "scrcpy",
                "moonlight",
                "sunshine",
                "solidcraft",
                "artcraft",
                "orcaslicer",
                "prusaslicer",
            ],
        )
        self.assertEqual(by_id["t3"].target, "https://t3.codes/install.sh")
        self.assertEqual(by_id["moonlight"].packages(), ["moonlight-qt"])
        self.assertEqual(by_id["prusaslicer"].packages(), ["prusa-slicer"])
        self.assertEqual(by_id["artcraft"].check, "art-craft")
        self.assertTrue(by_id["sunshine"].target.endswith("fc45.x86_64.rpm"))
        self.assertEqual(by_id["kiwi"].kind, "distrobox")
        self.assertEqual(by_id["kiwi"].target, "ubuntu:24.04 kiwi")
        self.assertEqual(by_id["duo"].kind, "dnf")
        self.assertEqual(by_id["duo"].packages(), ["duo_unix", "duo_unix-selinux"])
        self.assertEqual(by_id["claude"].repo_name(), "claude-code")
        self.assertEqual(by_id["claude"].packages(), ["claude-code"])
        self.assertEqual(by_id["vscode"].packages(), ["code"])
        self.assertEqual(
            by_id["virt"].packages(),
            ["virt-manager", "qemu-kvm", "libvirt-daemon-kvm", "virt-install"],
        )
        self.assertTrue(by_id["codex"].target.startswith("https://"))
        repos = Path(__file__).resolve().parents[1] / "apps" / "repos"
        for app in apps:
            if app.kind == "dnf-repo":
                self.assertTrue((repos / f"{app.repo_name()}.repo").is_file(), app.id)

    def test_command(self) -> None:
        self.assertEqual(main([]), 0)
        self.assertEqual(main(["nope"]), 2)
        self.assertEqual(main(["apps", "--list"]), 0)
        self.assertEqual(main(["duo", "--help"]), 0)
        self.assertEqual(main(["kiwi", "--help"]), 0)
        self.assertTrue(any("never mind" in line for line in OK))

    def test_kiwi_link_and_checksum(self) -> None:
        page = (
            'href="https://www.cytrence.com/_files/archives/'
            '851e5a_8282c203d4c841d98d4628512b50bd46.zip?dn=CytrenceKiwi-1.6.4-ubuntu24_amd64.zip"'
        )
        self.assertTrue(ubuntu_zip_url(page).endswith("ubuntu24_amd64.zip"))
        data = b"not-a-real-deb"
        digest = hashlib.sha256(data).hexdigest()
        verify_deb("CytrenceKiwi.deb", data, f"{digest}  CytrenceKiwi.deb\n")
        with self.assertRaises(InstallError):
            verify_deb("CytrenceKiwi.deb", b"tampered", f"{digest}  CytrenceKiwi.deb\n")

    def test_pinned_repo_keys(self) -> None:
        repos_dir = ROOT / "repos"
        keys_dir = repos_dir / "keys"
        for repo_file in sorted(repos_dir.glob("*.repo")):
            text = repo_file.read_text()
            self.assertIn("gpgcheck=1", text, repo_file.name)
            for line in text.splitlines():
                if line.startswith("gpgkey="):
                    value = line.split("=", 1)[1].strip()
                    self.assertTrue(value.startswith("file:///"), f"{repo_file.name}: {value}")
                    if value.startswith("file:///etc/pki/rpm-gpg/"):
                        key_name = value.rsplit("/", 1)[-1]
                        self.assertTrue((keys_dir / key_name).is_file(), f"missing key {key_name}")

    def test_is_installed_uses_user_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / ".local" / "bin"
            bin_dir.mkdir(parents=True)
            (bin_dir / "custom-tool").write_text("#!/bin/sh\n")
            app = App("Test", "custom", "Custom", "desc", "script", "https://example.invalid/i.sh", "custom-tool")
            with mock.patch.object(apps_install.shutil, "which", return_value=None), mock.patch.object(
                apps_install, "user_home", return_value=Path(tmp)
            ):
                self.assertTrue(apps_install.is_installed(app))

    def test_duo_ssh_reuses_existing_conf_and_handles_inactive_sshd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            conf = Path(tmp) / "login_duo.conf"
            conf.write_text("[duo]\n")
            calls: list[list[str]] = []

            def fake_run(cmd: list[str]) -> None:
                calls.append(cmd)

            with (
                mock.patch.object(duo, "CONF", conf),
                mock.patch.object(duo, "_ensure_installed"),
                mock.patch.object(duo, "_write_conf") as write_conf,
                mock.patch.object(duo, "_root_write"),
                mock.patch.object(duo, "_run", side_effect=fake_run),
                mock.patch.object(
                    duo.subprocess,
                    "run",
                    return_value=subprocess.CompletedProcess([], 3),
                ),
            ):
                rc = duo.run(["--ssh"])
            self.assertEqual(rc, 0)
            write_conf.assert_not_called()
            self.assertEqual(calls, [["sshd", "-t"]])


class InstallerHelpersTest(unittest.TestCase):
    def test_stream_magic_reads_only_prefix(self) -> None:
        with tempfile.NamedTemporaryFile() as tmp:
            tmp.write(b"\x28\xb5\x2f\xfd" + b"payload")
            tmp.flush()
            self.assertEqual(receive._stream_magic(tmp.name), b"\x28\xb5\x2f\xfd")

    def test_partition_layout_and_grub_stub(self) -> None:
        self.assertEqual(partition._sfdisk_script(False).count("\n"), 3)
        self.assertEqual(partition._sfdisk_script(True).count("\n"), 4)
        plain = partition.Layout("/dev/vda", "/dev/vda1", "/dev/vda2", "ESP-UUID", None)
        self.assertIn("($root)/@/boot/grub2", bootloader._grub_stub(plain, "FS-UUID"))
        luks = partition.Layout(
            "/dev/vda", "/dev/vda1", "/dev/mapper/borked", "ESP-UUID", "LUKS-UUID", "/dev/vda2", "BOOT-UUID"
        )
        stub = bootloader._grub_stub(luks, "FS-UUID")
        self.assertIn("BOOT-UUID", stub)
        self.assertIn("($root)/grub2", stub)
        self.assertFalse(bootloader._should_register_efi_entry("/dev/loop0"))
        self.assertTrue(bootloader._should_register_efi_entry("/dev/nvme0n1"))
        self.assertTrue(bootloader._should_register_efi_entry("/dev/vda"))

    def test_setfiles_error_check(self) -> None:
        self.assertTrue(bootloader._only_invalid_argument("setfiles: /foo: Invalid argument\n"))
        self.assertFalse(bootloader._only_invalid_argument("setfiles: /foo: Invalid argument\nsetfiles: Permission denied\n"))
        self.assertFalse(bootloader._only_invalid_argument(""))

    def test_disk_filter_and_reserved_users(self) -> None:
        sample = (
            "sda 500G disk 0\n"
            "sdb 16G disk 0\n"
            "sdc 16G disk 1\n"
            "zram0 8G disk 0\n"
            "loop0 2G disk 0\n"
            "sr0 1.2G rom 1\n"
            "nvme0n1 1T disk 0\n"
        )
        self.assertEqual(
            install_tui._filter_disks(sample, excluded={"sdb"}),
            [("/dev/sda", "500G"), ("/dev/nvme0n1", "1T")],
        )
        self.assertTrue(install_tui._is_reserved_user("root"))
        self.assertTrue(install_tui._is_reserved_user("cosmic-greeter"))
        self.assertFalse(install_tui._is_reserved_user("borked_user_test_xyz"))


if __name__ == "__main__":
    unittest.main()
