from pathlib import Path

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


REQUIRED_DIRS: tuple[Path, ...] = (
    settings.workspace_path,
    settings.uploads_path,
    settings.generated_path,
    settings.project_root / "backend" / "logs",
)


def ensure_runtime_directories() -> None:
    for directory in REQUIRED_DIRS:
        directory.mkdir(parents=True, exist_ok=True)
    logger.info("runtime_directories_ready", count=len(REQUIRED_DIRS))
