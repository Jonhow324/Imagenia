"""QwenPaw entry point for Imagenia.

The host-specific registration is intentionally isolated in this small adapter.
The application itself is dependency-free and can be tested with an ASGI client.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from src.imagenia_plugin import create_app
from src.imagenia_plugin.provider import OpenAIImageProvider


class ImageniaPlugin:
    def __init__(self) -> None:
        self.app = None

    def register(self, api: Any) -> None:
        if self.app is not None:
            self.app.worker.stop()
        data_dir = Path(os.environ.get("IMAGENIA_DATA_DIR", Path.home() / ".qwenpaw" / "plugins" / "imagenia"))
        self.app = create_app(data_dir)
        self.app.provider = OpenAIImageProvider(lambda: self.app.settings.effective()[0],
            base_url=lambda: self.app.settings.effective()[2],
            model=lambda: self.app.settings.effective()[3])
        self.app.worker.provider = self.app.provider
        # QwenPaw mounts APIRouter under /api + prefix. Import FastAPI lazily so
        # the dependency-free HTTP seam remains runnable outside the host.
        from src.imagenia_plugin.qwenpaw_router import build_router

        if not hasattr(api, "register_http_router"):
            raise RuntimeError("QwenPaw PluginApi.register_http_router is required")
        api.register_http_router(
            build_router(self.app),
            prefix="/imagenia",
            tags=["imagenia"],
        )
        self.app.worker.start()

    def unregister(self) -> None:
        if self.app is not None:
            self.app.worker.stop()
            self.app._trace_thread("unregister")
            self.app.database.close()
            self.app = None


plugin = ImageniaPlugin()
