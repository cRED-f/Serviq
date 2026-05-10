from __future__ import annotations

import asyncio
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.config import settings
from services.directory_access_store import (
    describe_accessible_path,
    get_access_roots,
    resolve_accessible_path,
)
from services.shell_settings_store import get_shell_settings
from tools.base import ToolDefinition, ToolExecutionContext, ToolResult, ToolRisk


class ShellPolicyError(RuntimeError):
    """Raised when a shell command violates Serviq's local sandbox policy."""


@dataclass(slots=True)
class ShellPolicyResult:
    allowed: bool
    reason: str
    blocked_pattern: str | None = None


@dataclass(slots=True)
class ShellCompleted:
    returncode: int
    stdout: str
    stderr: str
    elevated: bool
    runner: str


BLOCKED_COMMAND_PATTERNS = [
    # Directory deletion stays blocked. Single-file deletion is validated below.
    r"(^|\s)(rmdir|rd)\s",
    r"(^|\s)-recurse(\s|$)",
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
    # Privilege / policy bypass inside user commands
    r"set-executionpolicy",
    r"encodedcommand",
    r"\bbypass\b",
    r"start-process.*runas",
    # Network download + immediate execution patterns
    r"invoke-expression",
    r"\biex\b",
    r"curl\s+.*\|\s*(sh|bash|powershell|pwsh)",
    r"wget\s+.*\|\s*(sh|bash|powershell|pwsh)",
    r"invoke-webrequest\s+.*\|\s*invoke-expression",
]

DELETE_COMMANDS = {"del", "erase", "rm", "remove-item"}
DIRECTORY_DELETE_COMMANDS = {"rd", "rmdir"}
DELETE_COMMAND_PATTERN = re.compile(
    r"\b(del|erase|rm|remove-item|rd|rmdir)\b",
    flags=re.IGNORECASE,
)
SHELL_OPERATOR_PATTERN = re.compile(r"(&&|\|\||[;&|])")


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _is_allowed_target(path: Path, roots: list[Path]) -> bool:
    resolved = path.resolve()
    return any(resolved == root.resolve() or _is_relative_to(resolved, root) for root in roots)


def _strip_token(value: str) -> str:
    return value.strip().strip("'\"").strip()


def _is_powershell_executable(token: str) -> bool:
    name = Path(_strip_token(token)).name.casefold()
    return name in {"powershell", "powershell.exe", "pwsh", "pwsh.exe"}


def _split_command_tokens(command: str) -> list[str]:
    try:
        return shlex.split(command, posix=False)
    except ValueError as exc:
        raise ShellPolicyError(f"Could not parse shell command: {exc}") from exc


def _find_delete_command(tokens: list[str]) -> tuple[int, str] | None:
    for index, token in enumerate(tokens):
        clean = _strip_token(token).casefold()
        if clean in DELETE_COMMANDS or clean in DIRECTORY_DELETE_COMMANDS:
            return index, clean
    return None


def _resolve_shell_target(raw_target: str, cwd: Path) -> Path:
    clean = _strip_token(raw_target)
    if not clean:
        raise ShellPolicyError("Delete command target cannot be empty.")
    if any(char in clean for char in ["*", "?"]):
        raise ShellPolicyError("Wildcard deletes are blocked. Delete one explicit file path.")
    if SHELL_OPERATOR_PATTERN.search(clean):
        raise ShellPolicyError("Delete target contains shell operators.")

    path = Path(clean)
    return path.resolve() if path.is_absolute() else (cwd / path).resolve()


