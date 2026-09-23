"""Private OpenAI configuration and an explicit, non-generating connection probe."""

from __future__ import annotations

import json
import os
import stat
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-image-2.5"


class ConfigurationUnavailable(Exception):
    """The private configuration cannot be read or written safely."""


class ConnectionFailed(Exception):
    """The upstream connection failed; only the safe code is returned to callers."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def valid_base_url(value: object) -> bool:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > 2048:
        return False
    try:
        parsed = urlsplit(value)
        return (parsed.scheme in ("http", "https") and bool(parsed.hostname) and
                parsed.port != 0 and not parsed.username and not parsed.password and
                not parsed.query and not parsed.fragment and
                all(33 <= ord(char) <= 126 for char in value) and not value.endswith("/images/generations"))
    except ValueError:
        return False


def valid_model(value: object) -> bool:
    return isinstance(value, str) and 0 < len(value) <= 128 and all(
        char.isascii() and (char.isalnum() or char in "-_./") for char in value
    )


def probe_openai(key: str, base_url: str = DEFAULT_BASE_URL) -> None:
    """Verify authorization with a read-only models request, never an image request."""
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/models",
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            if response.status != 200:
                raise ConnectionFailed("service_unavailable")
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise ConnectionFailed("invalid_api_key") from None
        raise ConnectionFailed("service_unavailable") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ConnectionFailed("service_unavailable") from None


class OpenAISettings:
    def __init__(self, data_dir: Path, probe: Callable[..., None] = probe_openai) -> None:
        self.directory = data_dir / "config"
        self.file = self.directory / "openai.json"
        self.probe = probe

    def _read_file(self) -> dict[str, str]:
        try:
            directory_mode = self.directory.lstat().st_mode
            if not stat.S_ISDIR(directory_mode) or stat.S_IMODE(directory_mode) & 0o077:
                raise ConfigurationUnavailable()
            descriptor = os.open(self.file, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(descriptor, "r", encoding="utf-8") as private_file:
                mode = os.fstat(private_file.fileno()).st_mode
                if not stat.S_ISREG(mode) or stat.S_IMODE(mode) & 0o077:
                    raise ConfigurationUnavailable()
                data = json.load(private_file)
            if not isinstance(data, dict) or any(
                name in data and not validator(data[name]) for name, validator in
                (("api_key", lambda x: isinstance(x, str) and bool(x.strip())),
                 ("base_url", valid_base_url), ("model", valid_model))
            ):
                raise ConfigurationUnavailable()
            return data
        except FileNotFoundError:
            return {}
        except (OSError, ValueError, TypeError, AttributeError):
            raise ConfigurationUnavailable() from None

    def effective(self) -> tuple[str | None, str, str, str]:
        data = self._read_file()
        key = os.environ.get("IMAGENIA_OPENAI_API_KEY", "").strip()
        source = "environment" if key else "file" if data.get("api_key") else "none"
        base_url = os.environ.get("IMAGENIA_OPENAI_BASE_URL") or data.get("base_url") or DEFAULT_BASE_URL
        model = os.environ.get("IMAGENIA_OPENAI_MODEL") or data.get("model") or DEFAULT_MODEL
        if not valid_base_url(base_url) or not valid_model(model):
            raise ConfigurationUnavailable()
        return key or data.get("api_key"), source, base_url, model

    def current(self) -> tuple[str | None, str]:
        key, source, _, _ = self.effective()
        return key, source

    def status(self) -> dict[str, object]:
        key, source, base_url, model = self.effective()
        return {"openai": {"configured": bool(key), "source": source, "base_url": base_url, "model": model}}

    def save(self, key: str | None = None, base_url: str | None = None, model: str | None = None) -> None:
        # Partial updates preserve previously saved fields; omitted key never clears a secret.
        data = self._read_file()
        if key is not None:
            data["api_key"] = key
        if base_url is not None:
            data["base_url"] = base_url
        if model is not None:
            data["model"] = model
        try:
            self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            if self.directory.is_symlink():
                raise ConfigurationUnavailable()
            self.directory.chmod(0o700)
            temporary = self.directory / f".openai-{uuid.uuid4().hex}.tmp"
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                    json.dump(data, output)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, self.file)
            finally:
                temporary.unlink(missing_ok=True)
        except OSError:
            raise ConfigurationUnavailable() from None

    def test_connection(self) -> bool:
        key, _, base_url, _ = self.effective()
        if not key:
            return False
        self.probe(key, base_url)
        return True
