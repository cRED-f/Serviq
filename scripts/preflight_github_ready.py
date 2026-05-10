from __future__ import annotations

import os
import sys
from pathlib import Path


BLOCKED_EXACT = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
}

BLOCKED_DIRS = {
    ".venv",
    "venv",
    "env",
    "node_modules",
    "workspace",
    "logs",
    "uploads",
    "generated",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "target",
    "dist",
}

BLOCKED_SUFFIXES = {
    ".sqlite",
    ".sqlite3",
    ".db",
    ".db-shm",
    ".db-wal",
    ".log",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".rar",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
}

REQUIRED_FILES = {
    ".gitignore",
    ".env.example",
    "README.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
}


def should_skip_dir(path: Path) -> bool:
    parts = set(path.parts)
    return ".git" in parts or any(part in BLOCKED_DIRS for part in parts)


def main() -> int:
    root = Path.cwd()
    errors: list[str] = []
    warnings: list[str] = []

    for required in REQUIRED_FILES:
        if not (root / required).exists():
            errors.append(f"Missing required file: {required}")

    for current_root, dir_names, file_names in os.walk(root):
        current_path = Path(current_root)
        relative_dir = current_path.relative_to(root)

        dir_names[:] = [
            directory
            for directory in dir_names
            if directory != ".git"
        ]

        if should_skip_dir(relative_dir):
            continue

        for file_name in file_names:
            path = current_path / file_name
            relative = path.relative_to(root)
            rel_text = str(relative).replace("\\", "/")

            if file_name in BLOCKED_EXACT:
                errors.append(f"Blocked secret/env file exists: {rel_text}")

            if path.suffix.lower() in BLOCKED_SUFFIXES:
                errors.append(f"Blocked runtime/archive file exists: {rel_text}")

            if file_name.lower() == "cargo.lock":
                warnings.append(
                    f"Cargo.lock found: {rel_text}. For apps it is usually OK to commit; keep it if intentional."
                )

    if errors:
        print("Preflight failed.")
        print("")
        for error in errors:
            print(f"ERROR: {error}")
    else:
        print("Preflight passed. No blocked files found.")

    if warnings:
        print("")
        for warning in warnings:
            print(f"WARNING: {warning}")

    print("")
    print("Next safe commands:")
    print("  git add .")
    print("  git status")
    print("  git commit -m \"chore: prepare Serviq for GitHub\"")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
