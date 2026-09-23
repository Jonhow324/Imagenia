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


class ConfigurationUnavailable(Exception):
    """The private configuration cannot be read or written safely."""


class ConnectionFailed(Exception):
    """The upstream connection failed; only the safe code is returned to callers."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def probe_openai(key: str) -> None:
    """Verify authorization with a read-only models request, never an image request."""
    request = urllib.request.Request(
        "https://api.openai.com/v1/models",
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
    def __init__(self, data_dir: Path, probe: Callable[[str], None] = probe_openai) -> None:
        self.directory = data_dir / "config"
        self.file = self.directory / "openai.json"
        self.probe = probe

    def _file_key(self) -> str | None:
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
            key = data.get("api_key")
            if not isinstance(key, str) or not key.strip():
                raise ConfigurationUnavailable()
            return key
        except FileNotFoundError:
            return None
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            raise ConfigurationUnavailable() from None

    def current(self) -> tuple[str | None, str]:
        environment_key = os.environ.get("IMAGENIA_OPENAI_API_KEY", "").strip()
        if environment_key:
            return environment_key, "environment"
        file_key = self._file_key()
        return (file_key, "file") if file_key else (None, "none")

    def status(self) -> dict[str, object]:
        key, source = self.current()
        return {"openai": {"configured": bool(key), "source": source}}

    def save(self, key: str) -> None:
        # Never log or interpolate the key into an exception or response.
        try:
            self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            if self.directory.is_symlink():
                raise ConfigurationUnavailable()
            self.directory.chmod(0o700)
            temporary = self.directory / f".openai-{uuid.uuid4().hex}.tmp"
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                    json.dump({"api_key": key}, output)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, self.file)
            finally:
                temporary.unlink(missing_ok=True)
        except OSError:
            raise ConfigurationUnavailable() from None

    def test_connection(self) -> bool:
        key, _ = self.current()
        if not key:
            return False
        self.probe(key)
        return True
