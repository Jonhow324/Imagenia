"""Asset state transitions, including private-file deletion and task redaction."""
from __future__ import annotations

import os
import sqlite3
import stat
from pathlib import Path

from .jobs import now


class UnsafeAssetPath(Exception):
    """The persisted path cannot safely be removed."""


def set_favorite(db: sqlite3.Connection, asset_id: str, favorite: bool) -> sqlite3.Row | None:
    with db:
        db.execute("UPDATE image_assets SET is_favorite=?, favorited_at=?, updated_at=? WHERE id=?",
                   (int(favorite), now() if favorite else None, now(), asset_id))
    return db.execute("SELECT * FROM image_assets WHERE id=?", (asset_id,)).fetchone()


def delete_asset(db: sqlite3.Connection, data_dir: Path, asset_id: str) -> bool:
    row = db.execute("SELECT file_path FROM image_assets WHERE id=?", (asset_id,)).fetchone()
    if row is None:
        return False
    root = data_dir / "images"
    path = data_dir / row["file_path"]
    # Constrain to the image tree, not merely to the plugin's data directory.
    if (path.suffix != ".png" or not path.resolve().is_relative_to(root.resolve())
            or path.parent.is_symlink() or path.is_symlink()):
        raise UnsafeAssetPath()
    tombstone = None
    try:
        if path.exists():
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
                raise UnsafeAssetPath()
            tombstone = path.with_name(f".{path.name}.deleting")
            if tombstone.exists() or tombstone.is_symlink():
                raise UnsafeAssetPath()
            path.rename(tombstone)
        try:
            with db:
                db.execute("UPDATE image_assets SET source_asset_id=NULL, updated_at=? WHERE source_asset_id=?",
                           (now(), asset_id))
                # In-flight edits are invalidated; the worker also checks the
                # source and job status before publishing a generated result.
                db.execute("""UPDATE generation_jobs SET
                    status=CASE WHEN status IN ('pending','running') THEN 'failed' ELSE status END,
                    error_code=CASE WHEN status IN ('pending','running') THEN 'source_unavailable' ELSE error_code END,
                    error_message=NULL, prompt='', request_json=NULL,
                    source_asset_id=NULL, result_asset_id=NULL
                    WHERE source_asset_id=? OR result_asset_id=?""", (asset_id, asset_id))
                db.execute("DELETE FROM image_assets WHERE id=?", (asset_id,))
        except BaseException:
            if tombstone is not None:
                tombstone.rename(path)
            raise
        if tombstone is not None:
            tombstone.unlink()
        return True
    except FileNotFoundError:
        raise UnsafeAssetPath() from None
