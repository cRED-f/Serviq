from __future__ import annotations

import re
from pathlib import Path


IMPORT_LINE = "from services.tool_execution_guard import ensure_tool_enabled_or_result"
CALL_TEMPLATE = """{indent}disabled_tool_result = await ensure_tool_enabled_or_result({tool_expr})
{indent}if disabled_tool_result is not None:
{indent}    return disabled_tool_result
"""


COMMON_EXECUTOR_FILE_HINTS = (
    "tool",
    "agent",
    "approval",
    "executor",
    "runner",
    "graph",
)


PREFERRED_TOOL_NAME_PARAMS = (
    "tool_name",
    "name",
    "tool",
    "requested_tool",
    "selected_tool",
    "planned_tool",
    "action_tool",
)


def should_scan(path: Path) -> bool:
    if path.suffix != ".py":
        return False

    text_path = str(path).replace("\\", "/").lower()

    if "/.venv/" in text_path or "__pycache__" in text_path:
        return False

    if not text_path.startswith("backend/"):
        return False

    return any(hint in text_path for hint in COMMON_EXECUTOR_FILE_HINTS)


def find_matching_paren(text: str, open_index: int) -> int:
    depth = 0

    for index in range(open_index, len(text)):
        char = text[index]

        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1

            if depth == 0:
                return index

    return -1


def parse_params(signature: str) -> list[str]:
    # Strip defaults/annotations crudely but safely enough for common function signatures.
    params: list[str] = []

    for raw_part in signature.split(","):
        part = raw_part.strip()

        if not part or part in {"self", "cls", "*", "/"}:
            continue

        if part.startswith("*"):
            part = part.lstrip("*").strip()

        name = part.split(":", 1)[0].split("=", 1)[0].strip()

        if name and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
            params.append(name)

    return params


def find_tool_expr(params: list[str]) -> str | None:
    for preferred in PREFERRED_TOOL_NAME_PARAMS:
        if preferred in params:
            return preferred

    # Common state/plan dicts.
    for candidate in ("plan", "tool_call", "action", "request", "payload"):
        if candidate in params:
            return f"str({candidate}.get('tool_name') or {candidate}.get('name') or {candidate}.get('tool') or '')"

    return None


def looks_like_executor(name: str, body_start_sample: str) -> bool:
    lowered = name.lower()

    if lowered in {
        "execute_tool",
        "run_tool",
        "call_tool",
        "invoke_tool",
        "dispatch_tool",
        "maybe_use_tool",
        "execute_approved_tool",
        "run_approved_tool",
    }:
        return True

    if lowered.startswith("execute_") and "tool" in lowered:
        return True

    if lowered.startswith("run_") and "tool" in lowered:
        return True

    sample = body_start_sample.lower()

    return (
        "tool_name" in sample
        and (
            "approval" in sample
            or "subprocess" in sample
            or "shell" in sample
            or "tool_result" in sample
            or "execute" in sample
        )
    )


def patch_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    text = original

    if "ensure_tool_enabled_or_result" in text:
        return False

    # Function regex supports single and multiline signatures by finding "async def name(" then matching paren.
    matches: list[tuple[int, int, str, str, str]] = []

    for match in re.finditer(r"(?m)^([ \t]*)async def ([A-Za-z_][A-Za-z0-9_]*)\s*\(", text):
        indent = match.group(1)
        name = match.group(2)
        open_paren = text.find("(", match.start())
        close_paren = find_matching_paren(text, open_paren)

        if close_paren == -1:
            continue

        signature = text[open_paren + 1 : close_paren]
        params = parse_params(signature)
        tool_expr = find_tool_expr(params)

        if not tool_expr:
            continue

        # Find line end after def header.
        header_end = text.find("\n", close_paren)
        if header_end == -1:
            continue

        body_indent = indent + "    "
        sample = text[header_end : header_end + 1200]

        if not looks_like_executor(name, sample):
            continue

        matches.append((header_end + 1, header_end + 1, body_indent, tool_expr, name))

    if not matches:
        return False

    # Patch the first likely central executor only. Multiple auto-patches can over-block helper functions.
    insert_at, _, body_indent, tool_expr, function_name = matches[0]
    guard_code = CALL_TEMPLATE.format(indent=body_indent, tool_expr=tool_expr)
    text = text[:insert_at] + guard_code + text[insert_at:]

    # Add import after existing imports.
    lines = text.splitlines()
    if IMPORT_LINE not in text:
        insert_line = 0

        for index, line in enumerate(lines):
            if line.startswith("from ") or line.startswith("import "):
                insert_line = index + 1

        lines.insert(insert_line, IMPORT_LINE)
        text = "\n".join(lines) + "\n"

    backup = path.with_suffix(path.suffix + ".bak_tool_guard")
    backup.write_text(original, encoding="utf-8")
    path.write_text(text, encoding="utf-8")

    print(f"Patched {path} inside async function `{function_name}`.")
    print(f"Backup: {backup}")
    return True


def main() -> None:
    project_root = Path.cwd()

    if not (project_root / "backend").exists():
        raise SystemExit("Run this from project root, for example: D:\\code\\aiAssistant")

    # Make sure required new guard file exists.
    guard_file = project_root / "backend" / "services" / "tool_execution_guard.py"
    settings_file = project_root / "backend" / "services" / "tool_settings_store.py"

    if not settings_file.exists():
        raise SystemExit(
            "Missing backend/services/tool_settings_store.py. Apply the Tools backend patch first."
        )

    if not guard_file.exists():
        raise SystemExit(
            "Missing backend/services/tool_execution_guard.py. Extract this hotfix fully first."
        )

    patched = []

    for path in sorted((project_root / "backend").rglob("*.py")):
        rel = path.relative_to(project_root)

        if should_scan(rel) and patch_file(path):
            patched.append(str(rel))

    if patched:
        print("\nDone. Patched central tool executor candidate(s):")
        for item in patched:
            print(f" - {item}")
        print("\nRestart backend and test with all tools disabled.")
        return

    print("No central executor was auto-patched.")
    print("")
    print("Manual fix:")
    print("1. Search for where tools are executed:")
    print("   Select-String -Path backend\\**\\*.py -Pattern \"execute_tool|run_tool|tool_name|run_shell_command\"")
    print("")
    print("2. In that function, add this BEFORE approval creation and BEFORE execution:")
    print("")
    print("   from services.tool_execution_guard import ensure_tool_enabled_or_result")
    print("")
    print("   disabled_tool_result = await ensure_tool_enabled_or_result(tool_name)")
    print("   if disabled_tool_result is not None:")
    print("       return disabled_tool_result")
    print("")
    print("3. If approved tools execute in a separate function, add the same check there too.")


if __name__ == "__main__":
    main()
