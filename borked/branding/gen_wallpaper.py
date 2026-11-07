#!/usr/bin/env python3
"""Rasterize branding/wallpaper.svg into branding/wallpaper.png.

The SVG is the page background from projectborked.com. cosmic-bg reads a
PNG, and the two faces it names are vendored beside this script so the
render does not depend on whatever fonts the build host has installed.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SVG = ROOT / "wallpaper.svg"
PNG = ROOT / "wallpaper.png"
FONTS = ROOT / "fonts"

CONF = """<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <dir>{fonts}</dir>
  <cachedir>{cache}</cachedir>
</fontconfig>
"""


def main() -> None:
    if not SVG.is_file():
        raise SystemExit(f"missing {SVG}")
    with tempfile.TemporaryDirectory() as tmp:
        cache = Path(tmp) / "cache"
        cache.mkdir()
        conf = Path(tmp) / "fonts.conf"
        conf.write_text(CONF.format(fonts=FONTS, cache=cache))
        env = os.environ.copy()
        env["FONTCONFIG_FILE"] = str(conf)
        if shutil.which("rsvg-convert"):
            subprocess.check_call(
                ["rsvg-convert", "-w", "1920", "-h", "1080", "-o", str(PNG), str(SVG)],
                env=env,
            )
        elif shutil.which("magick"):
            subprocess.check_call(
                ["magick", "-background", "none", str(SVG), "-resize", "1920x1080", str(PNG)],
                env=env,
            )
        else:
            raise SystemExit("need rsvg-convert or magick to render wallpaper.svg")
    print(f"wrote {PNG}")


if __name__ == "__main__":
    main()
