"""Catalog shape. Does not install anything."""

import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps"))

from borked_apps.__main__ import main  # noqa: E402
from borked_apps.catalog import load  # noqa: E402
from borked_apps.install import InstallError  # noqa: E402
from borked_apps.kiwi import ubuntu_zip_url, verify_deb  # noqa: E402
from borked_apps.voice import OK  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
