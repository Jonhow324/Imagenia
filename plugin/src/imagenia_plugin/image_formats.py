"""Identify the PNG and JPEG byte streams accepted from image providers.

The workbench stores original provider bytes instead of re-encoding them, so this
module is intentionally limited to formats it can validate and measure safely.
"""

from __future__ import annotations

from typing import NamedTuple

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
_JPEG_START = b"\xff\xd8\xff"
# Start-of-frame markers carry the image dimensions. DHT (C4), JPG (C8) and
# DAC (CC) share the 0xC0 range but are not frame headers.
_JPEG_FRAMES = frozenset((0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                          0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF))


class ImageFormat(NamedTuple):
    mime: str
    suffix: str
    width: int
    height: int


def sniff_image(content: bytes) -> ImageFormat | None:
    """Return the verified format and dimensions, or None for unsupported data."""
    if len(content) >= 24 and content[:16] == _PNG_SIGNATURE:
        width = int.from_bytes(content[16:20], "big")
        height = int.from_bytes(content[20:24], "big")
        if width and height:
            return ImageFormat("image/png", ".png", width, height)
        return None
    if content[:3] != _JPEG_START:
        return None
    index = 2
    while index + 4 <= len(content):
        if content[index] != 0xFF:
            return None
        marker = content[index + 1]
        index += 2
        while marker == 0xFF:
            if index >= len(content):
                return None
            marker = content[index]
            index += 1
        if marker == 0xD9:
            return None
        if marker == 0xDA:
            # Start of scan before any frame header: dimensions are unavailable.
            return None
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            continue
        if index + 2 > len(content):
            return None
        length = int.from_bytes(content[index:index + 2], "big")
        if length < 2 or index + length > len(content):
            return None
        if marker in _JPEG_FRAMES:
            if length < 7:
                return None
            height = int.from_bytes(content[index + 3:index + 5], "big")
            width = int.from_bytes(content[index + 5:index + 7], "big")
            if width and height:
                return ImageFormat("image/jpeg", ".jpg", width, height)
            return None
        index += length
    return None
