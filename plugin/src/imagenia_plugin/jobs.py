"""Persistent serial generation queue with one dedicated worker."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .image_formats import IMAGE_SUFFIXES, sniff_image
from .provider import ImageProvider, ProviderError
from .private_storage import private_directory
from .settings import DEFAULT_MODEL
from .storage import open_database


JOB_TIMEOUT_SECONDS = 600

logger = logging.getLogger(__name__)


def source_image(db: sqlite3.Connection, data_dir: Path, asset_id: str) -> tuple[bytes, str]:
    """Read a current, plugin-owned PNG/JPEG; never trust a persisted path blindly."""
    row = db.execute("SELECT file_path FROM image_assets WHERE id=?", (asset_id,)).fetchone()
    if row is None:
        raise ProviderError("source_unavailable")
    try:
        root = (data_dir / "images").resolve()
        path = (data_dir / row["file_path"]).resolve()
        if not path.is_relative_to(root) or path.suffix not in IMAGE_SUFFIXES or path.stat().st_size > 25 * 1024 * 1024:
            raise ProviderError("source_unavailable")
        content = path.read_bytes()
        image_format = sniff_image(content)
        if (len(content) > 25 * 1024 * 1024 or image_format is None
                or (path.suffix != image_format.suffix and not (image_format.suffix == ".jpg" and path.suffix == ".jpeg"))):
            raise ProviderError("source_unavailable")
        return content, image_format.mime
    except OSError:
        raise ProviderError("source_unavailable") from None


def now() -> str:
    return datetime.now(UTC).isoformat()


class GenerationWorker:
    def __init__(self, data_dir: Path, provider: ImageProvider) -> None:
        self.data_dir = data_dir
        self.provider = provider
        self.resolve_provider = None
        self._stop = threading.Event()
        # Shutdown gate: latched by stop() and never cleared. A thread that
        # outlives the bounded join must not open or write the database again.
        self._shutdown = False
        self._thread: threading.Thread | None = None

    def _db_available(self) -> bool:
        return not self._shutdown

    def recover(self) -> None:
        if not self._db_available():
            return
        self._repair()

    def _repair(self) -> None:
        """Mark running jobs interrupted; only called on a thread holding the gate."""
        db = open_database(self.data_dir)
        try:
            with db:
                db.execute("""UPDATE generation_jobs SET status='failed', error_code='interrupted',
                    error_message='任务已中断，请重新提交。', finished_at=?, request_json=NULL
                    WHERE status='running'""", (now(),))
            # Never hold SQLite's write lock while taking the catalog lock:
            # submissions take the catalog lock before their short DB transaction.
            if self.resolve_provider:
                pending = db.execute("SELECT * FROM generation_jobs WHERE status='pending'").fetchall()
                for job in pending:
                    try:
                        self.resolve_provider(job)
                    except ProviderError:
                        with db:
                            db.execute("""UPDATE generation_jobs SET status='failed', error_code='configuration_changed',
                                error_message='服务配置已变化，请确认后重新提交。', finished_at=?, request_json=NULL
                                WHERE id=? AND status='pending'""", (now(), job["id"]))
        finally:
            db.close()

    def start(self) -> None:
        # stop() is terminal for one worker instance; each register() builds a
        # new app (and worker), so a fresh instance is started after a disable.
        if self._thread is not None or not self._db_available():
            return
        self.recover()
        self._thread = threading.Thread(target=self._run, name="imagenia-worker", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the worker and wait (bounded) until it no longer touches the database.

        The join must stay bounded: QwenPaw calls this from its event loop, so an
        unbounded join would freeze the host. A waiting worker normally leaves
        within its 0.5s wait; a provider request cannot be interrupted, so a
        worker inside one can outlive the timeout. That case is logged and the
        late result is discarded (see process_next), never published. The
        shutdown gate below makes that late result unable to touch the database.
        """
        # Latch the gate before signalling: anything resuming from here on (a
        # provider call outliving the join, or a pending expiry timer) is refused.
        self._shutdown = True
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
        self._thread = None
        if thread is not None and thread.is_alive():
            logger.warning("Imagenia worker did not stop within %.1fs", timeout)
            # Never open the database here: the surviving thread's own writes are
            # gated by _db_available(), and start()/recover() repairs the job later.
            return
        # The join proved the worker thread is gone, so this caller-thread repair
        # cannot race with it. A provider call cannot be killed safely; mark any
        # in-flight job as interrupted now so its result is never published.
        self._repair()

    def _run(self) -> None:
        while self._db_available() and not self._stop.is_set():
            try:
                if not self.process_next():
                    self._stop.wait(0.5)
            except Exception:
                # Keep the worker alive after a transient SQLite or filesystem failure.
                self._stop.wait(1)

    def _expire(self, job_id: str) -> None:
        """Persist a deadline without interrupting a potentially billable provider call."""
        # A timer can fire after stop(); never let it re-create the data directory.
        if not self._db_available():
            return
        try:
            db = open_database(self.data_dir)
            try:
                with db:
                    db.execute("""UPDATE generation_jobs SET status='failed', error_code='timeout',
                        error_message='图像服务超时，请重新提交。', finished_at=?, request_json=NULL
                        WHERE id=? AND status='running'""", (now(), job_id))
            finally:
                db.close()
        except Exception:
            # Timer thread must never print an exception containing paths or secrets.
            # The worker checks its deadline again before publishing a result.
            pass

    def process_next(self) -> bool:
        """Claim at most one pending job; also usable deterministically in HTTP tests."""
        if not self._db_available() or self._stop.is_set():
            return False
        db = open_database(self.data_dir)
        try:
            with db:
                db.execute("BEGIN IMMEDIATE")
                job = db.execute("""SELECT * FROM generation_jobs
                    WHERE status='pending' ORDER BY created_at, id LIMIT 1""").fetchone()
                if job is None:
                    return False
                db.execute("UPDATE generation_jobs SET status='running', started_at=? WHERE id=?", (now(), job["id"]))
            deadline = time.monotonic() + JOB_TIMEOUT_SECONDS
            timer = threading.Timer(JOB_TIMEOUT_SECONDS, self._expire, args=(job["id"],))
            timer.daemon = True
            timer.start()
            try:
                options = json.loads(job["request_json"])
                if self.resolve_provider:
                    provider, active_model = self.resolve_provider(job)
                else:
                    provider = self.provider
                    active_model = getattr(provider, "model", DEFAULT_MODEL)
                    active_model = active_model() if callable(active_model) else active_model
                if job["kind"] == "edit":
                    source, _ = source_image(db, self.data_dir, job["source_asset_id"])
                    content = provider.edit(job["prompt"], source, size=options["size"], quality=options["quality"])
                else:
                    content = provider.generate(job["prompt"], size=options["size"], quality=options["quality"])
                if self._stop.is_set():
                    raise ProviderError("interrupted")
                if time.monotonic() >= deadline:
                    raise ProviderError("timeout")
                image_format = sniff_image(content) if isinstance(content, bytes) and len(content) <= 25 * 1024 * 1024 else None
                if image_format is None or not 0 < image_format.width <= 8192 or not 0 < image_format.height <= 8192:
                    raise ProviderError("invalid_image")
                width, height = image_format.width, image_format.height
                asset_id = str(uuid.uuid4())
                timestamp = now()
                date = datetime.now(UTC)
                directory = self.data_dir / "images" / f"{date:%Y}" / f"{date:%m}"
                target = directory / f"{asset_id}{image_format.suffix}"
                relative = target.relative_to(self.data_dir).as_posix()
                # A stop that lands between the provider check above and this
                # publish must not re-create the image directories the host has
                # just deleted; refuse before touching the filesystem at all.
                if not self._db_available():
                    raise ProviderError("interrupted")
                private_directory(directory.parent)
                private_directory(directory)
                try:
                    if not self._db_available() or self._stop.is_set():
                        raise ProviderError("interrupted")
                    if time.monotonic() >= deadline:
                        raise ProviderError("timeout")
                    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                    with os.fdopen(descriptor, "wb") as image:
                        image.write(content)
                    # Check the gate again before opening a transaction: a stop
                    # during the write must discard these bytes, not publish them.
                    if not self._db_available() or self._stop.is_set():
                        raise ProviderError("interrupted")
                    with db:
                        if self._stop.is_set():
                            raise ProviderError("interrupted")
                        if time.monotonic() >= deadline:
                            raise ProviderError("timeout")
                        current = db.execute("SELECT status FROM generation_jobs WHERE id=?", (job["id"],)).fetchone()
                        if current is None or current["status"] != "running" or (job["kind"] == "edit" and
                            db.execute("SELECT 1 FROM image_assets WHERE id=?", (job["source_asset_id"],)).fetchone() is None):
                            raise ProviderError("source_unavailable")
                        db.execute("""INSERT INTO image_assets
                            (id,kind,source_asset_id,prompt,model,size,quality,width,height,file_path,
                            mime_type,file_size,created_at,updated_at,service_id,service_name,model_id)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (asset_id, "edited" if job["kind"] == "edit" else "generated", job["source_asset_id"],
                             job["prompt"], active_model, options["size"], options["quality"], width, height,
                             relative, image_format.mime, len(content), timestamp, timestamp,
                             job["service_id"], job["service_name"], job["model_id"]))
                        if self._stop.is_set():
                            raise ProviderError("interrupted")
                        if time.monotonic() >= deadline:
                            raise ProviderError("timeout")
                        db.execute("""UPDATE generation_jobs SET status='succeeded', result_asset_id=?,
                            finished_at=?, request_json=NULL WHERE id=?""", (asset_id, timestamp, job["id"]))
                except Exception:
                    target.unlink(missing_ok=True)
                    # Undo an empty image directory this attempt created. rmdir
                    # refuses non-empty directories, so existing images, the
                    # database and the data directory itself are never removed.
                    for created in (directory, directory.parent, self.data_dir / "images"):
                        try:
                            created.rmdir()
                        except OSError:
                            pass
                    raise
            except Exception as exc:
                code = "timeout" if isinstance(exc, TimeoutError) else (exc.code if isinstance(exc, ProviderError) and exc.code in {
                    "not_configured", "invalid_api_key", "invalid_image", "source_unavailable",
                    "timeout", "rate_limited", "invalid_response", "interrupted", "configuration_changed",
                    "edit_not_supported", "insufficient_balance", "invalid_request"} else "service_unavailable")
                messages = {"configuration_changed": "服务配置已变化，请确认后重新提交。", "not_configured": "请先配置 API Key。", "invalid_api_key": "API Key 无效，请检查配置。",
                            "invalid_image": "服务返回的图片无效，请重新提交。", "source_unavailable": "来源图片已不可用，请重新选择。",
                            "timeout": "图像服务超时，请重新提交。", "interrupted": "任务已中断，请重新提交。", "rate_limited": "图像服务请求过于频繁，请稍后重试。",
                            "invalid_response": "图像服务响应无效，请稍后重试。", "edit_not_supported": "此图像服务不支持编辑，请选择其他服务。",
                            "insufficient_balance": "图像服务账户余额不足，请充值或更换可用的 API Key。",
                            "invalid_request": "图像服务拒绝了请求参数，请调整提示词或画幅后重试。",
                            "service_unavailable": "图像服务暂时不可用，请稍后重新提交。"}
                if self._db_available():
                    with db:
                        db.execute("""UPDATE generation_jobs SET status='failed', error_code=?, error_message=?,
                            finished_at=?, request_json=NULL WHERE id=? AND status='running'""", (code, messages[code], now(), job["id"]))
            finally:
                timer.cancel()
            return True
        finally:
            db.close()
