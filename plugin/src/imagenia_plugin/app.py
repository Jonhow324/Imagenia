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
from typing import Any

from .provider import FakeImageProvider, ImageProvider
from .storage import open_database


class ImageniaApp:
    """Minimal ASGI app and dependency container for the plugin skeleton."""

    def __init__(self, data_dir: Path, provider: ImageProvider | None = None) -> None:
        self.data_dir = Path(data_dir)
        self.image_dir = self.data_dir / "images"
        self.image_dir.mkdir(parents=True, exist_ok=True)
        self.database = open_database(self.data_dir)
        self.provider = provider or FakeImageProvider()

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            return
        method = scope.get("method", "GET").upper()
        path = scope.get("path", "")
        body = await self._read_body(receive)
        status, payload = self.handle(method, path, body)
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
            return 200, {"openai": {"configured": False}}
        if method == "GET" and path == "/api/imagenia/assets":
            return 200, {"items": [], "next_cursor": None}
        if method == "POST" and path in {"/api/imagenia/jobs/generate", "/api/imagenia/jobs/edit"}:
            return self._create_job(path, body)
        return 404, {"error": {"code": "not_found", "message": "Resource not found"}}

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


def create_app(data_dir: str | Path, provider: ImageProvider | None = None) -> ImageniaApp:
    """Build an isolated app for QwenPaw or a test fixture."""
    return ImageniaApp(Path(data_dir), provider=provider)
