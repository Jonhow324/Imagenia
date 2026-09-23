"""Verify the edits request without making a network call."""
import base64
import io
import json
import sys
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from src.imagenia_plugin.provider import FakeImageProvider, OpenAIImageProvider, ProviderError  # noqa: E402


def test_edit_posts_png_to_configured_images_endpoint(monkeypatch):
    seen = {}
    png = FakeImageProvider.image_bytes

    def urlopen(request, timeout):
        seen.update(url=request.full_url, method=request.get_method(), headers=request.headers,
                    data=request.data, timeout=timeout)
        return io.BytesIO(json.dumps({"data": [{"b64_json": base64.b64encode(png).decode()}]}).encode())

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    provider = OpenAIImageProvider(lambda: "secret", base_url=lambda: "https://example.test/v1",
                                   model=lambda: "gpt-image-1")
    assert provider.edit("加一条河", png, size="portrait", quality="high") == png
    assert seen["url"] == "https://example.test/v1/images/edits"
    assert seen["method"] == "POST" and seen["timeout"] == 570
    assert seen["headers"]["Authorization"] == "Bearer secret"
    assert "multipart/form-data; boundary=" in seen["headers"]["Content-type"]
    assert b'name="image"; filename="source.png"' in seen["data"]
    assert b"Content-Type: image/png\r\n\r\n" + png in seen["data"]
    for value in (b'gpt-image-1', b'1024x1536', b'high', '加一条河'.encode()):
        assert value in seen["data"]


def test_edit_rejects_missing_key_and_maps_provider_errors(monkeypatch):
    provider = OpenAIImageProvider(lambda: None)
    with pytest.raises(ProviderError, match="not_configured"):
        provider.edit("prompt", FakeImageProvider.image_bytes, size="square", quality="standard")

    def unauthorized(*args, **kwargs):
        raise urllib.error.HTTPError("https://example.test", 401, "no", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", unauthorized)
    provider = OpenAIImageProvider(lambda: "secret")
    with pytest.raises(ProviderError, match="invalid_api_key"):
        provider.edit("prompt", FakeImageProvider.image_bytes, size="square", quality="standard")
