from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from core.config import settings
from db.session import AsyncSessionLocal

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check() -> dict:
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/")
async def health_check_slash() -> dict:
    return await health_check()


@router.get("/deep")
async def deep_health_check() -> dict:
    database_status = "ok"

    try:
        async with AsyncSessionLocal() as _session:
            pass
    except Exception as exc:  # noqa: BLE001 - health endpoint should report, not crash.
        database_status = f"error: {exc}"

    return {
        "status": "ok" if database_status == "ok" else "degraded",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "checks": {
            "database": database_status,
            "workspace": str(settings.workspace_path),
            "qdrant_url": settings.qdrant_url,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
