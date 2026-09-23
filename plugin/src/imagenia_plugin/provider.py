"""OpenAI Images adapter; tests inject a deterministic fake instead of networking."""

from __future__ import annotations

import base64
import binascii
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Protocol


class ProviderError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ImageProvider(Protocol):
    def generate(self, prompt: str, *, size: str, quality: str) -> bytes: ...


class OpenAIImageProvider:
    """Generate one PNG; model and endpoint are fixed by the backend."""

    model = "gpt-image-1"
    dimensions = {"square": "1024x1024", "landscape": "1536x1024", "portrait": "1024x1536"}
    qualities = {"standard": "medium", "high": "high"}

    def __init__(self, key_lookup: Callable[[], str | None]) -> None:
        self.key_lookup = key_lookup

    def generate(self, prompt: str, *, size: str, quality: str) -> bytes:
        key = self.key_lookup()
        if not key:
            raise ProviderError("not_configured")
        request = urllib.request.Request(
            "https://api.openai.com/v1/images/generations",
            data=json.dumps({"model": self.model, "prompt": prompt,
                             "size": self.dimensions[size], "quality": self.qualities[quality],
                             "n": 1}).encode("utf-8"),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=570) as response:
                payload = json.load(response)
            encoded = payload["data"][0]["b64_json"]
            return base64.b64decode(encoded, validate=True)
        except urllib.error.HTTPError as exc:
            raise ProviderError("invalid_api_key" if exc.code in (401, 403) else "service_unavailable") from None
        except (urllib.error.URLError, TimeoutError, OSError, KeyError, IndexError,
                ValueError, TypeError, binascii.Error):
            raise ProviderError("service_unavailable") from None


@dataclass
class FakeImageProvider:
    """Network-free PNG provider for tests; never used as the host default."""

    calls: int = 0
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