def _extract_delete_targets(tokens: list[str], command_index: int, command_name: str) -> list[str]:
    raw_targets: list[str] = []
    parts = tokens[command_index + 1 :]
    index = 0

    while index < len(parts):
        token = _strip_token(parts[index])
        lowered = token.casefold()
        if not token:
            index += 1
            continue

        if command_name in {"del", "erase"}:
            if token.startswith("/"):
                # /S deletes matching files from subdirectories, so block it.
                if "s" in lowered.replace("/", ""):
                    raise ShellPolicyError("Recursive delete switches are blocked.")
                index += 1
                continue
            if token.startswith("-"):
                raise ShellPolicyError("Unexpected delete switch. Use a simple file delete command.")
            raw_targets.append(token)
            index += 1
            continue

        # PowerShell Remove-Item / rm
        if lowered in {"-recurse", "-recursive", "-r"} or lowered.startswith("-r"):
            raise ShellPolicyError("Recursive deletes are blocked.")
        if lowered in {"-force", "-confirm:$false"}:
            index += 1
            continue
        if lowered in {"-path", "-literalpath"}:
            if index + 1 >= len(parts):
                raise ShellPolicyError(f"{token} requires a file path.")
            raw_targets.append(parts[index + 1])
            index += 2
            continue
        if token.startswith("-"):
            raise ShellPolicyError(
                "Only -Path, -LiteralPath, and -Force are allowed for file deletes."
            )

        raw_targets.append(token)
        index += 1

    return raw_targets


def _validate_file_delete_command(command: str, cwd: Path, access_roots: list[Path]) -> ShellPolicyResult:
    if SHELL_OPERATOR_PATTERN.search(command):
        return ShellPolicyResult(
            False,
            "Delete commands must be simple single-command operations.",
            blocked_pattern="shell-operator-delete",
        )

    try:
        tokens = _split_command_tokens(command)
    except ShellPolicyError as exc:
        return ShellPolicyResult(False, str(exc), blocked_pattern="delete-parse")

    delete_match = _find_delete_command(tokens)
    if delete_match is None:
        return ShellPolicyResult(
            False,
            "Delete command could not be identified safely.",
            blocked_pattern="delete-command-parse",
        )

    command_index, command_name = delete_match
    if command_name in DIRECTORY_DELETE_COMMANDS:
        return ShellPolicyResult(
            False,
            "Directory deletion is blocked from shell commands.",
            blocked_pattern=command_name,
        )

    if command_index > 0 and not _is_powershell_executable(tokens[0]):
        return ShellPolicyResult(
            False,
            "Delete command must be direct, not nested inside another command.",
            blocked_pattern="nested-delete-command",
        )

    try:
        targets = _extract_delete_targets(tokens, command_index, command_name)
        if not targets:
            raise ShellPolicyError("Delete command must include one explicit file path.")

        for raw_target in targets:
            target = _resolve_shell_target(raw_target, cwd)
            if not _is_allowed_target(target, access_roots):
                raise ShellPolicyError(
                    "Delete target is outside Serviq's allowed directories. "
                    "Add the parent folder in Settings > Directory access first."
                )
            if target.exists() and target.is_dir():
                raise ShellPolicyError("Directory deletion is blocked from shell commands.")
    except ShellPolicyError as exc:
        return ShellPolicyResult(False, str(exc), blocked_pattern="delete-target")

    return ShellPolicyResult(
        True,
        "Delete command targets are explicit files inside allowed directories.",
    )


def evaluate_shell_command(command: str, cwd: Path, access_roots: list[Path]) -> ShellPolicyResult:
    normalized = command.strip().lower()
    if not normalized:
        return ShellPolicyResult(False, "Command is empty.")
    if len(command) > settings.shell_max_command_chars:
        return ShellPolicyResult(
            False,
            f"Command is too long. Maximum is {settings.shell_max_command_chars} characters.",
        )

    delete_match = DELETE_COMMAND_PATTERN.search(normalized)
    if delete_match:
        return _validate_file_delete_command(command, cwd, access_roots)

    for pattern in BLOCKED_COMMAND_PATTERNS:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            return ShellPolicyResult(
                False,
                "Command matched a blocked shell-safety pattern.",
                blocked_pattern=pattern,
            )

    return ShellPolicyResult(True, "Command passed the current shell sandbox policy.")


async def _resolve_accessible_cwd(cwd_value: str | None) -> Path:
    cwd = await resolve_accessible_path(cwd_value or ".", default=".")
    cwd.mkdir(parents=True, exist_ok=True)
    if not cwd.is_dir():
        raise ShellPolicyError("Shell cwd must be a directory.")
    return cwd


