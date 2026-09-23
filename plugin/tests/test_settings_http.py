"""Observable configuration behavior through the plugin HTTP contract."""

import os
import stat
import sys
from pathlib import Path

import httpx
import pytest

PLUGIN_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from src.imagenia_plugin import create_app  # noqa: E402


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    monkeypatch.delenv("IMAGENIA_OPENAI_API_KEY", raising=False)
    calls = []

    def probe(key):
        calls.append(key)

    data_dir = tmp_path / "data"
    app = create_app(data_dir, connection_probe=probe)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test"), data_dir, calls


@pytest.mark.anyio
async def test_key_is_saved_and_overwritten_without_ever_returning_it(app_client):
    http, data_dir, calls = app_client
    async with http:
        empty = await http.get("/api/imagenia/settings")
        first = await http.put("/api/imagenia/settings/openai", json={"api_key": "sk-first-secret"})
        second = await http.put("/api/imagenia/settings/openai", json={"api_key": "sk-second-secret"})
        status = await http.get("/api/imagenia/settings")
    assert empty.json() == {"openai": {"configured": False, "source": "none"}}
    assert first.status_code == second.status_code == status.status_code == 200
    assert status.json() == second.json() == {"openai": {"configured": True, "source": "file"}}
    assert "sk-" not in repr(first.json()) + repr(second.json()) + repr(status.json())
    assert calls == []  # saving never makes a billable or non-billable external request
    private_file = data_dir / "config" / "openai.json"
    assert stat.S_IMODE(private_file.stat().st_mode) == 0o600
    assert stat.S_IMODE(private_file.parent.stat().st_mode) == 0o700
    assert "sk-second-secret" in private_file.read_text()
    assert "sk-first-secret" not in private_file.read_text()


@pytest.mark.anyio
async def test_environment_key_takes_priority_and_survives_file_updates(app_client, monkeypatch):
    http, _, calls = app_client
    async with http:
        await http.put("/api/imagenia/settings/openai", json={"api_key": "sk-file-secret"})
        monkeypatch.setenv("IMAGENIA_OPENAI_API_KEY", "sk-env-secret")
        state = await http.get("/api/imagenia/settings")
        result = await http.post("/api/imagenia/settings/openai/test")
    assert state.json() == {"openai": {"configured": True, "source": "environment"}}
    assert result.status_code == 200
    assert result.json() == {"status": "ok"}
    assert calls == ["sk-env-secret"]


@pytest.mark.anyio
async def test_connection_probe_is_explicit_and_never_calls_image_generation(app_client):
    http, _, calls = app_client
    async with http:
        missing = await http.post("/api/imagenia/settings/openai/test")
        await http.put("/api/imagenia/settings/openai", json={"api_key": "sk-test-secret"})
        tested = await http.post("/api/imagenia/settings/openai/test")
    assert missing.status_code == 409
    assert missing.json()["error"]["code"] == "not_configured"
    assert tested.json() == {"status": "ok"}
    assert calls == ["sk-test-secret"]


@pytest.mark.anyio
async def test_invalid_settings_input_and_probe_errors_are_safe(app_client):
    http, _, calls = app_client
    async with http:
        for payload in (b"not-json", b"[]", b'{}', b'{"api_key":"  "}', b'{"api_key":"sk-abc\\nunsafe"}'):
            result = await http.put("/api/imagenia/settings/openai", content=payload)
            assert result.status_code in {400, 422}
            assert "sk-" not in result.text
        state = await http.get("/api/imagenia/settings")
    assert state.json()["openai"]["configured"] is False
    assert calls == []


@pytest.mark.anyio
async def test_key_is_available_after_restart_and_permissions_remain_private(app_client):
    http, data_dir, _ = app_client
    async with http:
        await http.put("/api/imagenia/settings/openai", json={"api_key": "sk-persistent-secret"})
    restarted = create_app(data_dir, connection_probe=lambda key: None)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=restarted), base_url="http://test") as client:
        result = await client.get("/api/imagenia/settings")
    assert result.json() == {"openai": {"configured": True, "source": "file"}}
    assert stat.S_IMODE((data_dir / "config" / "openai.json").stat().st_mode) == 0o600

