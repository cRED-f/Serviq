from __future__ import annotations

import asyncio
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.config import settings
from tools.base import ToolDefinition, ToolExecutionContext, ToolResult, ToolRisk


class ShellPolicyError(RuntimeError):
    """Raised when a shell command violates Serviq's local sandbox policy."""


@dataclass(slots=True)
class ShellPolicyResult:
    allowed: bool
    reason: str
    blocked_pattern: str | None = None


BLOCKED_COMMAND_PATTERNS = [
    # Destructive file operations
    r"(^|\s)(rm|del|erase|rmdir|rd)\s",
    r"remove-item",
    r"\s-force\s",
    r"\s-recurse\s",

    # Disk / boot / system control
    r"format\s",
    r"diskpart",
    r"bcdedit",
    r"bootrec",
    r"shutdown",
    r"restart-computer",
    r"stop-computer",

    # Process / service / registry manipulation
    r"taskkill",
    r"kill\s+-",
    r"\breg\s+(add|delete|import|save|restore)",
    r"\bsc\s+(delete|stop|config)",
    r"\bnet\s+user\b",
    r"\bnet\s+localgroup\b",

    # Privilege / policy bypass
    r"set-executionpolicy",
    r"bypass",
    r"encodedcommand",
    r"start-process.*runas",

    # Network download + immediate execution patterns
    r"invoke-expression",
    r"\biex\b",
    r"curl\s+.*\|\s*(sh|bash|powershell|pwsh)",
    r"wget\s+.*\|\s*(sh|bash|powershell|pwsh)",
    r"invoke-webrequest\s+.*\|\s*invoke-expression",
]


def evaluate_shell_command(command: str) -> ShellPolicyResult:
    normalized = command.strip().lower()

    if not normalized:
        return ShellPolicyResult(False, "Command is empty.")

    if len(command) > settings.shell_max_command_chars:
        return ShellPolicyResult(
            False,
            f"Command is too long. Maximum is {settings.shell_max_command_chars} characters.",
        )

    for pattern in BLOCKED_COMMAND_PATTERNS:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            return ShellPolicyResult(
                False,
                "Command matched a blocked shell-safety pattern.",
                blocked_pattern=pattern,
            )

    return ShellPolicyResult(True, "Command passed the current shell sandbox policy.")


def _resolve_workspace_cwd(relative_cwd: str | None) -> Path:
    workspace = settings.workspace_path.resolve()
    candidate = (workspace / (relative_cwd or ".")).resolve()

    if not candidate.is_relative_to(workspace):
        raise ShellPolicyError("Shell cwd must stay inside the Serviq workspace.")

    candidate.mkdir(parents=True, exist_ok=True)

    return candidate


def _truncate_output(value: str, max_chars: int) -> tuple[str, bool]:
    if len(value) <= max_chars:
        return value, False

    return value[:max_chars] + "\n...[truncated]", True


def _run_shell_command_sync(
    *,
    command: str,
    cwd: Path,
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    """Run shell command in a worker thread.

    On Windows, `asyncio.create_subprocess_shell` can fail depending on the
    active event-loop policy. `subprocess.run` inside `asyncio.to_thread` is
    stable under Uvicorn on Windows and still keeps the FastAPI event loop free.
    """

    env = os.environ.copy()
    env["SERVIQ_WORKSPACE"] = str(settings.workspace_path.resolve())

    return subprocess.run(
        command,
        cwd=str(cwd),
        input="",
        capture_output=True,
        text=True,
        shell=True,
        timeout=timeout_seconds,
        env=env,
        encoding="utf-8",
        errors="replace",
    )


async def run_shell_command_tool(args: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
    command = str(args.get("command", "")).strip()
    relative_cwd = str(args.get("cwd", ".")).strip() or "."
    timeout_seconds = int(args.get("timeout_seconds", settings.tool_timeout_seconds))
    timeout_seconds = max(1, min(timeout_seconds, settings.tool_timeout_seconds))

    policy = evaluate_shell_command(command)

    if not policy.allowed:
        return ToolResult(
            name="run_shell_command",
            ok=False,
            risk=ToolRisk.HIGH,
            error=policy.reason,
            metadata={
                "blocked_pattern": policy.blocked_pattern,
                "policy": "serviq-shell-sandbox-v2",
            },
        )

    try:
        cwd = _resolve_workspace_cwd(relative_cwd)

        try:
            completed = await asyncio.to_thread(
                _run_shell_command_sync,
                command=command,
                cwd=cwd,
                timeout_seconds=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""

            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")

            stdout, stdout_truncated = _truncate_output(stdout, settings.shell_max_output_chars)
            stderr, stderr_truncated = _truncate_output(stderr, settings.shell_max_output_chars)

            return ToolResult(
                name="run_shell_command",
                ok=False,
                risk=ToolRisk.HIGH,
                error=f"Command timed out after {timeout_seconds} seconds.",
                output={
                    "command": command,
                    "cwd": str(cwd.relative_to(settings.workspace_path.resolve())),
                    "return_code": None,
                    "stdout": stdout,
                    "stderr": stderr,
                    "stdout_truncated": stdout_truncated,
                    "stderr_truncated": stderr_truncated,
                    "timed_out": True,
                },
                metadata={
                    "policy": "serviq-shell-sandbox-v2",
                    "runner": "subprocess.run-to-thread",
                },
            )

        stdout, stdout_truncated = _truncate_output(
            completed.stdout or "",
            settings.shell_max_output_chars,
        )
        stderr, stderr_truncated = _truncate_output(
            completed.stderr or "",
            settings.shell_max_output_chars,
        )

        return ToolResult(
            name="run_shell_command",
            ok=completed.returncode == 0,
            risk=ToolRisk.HIGH,
            output={
                "command": command,
                "cwd": str(cwd.relative_to(settings.workspace_path.resolve())),
                "return_code": completed.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "stdout_truncated": stdout_truncated,
                "stderr_truncated": stderr_truncated,
                "timed_out": False,
            },
            error=None if completed.returncode == 0 else f"Command exited with code {completed.returncode}.",
            metadata={
                "policy": "serviq-shell-sandbox-v2",
                "runner": "subprocess.run-to-thread",
            },
        )

    except Exception as exc:  # noqa: BLE001
        error_message = str(exc) or f"{type(exc).__name__}: {repr(exc)}"

        return ToolResult(
            name="run_shell_command",
            ok=False,
            risk=ToolRisk.HIGH,
            error=error_message,
            metadata={
                "policy": "serviq-shell-sandbox-v2",
                "runner": "subprocess.run-to-thread",
                "error_type": type(exc).__name__,
            },
        )


SHELL_TOOL_DEFINITIONS = [
    ToolDefinition(
        name="run_shell_command",
        description=(
            "Run a shell command inside the Serviq workspace with timeout and sandbox policy. "
            "Requires approval."
        ),
        risk=ToolRisk.HIGH,
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "cwd": {"type": "string", "default": "."},
                "timeout_seconds": {"type": "integer", "default": settings.tool_timeout_seconds},
            },
            "required": ["command"],
        },
        handler=run_shell_command_tool,
    )
]
