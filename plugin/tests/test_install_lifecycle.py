"""Installation, migration and host lifecycle at the HTTP and registration seams."""
import importlib.util
import sqlite3
import sys
from types import SimpleNamespace
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from src.imagenia_plugin import FakeImageProvider, create_app  # noqa: E402
from src.imagenia_plugin.storage import DatabaseMigrationError  # noqa: E402


@pytest.mark.anyio
async def test_upgrade_and_repeated_start_preserve_config_jobs_assets_and_files(tmp_path, monkeypatch):
    monkeypatch.delenv("IMAGENIA_OPENAI_API_KEY", raising=False)
    directory = tmp_path / "persistent-data"
    initial = create_app(directory, FakeImageProvider())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=initial), base_url="http://test") as http:
        saved = await http.put("/api/imagenia/settings/openai", json={"api_key": "sk-test-secret"})
        assert saved.status_code == 200
        queued = (await http.post("/api/imagenia/jobs/generate", json={"prompt": "kept"})).json()["job_id"]
        assert initial.worker.process_next()
        job = (await http.get(f"/api/imagenia/jobs/{queued}")).json()
        asset_id = job["result_asset_id"]
        original = (await http.get(f"/api/imagenia/assets/{asset_id}/content")).content
        favorite = await http.patch(f"/api/imagenia/assets/{asset_id}", json={"is_favorite": True})
        assert favorite.status_code == 200
    initial.database.close()
    for _ in range(2):  # overlay and restart must not change the data directory
        reopened = create_app(directory, FakeImageProvider())
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=reopened), base_url="http://test") as http:
            assert (await http.get("/api/imagenia/settings")).json()["openai"]["configured"]
            assert (await http.get(f"/api/imagenia/jobs/{queued}")).json()["result_asset_id"] == asset_id
            assert (await http.get(f"/api/imagenia/assets/{asset_id}")).json()["is_favorite"]
            assert (await http.get(f"/api/imagenia/assets/{asset_id}/content")).content == original
        assert reopened.database.execute("SELECT version FROM schema_version").fetchone()[0] == 3
        assert reopened.database.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert reopened.database.execute("PRAGMA foreign_key_check").fetchall() == []
        reopened.database.close()


def test_migration_constraints_indexes_and_foreign_key_delete_behavior(tmp_path):
    app = create_app(tmp_path / "data", FakeImageProvider())
    db = app.database
    assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    for table in ("image_assets", "generation_jobs"):
        assert any(row[2] == 1 for row in db.execute(f"PRAGMA index_list({table})"))  # primary-key uniqueness
    indexes = {row[1] for row in db.execute("PRAGMA index_list(image_assets)")}
    assert {"assets_created", "assets_favorite", "assets_source"} <= indexes
    assert any(row[3] == "source_asset_id" and row[6] == "SET NULL" for row in db.execute("PRAGMA foreign_key_list(image_assets)"))
    assert {row[3] for row in db.execute("PRAGMA foreign_key_list(generation_jobs)")} == {"source_asset_id", "result_asset_id"}
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO generation_jobs(id,kind,status,prompt,source_asset_id,created_at) VALUES ('x','edit','pending','p','missing','now')")
    db.rollback()
    with db:
        db.execute("""INSERT INTO image_assets (id,kind,prompt,model,size,quality,width,height,
            file_path,mime_type,file_size,created_at,updated_at)
            VALUES ('parent','generated','p','model','square','standard',1,1,'images/p.png','image/png',4,'now','now')""")
        db.execute("""INSERT INTO image_assets (id,kind,source_asset_id,prompt,model,size,quality,width,height,
            file_path,mime_type,file_size,created_at,updated_at)
            VALUES ('child','edited','parent','p','model','square','standard',1,1,'images/c.png','image/png',4,'now','now')""")
        db.execute("""INSERT INTO generation_jobs(id,kind,status,prompt,source_asset_id,result_asset_id,created_at)
            VALUES ('edit','edit','succeeded','p','parent','child','now')""")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO image_assets SELECT * FROM image_assets WHERE id='parent'")
    db.rollback()
    with db:
        db.execute("DELETE FROM image_assets WHERE id='parent'")
    assert db.execute("SELECT source_asset_id FROM image_assets WHERE id='child'").fetchone()[0] is None
    assert db.execute("SELECT source_asset_id FROM generation_jobs WHERE id='edit'").fetchone()[0] is None
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    app.database.close()


