"""Run the install phases in order."""

from __future__ import annotations

from borked_install.bootloader import install_bootloader
from borked_install.config import Config
from borked_install.configure import configure
from borked_install.partition import partition
from borked_install.receive import receive
from borked_install.util import Cleanup


def install(cfg: Config) -> None:
    cleanup = Cleanup()
    try:
        layout = partition(cfg.disk, cfg.luks_passphrase, cleanup)
        root, fs_uuid = receive(layout.root_dev, cfg.stream, cleanup)
        configure(root, cfg, layout, fs_uuid)
        install_bootloader(root, layout, fs_uuid, cfg)
        print("borked install: done", flush=True)
    finally:
        cleanup.run()
    if cfg.poweroff:
        import os

        os.sync()
        os.execvp("poweroff", ["poweroff", "-f"])
