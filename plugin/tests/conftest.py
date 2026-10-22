"""Keep test runs out of the real user home and default plugin data directory."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_imagenia_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("IMAGENIA_DATA_DIR", str(tmp_path / "plugin-data"))
