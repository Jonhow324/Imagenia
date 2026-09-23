"""Favorite and permanent deletion through the public ASGI contract."""
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from src.imagenia_plugin import FakeImageProvider, create_app  # noqa: E402


@pytest.mark.anyio
async def test_favorite_roundtrip_validation_and_filter(tmp_path, monkeypatch):
    monkeypatch.setenv("IMAGENIA_OPENAI_API_KEY", "sk-fake")
    app = create_app(tmp_path / "data", FakeImageProvider())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        queued = await http.post("/api/imagenia/jobs/generate", json={"prompt": "private source"})
        assert app.worker.process_next()
        asset_id = (await http.get(f"/api/imagenia/jobs/{queued.json()['job_id']}")).json()["result_asset_id"]
        url = f"/api/imagenia/assets/{asset_id}"
        assert (await http.patch(url, json={"is_favorite": True})).json()["is_favorite"] is True
        assert app.database.execute("SELECT favorited_at FROM image_assets WHERE id=?", (asset_id,)).fetchone()[0]
        assert [item["id"] for item in (await http.get("/api/imagenia/assets?favorite=true")).json()["items"]] == [asset_id]
        assert (await http.patch(url, json={"is_favorite": False})).json()["is_favorite"] is False
        assert app.database.execute("SELECT favorited_at FROM image_assets WHERE id=?", (asset_id,)).fetchone()[0] is None
        assert not (await http.get("/api/imagenia/assets?favorite=true")).json()["items"]
        for invalid in ([], {"is_favorite": 1}, {}, {"is_favorite": True, "prompt": "injected"}):
            assert (await http.patch(url, json=invalid)).status_code == 422
        assert (await http.patch(url, content=b"no-json")).status_code == 400
        assert (await http.patch("/api/imagenia/assets/missing", json={"is_favorite": True})).status_code == 404


@pytest.mark.anyio
async def test_delete_removes_file_detaches_children_and_redacts_jobs(tmp_path, monkeypatch):
    monkeypatch.setenv("IMAGENIA_OPENAI_API_KEY", "sk-fake")
    app = create_app(tmp_path / "data", FakeImageProvider())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        first = await http.post("/api/imagenia/jobs/generate", json={"prompt": "secret original"})
        assert app.worker.process_next()
        first_job = first.json()["job_id"]
        parent = (await http.get(f"/api/imagenia/jobs/{first_job}")).json()["result_asset_id"]
        second = await http.post("/api/imagenia/jobs/edit", json={"source_asset_id": parent, "prompt": "secret child"})
        assert app.worker.process_next()
        second_job = second.json()["job_id"]
        child = (await http.get(f"/api/imagenia/jobs/{second_job}")).json()["result_asset_id"]
        pending = await http.post("/api/imagenia/jobs/edit", json={"source_asset_id": parent, "prompt": "secret queued"})
        file_path = tmp_path / "data" / app.database.execute("SELECT file_path FROM image_assets WHERE id=?", (parent,)).fetchone()[0]
        assert file_path.is_file()
        assert (await http.delete(f"/api/imagenia/assets/{parent}")).status_code == 200
        assert not file_path.exists()
        assert (await http.get(f"/api/imagenia/assets/{parent}")).status_code == 404
        assert (await http.get(f"/api/imagenia/assets/{parent}/content")).status_code == 404
        assert (await http.get(f"/api/imagenia/assets/{child}")).json()["source_asset_id"] is None
        assert (await http.get(f"/api/imagenia/assets/{child}/content")).status_code == 200
        assert not app.worker.process_next()
        for job_id in (first_job, second_job, pending.json()["job_id"]):
            job = (await http.get(f"/api/imagenia/jobs/{job_id}")).json()
            assert job["prompt"] == "" and job["result_asset_id"] is None
            row = app.database.execute("SELECT * FROM generation_jobs WHERE id=?", (job_id,)).fetchone()
            assert row["request_json"] is None and row["source_asset_id"] is None
        assert (await http.get(f"/api/imagenia/jobs/{pending.json()['job_id']}")).json()["status"] == "failed"
        assert (await http.delete(f"/api/imagenia/assets/{parent}")).status_code == 404


@pytest.mark.anyio
async def test_delete_rejects_untrusted_stored_path_without_touching_outside_file(tmp_path):
    app = create_app(tmp_path / "data", FakeImageProvider())
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"do not delete")
    app.database.execute("""INSERT INTO image_assets
      (id,kind,prompt,model,size,quality,width,height,file_path,mime_type,file_size,created_at,updated_at)
      VALUES ('bad','generated','private','model','square','standard',1,1,?,'image/png',1,'now','now')""", (str(outside),))
    app.database.commit()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        assert (await http.delete("/api/imagenia/assets/bad")).status_code == 409
        assert outside.read_bytes() == b"do not delete"
        assert (await http.get("/api/imagenia/assets/bad")).status_code == 200

@pytest.mark.anyio
async def test_delete_while_edit_provider_is_running_cannot_publish_or_restore_secret(tmp_path, monkeypatch):
    import threading
    monkeypatch.setenv("IMAGENIA_OPENAI_API_KEY", "sk-fake")
    provider = FakeImageProvider()
    app = create_app(tmp_path / "data", provider)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        parent_job = await http.post("/api/imagenia/jobs/generate", json={"prompt": "original"})
        assert app.worker.process_next()
        parent = (await http.get(f"/api/imagenia/jobs/{parent_job.json()['job_id']}")).json()["result_asset_id"]
        edit = await http.post("/api/imagenia/jobs/edit", json={"source_asset_id": parent, "prompt": "private in flight"})
        started, release = threading.Event(), threading.Event()
        original_edit = provider.edit
        def blocked_edit(*args, **kwargs):
            started.set()
            assert release.wait(5)
            return original_edit(*args, **kwargs)
        provider.edit = blocked_edit
        worker = threading.Thread(target=app.worker.process_next)
        worker.start()
        try:
            assert started.wait(5)
            assert (await http.delete(f"/api/imagenia/assets/{parent}")).status_code == 200
        finally:
            release.set()
            worker.join(timeout=5)
        assert not worker.is_alive()
        job = (await http.get(f"/api/imagenia/jobs/{edit.json()['job_id']}")).json()
        assert job["status"] == "failed" and job["prompt"] == "" and job["result_asset_id"] is None
        assert (await http.get("/api/imagenia/assets")).json()["items"] == []


def test_recover_interrupted_delete_restores_or_reaps_private_file(tmp_path, monkeypatch):
    monkeypatch.setenv("IMAGENIA_OPENAI_API_KEY", "sk-fake")
    app = create_app(tmp_path / "data", FakeImageProvider())
    assert app.handle("POST", "/api/imagenia/jobs/generate", b'{"prompt":"private"}')[0] == 202
    assert app.worker.process_next()
    row = app.database.execute("SELECT id, file_path FROM image_assets").fetchone()
    image = app.data_dir / row["file_path"]
    tombstone = image.with_name(f".{image.name}.deleting")
    image.rename(tombstone)
    app.database.close()
    recovered = create_app(tmp_path / "data")
    assert image.exists() and not tombstone.exists()
    recovered.database.execute("DELETE FROM image_assets WHERE id=?", (row["id"],))
    recovered.database.commit()
    image.rename(tombstone)
    recovered.database.close()
    finished = create_app(tmp_path / "data")
    assert not image.exists() and not tombstone.exists()
    finished.database.close()
