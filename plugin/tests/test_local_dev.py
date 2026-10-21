"""Exercise the local entry point through the production FastAPI router."""

import asyncio
import struct
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from dev import create_dev_app  # noqa: E402


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def local_dev(tmp_path, monkeypatch):
    monkeypatch.setenv("IMAGENIA_DEV_DATA_DIR", str(tmp_path / "preview"))
    monkeypatch.setenv("IMAGENIA_DEV_PROVIDER", "fake")
    monkeypatch.setenv("IMAGENIA_DEV_SEED", "36")
    monkeypatch.setenv("IMAGENIA_DATA_DIR", str(tmp_path / "host-data"))
    for name in ("IMAGENIA_OPENAI_API_KEY", "IMAGENIA_OPENAI_BASE_URL", "IMAGENIA_OPENAI_MODEL"):
        monkeypatch.delenv(name, raising=False)

    def no_network(*args, **kwargs):
        pytest.fail("Preview mode must never contact an external provider")

    monkeypatch.setattr("urllib.request.urlopen", no_network)
    return tmp_path


@pytest.mark.anyio
async def test_preview_seeds_paginated_library_without_network_and_preserves_edits(local_dev):
    server = create_dev_app()
    async with server.router.lifespan_context(server):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server), base_url="http://local") as http:
            assert (await http.get("/api/imagenia/settings")).json()["openai"]["configured"]
            assert (await http.post("/api/imagenia/settings/openai/test")).status_code == 200
            first = (await http.get("/api/imagenia/assets")).json()
            assert len(first["items"]) == 30
            second = (await http.get("/api/imagenia/assets", params={"cursor": first["next_cursor"]})).json()
            assert len(second["items"]) == 6
            assert second["next_cursor"] is None
            asset_id = first["items"][0]["id"]
            assert (await http.delete(f"/api/imagenia/assets/{asset_id}")).status_code == 200
    assert not (local_dev / "host-data").exists()
    # Reopening uses the same SQLite/files, without reseeding deleted assets.
    reopened = create_dev_app()
    async with reopened.router.lifespan_context(reopened):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=reopened), base_url="http://local") as http:
            first = (await http.get("/api/imagenia/assets")).json()
            second = (await http.get("/api/imagenia/assets", params={"cursor": first["next_cursor"]})).json()
            assert len(first["items"]) + len(second["items"]) == 35
            assert (await http.get(f"/api/imagenia/assets/{asset_id}")).status_code == 404


@pytest.mark.anyio
async def test_preview_background_generation_and_edit_publish_real_pngs(local_dev, monkeypatch):
    monkeypatch.setenv("IMAGENIA_DEV_SEED", "0")
    server = create_dev_app()
    async with server.router.lifespan_context(server):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server), base_url="http://local") as http:
            source_id = None
            for path, size, dimensions in (("generate", "portrait", (1024, 1536)),
                                           ("edit", "landscape", (1536, 1024))):
                payload = {"prompt": "local scene with soft light", "size": size}
                if source_id:
                    payload["source_asset_id"] = source_id
                response = await http.post(f"/api/imagenia/jobs/{path}", json=payload)
                assert response.status_code == 202
                job_id = response.json()["job_id"]
                for _ in range(100):
                    job = (await http.get(f"/api/imagenia/jobs/{job_id}")).json()
                    if job["status"] in {"succeeded", "failed"}:
                        break
                    await asyncio.sleep(0.02)
                assert job["status"] == "succeeded"
                asset_id = job["result_asset_id"]
                content = (await http.get(f"/api/imagenia/assets/{asset_id}/content")).content
                assert content.startswith(b"\x89PNG\r\n\x1a\n")
                assert struct.unpack(">II", content[16:24]) == dimensions
                if source_id:
                    detail = (await http.get(f"/api/imagenia/assets/{asset_id}")).json()
                    assert detail["source_asset_id"] == source_id
                    assert (await http.get(f"/api/imagenia/assets/{source_id}/content")).status_code == 200
                source_id = asset_id


def test_openai_mode_rejects_automatic_seeding(local_dev, monkeypatch):
    monkeypatch.setenv("IMAGENIA_DEV_PROVIDER", "openai")
    with pytest.raises(ValueError, match="Seeding requires fake mode"):
        create_dev_app()
