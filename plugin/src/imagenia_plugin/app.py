"""Dependency-free ASGI application for the plugin HTTP contract.

QwenPaw can mount this application through its HTTP registration adapter. Keeping
routing here independent of FastAPI makes the contract testable without starting
QwenPaw or making a provider request.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from .provider import FakeImageProvider, ImageProvider, ProviderError
from .private_storage import private_directory, private_images, recover_deleted_images
from .asset_listing import list_asset_rows
from .asset_mutations import UnsafeAssetPath, delete_asset, set_favorite
from .jobs import GenerationWorker, source_image
from .settings import ConfigurationUnavailable, ConnectionFailed, OpenAISettings, valid_base_url, valid_model
from .storage import open_database


class ImageniaApp:
    """Minimal ASGI app and dependency container for the plugin skeleton."""

    def __init__(self, data_dir: Path, provider: ImageProvider | None = None, connection_probe: Callable[[str], None] | None = None) -> None:
        self._thread_probe = os.environ.get("IMAGENIA_THREAD_PROBE") == "1"
        self._thread_stages: set[tuple[str, int]] = set()
        self._trace_thread("create")
        self.data_dir = Path(data_dir)
        self.image_dir = self.data_dir / "images"
        private_directory(self.data_dir)
        private_images(self.data_dir)
        self.database = open_database(self.data_dir)
        try:
            recover_deleted_images(self.database, self.data_dir)
        except BaseException:
            self.database.close()
            raise
        self.provider = provider or FakeImageProvider()
        self.settings = OpenAISettings(self.data_dir, connection_probe) if connection_probe else OpenAISettings(self.data_dir)
        self.worker = GenerationWorker(self.data_dir, self.provider)

    def _trace_thread(self, stage: str) -> None:
        """Opt-in host lifecycle evidence; never include prompts or credentials."""
        if not self._thread_probe:
            return
        key = (stage, threading.get_ident())
        if key not in self._thread_stages:
            self._thread_stages.add(key)
            logging.getLogger("imagenia.thread_probe").warning("Imagenia %s thread=%s", *key)

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            return
        method = scope.get("method", "GET").upper()
        path = scope.get("path", "")
        body = await self._read_body(receive)
        if method == "GET" and path.startswith("/api/imagenia/assets/") and path.endswith("/content"):
            status, content = self.asset_content(path.split("/")[-2])
            await send({"type": "http.response.start", "status": status,
                        "headers": [(b"content-type", b"image/png" if status == 200 else b"application/json")]})
            await send({"type": "http.response.body", "body": content if status == 200 else b'{"error":{"code":"not_found"}}'})
            return
        status, payload = await self.test_connection() if method == "POST" and path == "/api/imagenia/settings/openai/test" else self.handle(method, path, body, scope.get("query_string", b""))
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json; charset=utf-8")],
        })
        await send({"type": "http.response.body", "body": encoded})

    async def _read_body(self, receive: Any) -> bytes:
        chunks: list[bytes] = []
        while True:
            message = await receive()
            chunks.append(message.get("body", b""))
            if not message.get("more_body", False):
                return b"".join(chunks)

    def handle(self, method: str, path: str, body: bytes = b"", query: bytes = b"") -> tuple[int, dict[str, Any]]:
        self._trace_thread("handle")
        if method == "GET" and path == "/api/imagenia/health":
            return 200, {
                "status": "ok",
                "service": "imagenia",
                "provider": "fake" if isinstance(self.provider, FakeImageProvider) else "custom",
                "database": "ok",
            }
        if method == "GET" and path == "/api/imagenia/settings":
            try:
                return 200, self.settings.status()
            except ConfigurationUnavailable:
                return self._settings_unavailable()
        if method == "PUT" and path == "/api/imagenia/settings/openai":
            return self._save_settings(body)
        if method == "GET" and path == "/api/imagenia/assets":
            try:
                rows, next_cursor = list_asset_rows(self.database, query)
            except ValueError:
                return 422, {"error": {"code": "invalid_filter", "message": "Invalid asset filter or cursor"}}
            return 200, {"items": [self._asset(row) for row in rows], "next_cursor": next_cursor}
        if path.startswith("/api/imagenia/assets/") and path.count("/") == 4:
            asset_id = path.rsplit("/", 1)[-1]
            if method == "PATCH":
                try:
                    change = json.loads(body)
                except (ValueError, UnicodeDecodeError):
                    return 400, {"error": {"code": "invalid_json", "message": "Request body must be JSON"}}
                if not isinstance(change, dict) or set(change) != {"is_favorite"} or type(change["is_favorite"]) is not bool:
                    return 422, {"error": {"code": "invalid_input", "message": "Expected is_favorite boolean"}}
                row = set_favorite(self.database, asset_id, change["is_favorite"])
                return (200, self._asset(row)) if row else self._missing()
            if method == "DELETE":
                try:
                    removed = delete_asset(self.database, self.data_dir, asset_id)
                except UnsafeAssetPath:
                    return 409, {"error": {"code": "asset_unavailable", "message": "Asset cannot be safely deleted"}}
                return (200, {"deleted": True}) if removed else self._missing()
        if method == "GET" and path.startswith("/api/imagenia/assets/") and path.count("/") == 4:
            row = self.database.execute("SELECT * FROM image_assets WHERE id=?", (path.rsplit("/", 1)[-1],)).fetchone()
            return (200, self._asset(row)) if row else self._missing()
        if method == "GET" and path == "/api/imagenia/jobs":
            rows = self.database.execute("SELECT * FROM generation_jobs ORDER BY created_at DESC, id DESC LIMIT 100").fetchall()
            return 200, {"items": [self._job(row) for row in rows]}
        if method == "GET" and path.startswith("/api/imagenia/jobs/") and path.count("/") == 4:
            row = self.database.execute("SELECT * FROM generation_jobs WHERE id=?", (path.rsplit("/", 1)[-1],)).fetchone()
            return (200, self._job(row)) if row else self._missing()
        if method == "POST" and path in {"/api/imagenia/jobs/generate", "/api/imagenia/jobs/edit"}:
            return self._create_job(path, body)
        return self._missing()

    @staticmethod
    def _missing() -> tuple[int, dict[str, Any]]:
        return 404, {"error": {"code": "not_found", "message": "Resource not found"}}

    @staticmethod
    def _asset(row: Any) -> dict[str, Any]:
        return {"id": row["id"], "kind": row["kind"], "prompt": row["prompt"],
                "model": row["model"], "size": row["size"], "quality": row["quality"],
                "width": row["width"], "height": row["height"], "created_at": row["created_at"],
                "is_favorite": bool(row["is_favorite"]), "source_asset_id": row["source_asset_id"]}

    @staticmethod
    def _job(row: Any) -> dict[str, Any]:
        return {"id": row["id"], "kind": row["kind"], "status": row["status"],
                "prompt": row["prompt"], "created_at": row["created_at"],
                "result_asset_id": row["result_asset_id"], "error_code": row["error_code"],
                "error_message": row["error_message"]}

    def asset_content(self, asset_id: str) -> tuple[int, bytes]:
        self._trace_thread("content")
        try:
            return 200, source_image(self.database, self.data_dir, asset_id)
        except ProviderError:
            return 404, b""

    def _settings_unavailable(self) -> tuple[int, dict[str, Any]]:
        return 503, {"error": {"code": "configuration_unavailable", "message": "Configuration is unavailable"}}

    def _save_settings(self, body: bytes) -> tuple[int, dict[str, Any]]:
        try:
            request = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            return 400, {"error": {"code": "invalid_json", "message": "Request body must be JSON"}}
        if not isinstance(request, dict):
            return 422, {"error": {"code": "invalid_api_key", "message": "A valid API key is required"}}
        if not request or any(field not in {"api_key", "base_url", "model"} for field in request):
            return 422, {"error": {"code": "invalid_options", "message": "Unsupported settings"}}
        key = request.get("api_key")
        if "api_key" in request and (not isinstance(key, str) or not key.strip() or len(key) > 512 or
                any(ord(char) < 33 or ord(char) > 126 for char in key.strip())):
            return 422, {"error": {"code": "invalid_api_key", "message": "A valid API key is required"}}
        if ("base_url" in request and not valid_base_url(request["base_url"])) or ("model" in request and not valid_model(request["model"])):
            return 422, {"error": {"code": "invalid_options", "message": "Unsupported base URL or model"}}
        try:
            self.settings.save(key.strip() if key is not None else None,
                               request.get("base_url"), request.get("model"))
            return 200, self.settings.status()
        except ConfigurationUnavailable:
            return self._settings_unavailable()

    async def test_connection(self) -> tuple[int, dict[str, Any]]:
        try:
            configured = self.settings.test_connection()
            if not configured:
                return 409, {"error": {"code": "not_configured", "message": "Configure an API key first"}}
            return 200, {"status": "ok"}
        except ConfigurationUnavailable:
            return self._settings_unavailable()
        except ConnectionFailed as exc:
            code = exc.code if exc.code in {"invalid_api_key", "service_unavailable"} else "service_unavailable"
            return 502, {"error": {"code": code, "message": "Connection test failed"}}
        except Exception:
            # Never expose provider exception text: it may contain credentials or headers.
            return 502, {"error": {"code": "service_unavailable", "message": "Connection test failed"}}

    def _create_job(self, path: str, body: bytes) -> tuple[int, dict[str, Any]]:
        editing = path.endswith("/edit")
        try:
            request = json.loads(body or b"{}")
        except (ValueError, UnicodeDecodeError):
            return 400, {"error": {"code": "invalid_json", "message": "Request body must be JSON"}}
        if not isinstance(request, dict):
            return 422, {"error": {"code": "invalid_input", "message": "Invalid request"}}
        prompt = request.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 4000:
            return 422, {"error": {"code": "invalid_prompt", "message": "A prompt is required"}}
        size, quality = request.get("size", "square"), request.get("quality", "standard")
        allowed = {"prompt", "size", "quality", "source_asset_id"} if editing else {"prompt", "size", "quality"}
        if size not in ("square", "landscape", "portrait") or quality not in ("standard", "high") or set(request) - allowed:
            return 422, {"error": {"code": "invalid_options", "message": "Unsupported size, quality or model"}}
        source_id = request.get("source_asset_id") if editing else None
        if editing:
            if not isinstance(source_id, str) or not source_id.strip() or len(source_id) > 128:
                return 422, {"error": {"code": "invalid_input", "message": "A source asset is required"}}
            if self.asset_content(source_id)[0] != 200:
                return self._missing()
        try:
            if not self.settings.status()["openai"]["configured"]:
                return 409, {"error": {"code": "not_configured", "message": "Configure an API key first"}}
        except ConfigurationUnavailable:
            return self._settings_unavailable()
        if self.database.execute("SELECT COUNT(*) FROM generation_jobs WHERE status='pending'").fetchone()[0] >= 50:
            return 429, {"error": {"code": "queue_full", "message": "Queue is full"}}
        job_id = str(uuid.uuid4())
        self.database.execute("""INSERT INTO generation_jobs
            (id, kind, status, prompt, source_asset_id, request_json, created_at)
            VALUES (?, ?, 'pending', ?, ?, ?, ?)""",
            (job_id, "edit" if editing else "generate", prompt.strip(), source_id,
             json.dumps({"size": size, "quality": quality}), datetime.now(UTC).isoformat()))
        self.database.commit()
        return 202, {"job_id": job_id, "status": "pending"}


def create_app(data_dir: str | Path, provider: ImageProvider | None = None, connection_probe: Callable[[str], None] | None = None) -> ImageniaApp:
    """Build an isolated app for QwenPaw or a test fixture."""
    return ImageniaApp(Path(data_dir), provider=provider, connection_probe=connection_probe)
