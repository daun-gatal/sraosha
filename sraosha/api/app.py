from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from sraosha.api.error_handlers import add_exception_handlers, cors_allow_origins
from sraosha.api.routers import (
    alerting_profiles,
    connections,
    contracts,
    data_quality,
    runs,
    schedules,
    teams,
)
from sraosha.api.spa import mount_spa
from sraosha.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="Sraosha API",
        description="Governance runtime for data contracts",
        version="0.2.1",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    add_exception_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_allow_origins(settings.CORS_ALLOWED_ORIGINS),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(teams.router, prefix="/api/v1/teams", tags=["Teams"])
    app.include_router(
        alerting_profiles.router, prefix="/api/v1/alerting-profiles", tags=["Alerting profiles"]
    )
    app.include_router(connections.router, prefix="/api/v1/connections", tags=["Connections"])
    app.include_router(contracts.router, prefix="/api/v1/contracts", tags=["Contracts"])
    app.include_router(runs.router, prefix="/api/v1/runs", tags=["Runs"])
    app.include_router(schedules.router, prefix="/api/v1/schedules", tags=["Schedules"])
    app.include_router(data_quality.router, prefix="/api/v1/data-quality", tags=["Data Quality"])

    spa_dist = mount_spa(app)

    @app.get("/", include_in_schema=False)
    async def root_redirect():
        if spa_dist is not None:
            return RedirectResponse(url="/app/")
        return RedirectResponse(url="/docs")

    return app
