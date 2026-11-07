#!/usr/bin/env python3
"""Draw branding/wallpaper.png. Solid regions, so the PNG stays small."""

import struct
import zlib
from pathlib import Path

W, H = 1920, 1080


def chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def pixel(x: int, y: int) -> bytes:
    # Deep plum field, a broken red bar, a thin warm line.
    if 180 <= y < 260 and (x < 760 or x > 1160):
        return b"\xe8\x50\x46"
    if 250 <= y < 258:
        return b"\xc4\x78\x55"
    shade = 18 + (x + y) // 180
    return bytes((shade, 12, 22))


def main() -> None:
    raw = bytearray()
    for y in range(H):
        raw.append(0)
        row = bytearray()
        for x in range(W):
            row.extend(pixel(x, y))
        raw.extend(row)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    dest = Path(__file__).with_name("wallpaper.png")
    dest.write_bytes(png)
    print(f"wrote {dest} ({len(png)} bytes)")


if __name__ == "__main__":
    main()
