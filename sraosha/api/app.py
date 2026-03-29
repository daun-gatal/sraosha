from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from sraosha.api.routers import compliance, contracts, drift, impact, runs

STATIC_DIR = Path(__file__).resolve().parent.parent / "static" / "dashboard"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Sraosha API",
        description="Governance runtime for data contracts",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(contracts.router, prefix="/api/v1/contracts", tags=["Contracts"])
    app.include_router(runs.router, prefix="/api/v1/runs", tags=["Runs"])
    app.include_router(drift.router, prefix="/api/v1/drift", tags=["Drift"])
    app.include_router(compliance.router, prefix="/api/v1/compliance", tags=["Compliance"])
    app.include_router(impact.router, prefix="/api/v1/impact", tags=["Impact"])

    _mount_dashboard(app)

    return app


def _mount_dashboard(app: FastAPI) -> None:
    """Serve the pre-built React dashboard as static files when available."""
    if not STATIC_DIR.is_dir():
        return

    index_html = STATIC_DIR / "index.html"
    if not index_html.is_file():
        return

    assets_dir = STATIC_DIR / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="dashboard-assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def serve_spa(path: str) -> FileResponse:
        """Catch-all: serve static files or fall back to index.html for SPA routing."""
        file = STATIC_DIR / path
        if file.is_file() and ".." not in path:
            return FileResponse(file)
        return FileResponse(index_html)
