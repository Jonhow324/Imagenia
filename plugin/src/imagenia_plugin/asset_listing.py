"""Validated, opaque keyset cursors for the public ImageAsset listing."""

from __future__ import annotations

import base64
import json
import re
import sqlite3
from urllib.parse import parse_qs

PAGE_SIZE = 30
MAX_PAGE_SIZE = 100


def _encode_cursor(row: sqlite3.Row) -> str:
    raw = json.dumps([row["created_at"], row["id"]], separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _decode_cursor(value: str) -> tuple[str, str]:
    if not value or len(value) > 512 or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for char in value):
        raise ValueError("invalid cursor")
    try:
        raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        pair = json.loads(raw)
        if (not isinstance(pair, list) or len(pair) != 2 or
            not all(isinstance(item, str) and 0 < len(item) <= 128 for item in pair)):
            raise ValueError("invalid cursor")
        return pair[0], pair[1]
    except (ValueError, UnicodeDecodeError):
        raise ValueError("invalid cursor") from None


def list_asset_rows(database: sqlite3.Connection, query: bytes) -> tuple[list[sqlite3.Row], str | None]:
    if len(query) > 1024:
        raise ValueError("invalid filters")
    try:
        params = parse_qs(query.decode("ascii"), keep_blank_values=True, strict_parsing=True)
    except (UnicodeDecodeError, ValueError):
        raise ValueError("invalid filters") from None
    if any(name not in {"cursor", "favorite", "kind", "limit"} or len(values) != 1 for name, values in params.items()):
        raise ValueError("invalid filters")
    favorite = params.get("favorite", ["false"])[0]
    kind = params.get("kind", ["all"])[0]
    if favorite not in {"true", "false"} or kind not in {"all", "generated", "edited"}:
        raise ValueError("invalid filters")
    raw_limit = params.get("limit", [str(PAGE_SIZE)])[0]
    if not re.fullmatch(r"[0-9]+", raw_limit) or not 1 <= int(raw_limit) <= MAX_PAGE_SIZE:
        raise ValueError("invalid filters")
    limit = int(raw_limit)
    conditions = []
    values: list[str | int] = []
    if favorite == "true":
        conditions.append("is_favorite = 1")
    if kind != "all":
        conditions.append("kind = ?")
        values.append(kind)
    if params.get("cursor", [""])[0] not in {"", "null"}:
        created_at, asset_id = _decode_cursor(params["cursor"][0])
        conditions.append("(created_at, id) < (?, ?)")
        values.extend((created_at, asset_id))
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    rows = database.execute(
        "SELECT * FROM image_assets" + where + " ORDER BY created_at DESC, id DESC LIMIT ?",
        (*values, limit + 1),
    ).fetchall()
    page = rows[:limit]
    return page, _encode_cursor(page[-1]) if len(rows) > limit else None
