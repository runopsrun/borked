"""Catalog shape. Does not install anything."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps"))

from borked_apps.__main__ import main  # noqa: E402
from borked_apps.catalog import load  # noqa: E402
from borked_apps.voice import OK  # noqa: E402


class CatalogTest(unittest.TestCase):
    def test_groups_and_kinds(self) -> None:
        apps = load()
        by_id = {app.id: app for app in apps}
        self.assertEqual(
            list(by_id),
            ["codex", "claude", "antigravity", "opencode", "vscode", "cursor", "rambox", "virt", "duo"],
        )
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
        self.assertTrue(any("never mind" in line for line in OK))


if __name__ == "__main__":
    unittest.main()
