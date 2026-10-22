"""MiniMax image_generation wire contract without network or billable requests."""
import base64
import io
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from src.imagenia_plugin.provider import MiniMaxImageProvider, ProviderError  # noqa: E402


def jpeg_bytes(width: int = 16, height: int = 16) -> bytes:
    app0 = b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    frame = (b"\xff\xc0\x00\x11\x08" + height.to_bytes(2, "big") + width.to_bytes(2, "big")
             + b"\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00")
    return b"\xff\xd8" + app0 + frame + b"\xff\xd9"


def test_generate_posts_native_request_and_decodes_base64():
    calls = []
    image = jpeg_bytes(1280, 720)

    def fake_open(request, timeout):
        calls.append((request.full_url, request.get_method(), json.loads(request.data),
                      request.get_header("Authorization"), timeout))
        return io.BytesIO(json.dumps({
            "id": "trace", "data": {"image_base64": [base64.b64encode(image).decode()]},
            "metadata": {"failed_count": "0", "success_count": "1"},
            "base_resp": {"status_code": 0, "status_msg": "success"},
        }).encode())

    monkey = pytest.MonkeyPatch()
    monkey.setattr(urllib.request, "urlopen", fake_open)
    try:
        provider = MiniMaxImageProvider(lambda: "mm-test-only")
        assert provider.generate("a paper forest", size="landscape", quality="high") == image
    finally:
        monkey.undo()

    assert len(calls) == 1
    url, method, body, authorization, timeout = calls[0]
    assert url == "https://api.minimax.cn/v1/image_generation"
    assert method == "POST" and timeout == 570
    assert authorization == "Bearer mm-test-only"
    assert body == {"model": "image-01", "prompt": "a paper forest", "aspect_ratio": "16:9",
                    "response_format": "base64", "n": 1}


def test_square_and_portrait_aspect_ratios():
    seen = []

    def fake_open(request, timeout):
        seen.append(json.loads(request.data)["aspect_ratio"])
        return io.BytesIO(json.dumps({"data": {"image_base64": [base64.b64encode(b"jpeg").decode()]}}).encode())

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
        return io.BytesIO(json.dumps({"data": {"image_base64": [base64.b64encode(b"jpeg").decode()]}}).encode())

    monkey = pytest.MonkeyPatch()
    monkey.setattr(urllib.request, "urlopen", fake_open)
    try:
        provider = MiniMaxImageProvider(lambda: "key", base_url="https://api.minimax.io/v1/",
                                        model="image-01-live")
        provider.generate("p", size="square", quality="standard")
    finally:
        monkey.undo()
    assert captured == [("https://api.minimax.io/v1/image_generation", "image-01-live")]


def test_errors_and_edit_are_stable_and_secret_free():
    with pytest.raises(ProviderError, match="not_configured"):
        MiniMaxImageProvider(lambda: None).generate("p", size="square", quality="standard")

    provider = MiniMaxImageProvider(lambda: "mm-private")
    with pytest.raises(ProviderError, match="edit_not_supported"):
        provider.edit("p", b"source", size="square", quality="standard")

    def unauthorized(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 401, "mm-private /tmp/private", {}, None)

    monkey = pytest.MonkeyPatch()
    monkey.setattr(urllib.request, "urlopen", unauthorized)
    try:
        with pytest.raises(ProviderError, match="invalid_api_key") as error:
            provider.generate("p", size="square", quality="standard")
    finally:
        monkey.undo()
    assert "mm-private" not in str(error.value) and "/tmp/private" not in str(error.value)

    def api_error(request, timeout):
        return io.BytesIO(json.dumps({"base_resp": {"status_code": 1004, "status_msg": "mm-private"}}).encode())

    monkey = pytest.MonkeyPatch()
    monkey.setattr(urllib.request, "urlopen", api_error)
    try:
        with pytest.raises(ProviderError, match="invalid_api_key") as error:
            provider.generate("p", size="square", quality="standard")
    finally:
        monkey.undo()
    assert "mm-private" not in str(error.value)


@pytest.mark.parametrize("payload", [
    {"data": {}}, {"data": {"image_base64": []}}, {"data": {"image_base64": ["not base64!"]}},
    {"base_resp": {"status_code": 0}},
])
def test_invalid_responses_are_reported(payload):
    monkey = pytest.MonkeyPatch()
    monkey.setattr(urllib.request, "urlopen", lambda request, timeout: io.BytesIO(json.dumps(payload).encode()))
    try:
        with pytest.raises(ProviderError, match="invalid_response"):
            MiniMaxImageProvider(lambda: "key").generate("p", size="square", quality="standard")
    finally:
        monkey.undo()


@pytest.mark.parametrize("status,expected", [
    (1002, "rate_limited"),
    (1004, "invalid_api_key"),
    (1008, "insufficient_balance"),
    (2013, "invalid_request"),
    (1013, "service_unavailable"),
])
def test_business_errors_keep_their_own_code(status, expected):
    """HTTP 200 + base_resp is MiniMax's normal error channel; do not flatten it."""
    payload = {"base_resp": {"status_code": status, "status_msg": "mm-private balance detail"}}
    monkey = pytest.MonkeyPatch()
    monkey.setattr(urllib.request, "urlopen", lambda request, timeout: io.BytesIO(json.dumps(payload).encode()))
    try:
        with pytest.raises(ProviderError, match=expected) as error:
            MiniMaxImageProvider(lambda: "key").generate("p", size="square", quality="standard")
    finally:
        monkey.undo()
    assert error.value.code == expected
    assert "mm-private" not in str(error.value)


def test_http_payment_required_maps_to_insufficient_balance():
    def payment_required(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 402, "mm-private", {}, None)

    monkey = pytest.MonkeyPatch()
    monkey.setattr(urllib.request, "urlopen", payment_required)
    try:
        with pytest.raises(ProviderError, match="insufficient_balance") as error:
            MiniMaxImageProvider(lambda: "key").generate("p", size="square", quality="standard")
    finally:
        monkey.undo()
    assert "mm-private" not in str(error.value)
