from __future__ import annotations

from pathlib import Path


def main() -> None:
    project_root = Path.cwd()
    router_path = project_root / "backend" / "api" / "router.py"
    route_file = project_root / "backend" / "api" / "routes" / "tool_settings.py"
    service_file = project_root / "backend" / "services" / "tool_settings_store.py"

    if not router_path.exists():
        raise SystemExit(f"Missing router file: {router_path}")

    if not route_file.exists():
        raise SystemExit(
            f"Missing route file: {route_file}\n"
            "Apply the tools-section patch first, then run this script again."
        )

    if not service_file.exists():
        raise SystemExit(
            f"Missing service file: {service_file}\n"
            "Apply the tools-section patch first, then run this script again."
        )

    text = router_path.read_text(encoding="utf-8")
    original = text

    # Case 1: router has grouped route imports:
    # from api.routes import chat, health, llm
    if "from api.routes import" in text and "tool_settings" not in text:
        lines = text.splitlines()
        updated_lines: list[str] = []

        for line in lines:
            stripped = line.strip()

            if stripped.startswith("from api.routes import") and "(" not in stripped:
                if line.rstrip().endswith(","):
                    updated_lines.append(f"{line} tool_settings")
                else:
                    updated_lines.append(f"{line}, tool_settings")
            else:
                updated_lines.append(line)

        text = "\n".join(updated_lines) + ("\n" if original.endswith("\n") else "")

    # Case 2: no grouped import or grouped edit did not happen.
    if "tool_settings" not in text:
        lines = text.splitlines()
        insert_at = 0

        for index, line in enumerate(lines):
            if line.startswith("from ") or line.startswith("import "):
                insert_at = index + 1

        lines.insert(insert_at, "from api.routes import tool_settings")
        text = "\n".join(lines) + "\n"

    include_line = "api_router.include_router(tool_settings.router)"

    if include_line not in text:
        lines = text.splitlines()
        insert_at = len(lines)

        for index, line in enumerate(lines):
            if "include_router" in line:
                insert_at = index + 1

        lines.insert(insert_at, include_line)
        text = "\n".join(lines) + "\n"

    if text == original:
        print("No change needed. tool_settings route already appears to be registered.")
        return

    backup_path = router_path.with_suffix(".py.bak_tool_settings")
    backup_path.write_text(original, encoding="utf-8")
    router_path.write_text(text, encoding="utf-8")

    print(f"Updated: {router_path}")
    print(f"Backup:  {backup_path}")
    print("")
    print("Restart the backend, then test:")
    print('Invoke-RestMethod "http://127.0.0.1:8787/api/tool-settings"')


if __name__ == "__main__":
    main()
