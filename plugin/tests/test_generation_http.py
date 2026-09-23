"""Generation and asset lifecycle tested at the public plugin HTTP boundary."""
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from src.imagenia_plugin import create_app, FakeImageProvider  # noqa: E402
from src.imagenia_plugin.provider import ProviderError  # noqa: E402


@pytest.fixture
def generation(tmp_path, monkeypatch):
    monkeypatch.setenv("IMAGENIA_OPENAI_API_KEY", "sk-fake")
    provider = FakeImageProvider()
    app = create_app(tmp_path / "data", provider=provider)
    return app, provider


@pytest.mark.anyio
async def test_submit_poll_and_read_persistent_image(generation):
    app, provider = generation
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        queued = await http.post("/api/imagenia/jobs/generate", json={"prompt": "mountain at dawn", "size": "portrait", "quality": "high"})
        assert queued.status_code == 202
        job_id = queued.json()["job_id"]
        pending = await http.get(f"/api/imagenia/jobs/{job_id}")
        assert pending.json()["status"] == "pending"
        assert provider.calls == 0
        assert app.worker.process_next()
        success = await http.get(f"/api/imagenia/jobs/{job_id}")
        assert success.json()["status"] == "succeeded"
        asset_id = success.json()["result_asset_id"]
        listing = await http.get("/api/imagenia/assets")
        assert [item["id"] for item in listing.json()["items"]] == [asset_id]
        assert listing.json()["items"][0]["quality"] == "high"
        content = await http.get(f"/api/imagenia/assets/{asset_id}/content")
        assert content.content == provider.image_bytes
        assert content.headers["content-type"].startswith("image/png")
        row = app.database.execute("SELECT file_path FROM image_assets WHERE id=?", (asset_id,)).fetchone()
        assert row["file_path"].startswith("images/20") and row["file_path"].endswith(f"/{asset_id}.png")
        assert (app.data_dir / row["file_path"]).read_bytes() == provider.image_bytes
        assert provider.calls == 1
        assert not app.worker.process_next()
        assert app.database.execute("SELECT COUNT(*) FROM image_assets").fetchone()[0] == 1
        restarted = create_app(app.data_dir, provider=FakeImageProvider())
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=restarted), base_url="http://test") as again:
            assert (await again.get(f"/api/imagenia/jobs/{job_id}")).json()["status"] == "succeeded"
            assert (await again.get(f"/api/imagenia/assets/{asset_id}/content")).content == provider.image_bytes


@pytest.mark.anyio
async def test_missing_configuration_and_invalid_inputs_never_enqueue(generation, monkeypatch):
    app, provider = generation
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        monkeypatch.delenv("IMAGENIA_OPENAI_API_KEY")
        missing = await http.post("/api/imagenia/jobs/generate", json={"prompt": "mountain at dawn"})
        monkeypatch.setenv("IMAGENIA_OPENAI_API_KEY", "sk-fake")
        for payload in ([], {}, {"prompt": "ok", "model": "arbitrary"},
                        {"prompt": "mountain at dawn", "quality": "premium"}):
            response = await http.post("/api/imagenia/jobs/generate", json=payload)
            assert response.status_code == 422
        unknown = await http.get("/api/imagenia/jobs/not-found")
        assert unknown.status_code == 404
    assert missing.status_code == 409 and missing.json()["error"]["code"] == "not_configured"
    assert provider.calls == 0


@pytest.mark.anyio
async def test_failed_provider_is_sanitized_and_no_asset_written(generation):
    app, _ = generation
    class FailingProvider:
        def generate(self, prompt, *, size, quality):
            raise ProviderError("secret-sk-sensitive")
    app.worker.provider = FailingProvider()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        queued = await http.post("/api/imagenia/jobs/generate", json={"prompt": "mountain at dawn"})
        assert app.worker.process_next()
        failed = await http.get(f"/api/imagenia/jobs/{queued.json()['job_id']}")
        assert failed.json()["status"] == "failed"
        assert "secret-sk-sensitive" not in failed.text
        assert (await http.get("/api/imagenia/assets")).json()["items"] == []

