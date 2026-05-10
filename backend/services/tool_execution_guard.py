from __future__ import annotations

from typing import Any

from services.tool_settings_store import ToolDisabledError, normalize_tool_id, require_tool_enabled


async def ensure_tool_enabled(tool_name: str) -> None:
    """
    Runtime gate for every tool execution.

    This must be called before:
    - creating an approval request
    - executing a tool directly
    - executing an approved tool after approval

    If the tool is disabled in Settings -> Tools, this raises ToolDisabledError.
    """
    await require_tool_enabled(tool_name)


def disabled_tool_result(tool_name: str, error: Exception | str | None = None) -> dict[str, Any]:
    normalized_tool_name = normalize_tool_id(tool_name)
    message = (
        str(error)
        if error
        else f"The tool '{normalized_tool_name}' is disabled in Serviq Tools settings."
    )

    return {
        "name": normalized_tool_name,
        "ok": False,
        "disabled": True,
        "approval_required": False,
        "risk": "disabled",
        "output": None,
        "error": message,
        "metadata": {
            "blocked_by": "serviq-tool-settings",
            "tool_name": normalized_tool_name,
        },
    }


async def ensure_tool_enabled_or_result(tool_name: str) -> dict[str, Any] | None:
    """
    Returns None when the tool is enabled.
    Returns a standard failed tool_result dict when disabled.

    Use this in tool executors that return dict-style tool results.
    """
    try:
        await ensure_tool_enabled(tool_name)
        return None
    except ToolDisabledError as error:
        return disabled_tool_result(tool_name, error)
