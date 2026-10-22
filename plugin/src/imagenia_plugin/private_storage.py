"""Fail closed on unexpected plugin storage and restrict only owned plugin paths."""
from __future__ import annotations

import os
import stat
import sqlite3
from pathlib import Path

from .image_formats import IMAGE_SUFFIXES


def _image_name(name: str) -> bool:
    return name.endswith(IMAGE_SUFFIXES)


def _tombstone(name: str) -> bool:
    if not name.startswith(".") or not name.endswith(".deleting"):
        return False
    return name[1:-len(".deleting")].endswith(IMAGE_SUFFIXES)


def private_directory(path: Path) -> None:
    # Parents can be supplied by the host; never change their permissions.
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink():
            raise RuntimeError("Plugin data path contains a symbolic link")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise RuntimeError("Plugin data directory is not owned by this process")
    path.chmod(0o700)


def private_file(path: Path) -> None:
    # O_NOFOLLOW blocks symlinks; the private parent prevents untrusted swaps.
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
            raise RuntimeError("Plugin data file is not an owned regular file")
        os.fchmod(descriptor, 0o600)
    finally:
        os.close(descriptor)


def private_images(data_dir: Path) -> None:
    root = data_dir / "images"
    private_directory(root)
    for year in root.iterdir():
        private_directory(year)
        for month in year.iterdir():
            private_directory(month)
            for image in month.iterdir():
                if not (_image_name(image.name) or _tombstone(image.name)):
                    raise RuntimeError("Unexpected file in plugin image storage")
                private_file(image)


def recover_deleted_images(db: sqlite3.Connection, data_dir: Path) -> None:
    """Finish/undo interrupted delete after consulting committed asset metadata."""
    root = data_dir / "images"
    for year in root.iterdir():
        for month in year.iterdir():
            for tombstone in month.iterdir():
                if not _tombstone(tombstone.name):
                    continue
                original = tombstone.with_name(tombstone.name[1:-len(".deleting")])
                relative = original.relative_to(data_dir).as_posix()
                exists = db.execute("SELECT 1 FROM image_assets WHERE file_path=?", (relative,)).fetchone()
                if exists and not original.exists():
                    tombstone.rename(original)
                else:
                    tombstone.unlink()
