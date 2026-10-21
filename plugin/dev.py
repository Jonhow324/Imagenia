"""Run Imagenia locally with the production HTTP router and isolated data."""

from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
import hashlib
import json
import os
from pathlib import Path
import struct
from typing import Any
import zlib

from src.imagenia_plugin import create_app
from src.imagenia_plugin.app import ImageniaApp
from src.imagenia_plugin.provider import OpenAIImageProvider


class PreviewImageProvider:
    """Return deterministic, correctly sized PNG previews without networking."""

    model = "local-preview"

    def generate(self, prompt: str, *, size: str, quality: str) -> bytes:
        width, height = {"square": (1024, 1024), "landscape": (1536, 1024),
                         "portrait": (1024, 1536)}[size]
        color = hashlib.sha256(prompt.encode()).digest()[:3]
        rows = []
        for y in range(height):
            pixel = bytes(40 + (channel + y * 80 // height) % 170 for channel in color)
            rows.append(b"\x00" + pixel * width)

        def chunk(kind: bytes, content: bytes) -> bytes:
            return (struct.pack(">I", len(content)) + kind + content
                    + struct.pack(">I", zlib.crc32(kind + content)))

        return (b"\x89PNG\r\n\x1a\n"
                + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b""))

    def edit(self, prompt: str, source: bytes, *, size: str, quality: str) -> bytes:
        return self.generate(prompt + hashlib.sha256(source).hexdigest(), size=size, quality=quality)


def seed_library(app: ImageniaApp, count: int) -> None:
    """Populate only an empty preview library through normal job processing."""
    if app.database.execute("SELECT COUNT(*) FROM generation_jobs").fetchone()[0]:
        return
    source_id = None
    for index in range(count):
        editing = source_id is not None and index % 4 == 3
        payload: dict[str, Any] = {
            "prompt": f"本地预览图片 {index + 1:02d}：光线、色彩与空间",
            "size": ("square", "landscape", "portrait")[index % 3],
            "quality": "standard",
        }
        if editing:
            payload["source_asset_id"] = source_id
        status, job = app.handle("POST", f"/api/imagenia/jobs/{'edit' if editing else 'generate'}",
                                 json.dumps(payload).encode())
        if status != 202 or not app.worker.process_next():
            raise RuntimeError("Could not create local preview assets")
        _, result = app.handle("GET", f"/api/imagenia/jobs/{job['job_id']}")
        if result["status"] != "succeeded":
            raise RuntimeError("Local preview generation failed")
        asset_id = result["result_asset_id"]
        if not editing:
            source_id = asset_id
        if index % 3 == 0:
            app.handle("PATCH", f"/api/imagenia/assets/{asset_id}", b'{"is_favorite":true}')


def create_dev_app():
    """Build the same router as QwenPaw, with a local worker lifespan."""
    from fastapi import FastAPI
    from src.imagenia_plugin.qwenpaw_router import build_router

    provider = os.environ.get("IMAGENIA_DEV_PROVIDER", "fake")
    if provider not in {"fake", "openai"}:
        raise ValueError("Unsupported local provider")
    seed_count = int(os.environ.get("IMAGENIA_DEV_SEED", "36" if provider == "fake" else "0"))
    if not 0 <= seed_count <= 100 or (provider == "openai" and seed_count):
        raise ValueError("Seeding requires fake mode and a count between 0 and 100")
    default_directory = Path(__file__).parent / ".local-data" / provider
    data_dir = Path(os.environ.get("IMAGENIA_DEV_DATA_DIR", default_directory))

    @asynccontextmanager
    async def lifespan(server):
        # This entry point is local-only; host authentication remains a QwenPaw concern.
        app = create_app(data_dir, provider=PreviewImageProvider() if provider == "fake" else None,
                         connection_probe=(lambda *_: None) if provider == "fake" else None)
        try:
            if provider == "fake":
                if not app.settings.status()["openai"]["configured"]:
                    app.settings.save("imagenia-local-demo", model="local-preview")
                seed_library(app, seed_count)
            else:
                app.provider = OpenAIImageProvider(lambda: app.settings.effective()[0],
                    base_url=lambda: app.settings.effective()[2], model=lambda: app.settings.effective()[3])
                app.worker.provider = app.provider
            server.state.imagenia = app
            # Register once per process; reload starts a fresh process and lifespan.
            server.include_router(build_router(app), prefix="/api/imagenia")
            app.worker.start()
            yield
        finally:
            app.worker.stop()
            app.database.close()

    return FastAPI(title="Imagenia local development", lifespan=lifespan)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("fake", "openai"), default="fake",
                        help="fake makes offline previews; openai uses the configured paid image API")
    parser.add_argument("--seed", type=int, help="initial preview image count, default 36 (fake only)")
    parser.add_argument("--data-dir", type=Path, help="separate local data directory")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--reload", action="store_true", help="restart the backend after Python edits")
    args = parser.parse_args()
    seed_count = args.seed if args.seed is not None else (36 if args.provider == "fake" else 0)
    if not 0 <= seed_count <= 100 or (args.provider == "openai" and seed_count):
        parser.error("--seed must be 0..100 and can only populate fake mode")
    os.environ["IMAGENIA_DEV_PROVIDER"] = args.provider
    os.environ["IMAGENIA_DEV_SEED"] = str(seed_count)
    if args.data_dir:
        os.environ["IMAGENIA_DEV_DATA_DIR"] = str(args.data_dir.resolve())
    print(f"Imagenia local provider: {args.provider}; API: http://127.0.0.1:{args.port}/api/imagenia", flush=True)
    if args.provider == "fake":
        print("Offline preview images; generation, editing and connection tests make no external requests.", flush=True)
    else:
        print("OpenAI mode: generation and editing use your configured provider and may incur charges.", flush=True)
    import uvicorn
    uvicorn.run("dev:create_dev_app", factory=True, host="127.0.0.1", port=args.port,
                reload=args.reload, reload_dirs=[str(Path(__file__).parent)] if args.reload else None)


if __name__ == "__main__":
    main()
