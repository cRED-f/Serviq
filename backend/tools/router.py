from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ToolPlan:
    name: str
    args: dict[str, Any]
    reason: str


def _clean_path_candidate(value: str) -> str:
    clean = value.strip()
    clean = clean.strip("`").strip()
    clean = clean.strip('"\'')
    clean = re.sub(r"^(?:named|name|called|at|path)\s*[:=]?\s*", "", clean, flags=re.IGNORECASE)
    clean = clean.strip('"\'` ')
    clean = clean.rstrip("\n\r\t .?!")
    return clean.strip('"\'` ')


def _looks_like_path(value: str) -> bool:
    clean = value.strip().strip('"\'` ')
    return bool(
        re.match(r"^[A-Za-z]:[\\/]", clean)
        or clean.startswith(("/", "~", "./", "../", "workspace/", "dir:"))
        or "/" in clean
        or "\\" in clean
    )


def infer_rename_file_args(message: str) -> dict[str, Any] | None:
    """Extract a conservative single-file rename request from plain English."""
    text = message.strip()
    patterns = [
        r"\bchange\s+(?:the\s+)?(?:file\s+name|filename)\s+from\s+(.+?)\s+to\s+(.+)$",
        r"\bchange\s+(?:the\s+)?(?:file\s+name|filename)\s+(.+?)\s+to\s+(.+)$",
        r"\brename\s+(?:the\s+)?(?:workspace\s+)?file\s+(?:named|called|name)?\s*[:=]?\s*(.+?)\s+(?:to|as|into)\s+(.+)$",
        r"\brename\s+(.+?)\s+(?:to|as|into)\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        source = _clean_path_candidate(match.group(1))
        destination = _clean_path_candidate(match.group(2))
        if not source or not destination:
            continue
        lowered_source = source.lower()
        lowered_destination = destination.lower()
        blocked_words = [" folder", " directory", "*", "?"]
        if any(token in lowered_source for token in blocked_words):
            return None
        if any(token in lowered_destination for token in [" folder", " directory", "*", "?"]):
            return None

        args: dict[str, Any] = {"source_path": source}
        if _looks_like_path(destination):
            args["destination_path"] = destination
        else:
            args["new_name"] = destination
        return args
    return None


def infer_delete_file_path(message: str) -> str | None:
    """Extract a single-file delete target from plain English.

    This does not create a delete plan unless that tool exists. It only helps the
    planner avoid unsafe shell deletion when a future delete tool is available.
    """
    text = message.strip()
    patterns = [
        r"^(?:delete|remove|erase)\s+(?:the\s+)?(?:workspace\s+)?file(?:\s+(?:named?|called|name|at|path))?\s*[:=]?\s+(.+)$",
        r"^(?:delete|remove|erase)\s+(?:the\s+)?file\s*[:=]\s*(.+)$",
        r"^(?:delete|remove|erase)\s+(.+\.[A-Za-z0-9]{1,12})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        candidate = _clean_path_candidate(match.group(1))
        if not candidate:
            continue
        lowered = candidate.lower()
        if any(token in lowered for token in ["*", "?", " folder", " directory"]):
            return None
        return candidate
    return None


def plan_tool_from_message(message: str) -> ToolPlan | None:
    """Deterministic, conservative tool planner.

    Future processes can replace this with model-native tool calling.
    """
    text = message.strip()
    lower = text.lower()

    rename_args = infer_rename_file_args(text)
    if rename_args:
        return ToolPlan(
            name="rename_workspace_file",
            args=rename_args,
            reason="User explicitly requested renaming one file.",
        )

    delete_path = infer_delete_file_path(text)
    if delete_path:
        return ToolPlan(
            name="delete_workspace_file",
            args={"path": delete_path},
            reason="User explicitly requested deleting one file.",
        )

    calculate_match = re.match(r"^(calculate|calc)\s+(.+)$", text, flags=re.IGNORECASE)
    if calculate_match:
        return ToolPlan(
            name="calculate",
            args={"expression": calculate_match.group(2).strip()},
            reason="User explicitly requested calculation.",
        )

    if lower.startswith("list workspace files"):
        remainder = text[len("list workspace files") :].strip()
        return ToolPlan(
            name="list_workspace_files",
            args={"relative_path": remainder or "."},
            reason="User explicitly requested workspace file listing.",
        )

    if lower.startswith("read workspace file"):
        remainder = text[len("read workspace file") :].strip()
        return ToolPlan(
            name="read_workspace_file",
            args={"relative_path": remainder, "max_chars": 12000},
            reason="User explicitly requested reading a workspace file.",
        )

    if lower.startswith("search memory"):
        remainder = text[len("search memory") :].strip()
        return ToolPlan(
            name="search_memory",
            args={"query": remainder or text, "limit": 5},
            reason="User explicitly requested memory search.",
        )

    if lower.startswith("save note"):
        title_match = re.search(
            r"title\s*:\s*(.+?)(?:\s+content\s*:|$)",
            text,
            flags=re.IGNORECASE,
        )
        content_match = re.search(
            r"content\s*:\s*(.+?)(?:\s+tags\s*:|$)",
            text,
            flags=re.IGNORECASE,
        )
        tags_match = re.search(r"tags\s*:\s*(.+)$", text, flags=re.IGNORECASE)
        if title_match and content_match:
            tags = []
            if tags_match:
                tags = [tag.strip() for tag in tags_match.group(1).split(",") if tag.strip()]
            return ToolPlan(
                name="save_note",
                args={
                    "title": title_match.group(1).strip(),
                    "content": content_match.group(1).strip(),
                    "tags": tags,
                },
                reason="User explicitly requested saving a note.",
            )

    if lower.startswith("write workspace file"):
        match = re.search(
            r"write\s+workspace\s+file\s+(.+?)\s+content\s*:\s*(.+?)(?:\s+overwrite\s*:\s*(true|false))?$",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if match:
            return ToolPlan(
                name="write_workspace_file",
                args={
                    "relative_path": match.group(1).strip(),
                    "content": match.group(2).strip(),
                    "overwrite": (match.group(3) or "false").lower() == "true",
                },
                reason="User explicitly requested writing a workspace file.",
            )

    if lower.startswith("append workspace file"):
        match = re.search(
            r"append\s+workspace\s+file\s+(.+?)\s+content\s*:\s*(.+)$",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if match:
            return ToolPlan(
                name="append_workspace_file",
                args={
                    "relative_path": match.group(1).strip(),
                    "content": match.group(2).strip(),
                },
                reason="User explicitly requested appending to a workspace file.",
            )

    # Format:
    # run shell command echo hello
    # shell python --version
    # run command git status
    shell_patterns = [
        r"^run\s+shell\s+command\s+(.+)$",
        r"^shell\s+(.+)$",
        r"^run\s+command\s+(.+)$",
    ]
    for pattern in shell_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return ToolPlan(
                name="run_shell_command",
                args={
                    "command": match.group(1).strip(),
                    "cwd": ".",
                },
                reason="User explicitly requested running a shell command.",
            )

    return None
