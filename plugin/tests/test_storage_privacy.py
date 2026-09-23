"""Private storage modes and a repeatable conditional SQLite thread probe."""
import os
import sqlite3
import stat
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from src.imagenia_plugin import FakeImageProvider, create_app  # noqa: E402


def mode(path):
    return stat.S_IMODE(path.lstat().st_mode)


def test_private_storage_under_permissive_umask(tmp_path, monkeypatch):
    monkeypatch.setenv("IMAGENIA_OPENAI_API_KEY", "sk-fake")
    previous = os.umask(0o022)
    try:
        root = tmp_path / "data"
        app = create_app(root, provider=FakeImageProvider())
        assert mode(root) == mode(root / "images") == 0o700
        assert mode(root / "imagenia.sqlite3") == 0o600
        app.handle("POST", "/api/imagenia/jobs/generate", b'{"prompt":"private"}')
        assert app.worker.process_next()
        asset = app.database.execute("SELECT file_path FROM image_assets").fetchone()
        path = root / asset[0]
        assert mode(path) == 0o600
        assert mode(path.parent) == mode(path.parent.parent) == 0o700
        app.database.close()
    finally:
        os.umask(previous)


def test_legacy_modes_are_repaired_only_within_owned_plugin_root(tmp_path):
    root = tmp_path / "data"
    (root / "images" / "2026" / "09").mkdir(parents=True)
    image = root / "images" / "2026" / "09" / "legacy.png"
    image.write_bytes(b"fake")
    db = root / "imagenia.sqlite3"
    db.touch()
    for path, old_mode in ((root, 0o755), (root / "images", 0o755), (image.parent.parent, 0o755),
                           (image.parent, 0o755), (image, 0o644), (db, 0o644)):
        path.chmod(old_mode)
    app = create_app(root)
    for path in (root, root / "images", image.parent.parent, image.parent):
        assert mode(path) == 0o700
    assert mode(db) == mode(image) == 0o600
    app.database.close()


def test_symlinks_and_unowned_paths_fail_closed(tmp_path, monkeypatch):
    target = tmp_path / "outside"
    target.mkdir()
    target.chmod(0o755)
    link = tmp_path / "linked"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises((OSError, RuntimeError)):
        create_app(link)
    assert mode(target) == 0o755
    root = tmp_path / "data"
    root.mkdir()
    (root / "imagenia.sqlite3").symlink_to(target / "db")
    with pytest.raises((OSError, RuntimeError)):
        create_app(root)
    assert not (target / "db").exists()
    (root / "imagenia.sqlite3").unlink()
    original = os.getuid
    monkeypatch.setattr(os, "getuid", lambda: original() + 1)
    root.chmod(0o755)
    with pytest.raises((OSError, RuntimeError)):
        create_app(root)
    assert mode(root) == 0o755


def test_conditional_cross_thread_access_still_fails_without_unsafe_shared_connection(tmp_path):
    app = create_app(tmp_path / "data")
    errors = []
    def foreign_thread():
        try:
            app.handle("GET", "/api/imagenia/assets")
        except sqlite3.ProgrammingError as exc:
            errors.append(type(exc))
    thread = threading.Thread(target=foreign_thread)
    thread.start()
    thread.join(timeout=2)
    assert errors == [sqlite3.ProgrammingError]
    assert app.handle("GET", "/api/imagenia/assets")[0] == 200
    app.database.close()

@pytest.mark.anyio
async def test_concurrent_same_event_loop_asgi_reads_are_not_cross_thread(tmp_path, monkeypatch, caplog):
    import asyncio
    import httpx
    monkeypatch.setenv("IMAGENIA_THREAD_PROBE", "1")
    app = create_app(tmp_path / "data")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        responses = await asyncio.gather(*(http.get("/api/imagenia/assets") for _ in range(6)))
    assert all(response.status_code == 200 for response in responses)
    assert any("Imagenia create thread=" in item.message for item in caplog.records)
    assert any("Imagenia handle thread=" in item.message for item in caplog.records)
    app.database.close()


def test_legacy_image_hardlink_is_rejected_without_chmod_of_other_file(tmp_path):
    outside = tmp_path / "unrelated.png"
    outside.write_bytes(b"not a plugin image")
    outside.chmod(0o644)
    root = tmp_path / "data"
    month = root / "images" / "2026" / "09"
    month.mkdir(parents=True)
    os.link(outside, month / "linked.png")
    with pytest.raises((OSError, RuntimeError)):
        create_app(root)
    assert mode(outside) == 0o644
