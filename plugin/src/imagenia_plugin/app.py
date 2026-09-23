"""Dependency-free ASGI application for the plugin HTTP contract.

QwenPaw can mount this application through its HTTP registration adapter. Keeping
routing here independent of FastAPI makes the contract testable without starting
QwenPaw or making a provider request.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from .provider import FakeImageProvider, ImageProvider
from .settings import ConfigurationUnavailable, ConnectionFailed, OpenAISettings
from .storage import open_database


class ImageniaApp:
    """Minimal ASGI app and dependency container for the plugin skeleton."""

    def __init__(self, data_dir: Path, provider: ImageProvider | None = None, connection_probe: Callable[[str], None] | None = None) -> None:
        self.data_dir = Path(data_dir)
        self.image_dir = self.data_dir / "images"
        self.image_dir.mkdir(parents=True, exist_ok=True)
        self.database = open_database(self.data_dir)
        self.provider = provider or FakeImageProvider()
        self.settings = OpenAISettings(self.data_dir, connection_probe) if connection_probe else OpenAISettings(self.data_dir)

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            return
        method = scope.get("method", "GET").upper()
        path = scope.get("path", "")
        body = await self._read_body(receive)
        status, payload = await self.test_connection() if method == "POST" and path == "/api/imagenia/settings/openai/test" else self.handle(method, path, body)
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

    def handle(self, method: str, path: str, body: bytes = b"") -> tuple[int, dict[str, Any]]:
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
            return 200, {"items": [], "next_cursor": None}
        if method == "POST" and path in {"/api/imagenia/jobs/generate", "/api/imagenia/jobs/edit"}:
            return self._create_job(path, body)
        return 404, {"error": {"code": "not_found", "message": "Resource not found"}}

    def _settings_unavailable(self) -> tuple[int, dict[str, Any]]:
        return 503, {"error": {"code": "configuration_unavailable", "message": "Configuration is unavailable"}}

    def _save_settings(self, body: bytes) -> tuple[int, dict[str, Any]]:
        try:
            request = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            return 400, {"error": {"code": "invalid_json", "message": "Request body must be JSON"}}
        if not isinstance(request, dict):
            return 422, {"error": {"code": "invalid_api_key", "message": "A valid API key is required"}}
        key = request.get("api_key")
        if not isinstance(key, str) or not key.strip() or len(key) > 512 or any(ord(char) < 33 or ord(char) > 126 for char in key.strip()):
            return 422, {"error": {"code": "invalid_api_key", "message": "A valid API key is required"}}
        try:
            self.settings.save(key.strip())
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
        try:
            request = json.loads(body or b"{}")
        except json.JSONDecodeError:
            return 400, {"error": {"code": "invalid_json", "message": "Request body must be JSON"}}
        prompt = request.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            return 422, {"error": {"code": "invalid_prompt", "message": "prompt is required"}}
        size = request.get("size", "square")
        quality = request.get("quality", "standard")
        if size not in {"square", "landscape", "portrait"} or quality not in {"standard", "high"}:
            return 422, {"error": {"code": "invalid_options", "message": "Unsupported size or quality"}}
        job_id = str(uuid.uuid4())
        kind = "edit" if path.endswith("/edit") else "generate"
        self.database.execute(
            "INSERT INTO generation_jobs(id, kind, status, prompt, source_asset_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (job_id, kind, "pending", prompt, request.get("source_asset_id"), datetime.now(UTC).isoformat()),
        )
        self.database.commit()
        return 202, {"job_id": job_id, "status": "pending"}


def create_app(data_dir: str | Path, provider: ImageProvider | None = None, connection_probe: Callable[[str], None] | None = None) -> ImageniaApp:
    """Build an isolated app for QwenPaw or a test fixture."""
    return ImageniaApp(Path(data_dir), provider=provider, connection_probe=connection_probe)
