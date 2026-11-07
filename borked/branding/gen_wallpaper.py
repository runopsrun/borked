#!/usr/bin/env python3
"""Draw branding/wallpaper.png from the projectborked.com page background."""

import math
import struct
import zlib
from pathlib import Path

W, H = 1920, 1080
BG = (0x0B, 0x0A, 0x12)
PINK = (0xFF, 0x3D, 0x81)
CYAN = (0x2D, 0xE2, 0xE6)


def chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def mix(base: tuple[int, int, int], color: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    return tuple(int(base[i] + (color[i] - base[i]) * amount) for i in range(3))


def glow(x: int, y: int, cx: float, cy: float, rx: float, ry: float) -> float:
    # The site fades each glow out by 60% of its radius.
    distance = math.hypot((x - cx) / rx, (y - cy) / ry)
    if distance >= 0.6:
        return 0.0
    return 1.0 - distance / 0.6


def main() -> None:
    raw = bytearray()
    pink_at = (0.80 * W, -0.10 * H)
    cyan_at = (-0.10 * W, 0.30 * H)
    for y in range(H):
        raw.append(0)
        for x in range(W):
            pix = BG
            pink = glow(x, y, *pink_at, 900, 600)
            if pink:
                pix = mix(pix, PINK, pink * (0x26 / 255))
            cyan = glow(x, y, *cyan_at, 800, 600)
            if cyan:
                pix = mix(pix, CYAN, cyan * (0x1A / 255))
            if y % 4 >= 2:
                pix = tuple(int(channel * (1 - 0x1F / 255)) for channel in pix)
            raw.extend(pix)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    dest = Path(__file__).with_name("wallpaper.png")
    dest.write_bytes(png)
    print(f"wrote {dest} ({len(png)} bytes)")


if __name__ == "__main__":
    main()
