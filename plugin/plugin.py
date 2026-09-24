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
            self.unregister()
        if not hasattr(api, "register_http_router"):
            raise RuntimeError("QwenPaw PluginApi.register_http_router is required")
        data_dir = Path(os.environ.get("IMAGENIA_DATA_DIR", Path.home() / ".qwenpaw" / "plugins" / "imagenia"))
        app = create_app(data_dir)  # A failed migration cannot register a backend.
        try:
            app.provider = OpenAIImageProvider(lambda: app.settings.effective()[0],
                base_url=lambda: app.settings.effective()[2],
                model=lambda: app.settings.effective()[3])
            app.worker.provider = app.provider
            # Import FastAPI only inside QwenPaw; the local HTTP seam needs none.
            from src.imagenia_plugin.qwenpaw_router import build_router

            app.worker.recover()
            api.register_http_router(
                build_router(app), prefix="/imagenia", tags=["imagenia"],
            )
            app.worker.start()
        except BaseException:
            app.worker.stop()
            app.database.close()
            raise
        self.app = app

    def unregister(self) -> None:
        if self.app is not None:
            self.app.worker.stop()
            self.app._trace_thread("unregister")
            self.app.database.close()
            self.app = None


plugin = ImageniaPlugin()
