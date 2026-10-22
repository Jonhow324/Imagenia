"""Multi-service selection, migration, lifecycle and secret-free HTTP behavior."""
import json
import os
import sqlite3
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from src.imagenia_plugin import FakeImageProvider, create_app
from src.imagenia_plugin.provider import ProviderError


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def app(tmp_path, monkeypatch):
    for name in ("API_KEY", "BASE_URL", "MODEL"):
        monkeypatch.delenv(f"IMAGENIA_OPENAI_{name}", raising=False)
    instance = create_app(tmp_path / "data", FakeImageProvider(), connection_probe=lambda *_: None)
    yield instance
    instance.worker.stop()
    instance.database.close()


def service(name="Service A", key="sk-service-a", *, editing=True):
    return {"name": name, "base_url": f"https://{name[-1].lower()}.example/v1", "api_key": key,
            "models": [{"name": "image-a", "sizes": ["square", "portrait"],
                        "qualities": ["standard"], "supports_edit": editing}]}


async def add(http, **kwargs):
    response = await http.post("/api/imagenia/services", json=service(**kwargs))
    assert response.status_code == 201, response.text
    return response.json()["services"][-1]


def selection(item, **kwargs):
    return {"service_id": item["id"], "model_id": item["models"][0]["id"], "prompt": "private prompt", **kwargs}


@pytest.mark.anyio
async def test_tasks_select_distinct_connections_and_history_survives_deletion(app):
    calls = []
    def factory(selected):
        calls.append((selected["base_url"], selected["api_key"], selected["model"]))
        return FakeImageProvider()
    app.provider_factory = factory
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        a = await add(http)
        b = await add(http, name="Service B", key="sk-service-b")
        for item in (a, b):
            queued = await http.post("/api/imagenia/jobs/generate", json=selection(item))
            assert queued.status_code == 202
            assert app.worker.process_next()
        assert calls == [("https://a.example/v1", "sk-service-a", "image-a"),
                         ("https://b.example/v1", "sk-service-b", "image-a")]
        deleted = await http.delete(f"/api/imagenia/services/{a['id']}")
        assert deleted.status_code == 200
        assets = (await http.get("/api/imagenia/assets")).json()["items"]
        assert {asset["service_name"] for asset in assets} == {"Service A", "Service B"}
        for asset in assets:
            assert (await http.get(f"/api/imagenia/assets/{asset['id']}/content")).status_code == 200
        public = (await http.get("/api/imagenia/jobs")).text + (await http.get("/api/imagenia/services")).text
        assert "sk-service-" not in public and "connection_fingerprint" not in public
        stored = (app.data_dir / "config" / "services.json").read_text()
        assert "sk-service-a" not in stored
        assert os.stat(app.data_dir / "config" / "services.json").st_mode & 0o777 == 0o600
        assert "sk-service-" not in (app.data_dir / "imagenia.sqlite3").read_bytes().decode("latin1")