def _truncate_output(value: str, max_chars: int) -> tuple[str, bool]:
    if len(value) <= max_chars:
        return value, False
    return value[:max_chars] + "\n...[truncated]", True


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _read_text_file(path: Path) -> str:
    """Read a bridge file without allowing capture failures to crash the tool."""
    try:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except PermissionError as exc:
        return f"[Serviq could not read {path.name}: permission denied ({exc})]"
    except OSError as exc:
        return f"[Serviq could not read {path.name}: {exc}]"


def _prepare_bridge_file(path: Path) -> None:
    """Create output files before elevation so the non-admin user owns them."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    try:
        # On Windows this keeps the file writable by the elevated same-user process.
        path.chmod(0o666)
    except OSError:
        pass


def _admin_bridge_base_dir(cwd: Path) -> Path:
    """Return a writable directory shared by Serviq and the elevated process."""
    candidates: list[Path] = []

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(Path(local_app_data) / "Serviq" / "admin-shell")

    candidates.extend(
        [
            settings.workspace_path.resolve() / ".serviq" / "admin-shell",
            cwd / ".serviq-admin-shell",
            Path(tempfile.gettempdir()) / "Serviq" / "admin-shell",
        ]
    )

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / f".write-test-{uuid.uuid4().hex}.tmp"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return candidate
        except OSError:
            continue

    raise ShellPolicyError("Could not create a writable admin-shell bridge directory.")


def _run_normal_shell_command_sync(
    *,
    command: str,
    cwd: Path,
    timeout_seconds: int,
    access_roots: list[str],
) -> ShellCompleted:
    """Run shell command in a worker thread without elevation."""
    env = os.environ.copy()
    env["SERVIQ_WORKSPACE"] = str(settings.workspace_path.resolve())
    env["SERVIQ_ACCESS_ROOTS"] = os.pathsep.join(access_roots)
    completed = subprocess.run(
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
    return ShellCompleted(
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
        elevated=False,
        runner="subprocess.run-to-thread",
    )


def _run_windows_admin_shell_command_sync(
    *,
    command: str,
    cwd: Path,
    timeout_seconds: int,
    access_roots: list[str],
) -> ShellCompleted:
    """Launch a Windows UAC PowerShell process and capture command output.

    A running non-admin Python process cannot elevate itself. The safe Windows
    pattern is to start a new process with `Start-Process -Verb RunAs`, which
    displays the UAC prompt.

    The previous implementation used `TemporaryDirectory()` and let the elevated
    process create stdout/stderr files. On some Windows setups, those files end
    up unreadable by the non-admin backend after elevation. This version creates
    an app-owned bridge directory and pre-creates all capture files before UAC.
    """
    if os.name != "nt":
        return _run_normal_shell_command_sync(
            command=command,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            access_roots=access_roots,
        )

    bridge_root = _admin_bridge_base_dir(cwd)
    bridge_dir = bridge_root / f"run-{uuid.uuid4().hex}"
    bridge_dir.mkdir(parents=True, exist_ok=True)

    script_path = bridge_dir / "run-command.ps1"
    stdout_path = bridge_dir / "stdout.txt"
    stderr_path = bridge_dir / "stderr.txt"
    exit_code_path = bridge_dir / "exit-code.txt"
    launcher_stdout_path = bridge_dir / "launcher-stdout.txt"
    launcher_stderr_path = bridge_dir / "launcher-stderr.txt"

    try:
        for capture_path in (
            stdout_path,
            stderr_path,
            exit_code_path,
            launcher_stdout_path,
            launcher_stderr_path,
        ):
            _prepare_bridge_file(capture_path)

        script_path.write_text(
            "\n".join(
                [
                    "$ErrorActionPreference = 'Continue'",
                    f"Set-Location -LiteralPath {_ps_quote(str(cwd))}",
                    f"$env:SERVIQ_WORKSPACE = {_ps_quote(str(settings.workspace_path.resolve()))}",
                    f"$env:SERVIQ_ACCESS_ROOTS = {_ps_quote(os.pathsep.join(access_roots))}",
                    f"$stdoutPath = {_ps_quote(str(stdout_path))}",
                    f"$stderrPath = {_ps_quote(str(stderr_path))}",
                    f"$exitCodePath = {_ps_quote(str(exit_code_path))}",
                    f"$serviqCommand = {_ps_quote(command)}",
                    "$exitCode = 0",
                    "try {",
                    "    & { Invoke-Expression $serviqCommand } 1> $stdoutPath 2> $stderrPath",
                    "    if ($null -ne $LASTEXITCODE) { $exitCode = $LASTEXITCODE }",
                    "    elseif (-not $?) { $exitCode = 1 }",
                    "} catch {",
                    "    $_ | Out-File -LiteralPath $stderrPath -Encoding utf8 -Append",
                    "    $exitCode = 1",
                    "}",
                    "Set-Content -LiteralPath $exitCodePath -Value $exitCode -Encoding utf8",
                    "exit $exitCode",
                ]
            ),
            encoding="utf-8",
        )
        try:
            script_path.chmod(0o666)
        except OSError:
            pass

        launcher_command = "\n".join(
            [
                f"$scriptPath = {_ps_quote(str(script_path))}",
                f"$launcherStdout = {_ps_quote(str(launcher_stdout_path))}",
                f"$launcherStderr = {_ps_quote(str(launcher_stderr_path))}",
                "$argumentList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $scriptPath)",
                "try {",
                "    $process = Start-Process -FilePath 'powershell.exe' -ArgumentList $argumentList -Verb RunAs -Wait -PassThru",
                "    if ($null -eq $process) { exit 1 }",
                "    exit $process.ExitCode",
                "} catch {",
                "    $_ | Out-File -LiteralPath $launcherStderr -Encoding utf8 -Append",
                "    exit 1",
                "}",
            ]
        )

        launcher = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", launcher_command],
            cwd=str(cwd),
            input="",
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            encoding="utf-8",
            errors="replace",
        )

        stdout = _read_text_file(stdout_path)
        stderr_parts = [
            _read_text_file(stderr_path),
            _read_text_file(launcher_stdout_path),
            _read_text_file(launcher_stderr_path),
            launcher.stderr or "",
        ]
        stderr = "\n".join(part for part in stderr_parts if part).strip()

        exit_code = launcher.returncode
        exit_code_text = _read_text_file(exit_code_path).strip()
        if exit_code_text and not exit_code_text.startswith("[Serviq could not read"):
            try:
                exit_code = int(exit_code_text.splitlines()[-1].strip())
            except ValueError:
                stderr = (stderr + "\n" if stderr else "") + (
                    f"Could not parse elevated exit code: {exit_code_text}"
                )

        if not exit_code_path.exists() and launcher.returncode != 0:
            stderr = (stderr + "\n" if stderr else "") + (
                "Administrator shell did not complete. The UAC prompt may have been denied."
            )

        return ShellCompleted(
            returncode=exit_code,
            stdout=stdout,
            stderr=stderr,
            elevated=True,
            runner="windows-uac-powershell-bridge-v2",
        )
    finally:
        try:
            shutil.rmtree(bridge_dir, ignore_errors=True)
        except OSError:
            pass

def _run_shell_command_sync(
    *,
    command: str,
    cwd: Path,
    timeout_seconds: int,
    access_roots: list[str],
    run_as_administrator: bool,
) -> ShellCompleted:
    if run_as_administrator and os.name == "nt":
        return _run_windows_admin_shell_command_sync(
            command=command,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            access_roots=access_roots,
        )
    return _run_normal_shell_command_sync(
        command=command,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        access_roots=access_roots,
    )


async def run_shell_command_tool(
    args: dict[str, Any],
    context: ToolExecutionContext,
) -> ToolResult:
    command = str(args.get("command", "")).strip()
    cwd_value = str(args.get("cwd") or args.get("path") or ".").strip() or "."
    timeout_seconds = int(args.get("timeout_seconds", settings.tool_timeout_seconds))
    timeout_seconds = max(1, min(timeout_seconds, settings.tool_timeout_seconds))

    try:
        cwd = await _resolve_accessible_cwd(cwd_value)
        access_root_paths = await get_access_roots()
        access_roots = [str(root) for root in access_root_paths]
        cwd_descriptor = await describe_accessible_path(cwd)

        policy = evaluate_shell_command(command, cwd, access_root_paths)
        if not policy.allowed:
            return ToolResult(
                name="run_shell_command",
                ok=False,
                risk=ToolRisk.HIGH,
                error=policy.reason,
                metadata={
                    "blocked_pattern": policy.blocked_pattern,
                    "policy": "serviq-shell-sandbox-v4-admin-directory-access",
                },
            )

        shell_settings = await get_shell_settings()
        run_as_administrator = bool(shell_settings.get("shell_run_as_administrator"))

        try:
            completed = await asyncio.to_thread(
                _run_shell_command_sync,
                command=command,
                cwd=cwd,
                timeout_seconds=timeout_seconds,
                access_roots=access_roots,
                run_as_administrator=run_as_administrator,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            stdout, stdout_truncated = _truncate_output(
                stdout,
                settings.shell_max_output_chars,
            )
            stderr, stderr_truncated = _truncate_output(
                stderr,
                settings.shell_max_output_chars,
            )
            return ToolResult(
                name="run_shell_command",
                ok=False,
                risk=ToolRisk.HIGH,
                error=(
                    f"Command timed out after {timeout_seconds} seconds. "
                    "If administrator mode is enabled, the UAC prompt may not have been approved."
                ),
                output={
                    "command": command,
                    "cwd": cwd_descriptor,
                    "return_code": None,
                    "stdout": stdout,
                    "stderr": stderr,
                    "stdout_truncated": stdout_truncated,
                    "stderr_truncated": stderr_truncated,
                    "timed_out": True,
                    "run_as_administrator": run_as_administrator and os.name == "nt",
                },
                metadata={
                    "policy": "serviq-shell-sandbox-v4-admin-directory-access",
                    "runner": "windows-uac-powershell"
                    if run_as_administrator and os.name == "nt"
                    else "subprocess.run-to-thread",
                    "admin_setting_enabled": run_as_administrator,
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
                "cwd": cwd_descriptor,
                "return_code": completed.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "stdout_truncated": stdout_truncated,
                "stderr_truncated": stderr_truncated,
                "timed_out": False,
                "run_as_administrator": completed.elevated,
            },
            error=None
            if completed.returncode == 0
            else f"Command exited with code {completed.returncode}.",
            metadata={
                "policy": "serviq-shell-sandbox-v4-admin-directory-access",
                "runner": completed.runner,
                "admin_setting_enabled": run_as_administrator,
                "admin_requested_not_supported": run_as_administrator and os.name != "nt",
            },
        )
    except Exception as exc:  # noqa: BLE001
        error_message = str(exc) or f"{type(exc).__name__}: {exc!r}"
        return ToolResult(
            name="run_shell_command",
            ok=False,
            risk=ToolRisk.HIGH,
            error=error_message,
            metadata={
                "policy": "serviq-shell-sandbox-v4-admin-directory-access",
                "runner": "subprocess.run-to-thread",
                "error_type": type(exc).__name__,
            },
        )


SHELL_TOOL_DEFINITIONS = [
    ToolDefinition(
        name="run_shell_command",
        description=(
            "Run a shell command inside the Serviq workspace or an enabled "
            "custom directory with timeout and sandbox policy. If enabled in "
            "Settings on Windows, approved commands launch through a UAC "
            "administrator prompt. Requires approval."
        ),
        risk=ToolRisk.HIGH,
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "cwd": {"type": "string", "default": "."},
                "path": {"type": "string", "default": "."},
                "timeout_seconds": {
                    "type": "integer",
                    "default": settings.tool_timeout_seconds,
                },
            },
            "required": ["command"],
        },
        handler=run_shell_command_tool,
    )
]
