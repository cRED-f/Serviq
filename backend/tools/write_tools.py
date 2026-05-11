from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from services.directory_access_store import (
    describe_accessible_path,
    get_access_roots,
    resolve_accessible_path,
)
from tools.base import ToolDefinition, ToolExecutionContext, ToolResult, ToolRisk


def _get_path_arg(args: dict[str, Any]) -> str:
    return str(args.get("path") or args.get("relative_path") or "").strip()


def _get_source_path_arg(args: dict[str, Any]) -> str:
    return str(
        args.get("source_path")
        or args.get("from_path")
        or args.get("old_path")
        or args.get("path")
        or args.get("relative_path")
        or ""
    ).strip()


def _get_destination_path_arg(args: dict[str, Any]) -> str:
    return str(
        args.get("destination_path")
        or args.get("target_path")
        or args.get("to_path")
        or args.get("new_path")
        or ""
    ).strip()


def _get_new_name_arg(args: dict[str, Any]) -> str:
    return str(args.get("new_name") or args.get("target_name") or args.get("name") or "").strip()


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


def _has_path_separator(value: str) -> bool:
    return "/" in value or "\\" in value


def _is_bare_filename(value: str) -> bool:
    clean = value.strip().strip("'\"")
    if not clean or clean in {".", ".."}:
        return False
    if _has_path_separator(clean):
        return False
    if Path(clean).name != clean:
        return False
    return True


async def _resolve_existing_file_path(requested_path: str) -> Path:
    """Resolve a file path, with a convenience search for bare filenames.

    A request like "rename huh.py to kak.py" often gives only a filename.
    Relative paths normally point to the workspace. If the file is not there and
    the user added folders in Settings, search the top level of each allowed root
    for exactly one matching file.
    """
    file_path = await resolve_accessible_path(requested_path, default="")
    if file_path.exists():
        return file_path

    if not _is_bare_filename(requested_path):
        return file_path

    requested_key = requested_path.casefold() if os.name == "nt" else requested_path
    matches: list[Path] = []
    for root in await get_access_roots():
        try:
            candidate = root / requested_path
            candidate_key = candidate.name.casefold() if os.name == "nt" else candidate.name
            if candidate.exists() and candidate.is_file() and candidate_key == requested_key:
                matches.append(candidate.resolve())
        except OSError:
            continue

    unique_matches: list[Path] = []
    seen: set[str] = set()
    for match in matches:
        key = str(match).casefold() if os.name == "nt" else str(match)
        if key not in seen:
            seen.add(key)
            unique_matches.append(match)

    if len(unique_matches) == 1:
        return unique_matches[0]
    if len(unique_matches) > 1:
        locations = ", ".join(str(path) for path in unique_matches[:6])
        raise ValueError(
            "Multiple allowed files match that name. Use a full path. "
            f"Matches: {locations}"
        )

    return file_path


async def write_workspace_file_tool(
    args: dict[str, Any],
    context: ToolExecutionContext,
) -> ToolResult:
    requested_path = _get_path_arg(args)
    content = str(args.get("content", ""))
    overwrite = bool(args.get("overwrite", False))
    if not requested_path:
        return ToolResult(
            name="write_workspace_file",
            ok=False,
            risk=ToolRisk.MEDIUM,
            error="Missing path.",
        )

    try:
        file_path = await resolve_accessible_path(requested_path, default="")
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
                "requested_path": requested_path,
                **await describe_accessible_path(file_path),
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


async def append_workspace_file_tool(
    args: dict[str, Any],
    context: ToolExecutionContext,
) -> ToolResult:
    requested_path = _get_path_arg(args)
    content = str(args.get("content", ""))
    if not requested_path:
        return ToolResult(
            name="append_workspace_file",
            ok=False,
            risk=ToolRisk.MEDIUM,
            error="Missing path.",
        )

    try:
        file_path = await resolve_accessible_path(requested_path, default="")
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
                "requested_path": requested_path,
                **await describe_accessible_path(file_path),
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


