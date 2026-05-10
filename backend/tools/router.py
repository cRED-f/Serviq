from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ToolPlan:
    name: str
    args: dict[str, Any]
    reason: str


def plan_tool_from_message(message: str) -> ToolPlan | None:
    """Deterministic, conservative tool planner.

    Future processes can replace this with model-native tool calling.
    """

    text = message.strip()
    lower = text.lower()

    calculate_match = re.match(r"^(calculate|calc)\s+(.+)$", text, flags=re.IGNORECASE)
    if calculate_match:
        return ToolPlan(
            name="calculate",
            args={"expression": calculate_match.group(2).strip()},
            reason="User explicitly requested calculation.",
        )

    if lower.startswith("list workspace files"):
        remainder = text[len("list workspace files"):].strip()
        return ToolPlan(
            name="list_workspace_files",
            args={"relative_path": remainder or "."},
            reason="User explicitly requested workspace file listing.",
        )

    if lower.startswith("read workspace file"):
        remainder = text[len("read workspace file"):].strip()
        return ToolPlan(
            name="read_workspace_file",
            args={"relative_path": remainder, "max_chars": 12000},
            reason="User explicitly requested reading a workspace file.",
        )

    if lower.startswith("search memory"):
        remainder = text[len("search memory"):].strip()
        return ToolPlan(
            name="search_memory",
            args={"query": remainder or text, "limit": 5},
            reason="User explicitly requested memory search.",
        )

    if lower.startswith("save note"):
        title_match = re.search(r"title\s*:\s*(.+?)(?:\s+content\s*:|$)", text, flags=re.IGNORECASE)
        content_match = re.search(r"content\s*:\s*(.+?)(?:\s+tags\s*:|$)", text, flags=re.IGNORECASE)
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
