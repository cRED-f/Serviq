from fastapi import APIRouter

from core.config import settings
from schemas.common import ApiResponse
from schemas.system import SystemInfo

router = APIRouter()


@router.get("/info", response_model=ApiResponse[SystemInfo])
async def system_info() -> ApiResponse[SystemInfo]:
    return ApiResponse(
        data=SystemInfo(
            app_name=settings.app_name,
            app_env=settings.app_env,
            backend_status="running",
            process="backend-core",
            workspace_dir=str(settings.workspace_path),
            lm_studio_base_url=settings.lm_studio_base_url,
            qdrant_url=settings.qdrant_url,
        )
    )
