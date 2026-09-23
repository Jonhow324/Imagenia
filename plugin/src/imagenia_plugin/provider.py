"""OpenAI Images adapter; tests inject a deterministic fake instead of networking."""

from __future__ import annotations

import base64
import binascii
import json
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Callable, Protocol

from .settings import DEFAULT_BASE_URL, DEFAULT_MODEL


class ProviderError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ImageProvider(Protocol):
    def generate(self, prompt: str, *, size: str, quality: str) -> bytes: ...
    def edit(self, prompt: str, source: bytes, *, size: str, quality: str) -> bytes: ...


class OpenAIImageProvider:
    """Generate one PNG with the effective backend model and endpoint."""
    dimensions = {"square": "1024x1024", "landscape": "1536x1024", "portrait": "1024x1536"}
    qualities = {"standard": "medium", "high": "high"}

    def __init__(self, key_lookup: Callable[[], str | None], *,
                 base_url: str | Callable[[], str] = DEFAULT_BASE_URL,
                 model: str | Callable[[], str] = DEFAULT_MODEL) -> None:
        self.key_lookup = key_lookup
        self.base_url = base_url
        self.model = model

    def generate(self, prompt: str, *, size: str, quality: str) -> bytes:
        key = self.key_lookup()
        if not key:
            raise ProviderError("not_configured")
        base_url = self.base_url() if callable(self.base_url) else self.base_url
        model = self.model() if callable(self.model) else self.model
        request = urllib.request.Request(
            f"{base_url.rstrip('/')}/images/generations",
            data=json.dumps({"model": model, "prompt": prompt,
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

    def edit(self, prompt: str, source: bytes, *, size: str, quality: str) -> bytes:
        key = self.key_lookup()
        if not key:
            raise ProviderError("not_configured")
        base_url = self.base_url() if callable(self.base_url) else self.base_url
        model = self.model() if callable(self.model) else self.model
        boundary = f"imagenia-{uuid.uuid4().hex}"
        body = bytearray()
        for name, value in (("model", model), ("prompt", prompt),
                            ("size", self.dimensions[size]), ("quality", self.qualities[quality]),
                            ("n", "1")):
            body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
            body.extend(value.encode("utf-8"))
            body.extend(b"\r\n")
        body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="source.png"\r\nContent-Type: image/png\r\n\r\n'.encode())
        body.extend(source)
        body.extend(f"\r\n--{boundary}--\r\n".encode())
        request = urllib.request.Request(
            f"{base_url.rstrip('/')}/images/edits", data=bytes(body),
            headers={"Authorization": f"Bearer {key}", "Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=570) as response:
                payload = json.load(response)
            return base64.b64decode(payload["data"][0]["b64_json"], validate=True)
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

    def edit(self, prompt: str, source: bytes, *, size: str, quality: str) -> bytes:
        self.calls += 1
        return self.image_bytes
