from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from core.config import settings

SHELL_ADMIN_CAUTION = (
    "Windows only. When enabled, Serviq launches approved shell commands through "
    "a UAC administrator prompt. Only use this with specific allowed folders, not "
    "drive roots or system directories. Shell commands still require approval."
)

SHELL_RUN_AS_ADMIN_KEY = "shell_run_as_administrator"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _workspace_dir() -> Path:
    workspace = settings.workspace_path.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def _db_path() -> Path:
    return _workspace_dir() / "serviq_shell_settings.sqlite3"


async def _connect() -> aiosqlite.Connection:
    connection = await aiosqlite.connect(_db_path())
    connection.row_factory = aiosqlite.Row
    return connection


async def ensure_shell_settings_store() -> None:
    db = await _connect()
    try:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS shell_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        now = _utcnow()
        await db.execute(
            """
            INSERT INTO shell_settings(key, value, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(key) DO NOTHING
            """,
            (SHELL_RUN_AS_ADMIN_KEY, "false", now, now),
        )
        await db.commit()
    finally:
        await db.close()


async def get_shell_settings() -> dict[str, Any]:
    await ensure_shell_settings_store()
    db = await _connect()
    try:
        cursor = await db.execute(
            """
            SELECT key, value
            FROM shell_settings
            """
        )
        rows = await cursor.fetchall()
        values = {str(row["key"]): str(row["value"]) for row in rows}
        return {
            "shell_run_as_administrator": values.get(
                SHELL_RUN_AS_ADMIN_KEY,
                "false",
            ).casefold()
            == "true",
            "shell_admin_caution": SHELL_ADMIN_CAUTION,
        }
    finally:
        await db.close()


async def set_shell_settings(
    *,
    shell_run_as_administrator: bool | None = None,
) -> dict[str, Any]:
    await ensure_shell_settings_store()

    if shell_run_as_administrator is not None:
        now = _utcnow()
        db = await _connect()
        try:
            await db.execute(
                """
                INSERT INTO shell_settings(key, value, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (
                    SHELL_RUN_AS_ADMIN_KEY,
                    "true" if shell_run_as_administrator else "false",
                    now,
                    now,
                ),
            )
            await db.commit()
        finally:
            await db.close()

    return await get_shell_settings()
