"""Optional FastAPI adapter used only when loaded inside QwenPaw."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .app import ImageniaApp


def build_router(app: ImageniaApp) -> APIRouter:
    """Expose the dependency-free contract through QwenPaw's APIRouter hook."""
    router = APIRouter()

    @router.api_route("/health", methods=["GET"])
    async def health() -> JSONResponse:
        status, payload = app.handle("GET", "/api/imagenia/health")
        return JSONResponse(payload, status_code=status)

    @router.api_route("/settings", methods=["GET"])
    async def settings() -> JSONResponse:
        status, payload = app.handle("GET", "/api/imagenia/settings")
        return JSONResponse(payload, status_code=status)

    @router.api_route("/settings/openai", methods=["PUT"])
    async def save_settings(request: Request) -> JSONResponse:
        status, payload = app.handle("PUT", "/api/imagenia/settings/openai", await request.body())
        return JSONResponse(payload, status_code=status)

    @router.api_route("/settings/openai/test", methods=["POST"])
    async def test_connection() -> JSONResponse:
        status, payload = await app.test_connection()
        return JSONResponse(payload, status_code=status)

    @router.api_route("/assets", methods=["GET"])
    async def assets() -> JSONResponse:
        status, payload = app.handle("GET", "/api/imagenia/assets")
        return JSONResponse(payload, status_code=status)

    @router.api_route("/jobs/generate", methods=["POST"])
    async def generate(request: Request) -> JSONResponse:
        return await _job_response(app, request, "/api/imagenia/jobs/generate")

    @router.api_route("/jobs/edit", methods=["POST"])
    async def edit(request: Request) -> JSONResponse:
        return await _job_response(app, request, "/api/imagenia/jobs/edit")

    return router


async def _job_response(app: ImageniaApp, request: Request, path: str) -> JSONResponse:
    body = await request.body()
    status, payload = app.handle("POST", path, body)
    return JSONResponse(payload, status_code=status)
