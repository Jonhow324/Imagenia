"""Uninstalling must release the data directory before the host deletes it."""
from __future__ import annotations

import importlib.util
import shutil
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parents[1]))
from src.imagenia_plugin import FakeImageProvider, jobs  # noqa: E402


def load_plugin(monkeypatch, install_dir: Path):
    """Load the real host entry point against a disposable installation directory."""
    monkeypatch.setenv("IMAGENIA_DATA_DIR", str(install_dir / "data"))
    monkeypatch.setenv("IMAGENIA_OPENAI_API_KEY", "sk-fake-uninstall")
    monkeypatch.setitem(sys.modules, "src.imagenia_plugin.qwenpaw_router",
                        SimpleNamespace(build_router=lambda app: object()))
    spec = importlib.util.spec_from_file_location(
        "imagenia_host_entry_uninstall", Path(__file__).parents[1] / "plugin.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Host:
    def __init__(self) -> None:
        self.calls = 0

    def register_http_router(self, *args, **kwargs) -> None:
        self.calls += 1


def test_unregister_releases_data_directory(tmp_path, monkeypatch):
    """A worker still finishing a provider call must not re-create the data directory."""
    install_dir = tmp_path / "plugins" / "imagenia"
    module = load_plugin(monkeypatch, install_dir)
    adapter = module.ImageniaPlugin()
    adapter.register(Host())
    app = adapter.app
    assert (install_dir / "data" / "imagenia.sqlite3").is_file()

    entered = threading.Event()

    class Slow:
        def generate(self, prompt, *, size, quality):
            entered.set()
            # Long enough for the former 1s join to give up, shorter than stop()'s timeout.
            time.sleep(1.5)
            return FakeImageProvider().image_bytes

    app.worker.provider = Slow()
    status, _ = app.handle("POST", "/api/imagenia/jobs/generate", b'{"prompt":"uninstall"}')
    assert status == 202
    assert entered.wait(2), "the worker never picked up the queued job"

    adapter.unregister()
    assert app.worker._thread is None

    # This is what the host does after unregister() when files are deleted.
    shutil.rmtree(install_dir)
    time.sleep(1)

    assert not (install_dir / "data" / "imagenia.sqlite3").exists(), \
        "the worker thread re-created the database after the plugin directory was deleted"


def test_worker_thread_stops_on_unregister(tmp_path, monkeypatch):
    """No imagenia thread may survive unregister()."""
    install_dir = tmp_path / "plugins" / "imagenia"
    module = load_plugin(monkeypatch, install_dir)
    adapter = module.ImageniaPlugin()
    adapter.register(Host())
    assert any("imagenia" in thread.name.lower() for thread in threading.enumerate())

    adapter.unregister()

    surviving = [thread.name for thread in threading.enumerate() if "imagenia" in thread.name.lower()]
    assert surviving == [], f"surviving threads: {surviving}"


def test_surviving_provider_call_cannot_recreate_database(tmp_path, monkeypatch):
    """A provider call outliving the stop timeout must never touch the database again."""
    install_dir = tmp_path / "plugins" / "imagenia"
    module = load_plugin(monkeypatch, install_dir)
    adapter = module.ImageniaPlugin()
    adapter.register(Host())
    app = adapter.app
    worker = app.worker

    entered, release = threading.Event(), threading.Event()

    class Stuck:
        def generate(self, prompt, *, size, quality):
            entered.set()
            release.wait(2)  # longer than the stop timeout below, still bounded
            return FakeImageProvider().image_bytes

    worker.provider = Stuck()
    status, _ = app.handle("POST", "/api/imagenia/jobs/generate", b'{"prompt":"outliving"}')
    assert status == 202
    assert entered.wait(2), "the worker never picked up the queued job"

    thread = worker._thread
    worker.stop(timeout=0.1)  # float timeout; the join deliberately gives up
    assert thread.is_alive(), "the provider call was expected to outlive stop()"

    # What unregister() plus the host do next: close the database, delete everything.
    app.database.close()
    shutil.rmtree(install_dir)

    # Let the survivor resume: its writes must be refused, not re-create the file.
    release.set()
    time.sleep(0.3)
    assert not (install_dir / "data" / "imagenia.sqlite3").exists(), \
        "a worker that survived stop() re-created the database after uninstall"

    # A stale expiry timer firing after shutdown must not re-create the directory;
    # a late recover() on the stopped instance must not either.
    worker._expire("late-timer")
    worker.recover()
    assert not (install_dir / "data").exists()


def test_late_stop_before_publish_creates_no_image_directory(tmp_path, monkeypatch):
    """A stop landing between the provider result and the image write leaves nothing."""
    install_dir = tmp_path / "plugins" / "imagenia"
    module = load_plugin(monkeypatch, install_dir)
    adapter = module.ImageniaPlugin()
    adapter.register(Host())
    app = adapter.app
    worker = app.worker

    arrived, resume = threading.Event(), threading.Event()
    real_sniff = jobs.sniff_image

    def pausing_sniff(content):
        # Pauses the worker after its post-provider stop check and before the
        # image directory exists: the exact window the publish guard must close.
        if threading.current_thread() is worker._thread:
            arrived.set()
            resume.wait(2)
        return real_sniff(content)

    monkeypatch.setattr(jobs, "sniff_image", pausing_sniff)
    worker.provider = FakeImageProvider()
    status, _ = app.handle("POST", "/api/imagenia/jobs/generate", b'{"prompt":"publish race"}')
    assert status == 202
    assert arrived.wait(2), "the worker never reached the image publish window"

    thread = worker._thread
    worker.stop(timeout=0.05)  # the join deliberately gives up; the gate stays latched
    assert thread.is_alive(), "the worker was expected to be mid-publish"
    app.database.close()
    shutil.rmtree(install_dir)  # what the host does after unregister()

    resume.set()
    thread.join(2)
    assert not thread.is_alive()

    assert not (install_dir / "data").exists(), \
        "a stopped worker re-created the plugin data directory while publishing an image"


def test_stop_during_publish_leaves_no_empty_image_directory(tmp_path, monkeypatch):
    """An interrupted publish removes the empty image directories it just created."""
    install_dir = tmp_path / "plugins" / "imagenia"
    module = load_plugin(monkeypatch, install_dir)
    adapter = module.ImageniaPlugin()
    adapter.register(Host())
    app = adapter.app
    worker = app.worker

    arrived, resume = threading.Event(), threading.Event()
    attempted: list[Path] = []
    real_directory = jobs.private_directory

    def pausing_directory(path):
        real_directory(path)
        attempted.append(path)
        if len(attempted) == 2:  # the year/month directory, after it exists
            arrived.set()
            resume.wait(2)

    monkeypatch.setattr(jobs, "private_directory", pausing_directory)
    worker.provider = FakeImageProvider()
    status, _ = app.handle("POST", "/api/imagenia/jobs/generate", b'{"prompt":"publish stop"}')
    assert status == 202
    assert arrived.wait(2), "the worker never created the image directories"

    thread = worker._thread
    worker.stop(timeout=0.05)
    resume.set()
    thread.join(2)
    assert not thread.is_alive()

    assert attempted[-1].parent.parent == install_dir / "data" / "images", \
        "the paused publish did not reach the image directory"
    assert not (install_dir / "data" / "images").exists(), \
        "an interrupted publish left empty image directories on disk"
    assert (install_dir / "data" / "imagenia.sqlite3").is_file(), \
        "cleanup must never remove pre-existing data"

