"""Small SQLite seam used by the first HTTP tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS generation_jobs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    prompt TEXT NOT NULL,
    source_asset_id TEXT,
    result_asset_id TEXT,
    error_code TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL
);
"""


def open_database(data_dir: Path) -> sqlite3.Connection:
    """Create the plugin data directory and initialize its SQLite database."""
    data_dir.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(data_dir / "imagenia.sqlite3")
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    if connection.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0] == 0:
        connection.execute("INSERT INTO schema_version(version) VALUES (1)")
        connection.commit()
    return connection
