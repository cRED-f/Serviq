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
        "id": "calculate",
        "name": "Calculator",
        "description": "Safely evaluate arithmetic expressions.",
        "icon": "calculator",
        "risk": "safe",
        "enabled_by_default": True,
    },
    {
        "id": "list_workspace_files",
        "name": "List files",
        "description": "Browse files and folders inside allowed Serviq directories.",
        "icon": "folder",
        "risk": "low",
        "enabled_by_default": True,
    },
    {
        "id": "read_workspace_file",
        "name": "Read file",
        "description": "Read text files from the workspace or allowed custom directories.",
        "icon": "file-text",
        "risk": "low",
        "enabled_by_default": True,
    },
    {
        "id": "write_workspace_file",
        "name": "Write file",
        "description": "Create or replace files inside allowed Serviq directories.",
        "icon": "file-plus",
        "risk": "medium",
        "enabled_by_default": True,
    },
    {
        "id": "append_workspace_file",
        "name": "Append file",
        "description": "Append text to files inside allowed Serviq directories.",
        "icon": "edit",
        "risk": "medium",
        "enabled_by_default": True,
    },
    {
        "id": "rename_workspace_file",
        "name": "Rename file",
        "description": "Rename one file inside an allowed Serviq directory after approval.",
        "icon": "edit",
        "risk": "high",
        "enabled_by_default": True,
    },
    {
        "id": "run_shell_command",
        "name": "Shell command",
        "description": "Run approved shell commands inside allowed Serviq directories.",
        "icon": "terminal",
        "risk": "high",
        "enabled_by_default": True,
    },
    {
        "id": "search_memory",
        "name": "Memory recall",
        "description": "Search saved semantic memory when it helps answer a question.",
        "icon": "memory",
        "risk": "low",
        "enabled_by_default": True,
    },
    {
        "id": "save_note",
        "name": "Memory save",
        "description": "Save useful notes to Serviq memory.",
        "icon": "database",
        "risk": "medium",
        "enabled_by_default": True,
    },
    {
        "id": "web_search",
        "name": "Web search",
        "description": "Search the web using DuckDuckGo to find current information.",
        "icon": "search",
        "risk": "medium",
        "enabled_by_default": True,
    },
    {
        "id": "web_fetch",
        "name": "Web fetch",
        "description": "Fetch and extract content from a webpage.",
        "icon": "globe",
        "risk": "medium",
        "enabled_by_default": True,
    },
]

TOOL_ALIASES: dict[str, str] = {
    "list_files": "list_workspace_files",
    "list_directory": "list_workspace_files",
    "read_file": "read_workspace_file",
    "write_file": "write_workspace_file",
    "edit_file": "write_workspace_file",
    "edit_workspace_file": "write_workspace_file",
    "append_file": "append_workspace_file",
    "rename_file": "rename_workspace_file",
    "rename_workspace": "rename_workspace_file",
    "move_file": "rename_workspace_file",
    "change_filename": "rename_workspace_file",
    "change_file_name": "rename_workspace_file",
    "search_files": "list_workspace_files",
    "search_workspace": "list_workspace_files",
    "shell": "run_shell_command",
    "run_command": "run_shell_command",
    "system_info": "run_shell_command",
    "get_system_info": "run_shell_command",
    "retrieve_memory": "search_memory",
    "recall_memory": "search_memory",
    "semantic_memory_search": "search_memory",
    "save_memory": "save_note",
    "save_semantic_memory": "save_note",
}

ICON_BY_TOOL_ID: dict[str, str] = {
    "calculate": "calculator",
    "list_workspace_files": "folder",
    "read_workspace_file": "file-text",
    "write_workspace_file": "file-plus",
    "append_workspace_file": "edit",
    "rename_workspace_file": "edit",
    "run_shell_command": "terminal",
    "search_memory": "memory",
    "save_note": "database",
}

DISPLAY_NAME_BY_TOOL_ID: dict[str, str] = {
    "calculate": "Calculator",
    "list_workspace_files": "List files",
    "read_workspace_file": "Read file",
    "write_workspace_file": "Write file",
    "append_workspace_file": "Append file",
    "rename_workspace_file": "Rename file",
    "run_shell_command": "Shell command",
    "search_memory": "Memory recall",
    "save_note": "Memory save",
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


def _humanize_tool_id(tool_id: str) -> str:
    words = tool_id.replace("_workspace", "").replace("_", " ").strip()
    return words.capitalize() if words else tool_id


def _risk_value(raw_risk: Any) -> str:
    value = getattr(raw_risk, "value", raw_risk)
    return str(value or "medium")


def _catalog_from_registered_tools() -> list[dict[str, Any]]:
    """Build catalog entries from the actual registered tool definitions.

    The Tools settings UI reads this store, not ToolRegistry directly. Keeping this
    lightweight discovery here prevents future bugs where a new registered tool
    works internally but does not show in the tool options page.
    """

    try:
        from tools.safe_tools import SAFE_TOOL_DEFINITIONS
        from tools.shell_tools import SHELL_TOOL_DEFINITIONS
        from tools.write_tools import WRITE_TOOL_DEFINITIONS
    except Exception:
        # If imports fail during startup or tests, keep the static catalog usable.
        return []

    entries: list[dict[str, Any]] = []
    for definition in [
        *SAFE_TOOL_DEFINITIONS,
        *WRITE_TOOL_DEFINITIONS,
        *SHELL_TOOL_DEFINITIONS,
    ]:
        tool_id = str(definition.name)
        entries.append(
            {
                "id": tool_id,
                "name": DISPLAY_NAME_BY_TOOL_ID.get(tool_id, _humanize_tool_id(tool_id)),
                "description": str(definition.description or "Serviq tool."),
                "icon": ICON_BY_TOOL_ID.get(tool_id, "database"),
                "risk": _risk_value(definition.risk),
                "enabled_by_default": bool(getattr(definition, "enabled", True)),
            }
        )
    return entries


def _tool_catalog() -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}

    for tool in DEFAULT_TOOL_CATALOG:
        merged[normalize_tool_id(tool["id"])] = {
            **tool,
            "id": normalize_tool_id(tool["id"]),
        }

    for tool in _catalog_from_registered_tools():
        tool_id = normalize_tool_id(tool["id"])
        current = merged.get(tool_id)
        if current:
            # Keep the nicer static display fields, but always refresh risk/default
            # from the actual registered definition.
            current["risk"] = tool.get("risk", current.get("risk", "medium"))
            current["enabled_by_default"] = tool.get(
                "enabled_by_default",
                current.get("enabled_by_default", True),
            )
        else:
            merged[tool_id] = {**tool, "id": tool_id}

    return list(merged.values())


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
        for tool in _tool_catalog():
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
        for tool in _tool_catalog():
            state = states.get(tool["id"])
            tools.append(
                {
                    "id": tool["id"],
                    "name": tool["name"],
                    "description": tool["description"],
                    "icon": tool["icon"],
                    "risk": tool["risk"],
                    "enabled": bool(state["enabled"])
                    if state
                    else bool(tool.get("enabled_by_default", True)),
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
    catalog_ids = {tool["id"] for tool in _tool_catalog()}
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
