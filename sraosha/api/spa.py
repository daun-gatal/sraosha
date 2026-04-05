"""Serve the built React SPA from ``frontend/dist`` when present."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_spa(app: FastAPI) -> Path | None:
    """Mount ``/app`` static assets and HTML shell. Returns dist path if mounted."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    dist = repo_root / "frontend" / "dist"
    index = dist / "index.html"
    assets_dir = dist / "assets"
    if not index.is_file():
        return None

    if assets_dir.is_dir():
        app.mount(
            "/app/assets",
            StaticFiles(directory=assets_dir),
            name="spa-assets",
        )

    @app.get("/app", include_in_schema=False)
    async def spa_app_no_slash():
        return FileResponse(index)

    @app.get("/app/", include_in_schema=False)
    async def spa_app_index():
        return FileResponse(index)

    @app.get("/app/{full_path:path}", include_in_schema=False)
    async def spa_client_routes(full_path: str):
        # /app/assets/* is served by StaticFiles; all other /app/* paths get the SPA shell.
        _ = full_path
        return FileResponse(index)

    return dist