async def rename_workspace_file_tool(
    args: dict[str, Any],
    context: ToolExecutionContext,
) -> ToolResult:
    source_request = _get_source_path_arg(args)
    destination_request = _get_destination_path_arg(args)
    new_name = _get_new_name_arg(args)
    overwrite = bool(args.get("overwrite", False))

    if not source_request:
        return ToolResult(
            name="rename_workspace_file",
            ok=False,
            risk=ToolRisk.HIGH,
            error="Missing source_path.",
        )
    if not destination_request and not new_name:
        return ToolResult(
            name="rename_workspace_file",
            ok=False,
            risk=ToolRisk.HIGH,
            error="Missing new_name or destination_path.",
        )

    try:
        source_path = await _resolve_existing_file_path(source_request)
        source_descriptor = await describe_accessible_path(source_path)

        if not source_path.exists():
            return ToolResult(
                name="rename_workspace_file",
                ok=False,
                risk=ToolRisk.HIGH,
                error=f"File does not exist: {source_request}",
                output={
                    "source_requested_path": source_request,
                    "source": source_descriptor,
                    "renamed": False,
                },
            )
        if not source_path.is_file():
            return ToolResult(
                name="rename_workspace_file",
                ok=False,
                risk=ToolRisk.HIGH,
                error="Refusing to rename this path because it is not a file.",
                output={
                    "source_requested_path": source_request,
                    "source": source_descriptor,
                    "renamed": False,
                },
            )

        if destination_request:
            destination_path = await resolve_accessible_path(destination_request, default="")
        else:
            clean_name = new_name.strip().strip("'\"")
            if not _is_bare_filename(clean_name):
                return ToolResult(
                    name="rename_workspace_file",
                    ok=False,
                    risk=ToolRisk.HIGH,
                    error="new_name must be a single filename, not a path.",
                    output={
                        "source_requested_path": source_request,
                        "source": source_descriptor,
                        "renamed": False,
                    },
                )
            destination_path = (source_path.parent / clean_name).resolve()
            # Re-run directory validation on the computed destination.
            destination_path = await resolve_accessible_path(str(destination_path), default="")

        destination_descriptor = await describe_accessible_path(destination_path)

        if source_path.resolve() == destination_path.resolve():
            return ToolResult(
                name="rename_workspace_file",
                ok=True,
                risk=ToolRisk.HIGH,
                output={
                    "source_requested_path": source_request,
                    "destination_requested_path": destination_request or new_name,
                    "source": source_descriptor,
                    "destination": destination_descriptor,
                    "renamed": False,
                    "unchanged": True,
                },
            )

        if not destination_path.parent.exists() or not destination_path.parent.is_dir():
            return ToolResult(
                name="rename_workspace_file",
                ok=False,
                risk=ToolRisk.HIGH,
                error="Destination folder does not exist.",
                output={
                    "source_requested_path": source_request,
                    "destination_requested_path": destination_request or new_name,
                    "source": source_descriptor,
                    "destination": destination_descriptor,
                    "renamed": False,
                },
            )

        if destination_path.exists():
            if destination_path.is_dir():
                return ToolResult(
                    name="rename_workspace_file",
                    ok=False,
                    risk=ToolRisk.HIGH,
                    error="Destination already exists and is a directory.",
                    output={
                        "source_requested_path": source_request,
                        "destination_requested_path": destination_request or new_name,
                        "source": source_descriptor,
                        "destination": destination_descriptor,
                        "renamed": False,
                    },
                )
            if not overwrite:
                return ToolResult(
                    name="rename_workspace_file",
                    ok=False,
                    risk=ToolRisk.HIGH,
                    error="Destination file already exists. Set overwrite=true to replace it.",
                    output={
                        "source_requested_path": source_request,
                        "destination_requested_path": destination_request or new_name,
                        "source": source_descriptor,
                        "destination": destination_descriptor,
                        "renamed": False,
                    },
                )
            source_path.replace(destination_path)
        else:
            source_path.rename(destination_path)

        return ToolResult(
            name="rename_workspace_file",
            ok=True,
            risk=ToolRisk.HIGH,
            output={
                "source_requested_path": source_request,
                "destination_requested_path": destination_request or new_name,
                "source": source_descriptor,
                "destination": await describe_accessible_path(destination_path),
                "renamed": True,
                "overwritten": overwrite,
            },
        )
    except Exception as exc:  # noqa: BLE001
        return ToolResult(
            name="rename_workspace_file",
            ok=False,
            risk=ToolRisk.HIGH,
            error=str(exc),
        )


WRITE_TOOL_DEFINITIONS = [
    ToolDefinition(
        name="write_workspace_file",
        description=(
            "Write a UTF-8 text file to workspace or any custom directory enabled in Settings. "
            "Use path formats: 'workspace/file.txt' for workspace, 'dir:0/file.txt' for first custom directory "
            "(e.g., 'dir:0/nkn.js' writes to C:\\Users\\fahim\\Downloads), 'dir:1/file.txt' for second, etc. "
            "Also accepts absolute paths like 'C:\\Users\\fahim\\Downloads\\file.txt'. Requires approval."
        ),
        risk=ToolRisk.MEDIUM,
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "relative_path": {"type": "string"},
                "content": {"type": "string"},
                "overwrite": {"type": "boolean", "default": False},
            },
            "required": ["path", "content"],
        },
        handler=write_workspace_file_tool,
    ),
    ToolDefinition(
        name="append_workspace_file",
        description=(
            "Append UTF-8 text to a file in workspace or any custom directory enabled in Settings. "
            "Use 'workspace/file.txt', 'dir:0/file.txt', 'dir:1/file.txt', or absolute paths. Requires approval."
        ),
        risk=ToolRisk.MEDIUM,
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "relative_path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
        handler=append_workspace_file_tool,
    ),
    ToolDefinition(
        name="rename_workspace_file",
        description=(
            "Rename one file in workspace or any custom directory enabled in Settings. "
            "Use 'workspace/file.txt', 'dir:0/file.txt', 'dir:1/file.txt', or absolute paths. "
            "Use this for rename/change filename requests instead of shell commands like "
            "Rename-Item, ren, mv, or move. Directories are refused. Requires approval."
        ),
        risk=ToolRisk.HIGH,
        parameters={
            "type": "object",
            "properties": {
                "source_path": {"type": "string"},
                "from_path": {"type": "string"},
                "path": {"type": "string"},
                "relative_path": {"type": "string"},
                "new_name": {"type": "string"},
                "destination_path": {"type": "string"},
                "target_path": {"type": "string"},
                "overwrite": {"type": "boolean", "default": False},
            },
            "required": ["source_path"],
        },
        handler=rename_workspace_file_tool,
    ),
]
