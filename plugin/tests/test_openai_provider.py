"""OpenAI wire contract without network or billable image requests."""
import io
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from src.imagenia_plugin.provider import OpenAIImageProvider, ProviderError  # noqa: E402


def test_models_sizes_quality_and_base64_mapping(monkeypatch):
    calls = []
    class Response(io.BytesIO):
        pass

    def fake_open(request, timeout):
        calls.append((request.full_url, request.get_method(), json.loads(request.data),
                      request.get_header("Authorization"), timeout))
        return Response(b'{"data":[{"b64_json":"cG5n"}]}')

    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    provider = OpenAIImageProvider(lambda: "sk-test-only")
    for size, quality in (("square", "standard"), ("landscape", "high"), ("portrait", "standard")):
        assert provider.generate("a glass house", size=size, quality=quality) == b"png"
    assert [call[2]["size"] for call in calls] == ["1024x1024", "1536x1024", "1024x1536"]
    assert [call[2]["quality"] for call in calls] == ["medium", "high", "medium"]
    assert all(call[0] == "https://api.openai.com/v1/images/generations" and
               call[1] == "POST" and call[2]["model"] == "gpt-image-2.5" and
               call[2]["n"] == 1 and call[3] == "Bearer sk-test-only" and call[4] == 570 for call in calls)


def test_missing_config_and_upstream_failure_are_safe(monkeypatch):
    with pytest.raises(ProviderError, match="not_configured"):
        OpenAIImageProvider(lambda: None).generate("prompt", size="square", quality="high")

    def fail(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 401, "sk-secret", {}, None)
    monkeypatch.setattr(urllib.request, "urlopen", fail)
    with pytest.raises(ProviderError, match="invalid_api_key") as error:
        OpenAIImageProvider(lambda: "sk-secret").generate("prompt", size="square", quality="high")
    assert "sk-secret" not in str(error.value)


def test_configured_endpoint_and_model_are_sent_without_network(monkeypatch):
    captured = []
    def fake_open(request, timeout):
        captured.append((request.full_url, json.loads(request.data)["model"]))
        return io.BytesIO(b'{"data":[{"b64_json":"cG5n"}]}')
    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    provider = OpenAIImageProvider(lambda: "sk-test-only",
        base_url=lambda: "https://gateway.example/v1/", model=lambda: "custom-image-v2")
    assert provider.generate("test", size="square", quality="standard") == b"png"
    assert captured == [("https://gateway.example/v1/images/generations", "custom-image-v2")]

@pytest.mark.parametrize("method", ["generate", "edit"])
@pytest.mark.parametrize("failure, expected", [
    (429, "rate_limited"), (503, "service_unavailable"),
    ("timeout", "timeout"), ("bad_json", "invalid_response"),
    ("bad_payload", "invalid_response"),
])
def test_upstream_failures_have_stable_safe_codes(monkeypatch, method, failure, expected):
    def fake_open(request, timeout):
        if isinstance(failure, int):
            raise urllib.error.HTTPError(request.full_url, failure, "sk-private /tmp/secret", {}, None)
        if failure == "timeout":
            raise urllib.error.URLError(TimeoutError("sk-private /tmp/secret"))
        return io.BytesIO(b"not json" if failure == "bad_json" else b'{"data":[]}')
    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    provider = OpenAIImageProvider(lambda: "sk-private")
    args = ("secret prompt", b"source") if method == "edit" else ("secret prompt",)
    with pytest.raises(ProviderError) as raised:
        getattr(provider, method)(*args, size="square", quality="standard")
    assert raised.value.code == expected
    assert "sk-private" not in str(raised.value)
    assert "/tmp/secret" not in str(raised.value)