@pytest.mark.anyio
async def test_busy_service_guards_secrets_endpoint_and_model_but_allows_rename_disable_and_add(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        a = await add(http)
        queued = await http.post("/api/imagenia/jobs/generate", json=selection(a))
        assert queued.status_code == 202
        for change in ({"api_key": "sk-new"}, {"base_url": "https://changed.example/v1"},
                       {"models": [dict(a["models"][0], name="other")]}):
            response = await http.put(f"/api/imagenia/services/{a['id']}", json=change)
            assert response.status_code == 409 and response.json()["error"]["code"] == "service_in_use"
        assert (await http.delete(f"/api/imagenia/services/{a['id']}")).status_code == 409
        assert (await http.put(f"/api/imagenia/services/{a['id']}", json={"name": "renamed", "enabled": False})).status_code == 200
        assert (await http.post("/api/imagenia/jobs/generate", json=selection(a))).status_code == 409
        assert app.worker.process_next()
        job = (await http.get(f"/api/imagenia/jobs/{queued.json()['job_id']}")).json()
        assert job["status"] == "succeeded" and job["service_name"] == "Service A"
        assert (await http.put(f"/api/imagenia/services/{a['id']}", json={"api_key": "sk-new"})).status_code == 200


@pytest.mark.anyio
async def test_capabilities_and_cross_service_edit_are_enforced(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        a = await add(http, editing=False)
        b = await add(http, name="Service B", key="sk-service-b")
        for extra in ({"size": "landscape"}, {"quality": "high"}, {"model_id": "missing"}, {"service_id": "missing"}):
            assert (await http.post("/api/imagenia/jobs/generate", json=selection(a, **extra))).status_code in (409, 422)
        queued = (await http.post("/api/imagenia/jobs/generate", json=selection(a))).json()
        app.worker.process_next()
        original = (await http.get(f"/api/imagenia/jobs/{queued['job_id']}")).json()["result_asset_id"]
        assert (await http.post("/api/imagenia/jobs/edit", json=selection(a, source_asset_id=original))).status_code == 422
        edited = await http.post("/api/imagenia/jobs/edit", json=selection(b, source_asset_id=original))
        assert edited.status_code == 202
        app.worker.process_next()
        output = (await http.get(f"/api/imagenia/jobs/{edited.json()['job_id']}")).json()["result_asset_id"]
        asset = (await http.get(f"/api/imagenia/assets/{output}")).json()
        assert asset["service_id"] == b["id"] and asset["source_asset_id"] == original
        assert (await http.get(f"/api/imagenia/assets/{original}/content")).status_code == 200


@pytest.mark.anyio
async def test_connection_test_is_explicit_read_only_and_failures_are_safe(app):
    probes = []
    def probe(key, url):
        probes.append((key, url))
        raise RuntimeError(f"Authorization {key} {url} /private/path")
    app.settings.probe = probe
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        a = await add(http)
        await http.get("/api/imagenia/services")
        assert probes == [] and app.provider.calls == 0
        response = await http.post(f"/api/imagenia/services/{a['id']}/test")
        assert response.status_code == 502
        assert probes == [("sk-service-a", "https://a.example/v1")]
        assert "sk-service-a" not in response.text and "/private/path" not in response.text
        assert app.provider.calls == 0


@pytest.mark.anyio
async def test_environment_is_read_only_and_changed_key_fails_without_network(tmp_path, monkeypatch):
    monkeypatch.setenv("IMAGENIA_OPENAI_API_KEY", "sk-before")
    for name in ("BASE_URL", "MODEL"):
        monkeypatch.delenv(f"IMAGENIA_OPENAI_{name}", raising=False)
    directory = tmp_path / "data"
    first = create_app(directory, FakeImageProvider())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=first), base_url="http://test") as http:
        catalog = (await http.get("/api/imagenia/services")).json()
        env = catalog["services"][0]
        assert env["id"] == "environment" and env["read_only"]
        assert (await http.put("/api/imagenia/services/environment", json={"api_key": "sk-new"})).status_code == 409
        assert (await http.delete("/api/imagenia/services/environment")).status_code == 409
        queued = (await http.post("/api/imagenia/jobs/generate", json=selection(env))).json()
    first.database.close()
    monkeypatch.setenv("IMAGENIA_OPENAI_API_KEY", "sk-after")
    fake = FakeImageProvider()
    reopened = create_app(directory, fake)
    try:
        reopened.worker.process_next()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=reopened), base_url="http://test") as http:
            job = (await http.get(f"/api/imagenia/jobs/{queued['job_id']}")).json()
            assert job["status"] == "failed" and job["error_code"] == "configuration_changed"
        assert fake.calls == 0
        contents = (directory / "config" / "services.json").read_text()
        assert "sk-before" not in contents and "sk-after" not in contents
    finally:
        reopened.database.close()


