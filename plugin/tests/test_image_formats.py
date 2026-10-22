"""Provider image bytes are accepted only in the formats the library can prove."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1]))
from src.imagenia_plugin.image_formats import sniff_image  # noqa: E402
from src.imagenia_plugin.provider import FakeImageProvider  # noqa: E402


def jpeg_bytes(width: int, height: int) -> bytes:
    app0 = b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    frame = (b"\xff\xc0\x00\x11\x08" + height.to_bytes(2, "big") + width.to_bytes(2, "big")
             + b"\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00")
    return b"\xff\xd8" + app0 + frame + b"\xff\xd9"


def test_png_and_jpeg_dimensions_and_mime():
    png = FakeImageProvider.image_bytes
    assert sniff_image(png) == ("image/png", ".png", 1, 1)
    assert sniff_image(jpeg_bytes(1280, 720)) == ("image/jpeg", ".jpg", 1280, 720)


def test_unsupported_or_truncated_data_is_rejected():
    jpeg = jpeg_bytes(32, 32)
    for content in (b"", b"not an image", png_without_dimensions(), jpeg[:2], jpeg[:6]):
        assert sniff_image(content) is None


def png_without_dimensions() -> bytes:
    # The signature is present but the IHDR dimensions are zero.
    return b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 8
