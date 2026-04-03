from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from sraosha.api.routers import (
    alerting_profiles,
    compliance,
    contracts,
    dashboard,
    data_quality,
    impact,
    runs,
    schedules,
    teams,
)


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

    app.include_router(teams.router, prefix="/api/v1/teams", tags=["Teams"])
    app.include_router(
        alerting_profiles.router, prefix="/api/v1/alerting-profiles", tags=["Alerting profiles"]
    )
    app.include_router(contracts.router, prefix="/api/v1/contracts", tags=["Contracts"])
    app.include_router(runs.router, prefix="/api/v1/runs", tags=["Runs"])
    app.include_router(compliance.router, prefix="/api/v1/compliance", tags=["Compliance"])
    app.include_router(impact.router, prefix="/api/v1/impact", tags=["Impact"])
    app.include_router(schedules.router, prefix="/api/v1/schedules", tags=["Schedules"])
    app.include_router(
        data_quality.router, prefix="/api/v1/data-quality", tags=["Data Quality"]
    )
    app.include_router(dashboard.router, prefix="/ui", tags=["Dashboard"])

    @app.get("/", include_in_schema=False)
    async def root_redirect():
        return RedirectResponse(url="/ui/")

    return app
