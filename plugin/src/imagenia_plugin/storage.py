"""Versioned, transactional SQLite schema for jobs and generated assets."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS generation_jobs (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL,
    prompt TEXT NOT NULL, source_asset_id TEXT, result_asset_id TEXT,
    error_code TEXT, error_message TEXT, created_at TEXT NOT NULL
)
"""

MIGRATION_V2 = (
    "ALTER TABLE generation_jobs ADD COLUMN request_json TEXT",
    "ALTER TABLE generation_jobs ADD COLUMN started_at TEXT",
    "ALTER TABLE generation_jobs ADD COLUMN finished_at TEXT",
    """CREATE TABLE image_assets (
        id TEXT PRIMARY KEY, kind TEXT NOT NULL, source_asset_id TEXT,
        prompt TEXT NOT NULL, model TEXT NOT NULL, size TEXT NOT NULL,
        quality TEXT NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL,
        file_path TEXT NOT NULL, mime_type TEXT NOT NULL, file_size INTEGER NOT NULL,
        is_favorite INTEGER NOT NULL DEFAULT 0, favorited_at TEXT,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    )""",
    "CREATE INDEX assets_created ON image_assets(created_at DESC, id DESC)",
    "CREATE INDEX assets_favorite ON image_assets(is_favorite, created_at DESC, id DESC)",
    "CREATE INDEX assets_source ON image_assets(source_asset_id)",
)


def open_database(data_dir: Path) -> sqlite3.Connection:
    data_dir.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(data_dir / "imagenia.sqlite3", timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
        row = connection.execute("SELECT version FROM schema_version").fetchone()
        if row is None:
            with connection:
                connection.execute(SCHEMA_V1)
                connection.execute("INSERT INTO schema_version(version) VALUES (1)")
            row = (1,)
        if row[0] == 1:
            with connection:
                for statement in MIGRATION_V2:
                    connection.execute(statement)
                connection.execute("UPDATE schema_version SET version = 2")
        elif row[0] != 2:
            raise RuntimeError("Unsupported database schema")
        return connection
    except BaseException:
        connection.close()
        raise
