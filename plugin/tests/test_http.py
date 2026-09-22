import json
import sys
from pathlib import Path

import httpx
import pytest

PLUGIN_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from src.imagenia_plugin import FakeImageProvider, create_app  # noqa: E402


@pytest.fixture
def client(tmp_path):
    provider = FakeImageProvider()
    app = create_app(tmp_path / "data", provider=provider)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test"), provider, tmp_path


@pytest.mark.anyio
async def test_health_check_uses_isolated_database(client):
    http, provider, tmp_path = client
    async with http:
        response = await http.get("/api/imagenia/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "imagenia", "provider": "fake", "database": "ok"}
    assert (tmp_path / "data" / "imagenia.sqlite3").exists()
    assert provider.calls == 0


@pytest.mark.anyio
async def test_generate_creates_pending_job_without_real_provider_call(client):
    http, provider, tmp_path = client
    async with http:
        response = await http.post(
            "/api/imagenia/jobs/generate",
            json={"prompt": "a quiet red house", "size": "square", "quality": "standard"},
        )
    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "pending"
    assert len(payload["job_id"]) == 36
    assert provider.calls == 0
    assert (tmp_path / "data" / "images").is_dir()


@pytest.mark.anyio
async def test_invalid_request_is_safe_and_does_not_call_provider(client):
    http, provider, _ = client
    async with http:
        response = await http.post("/api/imagenia/jobs/generate", content=b"not-json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_json"
    assert provider.calls == 0
