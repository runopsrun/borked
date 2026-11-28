"""borked-install entry point."""

from __future__ import annotations

import argparse
import os
import sys

from borked_install.config import load_config
from borked_install.install import install


def main() -> int:
    if os.geteuid() != 0:
        print("borked-install must run as root", file=sys.stderr)
        return 1
    parser = argparse.ArgumentParser(prog="borked-install")
    parser.add_argument("--config", help="JSON config. Otherwise look for a cidata volume.")
    args = parser.parse_args()
    cfg = load_config(args.config)
    if cfg.interactive and not cfg.poweroff:
        from borked_install.tui import present_install

        return present_install(cfg)
    install(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
