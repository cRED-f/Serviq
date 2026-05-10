from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from core.config import settings

WINDOWS_PROTECTED_NAMES = {
    "windows",
    "program files",
    "program files (x86)",
    "programdata",
    "system volume information",
    "recovery",
    "$recycle.bin",
    "perflogs",
}

POSIX_PROTECTED_ROOTS = {
    "/bin",
    "/boot",
    "/dev",
    "/etc",
    "/lib",
    "/lib64",
    "/proc",
    "/root",
    "/run",
    "/sbin",
    "/sys",
    "/usr",
    "/var",
}

DIRECTORY_CAUTION = (
    "Only add specific project or work folders. Do not add drive roots, /, C:\\, "
    "C:\\Windows, Program Files, or other operating-system directories."
)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _workspace_dir() -> Path:
    workspace = settings.workspace_path.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def _db_path() -> Path:
    return _workspace_dir() / "serviq_directory_access.sqlite3"


async def _connect() -> aiosqlite.Connection:
    connection = await aiosqlite.connect(_db_path())
    connection.row_factory = aiosqlite.Row
    return connection


async def ensure_directory_access_store() -> None:
    db = await _connect()
    try:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS accessible_directories (
                path TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        await db.commit()
    finally:
        await db.close()


def _expand_path(value: str) -> Path:
    expanded = os.path.expandvars(os.path.expanduser(value.strip()))
    path = Path(expanded)
    if path.is_absolute():
        return path.resolve()
    return (settings.project_root / path).resolve()


def _is_root_path(path: Path) -> bool:
    try:
        return path == Path(path.anchor).resolve()
    except Exception:  # noqa: BLE001
        return str(path).rstrip("/\\") == str(path.anchor).rstrip("/\\")


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _validate_not_dangerous_directory(path: Path) -> None:
    if _is_root_path(path):
        raise ValueError(f"Refusing to allow root directory: {path}")

    parts_lower = [part.casefold() for part in path.parts]
    if any(part in WINDOWS_PROTECTED_NAMES for part in parts_lower):
        raise ValueError(
            f"Refusing to allow protected Windows/system directory: {path}"
        )

    path_text = str(path).replace("\\", "/").rstrip("/")
    if path_text in POSIX_PROTECTED_ROOTS or any(
        path_text.startswith(f"{root}/") for root in POSIX_PROTECTED_ROOTS
    ):
        raise ValueError(f"Refusing to allow protected system directory: {path}")


def normalize_allowed_directory(value: str) -> str:
    clean = value.strip()
    if not clean:
        raise ValueError("Directory path cannot be empty.")

    path = _expand_path(clean)
    _validate_not_dangerous_directory(path)

    if not path.exists():
        raise ValueError(f"Directory does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"Path is not a directory: {path}")

    return str(path)


async def get_allowed_directories() -> list[str]:
    await ensure_directory_access_store()
    db = await _connect()
    try:
        cursor = await db.execute(
            """
            SELECT path
            FROM accessible_directories
            ORDER BY lower(path)
            """
        )
        rows = await cursor.fetchall()
        return [str(row["path"]) for row in rows]
    finally:
        await db.close()


async def set_allowed_directories(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []

    for raw_path in paths:
        value = normalize_allowed_directory(str(raw_path))
        key = value.casefold() if os.name == "nt" else value
        if key in seen:
            continue
        seen.add(key)
        normalized.append(value)

    await ensure_directory_access_store()
    now = _utcnow()
    db = await _connect()
    try:
        await db.execute("DELETE FROM accessible_directories")
        for path in normalized:
            await db.execute(
                """
                INSERT INTO accessible_directories(path, created_at, updated_at)
                VALUES (?, ?, ?)
                """,
                (path, now, now),
            )
        await db.commit()
    finally:
        await db.close()

    return await get_allowed_directories()


async def get_directory_access_settings() -> dict[str, Any]:
    return {
        "workspace_path": str(settings.workspace_path.resolve()),
        "accessible_directories": await get_allowed_directories(),
        "directory_caution": DIRECTORY_CAUTION,
    }


async def get_access_roots() -> list[Path]:
    roots = [settings.workspace_path.resolve()]
    for value in await get_allowed_directories():
        path = Path(value).resolve()
        if path.exists() and path.is_dir():
            roots.append(path)
    return roots


def _split_virtual_path(raw_path: str, custom_roots: list[Path]) -> Path | None:
    normalized = raw_path.strip().replace("\\", "/")
    if normalized in {"workspace", "workspace/"}:
        return settings.workspace_path.resolve()
    if normalized.startswith("workspace/"):
        return (settings.workspace_path.resolve() / normalized[len("workspace/") :]).resolve()

    match = re.match(r"^dir:(\d+)(?:/(.*))?$", normalized, flags=re.IGNORECASE)
    if not match:
        return None

    root_index = int(match.group(1))
    if root_index < 0 or root_index >= len(custom_roots):
        raise ValueError(f"Unknown accessible directory index: dir:{root_index}")
    rest = match.group(2) or "."
    return (custom_roots[root_index] / rest).resolve()


async def resolve_accessible_path(
    path_value: str | None,
    *,
    default: str = ".",
) -> Path:
    raw_path = str(path_value or default).strip() or default
    roots = await get_access_roots()
    workspace = roots[0]
    custom_roots = roots[1:]

    virtual_candidate = _split_virtual_path(raw_path, custom_roots)
    if virtual_candidate is not None:
        candidate = virtual_candidate
    else:
        expanded = os.path.expandvars(os.path.expanduser(raw_path))
        path = Path(expanded)
        candidate = path.resolve() if path.is_absolute() else (workspace / path).resolve()

    for root in roots:
        if candidate == root or _is_relative_to(candidate, root):
            return candidate

    allowed_roots = ", ".join(str(root) for root in roots)
    raise ValueError(
        "Path is outside Serviq's allowed directories. "
        f"Allowed roots: {allowed_roots}"
    )


async def describe_accessible_path(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    roots = await get_access_roots()
    workspace = roots[0]

    for index, root in enumerate(roots):
        if resolved == root or _is_relative_to(resolved, root):
            relative = "." if resolved == root else str(resolved.relative_to(root))
            if index == 0:
                return {
                    "path": str(resolved),
                    "absolute_path": str(resolved),
                    "access_root": str(root),
                    "access_root_type": "workspace",
                    "relative_path": relative,
                    "display_path": f"workspace/{relative}" if relative != "." else "workspace",
                }
            return {
                "path": str(resolved),
                "absolute_path": str(resolved),
                "access_root": str(root),
                "access_root_type": "custom",
                "access_root_index": index - 1,
                "relative_path": relative,
                "display_path": f"dir:{index - 1}/{relative}" if relative != "." else f"dir:{index - 1}",
            }

    return {
        "path": str(resolved),
        "absolute_path": str(resolved),
        "access_root": None,
        "access_root_type": "unknown",
        "relative_path": None,
        "display_path": str(resolved),
    }
