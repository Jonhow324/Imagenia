"""Private image-service catalog and immutable, secret-free task bindings."""
from __future__ import annotations

import copy
import hashlib
import hmac
import json
import os
import secrets
import stat
import threading
import uuid
from pathlib import Path
from typing import Any

from .settings import (ConfigurationUnavailable, DEFAULT_BASE_URL, DEFAULT_MINIMAX_BASE_URL,
                       DEFAULT_MINIMAX_MODEL, DEFAULT_MODEL, OpenAISettings, valid_base_url, valid_model)

SIZES = ("square", "landscape", "portrait")
QUALITIES = ("standard", "high")
PROVIDERS = ("openai", "minimax", "custom")
CONFIG_VERSION = 2

# Built-in starting points for the settings UI. They are defaults, not hidden
# services: users still create and save an independent service (and may change
# its address, models and capabilities) before anything can run.
PROVIDER_PRESETS = (
    {"id": "openai", "name": "OpenAI 图像", "base_url": DEFAULT_BASE_URL,
     "models": [{"name": "gpt-image-1", "sizes": list(SIZES), "qualities": list(QUALITIES),
                 "supports_edit": True}]},
    {"id": "minimax", "name": "MiniMax 图像", "base_url": DEFAULT_MINIMAX_BASE_URL,
     "models": [{"name": DEFAULT_MINIMAX_MODEL, "sizes": list(SIZES), "qualities": ["standard"],
                 "supports_edit": False}]},
    {"id": "custom", "name": "自定义兼容服务", "base_url": "", "models": []},
)


class ServiceError(Exception):
    def __init__(self, code: str, status: int = 422) -> None:
        self.code, self.status = code, status
        super().__init__(code)


def valid_key(value: object) -> bool:
    return isinstance(value, str) and 0 < len(value) <= 512 and all(33 <= ord(char) <= 126 for char in value)


def default_model(name: str, *, editing: bool = False, model_id: str | None = None) -> dict[str, Any]:
    return {"id": model_id or str(uuid.uuid4()), "name": name, "sizes": list(SIZES),
            "qualities": list(QUALITIES), "supports_edit": editing}


