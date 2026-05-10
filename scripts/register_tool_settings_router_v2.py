from __future__ import annotations

import importlib
import sys
from pathlib import Path


def find_import_block(lines: list[str]) -> tuple[int, int] | None:
    """
    Supports:
      from api.routes import chat, health
    and:
      from api.routes import (
          chat,
          health,
      )
    """
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

    if "tool_settings" in joined:
        return lines

    block = find_import_block(lines)

    if block is None:
        insert_at = 0
        for index, line in enumerate(lines):
            if line.startswith("from ") or line.startswith("import "):
                insert_at = index + 1

        lines.insert(insert_at, "from api.routes import tool_settings")
        return lines

    start, end = block
    first_line = lines[start].strip()

    # Single-line grouped import.
    if start == end:
        if lines[start].rstrip().endswith(","):
            lines[start] = f"{lines[start]} tool_settings"
        else:
            lines[start] = f"{lines[start]}, tool_settings"
        return lines

    # Multiline grouped import.
    indent = ""
    for line in lines[start + 1 : end]:
        if line.strip():
            indent = line[: len(line) - len(line.lstrip())]
            break

    if not indent:
        indent = "    "

    lines.insert(end, f"{indent}tool_settings,")
    return lines


def ensure_include(lines: list[str]) -> list[str]:
    joined = "\n".join(lines)
    include_line = "api_router.include_router(tool_settings.router)"

    if include_line in joined:
        return lines

    # Put it after the last api_router.include_router(...) line.
    insert_at = None
    for index, line in enumerate(lines):
        if "api_router.include_router" in line:
            insert_at = index + 1

    if insert_at is None:
        # Put it after api_router creation if found.
        for index, line in enumerate(lines):
            if "api_router" in line and "APIRouter" in line:
                insert_at = index + 1
                break

    if insert_at is None:
        insert_at = len(lines)

    lines.insert(insert_at, include_line)
    return lines


def patch_router(project_root: Path) -> None:
    router_path = project_root / "backend" / "api" / "router.py"
    route_file = project_root / "backend" / "api" / "routes" / "tool_settings.py"
    service_file = project_root / "backend" / "services" / "tool_settings_store.py"

    if not router_path.exists():
        raise SystemExit(f"Missing router file: {router_path}")

    if not route_file.exists():
        raise SystemExit(
            f"Missing route file: {route_file}\n"
            "Apply the tools-section backend patch first."
        )

    if not service_file.exists():
        raise SystemExit(
            f"Missing service file: {service_file}\n"
            "Apply the tools-section backend patch first."
        )

    original = router_path.read_text(encoding="utf-8")
    lines = original.splitlines()

    lines = ensure_import(lines)
    lines = ensure_include(lines)

    updated = "\n".join(lines) + ("\n" if original.endswith("\n") else "")

    if updated != original:
        backup_path = router_path.with_suffix(".py.bak_tool_settings_v2")
        backup_path.write_text(original, encoding="utf-8")
        router_path.write_text(updated, encoding="utf-8")
        print(f"Updated router: {router_path}")
        print(f"Backup written: {backup_path}")
    else:
        print("router.py already contains tool_settings import/include_router.")


def print_router_file(project_root: Path) -> None:
    router_path = project_root / "backend" / "api" / "router.py"
    print("\n--- backend/api/router.py ---")
    print(router_path.read_text(encoding="utf-8"))
    print("--- end router.py ---\n")


def test_import_and_routes(project_root: Path) -> None:
    backend_path = project_root / "backend"

    sys.path.insert(0, str(backend_path))

    print("Testing import: api.routes.tool_settings")
    importlib.import_module("api.routes.tool_settings")
    print("OK: api.routes.tool_settings imports successfully.")

    print("\nTesting FastAPI app route registration...")
    main_module = importlib.import_module("main")
    app = getattr(main_module, "app", None)

    if app is None:
        print("Could not find `app` in backend/main.py.")
        return

    matching_routes = []
    all_routes = []

    for route in getattr(app, "routes", []):
        path = getattr(route, "path", "")
        methods = sorted(getattr(route, "methods", []) or [])
        all_routes.append((path, methods))

        if "tool-settings" in path:
            matching_routes.append((path, methods))

    print("\nRegistered routes containing 'tool-settings':")
    if not matching_routes:
        print("NONE FOUND")
    else:
        for path, methods in matching_routes:
            print(f"{','.join(methods):12s} {path}")

    print("\nIf NONE FOUND, your backend/main.py is probably not including api_router from backend/api/router.py.")
    print("Search backend/main.py for something like:")
    print("  app.include_router(api_router, prefix='/api')")
    print("or:")
    print("  app.include_router(api_router)")


def main() -> None:
    project_root = Path.cwd()

    if not (project_root / "backend").exists():
        raise SystemExit("Run this script from project root: D:\\code\\aiAssistant")

    patch_router(project_root)
    print_router_file(project_root)
    test_import_and_routes(project_root)

    print("\nNext:")
    print("1. Stop backend completely.")
    print("2. Start backend again.")
    print("3. Test:")
    print('   Invoke-RestMethod "http://127.0.0.1:8787/api/tool-settings"')


if __name__ == "__main__":
    main()