@pytest.mark.anyio
async def test_legacy_migration_default_switch_and_removed_selection_do_not_fall_back(app):
    app.settings.save("sk-legacy", "https://legacy.example/v1", "old-model")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        migrated = (await http.get("/api/imagenia/services")).json()
        assert migrated["default"] == {"service_id": "legacy", "model_id": "legacy-model"}
        old = migrated["services"][0]
        assert old["models"][0]["supports_edit"]
        b = await add(http, name="Service B", key="sk-service-b")
        target = {"service_id": b["id"], "model_id": b["models"][0]["id"]}
        assert (await http.put("/api/imagenia/services/default", json=target)).status_code == 200
        queued = await http.post("/api/imagenia/jobs/generate", json=selection(old))
        app.worker.process_next()
        assert (await http.get(f"/api/imagenia/jobs/{queued.json()['job_id']}")).json()["service_id"] == "legacy"
        assert (await http.delete("/api/imagenia/services/legacy")).status_code == 200
        assert not app.settings.file.exists()
        assert (await http.post("/api/imagenia/jobs/generate", json=selection(old))).status_code == 409
        assert (await http.get("/api/imagenia/services")).json()["default"] == target


@pytest.mark.anyio
async def test_provider_failure_never_switches_to_a_different_service(app):
    calls = []
    class Failing:
        def generate(self, *args, **kwargs):
            raise ProviderError("rate_limited")
    def factory(selected):
        calls.append(selected["service_id"])
        return Failing()
    app.provider_factory = factory
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        a = await add(http)
        await add(http, name="Service B", key="sk-service-b")
        queued = await http.post("/api/imagenia/jobs/generate", json=selection(a, size="portrait"))
        assert app.worker.process_next()
        assert not app.worker.process_next()
        job = (await http.get(f"/api/imagenia/jobs/{queued.json()['job_id']}")).json()
        assert job["error_code"] == "rate_limited"
        assert job["options"] == {"size": "portrait", "quality": "standard"}
        assert calls == [a["id"]]


@pytest.mark.anyio
async def test_fastapi_host_exposes_same_catalog_contract(app):
    from fastapi import FastAPI
    from src.imagenia_plugin.qwenpaw_router import build_router
    host = FastAPI()
    host.include_router(build_router(app), prefix="/api/imagenia")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=host), base_url="http://test") as http:
        a = await add(http)
        assert (await http.post(f"/api/imagenia/services/{a['id']}/test")).status_code == 200
        queued = await http.post("/api/imagenia/jobs/generate", json=selection(a))
        assert queued.status_code == 202