@pytest.mark.anyio
async def test_recovery_interrupts_running_but_resumes_pending(generation):
    app, provider = generation
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        first = (await http.post("/api/imagenia/jobs/generate", json={"prompt": "first scene"})).json()["job_id"]
        second = (await http.post("/api/imagenia/jobs/generate", json={"prompt": "second scene"})).json()["job_id"]
        app.database.execute("UPDATE generation_jobs SET status='running' WHERE id=?", (first,))
        app.database.commit()
        app.worker.recover()
        assert (await http.get(f"/api/imagenia/jobs/{first}")).json()["error_code"] == "interrupted"
        assert (await http.get(f"/api/imagenia/jobs/{second}")).json()["status"] == "pending"
        assert app.worker.process_next()
        assert (await http.get(f"/api/imagenia/jobs/{second}")).json()["status"] == "succeeded"
    assert provider.calls == 1


@pytest.mark.anyio
async def test_pending_queue_is_bounded(generation):
    app, provider = generation
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        for index in range(50):
            response = await http.post("/api/imagenia/jobs/generate", json={"prompt": f"view {index}"})
            assert response.status_code == 202
        rejected = await http.post("/api/imagenia/jobs/generate", json={"prompt": "view 51"})
    assert rejected.status_code == 429
    assert rejected.json()["error"]["code"] == "queue_full"
    assert provider.calls == 0

@pytest.mark.anyio
async def test_asset_content_cannot_read_outside_image_directory(generation):
    app, _ = generation
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        queued = await http.post("/api/imagenia/jobs/generate", json={"prompt": "mountain at dawn"})
        app.worker.process_next()
        job = await http.get(f"/api/imagenia/jobs/{queued.json()['job_id']}")
        asset_id = job.json()["result_asset_id"]
        app.database.execute("UPDATE image_assets SET file_path='../private.txt' WHERE id=?", (asset_id,))
        app.database.commit()
        outside = app.data_dir.parent / "private.txt"
        outside.write_text("secret")
        result = await http.get(f"/api/imagenia/assets/{asset_id}/content")
    assert result.status_code == 404
    assert "secret" not in result.text

@pytest.mark.anyio
async def test_upgrade_preserves_version_one_jobs(tmp_path, monkeypatch):
    import sqlite3
    monkeypatch.setenv("IMAGENIA_OPENAI_API_KEY", "sk-fake")
    directory = tmp_path / "data"
    directory.mkdir()
    with sqlite3.connect(directory / "imagenia.sqlite3") as db:
        db.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
        db.execute("INSERT INTO schema_version VALUES (1)")
        db.execute("""CREATE TABLE generation_jobs (id TEXT PRIMARY KEY, kind TEXT NOT NULL,
            status TEXT NOT NULL, prompt TEXT NOT NULL, source_asset_id TEXT, result_asset_id TEXT,
            error_code TEXT, error_message TEXT, created_at TEXT NOT NULL)""")
        db.execute("INSERT INTO generation_jobs(id,kind,status,prompt,created_at) VALUES ('old','generate','failed','legacy','2026-09-20')")
    app = create_app(directory, provider=FakeImageProvider())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        result = await http.get("/api/imagenia/jobs/old")
    assert result.json()["status"] == "failed"
    assert app.database.execute("SELECT version FROM schema_version").fetchone()[0] == 2

@pytest.mark.anyio
async def test_started_worker_completes_queued_job_without_manual_process(generation):
    import asyncio
    app, provider = generation
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        app.worker.start()
        try:
            queued = await http.post("/api/imagenia/jobs/generate", json={"prompt": "automatic sunrise"})
            for _ in range(30):
                result = await http.get(f"/api/imagenia/jobs/{queued.json()['job_id']}")
                if result.json()["status"] == "succeeded":
                    break
                await asyncio.sleep(0.05)
            assert result.json()["status"] == "succeeded"
        finally:
            app.worker.stop()
    assert provider.calls == 1
