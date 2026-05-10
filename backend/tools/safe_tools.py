from __future__ import annotations

import ast
import operator
from pathlib import Path
from typing import Any

from core.config import settings
from tools.base import ToolDefinition, ToolExecutionContext, ToolResult, ToolRisk


_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_calculate_node(node: ast.AST) -> float | int:
    if isinstance(node, ast.Expression):
        return _safe_calculate_node(node.body)

    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return node.value

    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPERATORS:
        left = _safe_calculate_node(node.left)
        right = _safe_calculate_node(node.right)
        return _ALLOWED_OPERATORS[type(node.op)](left, right)

    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPERATORS:
        operand = _safe_calculate_node(node.operand)
        return _ALLOWED_OPERATORS[type(node.op)](operand)

    raise ValueError("Expression contains unsupported syntax.")


def _resolve_workspace_path(relative_path: str | None) -> Path:
    workspace = settings.workspace_path.resolve()
    candidate = (workspace / (relative_path or ".")).resolve()

    if not candidate.is_relative_to(workspace):
        raise ValueError("Path is outside the Serviq workspace.")

    return candidate


async def calculate_tool(args: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
    expression = str(args.get("expression", "")).strip()

    if not expression:
        return ToolResult(
            name="calculate",
            ok=False,
            risk=ToolRisk.SAFE,
            error="Missing expression.",
        )

    try:
        parsed = ast.parse(expression, mode="eval")
        result = _safe_calculate_node(parsed)

        return ToolResult(
            name="calculate",
            ok=True,
            risk=ToolRisk.SAFE,
            output={
                "expression": expression,
                "result": result,
            },
        )
    except Exception as exc:  # noqa: BLE001
        return ToolResult(
            name="calculate",
            ok=False,
            risk=ToolRisk.SAFE,
            error=str(exc),
        )


async def list_workspace_files_tool(args: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
    relative_path = str(args.get("relative_path", ".")).strip() or "."

    try:
        directory = _resolve_workspace_path(relative_path)

        if not directory.exists():
            return ToolResult(
                name="list_workspace_files",
                ok=False,
                risk=ToolRisk.LOW,
                error=f"Path does not exist: {relative_path}",
            )

        if not directory.is_dir():
            return ToolResult(
                name="list_workspace_files",
                ok=False,
                risk=ToolRisk.LOW,
                error=f"Path is not a directory: {relative_path}",
            )

        entries = []
        for item in sorted(directory.iterdir(), key=lambda path: (not path.is_dir(), path.name.lower())):
            entries.append(
                {
                    "name": item.name,
                    "relative_path": str(item.relative_to(settings.workspace_path.resolve())),
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else None,
                }
            )

        return ToolResult(
            name="list_workspace_files",
            ok=True,
            risk=ToolRisk.LOW,
            output={
                "relative_path": relative_path,
                "entries": entries,
            },
        )
    except Exception as exc:  # noqa: BLE001
        return ToolResult(
            name="list_workspace_files",
            ok=False,
            risk=ToolRisk.LOW,
            error=str(exc),
        )


async def read_workspace_file_tool(args: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
    relative_path = str(args.get("relative_path", "")).strip()
    max_chars = int(args.get("max_chars", 12000))

    if not relative_path:
        return ToolResult(
            name="read_workspace_file",
            ok=False,
            risk=ToolRisk.LOW,
            error="Missing relative_path.",
        )

    try:
        file_path = _resolve_workspace_path(relative_path)

        if not file_path.exists():
            return ToolResult(
                name="read_workspace_file",
                ok=False,
                risk=ToolRisk.LOW,
                error=f"File does not exist: {relative_path}",
            )

        if not file_path.is_file():
            return ToolResult(
                name="read_workspace_file",
                ok=False,
                risk=ToolRisk.LOW,
                error=f"Path is not a file: {relative_path}",
            )

        content = file_path.read_text(encoding="utf-8", errors="replace")

        return ToolResult(
            name="read_workspace_file",
            ok=True,
            risk=ToolRisk.LOW,
            output={
                "relative_path": relative_path,
                "content": content[:max_chars],
                "truncated": len(content) > max_chars,
                "size": file_path.stat().st_size,
            },
        )
    except Exception as exc:  # noqa: BLE001
        return ToolResult(
            name="read_workspace_file",
            ok=False,
            risk=ToolRisk.LOW,
            error=str(exc),
        )


async def search_memory_tool(args: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
    query = str(args.get("query", "")).strip()
    limit = int(args.get("limit", 5))

    if not query:
        return ToolResult(
            name="search_memory",
            ok=False,
            risk=ToolRisk.SAFE,
            error="Missing query.",
        )

    try:
        result = await context.memory_service.search_memory(query=query, limit=limit)
        return ToolResult(
            name="search_memory",
            ok=True,
            risk=ToolRisk.SAFE,
            output=result,
        )
    except Exception as exc:  # noqa: BLE001
        return ToolResult(
            name="search_memory",
            ok=False,
            risk=ToolRisk.SAFE,
            error=str(exc),
        )


async def save_note_tool(args: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
    title = str(args.get("title", "")).strip()
    content = str(args.get("content", "")).strip()
    tags_value = args.get("tags", [])

    if isinstance(tags_value, str):
        tags = [tag.strip() for tag in tags_value.split(",") if tag.strip()]
    elif isinstance(tags_value, list):
        tags = [str(tag).strip() for tag in tags_value if str(tag).strip()]
    else:
        tags = []

    if not title or not content:
        return ToolResult(
            name="save_note",
            ok=False,
            risk=ToolRisk.LOW,
            error="Missing title or content.",
        )

    try:
        result = await context.memory_service.add_memory(
            kind="note",
            title=title,
            content=content,
            tags=tags,
            source="tool:save_note",
            index_vector=True,
        )

        return ToolResult(
            name="save_note",
            ok=True,
            risk=ToolRisk.LOW,
            output=result,
        )
    except Exception as exc:  # noqa: BLE001
        return ToolResult(
            name="save_note",
            ok=False,
            risk=ToolRisk.LOW,
            error=str(exc),
        )


SAFE_TOOL_DEFINITIONS = [
    ToolDefinition(
        name="calculate",
        description="Safely evaluate a numeric arithmetic expression.",
        risk=ToolRisk.SAFE,
        parameters={
            "type": "object",
            "properties": {
                "expression": {"type": "string"},
            },
            "required": ["expression"],
        },
        handler=calculate_tool,
    ),
    ToolDefinition(
        name="list_workspace_files",
        description="List files and folders inside the Serviq workspace.",
        risk=ToolRisk.LOW,
        parameters={
            "type": "object",
            "properties": {
                "relative_path": {"type": "string", "default": "."},
            },
        },
        handler=list_workspace_files_tool,
    ),
    ToolDefinition(
        name="read_workspace_file",
        description="Read a UTF-8 text file inside the Serviq workspace.",
        risk=ToolRisk.LOW,
        parameters={
            "type": "object",
            "properties": {
                "relative_path": {"type": "string"},
                "max_chars": {"type": "integer", "default": 12000},
            },
            "required": ["relative_path"],
        },
        handler=read_workspace_file_tool,
    ),
    ToolDefinition(
        name="search_memory",
        description="Search Serviq local memory using vector search or SQLite fallback.",
        risk=ToolRisk.SAFE,
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
        handler=search_memory_tool,
    ),
    ToolDefinition(
        name="save_note",
        description="Save a note to Serviq memory.",
        risk=ToolRisk.LOW,
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "content"],
        },
        handler=save_note_tool,
    ),
]