@pytest.mark.anyio
async def test_restart_rejects_external_changes_before_claiming_jobs(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        a = await add(http)
        queued = (await http.post("/api/imagenia/jobs/generate", json=selection(a))).json()
        document = json.loads(app.services.file.read_text())
        document["services"][0]["base_url"] = "https://changed.example/v1"
        app.services.file.write_text(json.dumps(document))
        app.worker.recover()
        job = (await http.get(f"/api/imagenia/jobs/{queued['job_id']}")).json()
        assert job["status"] == "failed" and job["error_code"] == "configuration_changed"
        assert app.provider.calls == 0
        assert not app.worker.process_next()


@pytest.mark.anyio
async def test_corrupt_or_public_catalog_fails_safely_without_exposing_credentials(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        await add(http)
        app.services.file.chmod(0o644)
        failed = await http.get("/api/imagenia/services")
        assert failed.status_code == 503 and "sk-service-a" not in failed.text
        app.services.file.chmod(0o600)
        app.services.file.write_text('{"api_key":"sk-private", "version":1}')
        failed = await http.get("/api/imagenia/services")
        assert failed.status_code == 503 and "sk-private" not in failed.text


@pytest.mark.anyio
async def test_delete_source_clears_retry_data_and_keeps_service_history(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        a = await add(http)
        queued = (await http.post("/api/imagenia/jobs/generate", json=selection(a))).json()
        app.worker.process_next()
        asset_id = (await http.get(f"/api/imagenia/jobs/{queued['job_id']}")).json()["result_asset_id"]
        assert (await http.delete(f"/api/imagenia/assets/{asset_id}")).status_code == 200
        job = (await http.get(f"/api/imagenia/jobs/{queued['job_id']}")).json()
        assert job["prompt"] == "" and job["options"] is None
        assert job["service_name"] == "Service A" and job["result_asset_id"] is None


@pytest.mark.anyio
async def test_v3_upgrade_preserves_images_and_refuses_unbound_pending_requests(tmp_path, monkeypatch):
    from src.imagenia_plugin import storage
    directory = tmp_path / "data"
    with monkeypatch.context() as context:
        context.setattr(storage, "LATEST_VERSION", 3)
        old = create_app(directory, FakeImageProvider())
    old.settings.save("sk-legacy-migration")
    png = FakeImageProvider().image_bytes
    image_dir = directory / "images" / "2026" / "10"
    image_dir.mkdir(parents=True)
    (image_dir / "retained.png").write_bytes(png)
    with old.database:
        old.database.execute("""INSERT INTO image_assets
            (id,kind,prompt,model,size,quality,width,height,file_path,mime_type,file_size,is_favorite,created_at,updated_at)
            VALUES ('retained','generated','old prompt','legacy-model','square','standard',1,1,
                    'images/2026/10/retained.png','image/png',?,1,'old','old')""", (len(png),))
        old.database.execute("""INSERT INTO generation_jobs(id,kind,status,prompt,request_json,created_at)
            VALUES ('unbound','generate','pending','old queued prompt','{"size":"square","quality":"standard"}','old')""")
    old.database.close()
    reopened = create_app(directory, FakeImageProvider())
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=reopened), base_url="http://test") as http:
            asset = (await http.get("/api/imagenia/assets/retained")).json()
            assert asset["service_name"] == "历史配置" and asset["model"] == "legacy-model" and asset["is_favorite"]
            assert (await http.get("/api/imagenia/assets/retained/content")).content == png
            pending = (await http.get("/api/imagenia/jobs/unbound")).json()
            assert pending["status"] == "failed" and pending["error_code"] == "configuration_changed"
            assert pending["options"] == {"size": "square", "quality": "standard"}
            catalog = (await http.get("/api/imagenia/services")).json()
            assert catalog["default"] == {"service_id": "legacy", "model_id": "legacy-model"}
        assert reopened.database.execute("PRAGMA foreign_key_check").fetchall() == []
        assert reopened.provider.calls == 0
    finally:
        reopened.database.close()


@pytest.mark.anyio
async def test_real_adapter_requests_use_bound_accounts_after_default_and_name_change(app, monkeypatch):
    import base64
    import io
    import urllib.request
    from src.imagenia_plugin.provider import OpenAIImageProvider
    requests = []
    def fake_open(request, timeout):
        requests.append((request.full_url, request.get_header("Authorization"), json.loads(request.data)["model"]))
        return io.BytesIO(json.dumps({"data": [{"b64_json": base64.b64encode(FakeImageProvider().image_bytes).decode()}]}).encode())
    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    app.provider_factory = lambda selected: OpenAIImageProvider(lambda: selected["api_key"],
        base_url=selected["base_url"], model=selected["model"])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        a = await add(http)
        b = await add(http, name="Service B", key="sk-service-b")
        b_model = dict(b["models"][0], name="image-b")
        assert (await http.put(f"/api/imagenia/services/{b['id']}", json={"models": [b_model]})).status_code == 200
        jobs = []
        for item in (a, b):
            jobs.append((await http.post("/api/imagenia/jobs/generate", json=selection(item))).json()["job_id"])
        assert (await http.put("/api/imagenia/services/default", json={"service_id": b["id"], "model_id": b_model["id"]})).status_code == 200
        assert (await http.put(f"/api/imagenia/services/{a['id']}", json={"name": "Renamed A"})).status_code == 200
        assert app.worker.process_next()
        assert app.worker.process_next()
        assert sorted(requests) == sorted([
            ("https://a.example/v1/images/generations", "Bearer sk-service-a", "image-a"),
            ("https://b.example/v1/images/generations", "Bearer sk-service-b", "image-b"),
        ])
        for job_id, expected_name, expected_model in ((jobs[0], "Service A", "image-a"), (jobs[1], "Service B", "image-b")):
            job = (await http.get(f"/api/imagenia/jobs/{job_id}")).json()
            asset = (await http.get(f"/api/imagenia/assets/{job['result_asset_id']}")).json()
            assert job["status"] == "succeeded"
            assert asset["service_name"] == expected_name and asset["model"] == expected_model


@pytest.mark.anyio
async def test_pending_service_allows_adding_models_but_not_removing_existing_models(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        a = await add(http)
        assert (await http.post("/api/imagenia/jobs/generate", json=selection(a))).status_code == 202
        model = {**a["models"][0], "name": "new-model"}
        del model["id"]
        added = await http.put(f"/api/imagenia/services/{a['id']}", json={"models": [*a["models"], model]})
        assert added.status_code == 200
        models = added.json()["services"][0]["models"]
        removed = await http.put(f"/api/imagenia/services/{a['id']}", json={"models": [models[1]]})
        assert removed.status_code == 409
        assert app.worker.process_next()
        assert (await http.put(f"/api/imagenia/services/{a['id']}", json={"models": [models[1]]})).status_code == 200


@pytest.mark.anyio
async def test_first_service_defaults_to_no_edit_and_invalid_default_is_not_silently_replaced(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        a = await add(http, editing=False)
        assert not a["models"][0]["supports_edit"]
        assert (await http.put(f"/api/imagenia/services/{a['id']}", json={"enabled": False})).status_code == 200
        assert (await http.post("/api/imagenia/jobs/generate", json={"prompt": "confirm selection"})).status_code == 409
        await add(http, name="Service B", key="sk-service-b")
        assert (await http.post("/api/imagenia/jobs/generate", json={"prompt": "confirm selection"})).status_code == 409
        assert app.provider.calls == 0


def test_v4_migration_failure_rolls_back_without_partially_binding_jobs(tmp_path, monkeypatch):
    from src.imagenia_plugin import storage
    directory = tmp_path / "data"
    with monkeypatch.context() as context:
        context.setattr(storage, "LATEST_VERSION", 3)
        old = create_app(directory, FakeImageProvider())
    with old.database:
        old.database.execute("""INSERT INTO generation_jobs(id,kind,status,prompt,created_at)
            VALUES ('existing','generate','failed','keep this prompt','old')""")
    old.database.close()
    with monkeypatch.context() as context:
        context.setitem(storage.MIGRATIONS, 4, (*storage.MIGRATION_V4[:2], "SELECT * FROM missing_table"))
        with pytest.raises(storage.DatabaseMigrationError, match="v4"):
            create_app(directory, FakeImageProvider())
    with sqlite3.connect(directory / "imagenia.sqlite3") as database:
        assert database.execute("SELECT version FROM schema_version").fetchone()[0] == 3
        assert "service_id" not in {row[1] for row in database.execute("PRAGMA table_info(generation_jobs)")}
        assert database.execute("SELECT prompt FROM generation_jobs WHERE id='existing'").fetchone()[0] == "keep this prompt"
    reopened = create_app(directory, FakeImageProvider())
    assert reopened.database.execute("SELECT version FROM schema_version").fetchone()[0] == 4
    reopened.database.close()


@pytest.mark.anyio
@pytest.mark.parametrize("partial", [{"service_id": None}, {"model_id": None},
                                     {"service_id": None, "model_id": None}, {"service_id": "", "model_id": ""}])
async def test_explicit_invalid_selection_never_uses_the_default(app, partial):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        await add(http)
        response = await http.post("/api/imagenia/jobs/generate", json={"prompt": "do not silently redirect", **partial})
        assert response.status_code == 422 and response.json()["error"]["code"] == "invalid_selection"
        assert (await http.get("/api/imagenia/jobs")).json()["items"] == []


def minimax_service():
    return {"provider": "minimax", "name": "MiniMax", "base_url": "https://api.minimax.test/v1",
            "api_key": "mm-service-key",
            "models": [{"name": "image-01", "sizes": ["square", "landscape", "portrait"],
                        "qualities": ["standard"], "supports_edit": False}]}


@pytest.mark.anyio
async def test_catalog_offers_builtin_presets_and_keeps_custom_backward_compatible(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        catalog = (await http.get("/api/imagenia/services")).json()
        assert {item["id"] for item in catalog["providers"]} == {"openai", "minimax", "custom"}
        openai = next(item for item in catalog["providers"] if item["id"] == "openai")
        minimax = next(item for item in catalog["providers"] if item["id"] == "minimax")
        assert openai["base_url"] == "https://api.openai.com/v1"
        assert openai["models"][0]["name"] == "gpt-image-1" and openai["models"][0]["supports_edit"]
        assert minimax["base_url"] == "https://api.minimax.cn/v1"
        assert minimax["models"][0] == {"name": "image-01", "sizes": ["square", "landscape", "portrait"],
                                        "qualities": ["standard"], "supports_edit": False}

        custom = await add(http)
        assert custom["provider"] == "custom"
        created = await http.post("/api/imagenia/services", json=minimax_service())
        assert created.status_code == 201
        assert created.json()["services"][-1]["provider"] == "minimax"
        invalid = await http.post("/api/imagenia/services", json={**minimax_service(), "provider": "other"})
        assert invalid.status_code == 422 and invalid.json()["error"]["code"] == "invalid_service"


@pytest.mark.anyio
async def test_v1_catalog_is_read_as_custom_without_changing_behavior(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        item = await add(http, editing=False)
        document = json.loads(app.services.file.read_text())
        document["version"] = 1
        for service in document["services"]:
            service.pop("provider")
        app.services.file.write_text(json.dumps(document))

        migrated = (await http.get("/api/imagenia/services")).json()
        assert migrated["services"][0]["provider"] == "custom"
        queued = await http.post("/api/imagenia/jobs/generate", json=selection(item))
        assert queued.status_code == 202
        assert app.worker.process_next()
        assert (await http.get(f"/api/imagenia/jobs/{queued.json()['job_id']}")).json()["status"] == "succeeded"


@pytest.mark.anyio
async def test_provider_change_is_locked_while_a_job_is_active(app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        item = await add(http)
        assert (await http.post("/api/imagenia/jobs/generate", json=selection(item))).status_code == 202
        locked = await http.put(f"/api/imagenia/services/{item['id']}", json={"provider": "minimax"})
        assert locked.status_code == 409 and locked.json()["error"]["code"] == "service_in_use"
        assert app.worker.process_next()
        assert (await http.put(f"/api/imagenia/services/{item['id']}", json={"provider": "minimax"})).status_code == 200


@pytest.mark.anyio
async def test_bound_minimax_service_uses_native_adapter_and_stores_jpeg(app, monkeypatch):
    import base64
    import io
    import urllib.request
    from src.imagenia_plugin.provider import provider_for

    app.provider_factory = provider_for
    jpeg = (b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xc0\x00\x11\x08\x00\x10\x00\x10\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00\xff\xd9")
    requests = []

    def fake_open(request, timeout):
        requests.append((request.full_url, json.loads(request.data)))
        return io.BytesIO(json.dumps({"data": {"image_base64": [base64.b64encode(jpeg).decode()]},
                                      "base_resp": {"status_code": 0}}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        created = (await http.post("/api/imagenia/services", json=minimax_service())).json()["services"][-1]
        queued = await http.post("/api/imagenia/jobs/generate", json=selection(created))
        assert queued.status_code == 202
        assert app.worker.process_next()
        job = (await http.get(f"/api/imagenia/jobs/{queued.json()['job_id']}")).json()
        assert job["status"] == "succeeded"
        content = await http.get(f"/api/imagenia/assets/{job['result_asset_id']}/content")
        assert content.content == jpeg and content.headers["content-type"].startswith("image/jpeg")
        row = app.database.execute("SELECT file_path, mime_type FROM image_assets WHERE id=?",
                                   (job["result_asset_id"],)).fetchone()
        assert row["file_path"].endswith(".jpg") and row["mime_type"] == "image/jpeg"

    assert requests == [("https://api.minimax.test/v1/image_generation",
                         {"model": "image-01", "prompt": "private prompt", "aspect_ratio": "1:1",
                          "response_format": "base64", "n": 1})]
