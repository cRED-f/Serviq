from __future__ import annotations

import json
import platform
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from llm.lmstudio_client import LMStudioClient
from tools.registry import ToolRegistry
from tools.router import infer_delete_file_path, infer_rename_file_args, plan_tool_from_message

PlannerAction = Literal["direct_answer", "tool_call"]


@dataclass(slots=True)
class AgentToolPlan:
    action: PlannerAction
    reason: str
    tool_name: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    planner: str = "unknown"
    raw: str | None = None


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped, flags=re.IGNORECASE).strip()
        stripped = re.sub(r"```$", "", stripped).strip()

    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Planner response did not contain a JSON object.")

    parsed = json.loads(stripped[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Planner response JSON was not an object.")
    return parsed


def _clean_shell_command(command: str) -> str:
    cleaned = command.strip()
    cleaned = cleaned.strip("`")
    cleaned = cleaned.strip("\"'")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.rstrip("?.!")
    return cleaned.strip()


def infer_explicit_shell_command(user_message: str) -> str | None:
    text = user_message.strip()
    patterns = [
        r"\b(?:run|execute)\s+(.+?)\s+(?:from|in|inside|using)\s+(?:the\s+)?(?:terminal|shell|cmd|command\s+prompt|powershell)\b",
        r"\b(?:terminal|shell|cmd|command\s+prompt|powershell)\s+command\s+(.+)$",
        r"\brun\s+command\s+(.+)$",
        r"\brun\s+shell\s+command\s+(.+)$",
        r"^\s*shell\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        command = _clean_shell_command(match.group(1))
        if command:
            return command
    return None


def _file_tool_plan(
    *,
    tool_name: str,
    args: dict[str, Any],
    reason: str,
    planner: str,
    raw: str | None = None,
    confidence: float = 0.9,
) -> AgentToolPlan:
    return AgentToolPlan(
        action="tool_call",
        tool_name=tool_name,
        args=args,
        reason=reason,
        confidence=confidence,
        planner=planner,
        raw=raw,
    )


def _normalize_plan(
    *,
    parsed: dict[str, Any],
    raw: str,
    available_tool_names: set[str],
    planner: str,
    user_message: str = "",
) -> AgentToolPlan:
    action = parsed.get("action")
    reason = parsed.get("reason")
    tool_name = parsed.get("tool_name")
    args = parsed.get("args")
    confidence = parsed.get("confidence")

    explicit_shell_command = infer_explicit_shell_command(user_message)
    rename_file_args = infer_rename_file_args(user_message)
    rename_tool_available = "rename_workspace_file" in available_tool_names
    delete_file_path = infer_delete_file_path(user_message)
    delete_tool_available = "delete_workspace_file" in available_tool_names

    if rename_file_args and rename_tool_available and not explicit_shell_command:
        if action != "tool_call" or tool_name in {None, "run_shell_command"}:
            return _file_tool_plan(
                tool_name="rename_workspace_file",
                args=rename_file_args,
                reason=(
                    "User asked to rename one file; using the dedicated rename tool "
                    "instead of a shell rename command."
                ),
                confidence=0.95,
                planner=f"{planner}+rename_file_guard",
                raw=raw,
            )

    if delete_file_path and delete_tool_available and not explicit_shell_command:
        if action != "tool_call" or tool_name in {None, "run_shell_command"}:
            return _file_tool_plan(
                tool_name="delete_workspace_file",
                args={"path": delete_file_path},
                reason=(
                    "User asked to delete one file; using the dedicated delete tool "
                    "instead of a shell deletion command."
                ),
                confidence=0.94,
                planner=f"{planner}+delete_file_guard",
                raw=raw,
            )

    if action not in {"direct_answer", "tool_call"}:
        if rename_file_args and rename_tool_available:
            return _file_tool_plan(
                tool_name="rename_workspace_file",
                args=rename_file_args,
                reason="Planner returned an invalid action, but the user clearly asked to rename one file.",
                confidence=0.86,
                planner=f"{planner}+rename_file_recovery",
                raw=raw,
            )
        if delete_file_path and delete_tool_available:
            return _file_tool_plan(
                tool_name="delete_workspace_file",
                args={"path": delete_file_path},
                reason="Planner returned an invalid action, but the user clearly asked to delete one file.",
                confidence=0.85,
                planner=f"{planner}+delete_file_recovery",
                raw=raw,
            )
        if explicit_shell_command and "run_shell_command" in available_tool_names:
            return AgentToolPlan(
                action="tool_call",
                tool_name="run_shell_command",
                args={"command": explicit_shell_command, "cwd": "."},
                reason="Planner returned invalid action, but the user explicitly asked to run a shell command.",
                confidence=0.7,
                planner=f"{planner}+explicit_shell_recovery",
                raw=raw,
            )
        return AgentToolPlan(
            action="direct_answer",
            reason="Planner returned invalid action, so Serviq will answer directly.",
            confidence=0.0,
            planner=planner,
            raw=raw,
        )

    if not isinstance(reason, str) or not reason.strip():
        reason = "No planner reason provided."

    if action == "direct_answer":
        if rename_file_args and rename_tool_available:
            return _file_tool_plan(
                tool_name="rename_workspace_file",
                args=rename_file_args,
                reason="The user asked to rename one file.",
                confidence=0.9,
                planner=f"{planner}+rename_file_override",
                raw=raw,
            )
        if delete_file_path and delete_tool_available:
            return _file_tool_plan(
                tool_name="delete_workspace_file",
                args={"path": delete_file_path},
                reason="The user asked to delete one file.",
                confidence=0.88,
                planner=f"{planner}+delete_file_override",
                raw=raw,
            )
        if explicit_shell_command and "run_shell_command" in available_tool_names:
            return AgentToolPlan(
                action="tool_call",
                tool_name="run_shell_command",
                args={"command": explicit_shell_command, "cwd": "."},
                reason="The user explicitly asked to run a command in the terminal/shell.",
                confidence=0.85,
                planner=f"{planner}+explicit_shell_override",
                raw=raw,
            )
        return AgentToolPlan(
            action="direct_answer",
            reason=reason,
            confidence=float(confidence) if isinstance(confidence, int | float) else 0.5,
            planner=planner,
            raw=raw,
        )

    if not isinstance(tool_name, str) or tool_name not in available_tool_names:
        if rename_file_args and rename_tool_available:
            return _file_tool_plan(
                tool_name="rename_workspace_file",
                args=rename_file_args,
                reason="Planner requested an unavailable tool, but the user clearly asked to rename one file.",
                confidence=0.84,
                planner=f"{planner}+rename_file_unknown_tool_recovery",
                raw=raw,
            )
        if delete_file_path and delete_tool_available:
            return _file_tool_plan(
                tool_name="delete_workspace_file",
                args={"path": delete_file_path},
                reason="Planner requested an unavailable tool, but the user clearly asked to delete one file.",
                confidence=0.82,
                planner=f"{planner}+delete_file_unknown_tool_recovery",
                raw=raw,
            )
        return AgentToolPlan(
            action="direct_answer",
            reason=f"Planner requested unknown tool `{tool_name}`, so Serviq will answer directly.",
            confidence=0.0,
            planner=planner,
            raw=raw,
        )

    if not isinstance(args, dict):
        args = {}

    if tool_name == "run_shell_command" and explicit_shell_command:
        planned_command = str(args.get("command", "")).strip()
        if planned_command != explicit_shell_command:
            args = {
                **args,
                "command": explicit_shell_command,
                "cwd": args.get("cwd", "."),
            }
            reason = (
                f"{reason} Command corrected to preserve the user's exact requested shell command: "
                f"`{explicit_shell_command}`."
            )
            planner = f"{planner}+command_preservation"

    return AgentToolPlan(
        action="tool_call",
        tool_name=tool_name,
        args=args,
        reason=reason,
        confidence=float(confidence) if isinstance(confidence, int | float) else 0.5,
        planner=planner,
        raw=raw,
    )


def _tool_catalog_text(registry: ToolRegistry) -> str:
    tools = registry.list_tools()
    lines = []
    for tool in tools:
        lines.append(
            json.dumps(
                {
                    "name": tool["name"],
                    "description": tool["description"],
                    "risk": tool["risk"],
                    "parameters": tool["parameters"],
                },
                ensure_ascii=False,
            )
        )
    return "\n".join(lines)


def _memory_summary(memory_items: list[dict[str, Any]]) -> str:
    if not memory_items:
        return "No memory items were preloaded. Use search_memory when memory is needed."
    blocks = []
    for index, item in enumerate(memory_items[:5], start=1):
        blocks.append(f"{index}. {item.get('title', 'Untitled')}: {item.get('content', '')[:600]}")
    return "\n".join(blocks)


def _observation_summary(tool_observations: list[dict[str, Any]]) -> str:
    if not tool_observations:
        return "No tools have been executed yet."
    return json.dumps(tool_observations[-6:], ensure_ascii=False, indent=2, default=str)


def _wants_memory_recall(user_message: str) -> bool:
    lower = user_message.lower()
    phrases = [
        "do you remember",
        "what did i",
        "did i ever",
        "what was my",
        "what is my",
        "what backend",
        "what stack",
        "my preference",
        "my preferred",
        "favorite",
        "usually like",
        "usually use",
        "recall",
        "memory",
        "remembered",
    ]
    return any(phrase in lower for phrase in phrases)


def fallback_plan_from_deterministic_router(
    user_message: str,
    *,
    tool_observations: list[dict[str, Any]] | None = None,
    available_tool_names: set[str] | None = None,
) -> AgentToolPlan | None:
    available_tool_names = available_tool_names or set()

    rename_file_args = infer_rename_file_args(user_message)
    explicit_shell_command = infer_explicit_shell_command(user_message)
    if rename_file_args and "rename_workspace_file" in available_tool_names and not explicit_shell_command:
        return _file_tool_plan(
            tool_name="rename_workspace_file",
            args=rename_file_args,
            reason="Deterministic fallback detected a single-file rename request.",
            confidence=0.88,
            planner="deterministic_rename_file_fallback",
        )

    delete_file_path = infer_delete_file_path(user_message)
    if delete_file_path and "delete_workspace_file" in available_tool_names and not explicit_shell_command:
        return _file_tool_plan(
            tool_name="delete_workspace_file",
            args={"path": delete_file_path},
            reason="Deterministic fallback detected a single-file delete request.",
            confidence=0.86,
            planner="deterministic_delete_file_fallback",
        )

    if explicit_shell_command:
        return AgentToolPlan(
            action="tool_call",
            tool_name="run_shell_command",
            args={"command": explicit_shell_command, "cwd": "."},
            reason="Deterministic fallback detected an explicit shell/terminal command.",
            confidence=0.75,
            planner="deterministic_explicit_shell_fallback",
        )

    if available_tool_names and "search_memory" in available_tool_names and _wants_memory_recall(user_message):
        already_searched = any(
            observation.get("tool_name") == "search_memory"
            for observation in (tool_observations or [])
        )
        if not already_searched:
            return AgentToolPlan(
                action="tool_call",
                tool_name="search_memory",
                args={"query": user_message, "limit": 5},
                reason="User is asking about remembered preferences or previous information.",
                confidence=0.86,
                planner="semantic_memory_recall_fallback",
            )

    fallback = plan_tool_from_message(user_message)
    if not fallback:
        return None

    if available_tool_names and fallback.name not in available_tool_names:
        return None

    return AgentToolPlan(
        action="tool_call",
        tool_name=fallback.name,
        args=fallback.args,
        reason=f"Deterministic fallback router: {fallback.reason}",
        confidence=0.6,
        planner="deterministic_fallback",
    )


async def plan_next_action(
    *,
    lmstudio_client: LMStudioClient,
    model: str,
    user_message: str,
    history: list[dict[str, str]] | None,
    memory_items: list[dict[str, Any]] | None,
    registry: ToolRegistry,
    tool_observations: list[dict[str, Any]] | None = None,
    step_index: int = 1,
    max_steps: int = 4,
) -> AgentToolPlan:
    available_tool_names = {tool["name"] for tool in registry.list_tools()}
    tool_catalog = _tool_catalog_text(registry)
    memory_context = _memory_summary(memory_items or [])
    observation_context = _observation_summary(tool_observations or [])
    os_name = platform.system() or "unknown"

    system_prompt = f"""
You are Serviq's next-action planner.
Current operating system: {os_name}
Current tool step: {step_index}
Maximum tool steps allowed: {max_steps}

Decide whether Serviq should answer now or call exactly one more tool.

Available tools are JSON lines:
{tool_catalog}

Rules:
- Return ONLY valid JSON. No markdown. No explanation outside JSON.
- Choose "direct_answer" when the conversation and tool observations are enough to answer.
- Choose "tool_call" when one more tool is clearly needed.
- Long-term semantic memory is NOT automatically injected.
- If the user asks about remembered preferences, previous facts, saved facts, personal/project context, or "what did I say", choose search_memory.
- Do not call search_memory repeatedly with the same query if it already appears in observations.
- Do not call the same tool with the same args again if its result is already in observations.
- If the user asks to write/create/replace a file, choose write_workspace_file. Use path format 'dir:0/file.js' for custom directories (dir:0 = first custom directory in Settings, dir:1 = second, etc.), or absolute paths like 'C:\\Users\\fahim\\Downloads\\file.js'.
- If the user asks to rename/change the name of one file, choose rename_workspace_file. Works with 'dir:0/file.txt', 'dir:1/file.txt', or absolute paths.
- Never use run_shell_command for file rename requests. Do not plan Rename-Item, ren, mv, or move for natural-language rename requests.
- If the user asks to delete/remove/erase one file and delete_workspace_file is available, choose delete_workspace_file.
- Never use run_shell_command for file deletion. Do not plan rm, del, erase, rmdir, rd, or Remove-Item for natural-language delete-file requests.
- Never claim an approval request exists in the final answer. Only write/rename/delete/shell tool execution can create a real approval request.
- For terminal/current directory/process/package checks, choose run_shell_command.
- Preserve exact requested shell commands when the user explicitly asks for terminal/shell/cmd/powershell.
- For listing local workspace files without terminal/shell/command language, choose list_workspace_files.
- Virtual paths: "workspace" = workspace root, "dir:0" = first custom directory in Settings, "dir:1" = second, etc. Use list_workspace_files with these paths.
- For reading workspace files or files in custom directories, choose read_workspace_file. Use 'dir:0/file.txt', 'dir:1/file.txt', or absolute paths.
- For checking package.json scripts, list workspace files first, then read package.json if it exists.
- For arithmetic, choose calculate.
- For appending text to a file, choose append_workspace_file. Use 'dir:0/file.txt' or absolute paths.
- For saving a memory/note, choose save_note.
- For searching memory, choose search_memory.
- Do not invent tool names.
- Approval is handled by Serviq after your plan.

Output schema:
{{
  "action": "direct_answer" | "tool_call",
  "tool_name": string | null,
  "args": object,
  "reason": string,
  "confidence": number
}}
""".strip()

    history_excerpt = history[-8:] if history else []
    user_prompt = f"""
User message:
{user_message}

Recent conversation history:
{json.dumps(history_excerpt, ensure_ascii=False, indent=2)}

Preloaded memory summary:
{memory_context}

Previous tool observations:
{observation_context}

Return the JSON plan now.
""".strip()

    try:
        payload = await lmstudio_client.chat_completion(
            model=model,
            temperature=0.0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = _extract_json_object(str(content))
        normalized = _normalize_plan(
            parsed=parsed,
            raw=str(content),
            available_tool_names=available_tool_names,
            planner="llm_json_planner",
            user_message=user_message,
        )
        fallback = fallback_plan_from_deterministic_router(
            user_message,
            tool_observations=tool_observations or [],
            available_tool_names=available_tool_names,
        )

        # If the model wants to answer directly but a conservative fallback found
        # a clear local action, force the one-time safe tool call.
        if fallback and normalized.action == "direct_answer" and fallback.tool_name in {
            "search_memory",
            "rename_workspace_file",
            "delete_workspace_file",
        }:
            fallback.raw = f"LLM planner returned direct_answer: {content}"
            return fallback

        # If the model still tries a natural-language rename/delete through shell,
        # prefer the dedicated guarded file tool.
        if (
            fallback
            and fallback.tool_name in {"rename_workspace_file", "delete_workspace_file"}
            and normalized.tool_name == "run_shell_command"
            and not infer_explicit_shell_command(user_message)
        ):
            fallback.raw = f"LLM planner tried shell file operation: {content}"
            fallback.planner = f"deterministic_{fallback.tool_name}_shell_override"
            return fallback

        return normalized
    except Exception as exc:  # noqa: BLE001
        fallback = fallback_plan_from_deterministic_router(
            user_message,
            tool_observations=tool_observations or [],
            available_tool_names=available_tool_names,
        )
        if fallback:
            fallback.raw = f"LLM planner failed: {type(exc).__name__}: {exc}"
            return fallback
        return AgentToolPlan(
            action="direct_answer",
            reason=f"Planner failed and no fallback tool matched: {type(exc).__name__}: {exc}",
            confidence=0.0,
            planner="planner_failure_direct_answer",
        )
