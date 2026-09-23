"""Persistent serial generation queue with one dedicated worker."""

from __future__ import annotations

import json
import os
import sqlite3
import struct
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .provider import ImageProvider, ProviderError
from .private_storage import private_directory
from .settings import DEFAULT_MODEL
from .storage import open_database


def source_image(db: sqlite3.Connection, data_dir: Path, asset_id: str) -> bytes:
    """Read a current, plugin-owned PNG; never trust a persisted path blindly."""
    row = db.execute("SELECT file_path FROM image_assets WHERE id=?", (asset_id,)).fetchone()
    if row is None:
        raise ProviderError("source_unavailable")
    try:
        root = (data_dir / "images").resolve()
        path = (data_dir / row["file_path"]).resolve()
        if not path.is_relative_to(root) or path.suffix != ".png" or path.stat().st_size > 25 * 1024 * 1024:
            raise ProviderError("source_unavailable")
        content = path.read_bytes()
        if len(content) > 25 * 1024 * 1024 or content[:16] != b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR":
            raise ProviderError("source_unavailable")
        return content
    except OSError:
        raise ProviderError("source_unavailable") from None


def now() -> str:
    return datetime.now(UTC).isoformat()


class GenerationWorker:
    def __init__(self, data_dir: Path, provider: ImageProvider) -> None:
        self.data_dir = data_dir
        self.provider = provider
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def recover(self) -> None:
        db = open_database(self.data_dir)
        try:
            with db:
                db.execute("""UPDATE generation_jobs SET status='failed', error_code='interrupted',
                    error_message='任务已中断，请重新提交。', finished_at=?, request_json=NULL
                    WHERE status='running'""", (now(),))
        finally:
            db.close()

    def start(self) -> None:
        if self._thread is not None:
            return
        self.recover()
        self._thread = threading.Thread(target=self._run, name="imagenia-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                if not self.process_next():
                    self._stop.wait(0.5)
            except Exception:
                # Keep the worker alive after a transient SQLite or filesystem failure.
                self._stop.wait(1)

    def process_next(self) -> bool:
        """Claim at most one pending job; also usable deterministically in HTTP tests."""
        db = open_database(self.data_dir)
        try:
            with db:
                db.execute("BEGIN IMMEDIATE")
                job = db.execute("""SELECT id, kind, source_asset_id, prompt, request_json FROM generation_jobs
                    WHERE status='pending' ORDER BY created_at, id LIMIT 1""").fetchone()
                if job is None:
                    return False
                db.execute("UPDATE generation_jobs SET status='running', started_at=? WHERE id=?", (now(), job["id"]))
            try:
                options = json.loads(job["request_json"])
                active_model = getattr(self.provider, "model", DEFAULT_MODEL)
                active_model = active_model() if callable(active_model) else active_model
                if job["kind"] == "edit":
                    source = source_image(db, self.data_dir, job["source_asset_id"])
                    content = self.provider.edit(job["prompt"], source, size=options["size"], quality=options["quality"])
                else:
                    content = self.provider.generate(job["prompt"], size=options["size"], quality=options["quality"])
                if not isinstance(content, bytes) or len(content) > 25 * 1024 * 1024 or len(content) < 24 or content[:16] != b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR":
                    raise ProviderError("invalid_image")
                width, height = struct.unpack(">II", content[16:24])
                if not 0 < width <= 8192 or not 0 < height <= 8192:
                    raise ProviderError("invalid_image")
                asset_id = str(uuid.uuid4())
                timestamp = now()
                date = datetime.now(UTC)
                directory = self.data_dir / "images" / f"{date:%Y}" / f"{date:%m}"
                private_directory(directory.parent)
                private_directory(directory)
                target = directory / f"{asset_id}.png"
                relative = target.relative_to(self.data_dir).as_posix()
                try:
                    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                    with os.fdopen(descriptor, "wb") as image:
                        image.write(content)
                    with db:
                        current = db.execute("SELECT status FROM generation_jobs WHERE id=?", (job["id"],)).fetchone()
                        if current is None or current["status"] != "running" or (job["kind"] == "edit" and
                            db.execute("SELECT 1 FROM image_assets WHERE id=?", (job["source_asset_id"],)).fetchone() is None):
                            raise ProviderError("source_unavailable")
                        db.execute("""INSERT INTO image_assets
                            (id,kind,source_asset_id,prompt,model,size,quality,width,height,file_path,
                            mime_type,file_size,created_at,updated_at)
                            VALUES (?,?,?,?,?,?,?,?,?,?,'image/png',?,?,?)""",
                            (asset_id, "edited" if job["kind"] == "edit" else "generated", job["source_asset_id"],
                             job["prompt"], active_model, options["size"], options["quality"], width, height,
                             relative, len(content), timestamp, timestamp))
                        db.execute("""UPDATE generation_jobs SET status='succeeded', result_asset_id=?,
                            finished_at=?, request_json=NULL WHERE id=?""", (asset_id, timestamp, job["id"]))
                except Exception:
                    target.unlink(missing_ok=True)
                    raise
            except Exception as exc:
                code = exc.code if isinstance(exc, ProviderError) and exc.code in {
                    "not_configured", "invalid_api_key", "invalid_image", "source_unavailable"} else "service_unavailable"
                messages = {"not_configured": "请先配置 API Key。", "invalid_api_key": "API Key 无效，请检查配置。",
                            "invalid_image": "服务返回的图片无效，请重新提交。", "source_unavailable": "来源图片已不可用，请重新选择。", "service_unavailable": "图像服务暂时不可用，请稍后重新提交。"}
                with db:
                    db.execute("""UPDATE generation_jobs SET status='failed', error_code=?, error_message=?,
                        finished_at=?, request_json=NULL WHERE id=?""", (code, messages[code], now(), job["id"]))
            return True
        finally:
            db.close()
