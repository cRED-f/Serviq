from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.router import api_router
from core.config import settings
from core.errors import register_exception_handlers
from core.logging import configure_logging, get_logger
from core.middleware import register_middlewares
from db.init_db import init_database
from services.startup import ensure_runtime_directories

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    ensure_runtime_directories()
    await init_database()
    logger.info("serviq_backend_started", env=settings.app_env)
    yield
    logger.info("serviq_backend_stopped")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_middlewares(app)
register_exception_handlers(app)

# Canonical API mount.
app.include_router(api_router, prefix="/api")


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "api": "/api",
    }
