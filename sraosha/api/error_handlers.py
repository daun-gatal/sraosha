"""Consistent JSON error bodies for API and SPA clients."""

from __future__ import annotations

from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def _cors_origins_list(raw: str) -> list[str]:
    s = (raw or "").strip()
    if not s or s == "*":
        return ["*"]
    return [o.strip() for o in s.split(",") if o.strip()]


def add_exception_handlers(app: Any) -> None:
    """Register handlers (call from ``create_app`` after app is created)."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        body: dict[str, Any] = {
            "detail": exc.detail,
            "status_code": exc.status_code,
        }
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": exc.errors(),
                "status_code": 422,
                "error": "validation_error",
            },
        )


def cors_allow_origins(settings_cors: str) -> list[str]:
    """Parse ``CORS_ALLOWED_ORIGINS`` for CORSMiddleware."""
    return _cors_origins_list(settings_cors)
