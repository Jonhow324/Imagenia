"""Image provider interfaces used by the HTTP and worker seams."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class ImageProvider(Protocol):
    """The narrow boundary the real OpenAI adapter will implement later."""

    def generate(self, prompt: str, *, size: str, quality: str) -> bytes:
        """Return image bytes for a generation request."""


@dataclass
class FakeImageProvider:
    """Deterministic provider for tests and local mock development.

    The payload is a valid 1x1 transparent PNG. No network calls are made.
    """

    calls: int = 0

    # A tiny transparent PNG, kept inline to make the test seam dependency-free.
    image_bytes: bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
        b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDAT"
        b"\x08\xd7c\xf8\xcf\xc0\xf0\x1f\x00\x05\x00\x01\xff"
        b"\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    def generate(self, prompt: str, *, size: str, quality: str) -> bytes:
        self.calls += 1
        return self.image_bytes
