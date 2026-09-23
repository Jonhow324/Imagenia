"""Repeatable local SQLite probe; no QwenPaw host claim or paid provider calls.

Run: python plugin/tests/storage_probe.py
"""
import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from src.imagenia_plugin import FakeImageProvider, create_app  # noqa: E402


class BlockingProvider(FakeImageProvider):
    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()

    def generate(self, *args, **kwargs):
        self.started.set()
        if not self.release.wait(5):
            raise RuntimeError("probe provider timeout")
        return super().generate(*args, **kwargs)


def percentile(samples, proportion):
    ordered = sorted(samples)
    return round(ordered[int((len(ordered) - 1) * proportion)], 3)


def main():
    with tempfile.TemporaryDirectory(prefix="imagenia-probe-") as directory:
        previous = os.environ.get("IMAGENIA_OPENAI_API_KEY")
        os.environ["IMAGENIA_OPENAI_API_KEY"] = "sk-test-only"
        try:
            provider = BlockingProvider()
            app = create_app(Path(directory) / "data", provider)
            app.handle("POST", "/api/imagenia/jobs/generate", b'{"prompt":"probe"}')
            thread = threading.Thread(target=app.worker.process_next)
            thread.start()
            assert provider.started.wait(5)
            latencies = []
            for _ in range(50):
                start = time.perf_counter()
                assert app.handle("GET", "/api/imagenia/assets")[0] == 200
                latencies.append((time.perf_counter() - start) * 1000)
            # A deliberately long EXCLUSIVE writer is a control case, not the
            # normal provider wait: it demonstrates observable lock contention.
            provider.release.set()
            thread.join(timeout=5)
            assert not thread.is_alive()
            exclusive_ready = threading.Event()
            def exclusive_writer():
                with sqlite3.connect(app.data_dir / "imagenia.sqlite3") as other:
                    other.execute("BEGIN EXCLUSIVE")
                    exclusive_ready.set()
                    time.sleep(0.12)
            lock_thread = threading.Thread(target=exclusive_writer)
            lock_thread.start()
            assert exclusive_ready.wait(5)
            start = time.perf_counter()
            assert app.handle("GET", "/api/imagenia/assets")[0] == 200
            exclusive_ms = round((time.perf_counter() - start) * 1000, 3)
            lock_thread.join(timeout=5)
            assert not lock_thread.is_alive()
            print(json.dumps({"journal_mode": app.database.execute("PRAGMA journal_mode").fetchone()[0],
                "local_route_thread": threading.get_ident(), "provider_wait_get_count": len(latencies),
                "provider_wait_get_ms": {"p50": percentile(latencies, 0.5),
                    "p95": percentile(latencies, 0.95), "max": round(max(latencies), 3)},
                "exclusive_writer_get_ms": exclusive_ms}, ensure_ascii=False))
            app.database.close()
        finally:
            if previous is None:
                os.environ.pop("IMAGENIA_OPENAI_API_KEY", None)
            else:
                os.environ["IMAGENIA_OPENAI_API_KEY"] = previous


if __name__ == "__main__":
    main()
