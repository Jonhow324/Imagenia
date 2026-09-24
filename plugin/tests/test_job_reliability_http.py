"""GenerationJob recovery, deadline and safe provider failures over HTTP."""
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from src.imagenia_plugin import FakeImageProvider, create_app  # noqa: E402


@pytest.mark.anyio
async def test_provider_timeout_fails_without_asset_or_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("IMAGENIA_OPENAI_API_KEY", "sk-fake")
    app = create_app(tmp_path / "data", FakeImageProvider())
    class TimedOut:
        def generate(self, prompt, *, size, quality):
            raise TimeoutError("secret-key /absolute/private/path")
    app.worker.provider = TimedOut()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        queued = await http.post("/api/imagenia/jobs/generate", json={"prompt": "private scene"})
        assert app.worker.process_next()
        failed = await http.get(f"/api/imagenia/jobs/{queued.json()['job_id']}")
        assert failed.json()["status"] == "failed"
        assert failed.json()["error_code"] == "timeout"
        assert failed.json()["result_asset_id"] is None
        assert "secret-key" not in failed.text and "/absolute/private/path" not in failed.text
        assert (await http.get("/api/imagenia/assets")).json()["items"] == []

@pytest.mark.anyio
async def test_ten_minute_deadline_marks_blocked_job_failed_without_publishing(tmp_path, monkeypatch):
    import asyncio
    import threading
    from src.imagenia_plugin import jobs

    monkeypatch.setenv("IMAGENIA_OPENAI_API_KEY", "sk-fake")
    monkeypatch.setattr(jobs, "JOB_TIMEOUT_SECONDS", 0.03)
    entered, release = threading.Event(), threading.Event()
    fake = FakeImageProvider()
    class SlowProvider:
        def generate(self, prompt, *, size, quality):
            entered.set()
            release.wait(2)
            return fake.image_bytes
    app = create_app(tmp_path / "data", SlowProvider())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        queued = await http.post("/api/imagenia/jobs/generate", json={"prompt": "very private scene"})
        assert queued.status_code == 202
        app.worker.start()
        try:
            for _ in range(100):
                if entered.is_set():
                    break
                await asyncio.sleep(0.01)
            assert entered.is_set()
            for _ in range(60):
                result = await http.get(f"/api/imagenia/jobs/{queued.json()['job_id']}")
                if result.json()["status"] == "failed":
                    break
                await asyncio.sleep(0.01)
            assert result.json()["error_code"] == "timeout"
            assert result.json()["result_asset_id"] is None
            release.set()
            await asyncio.sleep(0.05)
            assert (await http.get("/api/imagenia/assets")).json()["items"] == []
            assert list((tmp_path / "data" / "images").rglob("*.png")) == []
        finally:
            release.set()
            app.worker.stop()

@pytest.mark.anyio
async def test_restart_interrupts_running_and_resumes_pending_without_retry(tmp_path, monkeypatch):
    import asyncio
    monkeypatch.setenv("IMAGENIA_OPENAI_API_KEY", "sk-fake")
    directory = tmp_path / "data"
    first = create_app(directory, FakeImageProvider())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=first), base_url="http://test") as http:
        interrupted = (await http.post("/api/imagenia/jobs/generate", json={"prompt": "first"})).json()["job_id"]
        pending = (await http.post("/api/imagenia/jobs/generate", json={"prompt": "second"})).json()["job_id"]
        first.database.execute("UPDATE generation_jobs SET status='running' WHERE id=?", (interrupted,))
        first.database.commit()
    first.database.close()
    provider = FakeImageProvider()
    restarted = create_app(directory, provider)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=restarted), base_url="http://test") as http:
        restarted.worker.start()
        try:
            for _ in range(100):
                resumed = await http.get(f"/api/imagenia/jobs/{pending}")
                if resumed.json()["status"] == "succeeded":
                    break
                await asyncio.sleep(0.01)
            stopped = await http.get(f"/api/imagenia/jobs/{interrupted}")
            assert stopped.json()["status"] == "failed"
            assert stopped.json()["error_code"] == "interrupted"
            assert stopped.json()["result_asset_id"] is None
            assert resumed.json()["status"] == "succeeded"
            assert provider.calls == 1
        finally:
            restarted.worker.stop()


@pytest.mark.anyio
@pytest.mark.parametrize("upstream_code", ["rate_limited", "invalid_response", "service_unavailable"])
async def test_provider_failure_http_response_and_logs_are_redacted(tmp_path, monkeypatch, caplog, upstream_code):
    from src.imagenia_plugin.provider import ProviderError
    monkeypatch.setenv("IMAGENIA_OPENAI_API_KEY", "sk-private")
    app = create_app(tmp_path / "data", FakeImageProvider())
    class Failing:
        def generate(self, prompt, *, size, quality):
            raise ProviderError(upstream_code)
    app.worker.provider = Failing()
    with caplog.at_level("DEBUG"):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
            queued = await http.post("/api/imagenia/jobs/generate", json={"prompt": "private unique prompt"})
            assert app.worker.process_next()
            result = await http.get(f"/api/imagenia/jobs/{queued.json()['job_id']}")
            assert result.json()["error_code"] == upstream_code
            assert (await http.get("/api/imagenia/assets")).json()["items"] == []
    for sensitive in ("sk-private", "Authorization", "private unique prompt", str(tmp_path)):
        assert sensitive not in str({key: result.json()[key] for key in ("error_code", "error_message")})
        assert sensitive not in caplog.text
