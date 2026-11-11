"""MiniMax H3-Image wire contract without network or billable requests."""
import base64
import io
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from src.imagenia_plugin.provider import FakeImageProvider, MiniMaxImageProvider, ProviderError  # noqa: E402


def jpeg_bytes(width: int = 16, height: int = 16) -> bytes:
    app0 = b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    frame = (b"\xff\xc0\x00\x11\x08" + height.to_bytes(2, "big") + width.to_bytes(2, "big")
             + b"\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00")
    return b"\xff\xd8" + app0 + frame + b"\xff\xd9"


def image_response(image: bytes) -> io.BytesIO:
    return io.BytesIO(json.dumps({
        "created": 1792308678,
        "data": [{"b64_json": base64.b64encode(image).decode(), "size": "1360x768",
                  "revised_prompt": "enhanced prompt"}],
        "output_format": "jpeg", "usage": {"generated_images": 1}, "request_id": "trace",
    }).encode())


def test_generate_posts_h3_request_and_decodes_base64():
    calls = []
    image = jpeg_bytes(1280, 720)

    def fake_open(request, timeout):
        calls.append((request.full_url, request.get_method(), json.loads(request.data),
                      request.get_header("Authorization"), timeout))
        return image_response(image)

    monkey = pytest.MonkeyPatch()
    monkey.setattr(urllib.request, "urlopen", fake_open)
    try:
        provider = MiniMaxImageProvider(lambda: "mm-test-only")
        assert provider.generate("a paper forest", size="landscape", quality="high") == image
    finally:
        monkey.undo()

    assert len(calls) == 1
    url, method, body, authorization, timeout = calls[0]
    assert url == "https://api.minimax.cn/v1/images/generations"
    assert method == "POST" and timeout == 570
    assert authorization == "Bearer mm-test-only"
    assert body == {"model": "MiniMax-H3-Image", "prompt": "a paper forest", "aspect_ratio": "16:9",
                    "area": "1K", "response_format": "b64_json", "n": 1}


def test_square_and_portrait_aspect_ratios():
    seen = []

    def fake_open(request, timeout):
        seen.append(json.loads(request.data)["aspect_ratio"])
        return image_response(b"jpeg")

    monkey = pytest.MonkeyPatch()
    monkey.setattr(urllib.request, "urlopen", fake_open)
    try:
        provider = MiniMaxImageProvider(lambda: "key")
        provider.generate("p", size="square", quality="standard")
        provider.generate("p", size="portrait", quality="standard")
    finally:
        monkey.undo()
    assert seen == ["1:1", "9:16"]


def test_configured_base_url_and_model_are_used():
    captured = []

    def fake_open(request, timeout):
        captured.append((request.full_url, json.loads(request.data)["model"]))
        return image_response(b"jpeg")

    monkey = pytest.MonkeyPatch()
    monkey.setattr(urllib.request, "urlopen", fake_open)
    try:
        provider = MiniMaxImageProvider(lambda: "key", base_url="https://api.minimax.io/v1/",
                                        model="MiniMax-H3-Image-Highspeed")
        provider.generate("p", size="square", quality="standard")
    finally:
        monkey.undo()
    assert captured == [("https://api.minimax.io/v1/images/generations", "MiniMax-H3-Image-Highspeed")]


@pytest.mark.parametrize("source,mime", [(FakeImageProvider.image_bytes, "image/png"),
                                         (jpeg_bytes(), "image/jpeg")])
def test_edit_posts_reference_image_as_data_uri(source, mime):
    calls = []
    result = jpeg_bytes(32, 32)

    def fake_open(request, timeout):
        calls.append((request.full_url, request.get_method(), json.loads(request.data),
                      request.get_header("Authorization"), timeout))
        return image_response(result)

    monkey = pytest.MonkeyPatch()
    monkey.setattr(urllib.request, "urlopen", fake_open)
    try:
        provider = MiniMaxImageProvider(lambda: "mm-test-only")
        assert provider.edit("add a river", source, size="portrait", quality="standard") == result
    finally:
        monkey.undo()

    assert len(calls) == 1
    url, method, body, authorization, timeout = calls[0]
    assert url == "https://api.minimax.cn/v1/images/edits"
    assert method == "POST" and timeout == 570
    assert authorization == "Bearer mm-test-only"
    assert body == {"model": "MiniMax-H3-Image", "prompt": "add a river",
                    "images": [{"image_url": f"data:{mime};base64,{base64.b64encode(source).decode()}"}],
                    "aspect_ratio": "9:16", "area": "1K", "response_format": "b64_json", "n": 1}


def test_edit_rejects_unrecognised_source_without_a_request():
    def fail_open(request, timeout):
        raise AssertionError("no request may be sent for an invalid source")

    monkey = pytest.MonkeyPatch()
    monkey.setattr(urllib.request, "urlopen", fail_open)
    try:
        with pytest.raises(ProviderError, match="invalid_request"):
            MiniMaxImageProvider(lambda: "key").edit("p", b"not an image", size="square", quality="standard")
    finally:
        monkey.undo()


def test_missing_key_is_not_configured_for_generate_and_edit():
    provider = MiniMaxImageProvider(lambda: None)
    with pytest.raises(ProviderError, match="not_configured"):
        provider.generate("p", size="square", quality="standard")
    with pytest.raises(ProviderError, match="not_configured"):
        provider.edit("p", FakeImageProvider.image_bytes, size="square", quality="standard")


@pytest.mark.parametrize("status,expected", [
    (400, "invalid_request"),
    (401, "invalid_api_key"),
    (403, "invalid_api_key"),
    (402, "insufficient_balance"),
    (422, "invalid_request"),
    (429, "rate_limited"),
    (500, "service_unavailable"),
])
def test_http_errors_keep_their_own_code_and_stay_secret_free(status, expected):
    def http_error(request, timeout):
        raise urllib.error.HTTPError(request.full_url, status, "mm-private /tmp/private", {}, None)

    monkey = pytest.MonkeyPatch()
    monkey.setattr(urllib.request, "urlopen", http_error)
    try:
        with pytest.raises(ProviderError, match=expected) as error:
            MiniMaxImageProvider(lambda: "mm-private").generate("p", size="square", quality="standard")
    finally:
        monkey.undo()
    assert error.value.code == expected
    assert "mm-private" not in str(error.value) and "/tmp/private" not in str(error.value)


def test_edit_http_errors_use_the_same_mapping():
    def unauthorized(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 401, "mm-private", {}, None)

    monkey = pytest.MonkeyPatch()
    monkey.setattr(urllib.request, "urlopen", unauthorized)
    try:
        with pytest.raises(ProviderError, match="invalid_api_key") as error:
            MiniMaxImageProvider(lambda: "mm-private").edit(
                "p", FakeImageProvider.image_bytes, size="square", quality="standard")
    finally:
        monkey.undo()
    assert "mm-private" not in str(error.value)


@pytest.mark.parametrize("payload", [
    {}, {"data": []}, {"data": [{}]}, {"data": [{"b64_json": "not base64!"}]},
    {"data": [{"error": {"code": "1027", "message": "output image failed content safety check"}}]},
])
def test_invalid_responses_are_reported(payload):
    monkey = pytest.MonkeyPatch()
    monkey.setattr(urllib.request, "urlopen", lambda request, timeout: io.BytesIO(json.dumps(payload).encode()))
    try:
        with pytest.raises(ProviderError, match="invalid_response"):
            MiniMaxImageProvider(lambda: "key").generate("p", size="square", quality="standard")
    finally:
        monkey.undo()