@pytest.mark.anyio
async def test_insecure_or_corrupt_private_file_never_exposes_content(app_client):
    http, data_dir, _ = app_client
    private_file = data_dir / "config" / "openai.json"
    private_file.parent.mkdir(parents=True)
    private_file.write_text('{"api_key":"sk-exposed-secret"}')
    private_file.chmod(0o644)
    async with http:
        insecure = await http.get("/api/imagenia/settings")
        private_file.chmod(0o600)
        private_file.write_text('{"api_key":')
        corrupt = await http.get("/api/imagenia/settings")
    for result in (insecure, corrupt):
        assert result.status_code == 503
        assert result.json()["error"]["code"] == "configuration_unavailable"
        assert "sk-exposed-secret" not in result.text


@pytest.mark.anyio
async def test_failed_connection_is_redacted_without_changing_saved_key(tmp_path, monkeypatch):
    monkeypatch.delenv("IMAGENIA_OPENAI_API_KEY", raising=False)

    def failing_probe(key):
        raise RuntimeError(f"Authorization: Bearer {key}")

    app = create_app(tmp_path / "data", connection_probe=failing_probe)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        await http.put("/api/imagenia/settings/openai", json={"api_key": "sk-private-secret"})
        failed = await http.post("/api/imagenia/settings/openai/test")
        status = await http.get("/api/imagenia/settings")
    assert failed.status_code == 502
    assert failed.json()["error"]["code"] == "service_unavailable"
    assert "sk-private-secret" not in failed.text
    assert status.json() == {"openai": {"configured": True, "source": "file"}}

@pytest.mark.anyio
async def test_private_config_directory_must_not_be_world_readable(app_client):
    http, data_dir, _ = app_client
    async with http:
        await http.put("/api/imagenia/settings/openai", json={"api_key": "sk-private-secret"})
        (data_dir / "config").chmod(0o755)
        response = await http.get("/api/imagenia/settings")
    assert response.status_code == 503
    assert "sk-private-secret" not in response.text

@pytest.mark.anyio
async def test_connection_failure_code_cannot_echo_secret(tmp_path, monkeypatch):
    from src.imagenia_plugin.settings import ConnectionFailed

    monkeypatch.delenv("IMAGENIA_OPENAI_API_KEY", raising=False)

    def failing_probe(key):
        raise ConnectionFailed(f"Authorization: Bearer {key}")

    app = create_app(tmp_path / "data", connection_probe=failing_probe)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        await http.put("/api/imagenia/settings/openai", json={"api_key": "sk-private-secret"})
        response = await http.post("/api/imagenia/settings/openai/test")
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "service_unavailable"
    assert "sk-private-secret" not in response.text

@pytest.mark.anyio
async def test_real_probe_uses_read_only_models_endpoint_and_maps_auth_failure(tmp_path, monkeypatch):
    import urllib.error
    import urllib.request

    monkeypatch.delenv("IMAGENIA_OPENAI_API_KEY", raising=False)
    observed = []

    def fake_urlopen(request, timeout):
        observed.append((request.full_url, request.get_method(), request.get_header("Authorization"), timeout))
        raise urllib.error.HTTPError(request.full_url, 401, "bad key", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    app = create_app(tmp_path / "data")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        await http.put("/api/imagenia/settings/openai", json={"api_key": "sk-private-secret"})
        result = await http.post("/api/imagenia/settings/openai/test")
    assert observed == [("https://api.openai.com/v1/models", "GET", "Bearer sk-private-secret", 5)]
    assert result.status_code == 502
    assert result.json()["error"]["code"] == "invalid_api_key"
    assert "sk-private-secret" not in result.text


@pytest.mark.anyio
async def test_control_characters_are_not_persisted_in_api_key(app_client):
    http, data_dir, _ = app_client
    async with http:
        result = await http.put("/api/imagenia/settings/openai", json={"api_key": "sk-unsafe\tsecret"})
    assert result.status_code == 422
    assert not (data_dir / "config" / "openai.json").exists()
