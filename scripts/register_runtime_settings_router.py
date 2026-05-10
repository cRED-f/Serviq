from __future__ import annotations

from pathlib import Path


def find_import_block(lines: list[str]) -> tuple[int, int] | None:
    for index, line in enumerate(lines):
        stripped = line.strip()

        if not stripped.startswith("from api.routes import"):
            continue

        if "(" not in stripped:
            return index, index

        end = index
        while end < len(lines):
            if ")" in lines[end]:
                return index, end
            end += 1

        return index, index

    return None


def ensure_import(lines: list[str]) -> list[str]:
    joined = "\n".join(lines)

    if "runtime_settings" in joined:
        return lines

    block = find_import_block(lines)

    if block is None:
        insert_at = 0
        for index, line in enumerate(lines):
            if line.startswith("from ") or line.startswith("import "):
                insert_at = index + 1
        lines.insert(insert_at, "from api.routes import runtime_settings")
        return lines

    start, end = block

    if start == end:
        lines[start] = f"{lines[start]}, runtime_settings"
        return lines

    indent = "    "
    for line in lines[start + 1 : end]:
        if line.strip():
            indent = line[: len(line) - len(line.lstrip())]
            break

    lines.insert(end, f"{indent}runtime_settings,")
    return lines


def ensure_include(lines: list[str]) -> list[str]:
    include_line = "api_router.include_router(runtime_settings.router)"

    if include_line in "\n".join(lines):
        return lines

    insert_at = None
    for index, line in enumerate(lines):
        if "api_router.include_router" in line:
            insert_at = index + 1

    if insert_at is None:
        insert_at = len(lines)

    lines.insert(insert_at, include_line)
    return lines


def main() -> None:
    project_root = Path.cwd()
    router_path = project_root / "backend" / "api" / "router.py"

    if not router_path.exists():
        raise SystemExit(f"Missing router file: {router_path}")

    original = router_path.read_text(encoding="utf-8")
    lines = original.splitlines()
    lines = ensure_import(lines)
    lines = ensure_include(lines)
    updated = "\n".join(lines) + ("\n" if original.endswith("\n") else "")

    if updated != original:
        backup = router_path.with_suffix(".py.bak_runtime_settings")
        backup.write_text(original, encoding="utf-8")
        router_path.write_text(updated, encoding="utf-8")
        print(f"Updated: {router_path}")
        print(f"Backup: {backup}")
    else:
        print("runtime_settings router already registered.")

    print('Test after backend restart: Invoke-RestMethod "http://127.0.0.1:8787/api/runtime-settings"')


if __name__ == "__main__":
    main()
