from __future__ import annotations

import re
from pathlib import Path


HELPER_IMPORT = "from services.runtime_settings_store import get_answer_style_instruction"


def candidate_files(project_root: Path) -> list[Path]:
    backend = project_root / "backend"
    files: list[Path] = []

    for path in backend.rglob("*.py"):
        rel = str(path.relative_to(project_root)).replace("\\", "/").lower()

        if ".venv" in rel or "__pycache__" in rel:
            continue

        text = path.read_text(encoding="utf-8", errors="ignore").lower()

        if (
            "system" in text
            and "messages" in text
            and ("chat" in rel or "agent" in rel or "llm" in rel or "graph" in rel or "service" in rel)
        ):
            files.append(path)

    return files


def patch_simple_system_prompt(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    text = original

    if "get_answer_style_instruction" in text:
        return False

    # Looks for a variable named system_prompt = "..."
    pattern = r'(?m)^([ \t]*)(system_prompt|SYSTEM_PROMPT)\s*=\s*("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"[^"\n]*"|\'[^\'\n]*\')'
    match = re.search(pattern, text)

    if not match:
        return False

    indent = match.group(1)
    var_name = match.group(2)
    assignment_end = match.end()

    injection = (
        f"\n{indent}answer_style_instruction = await get_answer_style_instruction()\n"
        f"{indent}if answer_style_instruction:\n"
        f"{indent}    {var_name} = f\"{{{var_name}}}\\n\\n{{answer_style_instruction}}\"\n"
    )

    text = text[:assignment_end] + injection + text[assignment_end:]

    lines = text.splitlines()
    insert_at = 0

    for index, line in enumerate(lines):
        if line.startswith("from ") or line.startswith("import "):
            insert_at = index + 1

    lines.insert(insert_at, HELPER_IMPORT)
    text = "\n".join(lines) + "\n"

    backup = path.with_suffix(path.suffix + ".bak_concise_style")
    backup.write_text(original, encoding="utf-8")
    path.write_text(text, encoding="utf-8")

    print(f"Patched concise style in: {path}")
    print(f"Backup: {backup}")
    return True


def main() -> None:
    project_root = Path.cwd()

    if not (project_root / "backend").exists():
        raise SystemExit("Run this from project root.")

    patched = []

    for path in candidate_files(project_root):
        if patch_simple_system_prompt(path):
            patched.append(path)

    if patched:
        print("\nRestart backend.")
        return

    print("Could not safely auto-patch the agent prompt.")
    print("")
    print("Manual fix: in the function that builds your system prompt/messages, add:")
    print("")
    print("from services.runtime_settings_store import get_answer_style_instruction")
    print("")
    print("answer_style_instruction = await get_answer_style_instruction()")
    print("if answer_style_instruction:")
    print("    system_prompt = f\"{system_prompt}\\n\\n{answer_style_instruction}\"")
    print("")
    print("Put this before calling LM Studio.")


if __name__ == "__main__":
    main()
