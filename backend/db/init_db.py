from core.logging import get_logger
from db.base import Base
from db.session import engine

# Import models so SQLAlchemy registers metadata.
from db import models as _models  # noqa: F401

logger = get_logger(__name__)


async def init_database() -> None:
    """Create local SQLite tables for development/local desktop usage.

    Alembic migrations remain part of the final stack, but create_all gives the
    desktop app a reliable first-run local bootstrap.
    """

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database_ready")


async def close_database() -> None:
    await engine.dispose()
    logger.info("database_closed")
