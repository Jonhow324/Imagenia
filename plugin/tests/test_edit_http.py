"""Editing creates a new linked asset without changing the source."""
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from src.imagenia_plugin import FakeImageProvider, create_app  # noqa: E402
from src.imagenia_plugin.provider import ProviderError  # noqa: E402


@pytest.mark.anyio
async def test_edit_retains_source_and_records_direct_parent(tmp_path, monkeypatch):
    monkeypatch.setenv("IMAGENIA_OPENAI_API_KEY", "sk-fake")
    provider = FakeImageProvider()
    app = create_app(tmp_path / "data", provider=provider)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        created = await http.post("/api/imagenia/jobs/generate", json={"prompt": "original landscape"})
        assert app.worker.process_next()
        source_id = (await http.get(f"/api/imagenia/jobs/{created.json()['job_id']}")).json()["result_asset_id"]
        original = (await http.get(f"/api/imagenia/assets/{source_id}" )).json()
        original_bytes = (await http.get(f"/api/imagenia/assets/{source_id}/content")).content

        edited = await http.post("/api/imagenia/jobs/edit", json={
            "source_asset_id": source_id, "prompt": "add a small river", "size": "portrait", "quality": "high"})
        assert edited.status_code == 202
        pending = (await http.get(f"/api/imagenia/jobs/{edited.json()['job_id']}")).json()
        assert pending["kind"] == "edit" and pending["status"] == "pending"
        assert app.worker.process_next()
        completed = (await http.get(f"/api/imagenia/jobs/{edited.json()['job_id']}")).json()
        assert completed["status"] == "succeeded"
        result = (await http.get(f"/api/imagenia/assets/{completed['result_asset_id']}")).json()
        assert result["id"] != source_id and result["kind"] == "edited"
        assert result["source_asset_id"] == source_id and result["prompt"] == "add a small river"
        assert result["size"] == "portrait" and result["quality"] == "high"
        assert (await http.get(f"/api/imagenia/assets/{source_id}")).json() == original
        assert (await http.get(f"/api/imagenia/assets/{source_id}/content")).content == original_bytes
        assert (await http.get(f"/api/imagenia/assets/{result['id']}/content")).status_code == 200
        assert provider.calls == 2
        # Editing an edited asset records only its immediate parent.
        chained = await http.post("/api/imagenia/jobs/edit", json={
            "source_asset_id": result["id"], "prompt": "add a cloud"})
        assert chained.status_code == 202 and app.worker.process_next()
        child_id = (await http.get(f"/api/imagenia/jobs/{chained.json()['job_id']}")).json()["result_asset_id"]
        child = (await http.get(f"/api/imagenia/assets/{child_id}")).json()
        assert child["source_asset_id"] == result["id"]
        assert child["source_asset_id"] != source_id


@pytest.mark.anyio
async def test_edit_rejects_missing_or_unavailable_source_and_invalid_input(tmp_path, monkeypatch):
    monkeypatch.setenv("IMAGENIA_OPENAI_API_KEY", "sk-fake")
    app = create_app(tmp_path / "data", provider=FakeImageProvider())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        missing = await http.post("/api/imagenia/jobs/edit", json={"source_asset_id": "missing", "prompt": "change colors"})
        assert missing.status_code == 404 and missing.json()["error"]["code"] == "not_found"
        created = await http.post("/api/imagenia/jobs/generate", json={"prompt": "original landscape"})
        app.worker.process_next()
        source_id = (await http.get(f"/api/imagenia/jobs/{created.json()['job_id']}")).json()["result_asset_id"]
        for body in ({"prompt": "change colors"}, {"source_asset_id": source_id, "prompt": "  "},
                     {"source_asset_id": source_id, "prompt": "change colors", "model": "untrusted"},
                     {"source_asset_id": source_id, "prompt": "change colors", "mask": "bad"},
                     {"source_asset_id": source_id, "prompt": "change colors", "image": "bad"}):
            assert (await http.post("/api/imagenia/jobs/edit", json=body)).status_code == 422
        app.database.execute("UPDATE image_assets SET file_path='images/absent.png' WHERE id=?", (source_id,))
        app.database.commit()
        unavailable = await http.post("/api/imagenia/jobs/edit", json={"source_asset_id": source_id, "prompt": "change colors"})
        assert unavailable.status_code == 404
        assert "images/absent.png" not in unavailable.text


@pytest.mark.anyio
async def test_failed_edit_keeps_source_and_no_result(tmp_path, monkeypatch):
    monkeypatch.setenv("IMAGENIA_OPENAI_API_KEY", "sk-fake")
    provider = FakeImageProvider()
    app = create_app(tmp_path / "data", provider=provider)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        created = await http.post("/api/imagenia/jobs/generate", json={"prompt": "original landscape"})
        app.worker.process_next()
        source_id = (await http.get(f"/api/imagenia/jobs/{created.json()['job_id']}")).json()["result_asset_id"]
        def fail(*args, **kwargs):
            raise ProviderError("service_unavailable")
        provider.edit = fail
        edited = await http.post("/api/imagenia/jobs/edit", json={"source_asset_id": source_id, "prompt": "add river"})
        assert edited.status_code == 202 and app.worker.process_next()
        job = (await http.get(f"/api/imagenia/jobs/{edited.json()['job_id']}")).json()
        assert job["status"] == "failed" and job["result_asset_id"] is None
        assets = (await http.get("/api/imagenia/assets")).json()["items"]
        assert [asset["id"] for asset in assets] == [source_id]

@pytest.mark.anyio
async def test_queued_edit_fails_safely_if_source_disappears(tmp_path, monkeypatch):
    monkeypatch.setenv("IMAGENIA_OPENAI_API_KEY", "sk-fake")
    provider = FakeImageProvider()
    app = create_app(tmp_path / "data", provider=provider)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        created = await http.post("/api/imagenia/jobs/generate", json={"prompt": "original"})
        app.worker.process_next()
        source_id = (await http.get(f"/api/imagenia/jobs/{created.json()['job_id']}")).json()["result_asset_id"]
        edited = await http.post("/api/imagenia/jobs/edit", json={"source_asset_id": source_id, "prompt": "alter"})
        app.database.execute("UPDATE image_assets SET file_path='images/missing.png' WHERE id=?", (source_id,))
        app.database.commit()
        assert app.worker.process_next()
        result = (await http.get(f"/api/imagenia/jobs/{edited.json()['job_id']}")).json()
        assert result["status"] == "failed" and result["error_code"] == "source_unavailable"
        assert result["result_asset_id"] is None and provider.calls == 1
        assert "missing.png" not in result["error_message"]
