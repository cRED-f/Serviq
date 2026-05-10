from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite


DEFAULT_ANSWER_STYLE = "concise"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _workspace_dir() -> Path:
    workspace = Path(os.getenv("WORKSPACE_DIR", "./workspace"))

    if not workspace.is_absolute():
        workspace = _project_root() / str(workspace).lstrip("./\\")

    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def _db_path() -> Path:
    return _workspace_dir() / "serviq_runtime_settings.sqlite3"


async def _connect() -> aiosqlite.Connection:
    connection = await aiosqlite.connect(_db_path())
    connection.row_factory = aiosqlite.Row
    return connection


async def ensure_runtime_settings_store() -> None:
    db = await _connect()
    try:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS runtime_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        now = _utcnow()
        default_embedding_model = os.getenv("LM_STUDIO_DEFAULT_EMBEDDING_MODEL", "").strip()

        defaults = {
            "selected_embedding_model": default_embedding_model,
            "answer_style": DEFAULT_ANSWER_STYLE,
        }

        for key, value in defaults.items():
            await db.execute(
                """
                INSERT INTO runtime_settings(key, value, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO NOTHING
                """,
                (key, value, now, now),
            )

        await db.commit()
    finally:
        await db.close()


async def get_runtime_settings() -> dict[str, Any]:
    await ensure_runtime_settings_store()

    db = await _connect()
    try:
        cursor = await db.execute(
            """
            SELECT key, value
            FROM runtime_settings
            """
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()

    values = {row["key"]: row["value"] for row in rows}

    return {
        "selected_embedding_model": values.get("selected_embedding_model", ""),
        "answer_style": values.get("answer_style", DEFAULT_ANSWER_STYLE),
    }


async def set_runtime_setting(key: str, value: str) -> dict[str, Any]:
    allowed_keys = {
        "selected_embedding_model",
        "answer_style",
    }

    if key not in allowed_keys:
        raise KeyError(f"Unknown runtime setting: {key}")

    clean_value = value.strip()

    if key == "answer_style" and clean_value not in {"concise", "normal"}:
        raise ValueError("answer_style must be 'concise' or 'normal'.")

    await ensure_runtime_settings_store()

    now = _utcnow()
    db = await _connect()
    try:
        await db.execute(
            """
            INSERT INTO runtime_settings(key, value, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, clean_value, now, now),
        )
        await db.commit()
    finally:
        await db.close()

    return await get_runtime_settings()


async def set_runtime_settings(
    *,
    selected_embedding_model: str | None = None,
    answer_style: str | None = None,
) -> dict[str, Any]:
    settings = await get_runtime_settings()

    if selected_embedding_model is not None:
        settings = await set_runtime_setting("selected_embedding_model", selected_embedding_model)

    if answer_style is not None:
        settings = await set_runtime_setting("answer_style", answer_style)

    return settings


async def get_selected_embedding_model() -> str:
    settings = await get_runtime_settings()
    return str(settings.get("selected_embedding_model") or "").strip()


async def get_answer_style_instruction() -> str:
    settings = await get_runtime_settings()
    answer_style = str(settings.get("answer_style") or DEFAULT_ANSWER_STYLE).strip()

    if answer_style != "concise":
        return ""

    return (
        "Answer briefly and directly. "
        "Do not add extra summary, extra sections, long explanations, or follow-up offers unless the user asks. "
        "Use the minimum words needed to solve the request."
    )