class ServiceCatalog:
    """Serialize task selection/configuration changes and persist secrets atomically."""
    def __init__(self, data_dir: Path, legacy: OpenAISettings) -> None:
        self.file = data_dir / "config" / "services.json"
        self.legacy = legacy
        self.lock = threading.RLock()

    def _write(self, document: dict[str, Any]) -> None:
        directory = self.file.parent
        temporary = directory / f".services-{uuid.uuid4().hex}.tmp"
        try:
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            if directory.is_symlink() or directory.stat().st_uid != os.getuid():
                raise ConfigurationUnavailable()
            directory.chmod(0o700)
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                json.dump(document, output, ensure_ascii=False)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.file)
        except OSError:
            raise ConfigurationUnavailable() from None
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def _load(self) -> dict[str, Any]:
        try:
            directory = self.file.parent.lstat()
            if not stat.S_ISDIR(directory.st_mode) or directory.st_mode & 0o077 or directory.st_uid != os.getuid():
                raise ConfigurationUnavailable()
            descriptor = os.open(self.file, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(descriptor, encoding="utf-8") as source:
                info = os.fstat(source.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.getuid() or info.st_nlink != 1:
                    raise ConfigurationUnavailable()
                data = json.load(source)
            version = data.get("version") if isinstance(data, dict) else None
            if (version not in (1, CONFIG_VERSION) or
                    not isinstance(data.get("signing_key"), str) or len(data["signing_key"]) != 64 or
                    any(char not in "0123456789abcdef" for char in data["signing_key"]) or
                    not isinstance(data.get("services"), list)):
                raise ConfigurationUnavailable()
            ids = set()
            for service in data["services"]:
                # v1 had one implicit protocol: an OpenAI Images-compatible endpoint.
                if version == 1 and isinstance(service, dict):
                    service["provider"] = "custom"
                self._validate(service)
                if service["id"] in ids or service["id"] == "environment":
                    raise ConfigurationUnavailable()
                ids.add(service["id"])
            selection = data.get("default")
            if selection is not None and (not isinstance(selection, dict) or set(selection) != {"service_id", "model_id"}
                                          or not all(isinstance(value, str) for value in selection.values())):
                raise ConfigurationUnavailable()
            if version == 1:
                data["version"] = CONFIG_VERSION
            return data
        except FileNotFoundError:
            legacy = self.legacy._read_file()
            services = []
            if legacy:
                services.append({"id": "legacy", "provider": "custom", "name": "默认图像服务", "enabled": True,
                    "base_url": legacy.get("base_url", DEFAULT_BASE_URL), "api_key": legacy.get("api_key", ""),
                    "models": [default_model(legacy.get("model", DEFAULT_MODEL), editing=True, model_id="legacy-model")]})
            environment = self._environment()
            first = environment or (services[0] if services else None)
            data = {"version": CONFIG_VERSION, "signing_key": secrets.token_hex(32), "services": services,
                    "default": {"service_id": first["id"], "model_id": first["models"][0]["id"]} if first else None}
            self._write(data)
            return data
        except (OSError, ValueError, TypeError, KeyError, ServiceError):
            raise ConfigurationUnavailable() from None

    def _environment(self) -> dict[str, Any] | None:
        if not any(os.environ.get(f"IMAGENIA_OPENAI_{name}", "").strip() for name in ("API_KEY", "BASE_URL", "MODEL")):
            return None
        key, _, url, model = self.legacy.effective()
        return {"id": "environment", "provider": "custom", "name": "环境配置", "base_url": url,
                "api_key": key or "", "enabled": True,
                "models": [default_model(model, editing=True, model_id="environment-model")]}

    def _all(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        environment = self._environment()
        return ([environment] if environment else []) + document["services"]

    @staticmethod
    def _validate(service: Any) -> None:
        if (not isinstance(service, dict) or set(service) != {"id", "provider", "name", "base_url", "api_key", "enabled", "models"} or
                not isinstance(service["id"], str) or not 0 < len(service["id"]) <= 128 or
                not isinstance(service["provider"], str) or service["provider"] not in PROVIDERS or
                not isinstance(service["name"], str) or not service["name"].strip() or len(service["name"]) > 100 or
                not valid_base_url(service["base_url"]) or type(service["enabled"]) is not bool or
                not isinstance(service["api_key"], str) or (service["api_key"] and not valid_key(service["api_key"])) or
                not isinstance(service["models"], list) or not 1 <= len(service["models"]) <= 50):
            raise ServiceError("invalid_service")
        ids, names = set(), set()
        for model in service["models"]:
            if (not isinstance(model, dict) or set(model) != {"id", "name", "sizes", "qualities", "supports_edit"} or
                    not isinstance(model["id"], str) or not 0 < len(model["id"]) <= 128 or model["id"] in ids or
                    not valid_model(model["name"]) or model["name"] in names or type(model["supports_edit"]) is not bool):
                raise ServiceError("invalid_model")
            ids.add(model["id"])
            names.add(model["name"])
            for field, allowed in (("sizes", SIZES), ("qualities", QUALITIES)):
                values = model[field]
                if (not isinstance(values, list) or not values or not all(isinstance(value, str) and value in allowed for value in values)
                        or len(set(values)) != len(values)):
                    raise ServiceError("invalid_model")

    def status(self, database=None) -> dict[str, Any]:
        with self.lock:
            data = self._load()
            services = []
            for service in self._all(data):
                public = {name: copy.deepcopy(value) for name, value in service.items() if name != "api_key"}
                public.update(configured=bool(service["api_key"]), read_only=service["id"] == "environment")
                public["active_jobs"] = self._busy(database, service["id"]) if database is not None else 0
                services.append(public)
            return {"services": services, "default": data["default"],
                    "providers": copy.deepcopy(list(PROVIDER_PRESETS))}

    @staticmethod
    def _busy(database, service_id: str) -> int:
        return database.execute("SELECT COUNT(*) FROM generation_jobs WHERE service_id=? AND status IN ('pending','running')",
                                (service_id,)).fetchone()[0]

    def save(self, request: Any, database, service_id: str | None = None) -> dict[str, Any]:
        with self.lock:
            data = self._load()
            if not isinstance(request, dict) or set(request) - {"provider", "name", "base_url", "api_key", "enabled", "models"}:
                raise ServiceError("invalid_service")
            if service_id == "environment":
                raise ServiceError("read_only_service", 409)
            old = next((service for service in data["services"] if service["id"] == service_id), None)
            if service_id is not None and old is None:
                raise ServiceError("service_not_found", 404)
            if old is None and len(data["services"]) >= 50:
                raise ServiceError("service_limit", 409)
            service = copy.deepcopy(old) if old else {"id": str(uuid.uuid4()), "provider": "custom",
                                                     "enabled": True, "api_key": ""}
            service.update(request)
            # Empty key is only allowed when preserving an existing secret.
            if old and request.get("api_key") == "":
                service["api_key"] = old["api_key"]
            if isinstance(service.get("models"), list):
                service["models"] = [dict(model, id=model.get("id") or str(uuid.uuid4())) if isinstance(model, dict) else model
                                     for model in service["models"]]
            self._validate(service)
            if not old and not service["api_key"]:
                raise ServiceError("invalid_api_key")
            if old and old["id"] == "legacy" and self._busy(database, "environment"):
                if (service["api_key"] != old["api_key"] or service["base_url"] != old["base_url"] or
                        service["provider"] != old["provider"] or service["models"][0]["name"] != old["models"][0]["name"]):
                    raise ServiceError("service_in_use", 409)
            if old and self._busy(database, service["id"]):
                previous = {model["id"]: model["name"] for model in old["models"]}
                current = {model["id"]: model["name"] for model in service["models"]}
                if (service["api_key"] != old["api_key"] or service["base_url"] != old["base_url"] or
                        service["provider"] != old["provider"] or
                        any(current.get(key) != value for key, value in previous.items())):
                    raise ServiceError("service_in_use", 409)
            if old:
                data["services"][data["services"].index(old)] = service
            else:
                data["services"].append(service)
                if data["default"] is None:
                    data["default"] = {"service_id": service["id"], "model_id": service["models"][0]["id"]}
            if service["id"] == "legacy":
                # Keep the compatibility endpoint and inherited environment fields in sync.
                self.legacy.save(service["api_key"] or None, service["base_url"], service["models"][0]["name"])
            self._write(data)
            return self.status(database)

    def delete(self, service_id: str, database) -> dict[str, Any]:
        with self.lock:
            data = self._load()
            if service_id == "environment":
                raise ServiceError("read_only_service", 409)
            service = next((item for item in data["services"] if item["id"] == service_id), None)
            if service is None:
                raise ServiceError("service_not_found", 404)
            if self._busy(database, service_id) or (service_id == "legacy" and self._busy(database, "environment")):
                raise ServiceError("service_in_use", 409)
            data["services"].remove(service)
            if data["default"] and data["default"]["service_id"] == service_id:
                data["default"] = None
            self._write(data)
            # The legacy route must not retain a second, hidden copy of a deleted credential.
            if service_id == "legacy":
                try:
                    self.legacy.file.unlink(missing_ok=True)
                except OSError:
                    raise ConfigurationUnavailable() from None
            return self.status(database)

    def set_default(self, selection: Any, database) -> dict[str, Any]:
        with self.lock:
            if not isinstance(selection, dict) or set(selection) != {"service_id", "model_id"}:
                raise ServiceError("invalid_selection")
            self.select(selection["service_id"], selection["model_id"])
            data = self._load()
            data["default"] = selection
            self._write(data)
            return self.status(database)

    def select(self, service_id=None, model_id=None, *, editing=False, size=None, quality=None, submitted=False) -> dict[str, Any]:
        with self.lock:
            data = self._load()
            if service_id is None and model_id is None:
                selection = data["default"]
                if not selection:
                    raise ServiceError("not_configured", 409)
                service_id, model_id = selection["service_id"], selection["model_id"]
            if not isinstance(service_id, str) or not isinstance(model_id, str):
                raise ServiceError("invalid_selection")
            service = next((item for item in self._all(data) if item["id"] == service_id), None)
            if service is None:
                raise ServiceError("service_not_found", 409)
            model = next((item for item in service["models"] if item["id"] == model_id), None)
            if model is None:
                raise ServiceError("model_not_found", 409)
            if not submitted:
                if not service["enabled"]:
                    raise ServiceError("service_disabled", 409)
                if editing and not model["supports_edit"]:
                    raise ServiceError("edit_not_supported", 422)
                if size is not None and size not in model["sizes"] or quality is not None and quality not in model["qualities"]:
                    raise ServiceError("unsupported_options")
            if not service["api_key"]:
                raise ServiceError("not_configured", 409)
            # Keep the v1 tuple for custom services so an upgrade does not
            # invalidate already-queued jobs. Other protocols append their kind.
            connection = [service["base_url"], service["api_key"], model["name"]]
            if service["provider"] != "custom":
                connection.append(service["provider"])
            fingerprint = hmac.new(data["signing_key"].encode(),
                                   json.dumps(connection, ensure_ascii=True).encode(), hashlib.sha256).hexdigest()
            return {"service_id": service_id, "service_name": service["name"], "model_id": model_id,
                    "model": model["name"], "provider": service["provider"],
                    "base_url": service["base_url"], "api_key": service["api_key"],
                    "connection_fingerprint": fingerprint}

    def connection(self, service_id: str) -> tuple[str, str]:
        with self.lock:
            service = next((item for item in self._all(self._load()) if item["id"] == service_id), None)
            if service is None:
                raise ServiceError("service_not_found", 404)
            if not service["api_key"]:
                raise ServiceError("not_configured", 409)
            return service["api_key"], service["base_url"]

    def save_legacy(self, key, url, model, database) -> None:
        with self.lock:
            data = self._load()
            if any(self._busy(database, name) for name in ("legacy", "environment")):
                raise ServiceError("service_in_use", 409)
            self.legacy.save(key, url, model)
            values = self.legacy._read_file()
            service = next((item for item in data["services"] if item["id"] == "legacy"), None)
            if service is None:
                service = {"id": "legacy", "provider": "custom", "name": "默认图像服务",
                           "enabled": True, "api_key": "", "models": []}
                data["services"].append(service)
            service.update(api_key=values.get("api_key", ""), base_url=values.get("base_url", DEFAULT_BASE_URL),
                           models=[default_model(values.get("model", DEFAULT_MODEL), editing=True, model_id="legacy-model")])
            if data["default"] is None:
                data["default"] = {"service_id": "environment" if self._environment() else "legacy",
                                   "model_id": "environment-model" if self._environment() else "legacy-model"}
            self._write(data)
