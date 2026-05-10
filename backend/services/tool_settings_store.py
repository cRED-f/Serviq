from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite


class ToolDisabledError(RuntimeError):
    """Raised when the agent tries to use a disabled tool."""


DEFAULT_TOOL_CATALOG: list[dict[str, Any]] = [
    {
        "id": "list_workspace_files",
        "name": "List files",
        "description": "Browse files and folders inside the Serviq workspace.",
        "icon": "folder",
        "risk": "low",
        "enabled_by_default": True,
    },
    {
        "id": "read_workspace_file",
        "name": "Read file",
        "description": "Read text files from the workspace so Serviq can inspect code or notes.",
        "icon": "file-text",
        "risk": "low",
        "enabled_by_default": True,
    },
    {
        "id": "write_workspace_file",
        "name": "Write file",
        "description": "Create new files inside the workspace.",
        "icon": "file-plus",
        "risk": "medium",
        "enabled_by_default": True,
    },
    {
        "id": "edit_workspace_file",
        "name": "Edit file",
        "description": "Modify existing workspace files.",
        "icon": "edit",
        "risk": "medium",
        "enabled_by_default": True,
    },
    {
        "id": "search_workspace",
        "name": "Search workspace",
        "description": "Search project files and notes for useful context.",
        "icon": "search",
        "risk": "low",
        "enabled_by_default": True,
    },
    {
        "id": "run_shell_command",
        "name": "Shell command",
        "description": "Run approved shell commands inside the Serviq sandbox.",
        "icon": "terminal",
        "risk": "high",
        "enabled_by_default": True,
    },
    {
        "id": "get_system_info",
        "name": "System info",
        "description": "Check local runtime status, paths, and environment information.",
        "icon": "cpu",
        "risk": "low",
        "enabled_by_default": True,
    },
    {
        "id": "semantic_memory_search",
        "name": "Memory recall",
        "description": "Search saved semantic memory when it helps answer a question.",
        "icon": "memory",
        "risk": "low",
        "enabled_by_default": True,
    },
    {
        "id": "save_semantic_memory",
        "name": "Memory save",
        "description": "Save important long-term memories when Serviq decides they are useful.",
        "icon": "database",
        "risk": "medium",
        "enabled_by_default": True,
    },
]


TOOL_ALIASES: dict[str, str] = {
    "list_files": "list_workspace_files",
    "list_directory": "list_workspace_files",
    "read_file": "read_workspace_file",
    "write_file": "write_workspace_file",
    "edit_file": "edit_workspace_file",
    "search_files": "search_workspace",
    "shell": "run_shell_command",
    "run_command": "run_shell_command",
    "system_info": "get_system_info",
    "retrieve_memory": "semantic_memory_search",
    "recall_memory": "semantic_memory_search",
    "save_memory": "save_semantic_memory",
}


def normalize_tool_id(tool_id: str) -> str:
    clean = tool_id.strip()
    return TOOL_ALIASES.get(clean, clean)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project_root() -> Path:
    # backend/services/tool_settings_store.py -> project root
    return Path(__file__).resolve().parents[2]


def _workspace_dir() -> Path:
    workspace = Path(os.getenv("WORKSPACE_DIR", "./workspace"))

    if not workspace.is_absolute():
        workspace = _project_root() / str(workspace).lstrip("./\\")

    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def _db_path() -> Path:
    return _workspace_dir() / "serviq_tool_settings.sqlite3"


async def _connect() -> aiosqlite.Connection:
    connection = await aiosqlite.connect(_db_path())
    connection.row_factory = aiosqlite.Row
    return connection


async def ensure_tool_settings_store() -> None:
    db = await _connect()
    try:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS tool_settings (
                tool_id TEXT PRIMARY KEY,
                enabled INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        now = _utcnow()

        for tool in DEFAULT_TOOL_CATALOG:
            await db.execute(
                """
                INSERT INTO tool_settings(tool_id, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(tool_id) DO NOTHING
                """,
                (
                    tool["id"],
                    1 if tool.get("enabled_by_default", True) else 0,
                    now,
                    now,
                ),
            )

        await db.commit()
    finally:
        await db.close()


async def list_tool_settings() -> list[dict[str, Any]]:
    await ensure_tool_settings_store()

    db = await _connect()
    try:
        cursor = await db.execute(
            """
            SELECT tool_id, enabled, created_at, updated_at
            FROM tool_settings
            """
        )
        rows = await cursor.fetchall()
        states = {row["tool_id"]: dict(row) for row in rows}

        tools: list[dict[str, Any]] = []

        for tool in DEFAULT_TOOL_CATALOG:
            state = states.get(tool["id"])
            tools.append(
                {
                    "id": tool["id"],
                    "name": tool["name"],
                    "description": tool["description"],
                    "icon": tool["icon"],
                    "risk": tool["risk"],
                    "enabled": bool(state["enabled"]) if state else bool(tool.get("enabled_by_default", True)),
                    "created_at": state["created_at"] if state else None,
                    "updated_at": state["updated_at"] if state else None,
                }
            )

        return tools
    finally:
        await db.close()


async def get_tool_setting(tool_id: str) -> dict[str, Any] | None:
    normalized_tool_id = normalize_tool_id(tool_id)
    tools = await list_tool_settings()

    for tool in tools:
        if tool["id"] == normalized_tool_id:
            return tool

    return None


async def is_tool_enabled(tool_id: str) -> bool:
    tool = await get_tool_setting(tool_id)

    # Unknown tools default to disabled for safety.
    if tool is None:
        return False

    return bool(tool["enabled"])


async def set_tool_enabled(tool_id: str, enabled: bool) -> dict[str, Any]:
    await ensure_tool_settings_store()

    normalized_tool_id = normalize_tool_id(tool_id)
    catalog_ids = {tool["id"] for tool in DEFAULT_TOOL_CATALOG}

    if normalized_tool_id not in catalog_ids:
        raise KeyError(f"Unknown tool: {tool_id}")

    now = _utcnow()

    db = await _connect()
    try:
        await db.execute(
            """
            INSERT INTO tool_settings(tool_id, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(tool_id) DO UPDATE SET
                enabled = excluded.enabled,
                updated_at = excluded.updated_at
            """,
            (normalized_tool_id, 1 if enabled else 0, now, now),
        )
        await db.commit()
    finally:
        await db.close()

    tool = await get_tool_setting(normalized_tool_id)

    if tool is None:
        raise RuntimeError(f"Failed to load tool setting after update: {normalized_tool_id}")

    return tool


async def require_tool_enabled(tool_id: str) -> None:
    normalized_tool_id = normalize_tool_id(tool_id)

    if await is_tool_enabled(normalized_tool_id):
        return

    raise ToolDisabledError(
        f"The tool '{normalized_tool_id}' is disabled in Serviq Tools settings."
    )


async def get_enabled_tool_ids() -> list[str]:
    tools = await list_tool_settings()
    return [tool["id"] for tool in tools if tool["enabled"]]


async def get_disabled_tool_ids() -> list[str]:
    tools = await list_tool_settings()
    return [tool["id"] for tool in tools if not tool["enabled"]]
