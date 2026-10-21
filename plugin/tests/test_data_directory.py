"""Container data retention through the real QwenPaw registration boundary."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from src.imagenia_plugin import FakeImageProvider, create_app  # noqa: E402
from src.imagenia_plugin.jobs import GenerationWorker  # noqa: E402


def load_plugin(monkeypatch, install_dir: Path, home: Path):
    spec = importlib.util.spec_from_file_location(
        "imagenia_storage_entry", Path(__file__).parents[1] / "plugin.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "__file__", str(install_dir / "plugin.py"))
    monkeypatch.chdir(home.parent)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("IMAGENIA_DATA_DIR", raising=False)
    for key in ("IMAGENIA_OPENAI_API_KEY", "IMAGENIA_OPENAI_BASE_URL", "IMAGENIA_OPENAI_MODEL"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setitem(sys.modules, "src.imagenia_plugin.qwenpaw_router",
                        SimpleNamespace(build_router=lambda app: object()))
    monkeypatch.setattr(module, "OpenAIImageProvider", lambda *args, **kwargs: FakeImageProvider())
    # Execute jobs synchronously; provider calls cannot race assertions or use the network.
    monkeypatch.setattr(GenerationWorker, "start", lambda self: None)
    return module


def register(module):
    adapter = module.ImageniaPlugin()
    adapter.register(SimpleNamespace(register_http_router=lambda *args, **kwargs: None))
    return adapter


@pytest.mark.anyio
async def test_container_recreation_preserves_configuration_and_images_in_install_directory(tmp_path, monkeypatch):
    install_dir = tmp_path / "persistent-plugins" / "imagenia"
    module = load_plugin(monkeypatch, install_dir, tmp_path / "old-container-home")
    adapter = register(module)
    try:
        assert adapter.app.data_dir == install_dir / "data"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=adapter.app), base_url="http://test") as http:
            saved = await http.put("/api/imagenia/settings/openai", json={
                "api_key": "sk-fake-persistence-test", "base_url": "https://images.example/v1", "model": "test-model",
            })
            assert saved.status_code == 200
            queued = await http.post("/api/imagenia/jobs/generate", json={"prompt": "retained image"})
            assert queued.status_code == 202
            job_id = queued.json()["job_id"]
            assert adapter.app.worker.process_next()
            job = (await http.get(f"/api/imagenia/jobs/{job_id}")).json()
            assert job["status"] == "succeeded"
            asset_id = job["result_asset_id"]
            image = (await http.get(f"/api/imagenia/assets/{asset_id}/content")).content
            assert (await http.patch(f"/api/imagenia/assets/{asset_id}", json={"is_favorite": True})).status_code == 200
    finally:
        adapter.unregister()

    assert (install_dir / "data" / "config" / "openai.json").is_file()
    assert (install_dir / "data" / "imagenia.sqlite3").is_file()
    assert len(list((install_dir / "data" / "images").glob("*/*/*.png"))) == 1
    # New container: a fresh home and a new plugin instance, with the installation retained.
    module = load_plugin(monkeypatch, install_dir, tmp_path / "new-container-home")
    adapter = register(module)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=adapter.app), base_url="http://test") as http:
            settings = (await http.get("/api/imagenia/settings")).json()["openai"]
            assert settings["configured"] and settings["source"] == "file"
            assert settings["base_url"] == "https://images.example/v1"
            assert settings["model"] == "test-model"
            assert (await http.get(f"/api/imagenia/jobs/{job_id}")).json()["result_asset_id"] == asset_id
            assert (await http.get(f"/api/imagenia/assets/{asset_id}")).json()["is_favorite"]
            assert (await http.get(f"/api/imagenia/assets/{asset_id}/content")).content == image
    finally:
        adapter.unregister()


def test_explicit_data_directory_overrides_installation_and_legacy(tmp_path, monkeypatch):
    home = tmp_path / "home"
    module = load_plugin(monkeypatch, tmp_path / "plugin", home)
    legacy = create_app(home / ".qwenpaw" / "plugins" / "imagenia", FakeImageProvider())
    legacy.database.close()
    configured = tmp_path / "external-volume"
    monkeypatch.setenv("IMAGENIA_DATA_DIR", str(configured))
    adapter = register(module)
    try:
        assert adapter.app.data_dir == configured
    finally:
        adapter.unregister()


def test_existing_legacy_configuration_is_kept_with_migration_warning(tmp_path, monkeypatch, caplog):
    home = tmp_path / "home"
    install_dir = tmp_path / "plugin"
    module = load_plugin(monkeypatch, install_dir, home)
    legacy_dir = home / ".qwenpaw" / "plugins" / "imagenia"
    legacy = create_app(legacy_dir, FakeImageProvider())
    legacy.settings.save("sk-fake-legacy-test")
    legacy.database.close()
    adapter = register(module)
    try:
        assert adapter.app.data_dir == legacy_dir
        assert adapter.app.settings.status()["openai"]["configured"]
        assert not (install_dir / "data").exists()
        assert "IMAGENIA_DATA_DIR" in caplog.text
        assert "sk-fake-legacy-test" not in caplog.text
    finally:
        adapter.unregister()


def test_installation_data_takes_precedence_over_leftover_legacy_data(tmp_path, monkeypatch):
    home = tmp_path / "home"
    install_dir = tmp_path / "plugin"
    module = load_plugin(monkeypatch, install_dir, home)
    for directory, model in (
        (home / ".qwenpaw" / "plugins" / "imagenia", "legacy-model"),
        (install_dir / "data", "retained-model"),
    ):
        app = create_app(directory, FakeImageProvider())
        app.settings.save("sk-fake-test", model=model)
        app.database.close()
    adapter = register(module)
    try:
        assert adapter.app.data_dir == install_dir / "data"
        assert adapter.app.settings.effective()[3] == "retained-model"
    finally:
        adapter.unregister()


@pytest.mark.parametrize("value", ["", "   "])
def test_empty_explicit_data_directory_is_rejected(tmp_path, monkeypatch, value):
    module = load_plugin(monkeypatch, tmp_path / "plugin", tmp_path / "home")
    monkeypatch.setenv("IMAGENIA_DATA_DIR", value)
    with pytest.raises(RuntimeError, match="IMAGENIA_DATA_DIR"):
        register(module)
