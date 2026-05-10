from __future__ import annotations

import traceback

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _is_development() -> bool:
    return settings.app_env.lower() in {"dev", "development", "local"}


def register_exception_handlers(app: FastAPI) -> None:
    """Register stable JSON error handlers for the Serviq backend."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        logger.warning(
            "http_exception",
            status_code=exc.status_code,
            path=request.url.path,
            request_id=_request_id(request),
            detail=str(exc.detail),
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "type": "http_error",
                    "message": exc.detail,
                    "status_code": exc.status_code,
                    "request_id": _request_id(request),
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        logger.warning(
            "request_validation_error",
            path=request.url.path,
            request_id=_request_id(request),
            errors=exc.errors(),
        )

        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "type": "validation_error",
                    "message": "Request validation failed.",
                    "status_code": 422,
                    "request_id": _request_id(request),
                    "details": exc.errors(),
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        error_type = type(exc).__name__
        error_message = str(exc) or repr(exc)

        logger.exception(
            "unhandled_exception",
            path=request.url.path,
            request_id=_request_id(request),
            error_type=error_type,
            error=error_message,
        )

        payload = {
            "error": {
                "type": "internal_server_error",
                "message": "Internal server error.",
                "status_code": 500,
                "request_id": _request_id(request),
            }
        }

        if _is_development():
            payload["error"]["message"] = f"{error_type}: {error_message}"
            payload["error"]["traceback"] = traceback.format_exception(
                type(exc),
                exc,
                exc.__traceback__,
            )

        return JSONResponse(status_code=500, content=payload)


def register_error_handlers(app: FastAPI) -> None:
    """Backward-compatible alias."""
    register_exception_handlers(app)