def test_failed_upgrade_rolls_back_and_refuses_backend_registration(tmp_path, monkeypatch):
    directory = tmp_path / "data"
    initial = create_app(directory, FakeImageProvider())
    initial.database.close()
    with sqlite3.connect(directory / "imagenia.sqlite3") as db:
        db.execute("UPDATE schema_version SET version=2")
        db.execute("DROP INDEX assets_source")
        db.execute("ALTER TABLE image_assets RENAME TO image_assets_legacy")
        # Force v3's table rebuild to fail without losing the original schema.
        db.execute("CREATE TABLE image_assets(id TEXT PRIMARY KEY)")
    with pytest.raises(DatabaseMigrationError, match="v3") as failure:
        create_app(directory, FakeImageProvider())
    assert str(directory) not in str(failure.value)
    with sqlite3.connect(directory / "imagenia.sqlite3") as db:
        assert db.execute("SELECT version FROM schema_version").fetchone()[0] == 2
        assert db.execute("SELECT name FROM sqlite_master WHERE name='image_assets_legacy'").fetchone()
    monkeypatch.setenv("IMAGENIA_DATA_DIR", str(directory))
    monkeypatch.setitem(sys.modules, "src.imagenia_plugin.qwenpaw_router", SimpleNamespace(build_router=lambda app: object()))
    plugin_file = Path(__file__).parents[1] / "plugin.py"
    spec = importlib.util.spec_from_file_location("imagenia_host_entry", plugin_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    class Host:
        calls = 0
        def register_http_router(self, *args, **kwargs):
            self.calls += 1
    host = Host()
    adapter = module.ImageniaPlugin()
    with pytest.raises(DatabaseMigrationError):
        adapter.register(host)
    assert host.calls == 0
    assert adapter.app is None


def test_host_disable_reinstall_keeps_data_and_does_not_restart_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("IMAGENIA_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setitem(sys.modules, "src.imagenia_plugin.qwenpaw_router", SimpleNamespace(build_router=lambda app: object()))
    plugin_file = Path(__file__).parents[1] / "plugin.py"
    spec = importlib.util.spec_from_file_location("imagenia_host_entry_lifecycle", plugin_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    class Host:
        def __init__(self):
            self.calls = 0
        def register_http_router(self, *args, **kwargs):
            self.calls += 1
    host = Host()
    adapter = module.ImageniaPlugin()
    adapter.register(host)
    first = adapter.app
    assert host.calls == 1
    first.database.execute("INSERT INTO generation_jobs(id,kind,status,prompt,created_at) VALUES ('kept','generate','failed','p','now')")
    first.database.commit()
    adapter.unregister()
    assert adapter.app is None
    assert first.worker._stop.is_set()
    with pytest.raises(sqlite3.ProgrammingError):
        first.database.execute("SELECT 1")
    assert (tmp_path / "data" / "imagenia.sqlite3").exists()
    adapter.register(host)
    assert adapter.app.database.execute("SELECT id FROM generation_jobs WHERE id='kept'").fetchone()[0] == "kept"
    adapter.unregister()
    assert host.calls == 2


def test_failed_host_router_registration_leaves_no_active_backend(tmp_path, monkeypatch):
    monkeypatch.setenv("IMAGENIA_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setitem(sys.modules, "src.imagenia_plugin.qwenpaw_router", SimpleNamespace(build_router=lambda app: object()))
    spec = importlib.util.spec_from_file_location("imagenia_host_entry_fail", Path(__file__).parents[1] / "plugin.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    class BrokenHost:
        def register_http_router(self, *args, **kwargs):
            raise RuntimeError("host refused router")
    adapter = module.ImageniaPlugin()
    with pytest.raises(RuntimeError, match="host refused router"):
        adapter.register(BrokenHost())
    assert adapter.app is None


def test_upgrade_from_legacy_v2_keeps_jobs_assets_and_references(tmp_path, monkeypatch):
    monkeypatch.setenv("IMAGENIA_OPENAI_API_KEY", "sk-test")
    data = tmp_path / "legacy"
    data.mkdir()
    with sqlite3.connect(data / "imagenia.sqlite3") as db:
        db.executescript("""
            CREATE TABLE schema_version(version INTEGER NOT NULL);
            INSERT INTO schema_version VALUES(2);
            CREATE TABLE generation_jobs (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL,
                prompt TEXT NOT NULL, source_asset_id TEXT, result_asset_id TEXT,
                error_code TEXT, error_message TEXT, created_at TEXT NOT NULL,
                request_json TEXT, started_at TEXT, finished_at TEXT);
            CREATE TABLE image_assets (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, source_asset_id TEXT,
                prompt TEXT NOT NULL, model TEXT NOT NULL, size TEXT NOT NULL,
                quality TEXT NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL,
                file_path TEXT NOT NULL, mime_type TEXT NOT NULL, file_size INTEGER NOT NULL,
                is_favorite INTEGER NOT NULL DEFAULT 0, favorited_at TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE INDEX assets_created ON image_assets(created_at DESC, id DESC);
            CREATE INDEX assets_favorite ON image_assets(is_favorite, created_at DESC, id DESC);
            CREATE INDEX assets_source ON image_assets(source_asset_id);
            INSERT INTO image_assets(id,kind,prompt,model,size,quality,width,height,
                file_path,mime_type,file_size,is_favorite,created_at,updated_at) VALUES
                ('old-asset','generated','legacy','model','square','standard',1,1,
                'images/2026/09/old-asset.png','image/png',4,1,'old','old');
            INSERT INTO generation_jobs(id,kind,status,prompt,result_asset_id,created_at)
                VALUES('old-job','generate','succeeded','legacy','old-asset','old');
        """)
    image = data / "images" / "2026" / "09" / "old-asset.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(FakeImageProvider().image_bytes)
    app = create_app(data, FakeImageProvider())
    assert app.database.execute("SELECT version FROM schema_version").fetchone()[0] == 3
    assert app.database.execute("SELECT result_asset_id FROM generation_jobs WHERE id='old-job'").fetchone()[0] == 'old-asset'
    assert app.database.execute("SELECT is_favorite FROM image_assets WHERE id='old-asset'").fetchone()[0] == 1
    assert app.database.execute("PRAGMA foreign_key_check").fetchall() == []
    assert image.read_bytes() == FakeImageProvider().image_bytes
    app.database.close()


def test_disable_interrupts_inflight_job_and_never_publishes_late_result(tmp_path, monkeypatch):
    import threading
    monkeypatch.setenv("IMAGENIA_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("IMAGENIA_OPENAI_API_KEY", "sk-test")
    monkeypatch.setitem(sys.modules, "src.imagenia_plugin.qwenpaw_router", SimpleNamespace(build_router=lambda app: object()))
    spec = importlib.util.spec_from_file_location("imagenia_host_entry_stop", Path(__file__).parents[1] / "plugin.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    class Host:
        def register_http_router(self, *args, **kwargs):
            pass
    entered, release = threading.Event(), threading.Event()
    class Blocked:
        def generate(self, prompt, *, size, quality):
            entered.set()
            release.wait(3)
            return FakeImageProvider().image_bytes
    adapter = module.ImageniaPlugin()
    adapter.register(Host())
    adapter.app.worker.provider = Blocked()
    status, body = adapter.app.handle("POST", "/api/imagenia/jobs/generate", b'{"prompt":"test"}')
    assert status == 202
    try:
        assert entered.wait(2)
        old_worker = adapter.app.worker
        adapter.unregister()
    finally:
        release.set()
    old_worker._thread.join(timeout=2)
    with sqlite3.connect(tmp_path / "data" / "imagenia.sqlite3") as db:
        assert db.execute("SELECT status,error_code FROM generation_jobs WHERE id=?", (body["job_id"],)).fetchone() == ("failed", "interrupted")
        assert db.execute("SELECT COUNT(*) FROM image_assets").fetchone()[0] == 0
    assert list((tmp_path / "data" / "images").rglob("*.png")) == []
