"""Versioned transactional SQLite migrations and private database access."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .private_storage import private_directory, private_file


class DatabaseMigrationError(RuntimeError):
    """Safe startup error: includes migration version, never SQL or data paths."""


SCHEMA_V1 = """CREATE TABLE generation_jobs (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL,
    prompt TEXT NOT NULL, source_asset_id TEXT, result_asset_id TEXT,
    error_code TEXT, error_message TEXT, created_at TEXT NOT NULL
)"""

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

# Rebuild rather than mutate the already-released v2 schema in place. All copying,
# validation, version advancement and old-table removal happen in one transaction.
MIGRATION_V3 = (
    "ALTER TABLE generation_jobs RENAME TO generation_jobs_legacy",
    "ALTER TABLE image_assets RENAME TO image_assets_legacy",
    """CREATE TABLE image_assets (
        id TEXT PRIMARY KEY, kind TEXT NOT NULL,
        source_asset_id TEXT REFERENCES image_assets(id) ON DELETE SET NULL,
        prompt TEXT NOT NULL, model TEXT NOT NULL, size TEXT NOT NULL,
        quality TEXT NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL,
        file_path TEXT NOT NULL, mime_type TEXT NOT NULL, file_size INTEGER NOT NULL,
        is_favorite INTEGER NOT NULL DEFAULT 0, favorited_at TEXT,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    )""",
    """INSERT INTO image_assets SELECT id,kind,source_asset_id,prompt,model,size,quality,
        width,height,file_path,mime_type,file_size,is_favorite,favorited_at,created_at,updated_at
        FROM image_assets_legacy""",
    """CREATE TABLE generation_jobs (
        id TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL,
        prompt TEXT NOT NULL,
        source_asset_id TEXT REFERENCES image_assets(id) ON DELETE SET NULL,
        result_asset_id TEXT REFERENCES image_assets(id) ON DELETE SET NULL,
        error_code TEXT, error_message TEXT, created_at TEXT NOT NULL,
        request_json TEXT, started_at TEXT, finished_at TEXT
    )""",
    """INSERT INTO generation_jobs SELECT id,kind,status,prompt,source_asset_id,
        result_asset_id,error_code,error_message,created_at,request_json,started_at,finished_at
        FROM generation_jobs_legacy""",
    "DROP TABLE generation_jobs_legacy",
    "DROP TABLE image_assets_legacy",
    "CREATE INDEX assets_created ON image_assets(created_at DESC, id DESC)",
    "CREATE INDEX assets_favorite ON image_assets(is_favorite, created_at DESC, id DESC)",
    "CREATE INDEX assets_source ON image_assets(source_asset_id)",
)

MIGRATIONS = {1: (SCHEMA_V1,), 2: MIGRATION_V2, 3: MIGRATION_V3}
LATEST_VERSION = max(MIGRATIONS)


def _migrate(connection: sqlite3.Connection) -> None:
    # A write lock serializes competing first starts/upgrades. Each version is
    # individually atomic, so a failed v3 leaves v2 intact and retryable.
    connection.execute("BEGIN IMMEDIATE")
    try:
        exists = connection.execute("""SELECT 1 FROM sqlite_master
            WHERE type='table' AND name='schema_version'""").fetchone()
        if not exists:
            other_tables = connection.execute("""SELECT 1 FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%' LIMIT 1""").fetchone()
            if other_tables:
                raise DatabaseMigrationError("Imagenia database version metadata is missing")
            connection.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
            connection.execute("INSERT INTO schema_version VALUES (0)")
        versions = connection.execute("SELECT version FROM schema_version").fetchall()
        if len(versions) != 1 or not isinstance(versions[0][0], int) or not 0 <= versions[0][0] <= LATEST_VERSION:
            raise DatabaseMigrationError("Imagenia database version metadata is invalid")
        version = versions[0][0]
        connection.commit()
    except sqlite3.Error:
        connection.rollback()
        raise DatabaseMigrationError("Imagenia database version metadata cannot be read") from None
    except BaseException:
        connection.rollback()
        raise

    while version < LATEST_VERSION:
        target = version + 1
        try:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute("SELECT version FROM schema_version").fetchone()[0]
            if current != version:
                connection.rollback()
                version = current
                continue
            for statement in MIGRATIONS[target]:
                connection.execute(statement)
            if target == 3 and connection.execute("PRAGMA foreign_key_check").fetchone():
                raise sqlite3.IntegrityError("invalid references")
            connection.execute("UPDATE schema_version SET version=?", (target,))
            connection.commit()
            version = target
        except (sqlite3.Error, ValueError):
            connection.rollback()
            raise DatabaseMigrationError(f"Imagenia database migration v{target} failed") from None
        except BaseException:
            connection.rollback()
            raise


def open_database(data_dir: Path) -> sqlite3.Connection:
    private_directory(data_dir)
    private_file(data_dir / "imagenia.sqlite3")
    connection = sqlite3.connect(data_dir / "imagenia.sqlite3", timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        _migrate(connection)
        connection.execute("PRAGMA foreign_keys=ON")
        return connection
    except BaseException:
        connection.close()
        raise
