from __future__ import annotations

import time
from uuid import uuid4

from fastapi import FastAPI, Request, Response

from core.logging import get_logger

logger = get_logger(__name__)


def register_middlewares(app: FastAPI) -> None:
    """Register lightweight production middleware for request IDs and timing."""

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        request_id = request.headers.get("x-request-id", str(uuid4()))
        request.state.request_id = request_id

        started_at = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        response.headers["x-request-id"] = request_id

        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id,
        )

        return response


# Backward-compatible alias in case older modules use a different name.
def register_middleware(app: FastAPI) -> None:
    register_middlewares(app)
