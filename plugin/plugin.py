"""QwenPaw entry point for Imagenia.

The host-specific registration is intentionally isolated in this small adapter.
The application itself is dependency-free and can be tested with an ASGI client.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from src.imagenia_plugin import create_app
from src.imagenia_plugin.provider import MiniMaxImageProvider, OpenAIImageProvider


def data_directory() -> Path:
    """Keep new data with the installed plugin, without hiding legacy data."""
    configured = os.environ.get("IMAGENIA_DATA_DIR")
    if configured is not None:
        if not configured.strip():
            raise RuntimeError("IMAGENIA_DATA_DIR must not be empty")
        return Path(configured)

    directory = Path(__file__).resolve().parent / "data"
    legacy = Path.home() / ".qwenpaw" / "plugins" / "imagenia"

    def has_data(candidate: Path) -> bool:
        return any((candidate / name).exists() or (candidate / name).is_symlink()
                   for name in ("imagenia.sqlite3", "config", "images"))

    if not has_data(directory) and has_data(legacy):
        logging.getLogger(__name__).warning(
            "Imagenia is using its legacy home data directory. For Docker persistence, "
            "stop the plugin, back up and copy the complete data directory to a persistent "
            "mount, then set IMAGENIA_DATA_DIR to that location. See plugin/README.md."
        )
        return legacy
    return directory


class ImageniaPlugin:
    def __init__(self) -> None:
        self.app = None

    def register(self, api: Any) -> None:
        if self.app is not None:
            self.unregister()
        if not hasattr(api, "register_http_router"):
            raise RuntimeError("QwenPaw PluginApi.register_http_router is required")
        data_dir = data_directory()
        app = create_app(data_dir)  # A failed migration cannot register a backend.
        try:
            app.provider = OpenAIImageProvider(lambda: app.settings.effective()[0],
                base_url=lambda: app.settings.effective()[2],
                model=lambda: app.settings.effective()[3])
            app.worker.provider = app.provider

            def provider_factory(selected):
                if selected.get("provider") == "minimax":
                    return MiniMaxImageProvider(lambda: selected["api_key"],
                                                base_url=selected["base_url"], model=selected["model"])
                return OpenAIImageProvider(lambda: selected["api_key"],
                                           base_url=selected["base_url"], model=selected["model"])

            app.provider_factory = provider_factory
            # Import FastAPI only inside QwenPaw; the local HTTP seam needs none.
            from src.imagenia_plugin.qwenpaw_router import build_router

            app.worker.recover()
            api.register_http_router(
                build_router(app), prefix="/imagenia", tags=["imagenia"],
            )
            app.worker.start()
        except BaseException:
            # Same order as unregister(): the worker must stop before its database.
            app.worker.stop()
            app.database.close()
            raise
        self.app = app

    def unregister(self) -> None:
        if self.app is not None:
            # Order matters: the worker thread must be fully stopped before the
            # database is closed. A surviving thread would re-open the database
            # after the host deletes the plugin directory and re-create
            # data/imagenia.sqlite3, which then blocks re-installation.
            self.app.worker.stop()
            self.app._trace_thread("unregister")
            self.app.database.close()
            self.app = None


plugin = ImageniaPlugin()
