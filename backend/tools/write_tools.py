from __future__ import annotations

from pathlib import Path
from typing import Any

from core.config import settings
from tools.base import ToolDefinition, ToolExecutionContext, ToolResult, ToolRisk


def _resolve_workspace_path(relative_path: str | None) -> Path:
    workspace = settings.workspace_path.resolve()
    candidate = (workspace / (relative_path or "")).resolve()

    if not candidate.is_relative_to(workspace):
        raise ValueError("Path is outside the Serviq workspace.")

    return candidate


def _is_reasonable_text_file(path: Path) -> bool:
    blocked_suffixes = {
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".bin",
        ".zip",
        ".7z",
        ".rar",
        ".tar",
        ".gz",
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".gif",
        ".ico",
        ".pdf",
    }

    return path.suffix.lower() not in blocked_suffixes


async def write_workspace_file_tool(args: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
    relative_path = str(args.get("relative_path", "")).strip()
    content = str(args.get("content", ""))
    overwrite = bool(args.get("overwrite", False))

    if not relative_path:
        return ToolResult(
            name="write_workspace_file",
            ok=False,
            risk=ToolRisk.MEDIUM,
            error="Missing relative_path.",
        )

    try:
        file_path = _resolve_workspace_path(relative_path)

        if not _is_reasonable_text_file(file_path):
            return ToolResult(
                name="write_workspace_file",
                ok=False,
                risk=ToolRisk.MEDIUM,
                error=f"Refusing to write unsupported/binary file type: {file_path.suffix}",
            )

        if file_path.exists() and not overwrite:
            return ToolResult(
                name="write_workspace_file",
                ok=False,
                risk=ToolRisk.MEDIUM,
                error="File already exists. Set overwrite=true to replace it.",
            )

        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

        return ToolResult(
            name="write_workspace_file",
            ok=True,
            risk=ToolRisk.MEDIUM,
            output={
                "relative_path": str(file_path.relative_to(settings.workspace_path.resolve())),
                "bytes_written": len(content.encode("utf-8")),
                "overwritten": overwrite,
            },
        )
    except Exception as exc:  # noqa: BLE001
        return ToolResult(
            name="write_workspace_file",
            ok=False,
            risk=ToolRisk.MEDIUM,
            error=str(exc),
        )


async def append_workspace_file_tool(args: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
    relative_path = str(args.get("relative_path", "")).strip()
    content = str(args.get("content", ""))

    if not relative_path:
        return ToolResult(
            name="append_workspace_file",
            ok=False,
            risk=ToolRisk.MEDIUM,
            error="Missing relative_path.",
        )

    try:
        file_path = _resolve_workspace_path(relative_path)

        if not _is_reasonable_text_file(file_path):
            return ToolResult(
                name="append_workspace_file",
                ok=False,
                risk=ToolRisk.MEDIUM,
                error=f"Refusing to write unsupported/binary file type: {file_path.suffix}",
            )

        file_path.parent.mkdir(parents=True, exist_ok=True)

        with file_path.open("a", encoding="utf-8") as handle:
            handle.write(content)

        return ToolResult(
            name="append_workspace_file",
            ok=True,
            risk=ToolRisk.MEDIUM,
            output={
                "relative_path": str(file_path.relative_to(settings.workspace_path.resolve())),
                "bytes_appended": len(content.encode("utf-8")),
            },
        )
    except Exception as exc:  # noqa: BLE001
        return ToolResult(
            name="append_workspace_file",
            ok=False,
            risk=ToolRisk.MEDIUM,
            error=str(exc),
        )


WRITE_TOOL_DEFINITIONS = [
    ToolDefinition(
        name="write_workspace_file",
        description="Write a UTF-8 text file inside the Serviq workspace. Requires approval.",
        risk=ToolRisk.MEDIUM,
        parameters={
            "type": "object",
            "properties": {
                "relative_path": {"type": "string"},
                "content": {"type": "string"},
                "overwrite": {"type": "boolean", "default": False},
            },
            "required": ["relative_path", "content"],
        },
        handler=write_workspace_file_tool,
    ),
    ToolDefinition(
        name="append_workspace_file",
        description="Append UTF-8 text to a file inside the Serviq workspace. Requires approval.",
        risk=ToolRisk.MEDIUM,
        parameters={
            "type": "object",
            "properties": {
                "relative_path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["relative_path", "content"],
        },
        handler=append_workspace_file_tool,
    ),
]
