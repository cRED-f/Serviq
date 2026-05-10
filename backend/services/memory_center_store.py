from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

VALID_MEMORY_STATUSES = {"active", "archived", "deleted"}
VALID_IMPORTANCE_LEVELS = {"low", "medium", "high"}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _workspace_dir() -> Path:
    workspace = Path(os.getenv("WORKSPACE_DIR", "./workspace"))
    if not workspace.is_absolute():
        workspace = _project_root() / str(workspace).lstrip("./\\")
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def _db_path() -> Path:
    return _workspace_dir() / "serviq_memory_center.sqlite3"


async def _connect() -> aiosqlite.Connection:
    connection = await aiosqlite.connect(_db_path())
    connection.row_factory = aiosqlite.Row
    return connection


def _make_title(content: str) -> str:
    clean = " ".join(content.strip().split())
    return clean[:70] + ("..." if len(clean) > 70 else "") if clean else "Untitled memory"


def _normalize_status(status: str | None) -> str:
    clean = (status or "active").strip().lower()
    if clean not in VALID_MEMORY_STATUSES:
        raise ValueError(f"Invalid memory status: {status}")
    return clean


def _normalize_importance(importance: str | None) -> str:
    clean = (importance or "medium").strip().lower()
    if clean not in VALID_IMPORTANCE_LEVELS:
        raise ValueError(f"Invalid memory importance: {importance}")
    return clean


async def ensure_memory_center_store() -> None:
    db = await _connect()
    try:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_items (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'general',
                importance TEXT NOT NULL DEFAULT 'medium',
                source TEXT NOT NULL DEFAULT 'manual',
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                archived_at TEXT,
                deleted_at TEXT
            )
            """
        )
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memory_items_status_updated
            ON memory_items(status, updated_at DESC)
            """
        )
        await db.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_items_fts
            USING fts5(id UNINDEXED, title, content, category, source)
            """
        )
        await db.commit()
    finally:
        await db.close()


async def _sync_fts(
    db: aiosqlite.Connection,
    *,
    memory_id: str,
    title: str,
    content: str,
    category: str,
    source: str,
) -> None:
    await db.execute("DELETE FROM memory_items_fts WHERE id = ?", (memory_id,))
    await db.execute(
        "INSERT INTO memory_items_fts(id, title, content, category, source) VALUES (?, ?, ?, ?, ?)",
        (memory_id, title, content, category, source),
    )


def _row_to_memory(row: sqlite3.Row | aiosqlite.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "content": row["content"],
        "category": row["category"],
        "importance": row["importance"],
        "source": row["source"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "archived_at": row["archived_at"],
        "deleted_at": row["deleted_at"],
    }


async def list_memory_items(*, status: str = "active", query: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    await ensure_memory_center_store()
    clean_status = _normalize_status(status)
    clean_query = (query or "").strip()
    safe_limit = max(1, min(limit, 300))
    db = await _connect()
    try:
        if clean_query:
            cursor = await db.execute(
                """
                SELECT m.* FROM memory_items_fts f
                JOIN memory_items m ON m.id = f.id
                WHERE memory_items_fts MATCH ? AND m.status = ?
                ORDER BY m.updated_at DESC LIMIT ?
                """,
                (clean_query, clean_status, safe_limit),
            )
        else:
            cursor = await db.execute(
                """
                SELECT * FROM memory_items
                WHERE status = ?
                ORDER BY updated_at DESC LIMIT ?
                """,
                (clean_status, safe_limit),
            )
        rows = await cursor.fetchall()
        return [_row_to_memory(row) for row in rows]
    finally:
        await db.close()


async def get_memory_item(memory_id: str) -> dict[str, Any] | None:
    await ensure_memory_center_store()
    db = await _connect()
    try:
        cursor = await db.execute("SELECT * FROM memory_items WHERE id = ?", (memory_id,))
        row = await cursor.fetchone()
        return _row_to_memory(row) if row else None
    finally:
        await db.close()


async def create_memory_item(
    *,
    content: str,
    title: str | None = None,
    category: str = "general",
    importance: str = "medium",
    source: str = "manual",
    memory_id: str | None = None,
) -> dict[str, Any]:
    await ensure_memory_center_store()
    clean_content = content.strip()
    if not clean_content:
        raise ValueError("Memory content cannot be empty.")
    clean_title = (title or "").strip() or _make_title(clean_content)
    clean_category = category.strip() or "general"
    clean_importance = _normalize_importance(importance)
    clean_source = source.strip() or "manual"
    final_id = memory_id or str(uuid.uuid4())
    now = _utcnow()
    db = await _connect()
    try:
        await db.execute(
            """
            INSERT INTO memory_items(id, title, content, category, importance, source, status, created_at, updated_at, archived_at, deleted_at)
            VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, NULL, NULL)
            """,
            (final_id, clean_title, clean_content, clean_category, clean_importance, clean_source, now, now),
        )
        await _sync_fts(db, memory_id=final_id, title=clean_title, content=clean_content, category=clean_category, source=clean_source)
        await db.commit()
    finally:
        await db.close()
    memory = await get_memory_item(final_id)
    if memory is None:
        raise RuntimeError("Failed to create memory item.")
    return memory


async def update_memory_item(
    memory_id: str,
    *,
    title: str | None = None,
    content: str | None = None,
    category: str | None = None,
    importance: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    await ensure_memory_center_store()
    current = await get_memory_item(memory_id)
    if current is None:
        raise KeyError(f"Memory item not found: {memory_id}")
    next_title = (title if title is not None else current["title"]).strip()
    next_content = (content if content is not None else current["content"]).strip()
    next_category = (category if category is not None else current["category"]).strip() or "general"
    next_importance = _normalize_importance(importance if importance is not None else current["importance"])
    next_status = _normalize_status(status if status is not None else current["status"])
    if not next_title:
        next_title = _make_title(next_content)
    if not next_content:
        raise ValueError("Memory content cannot be empty.")
    now = _utcnow()
    archived_at = current["archived_at"]
    deleted_at = current["deleted_at"]
    if next_status == "archived" and current["status"] != "archived":
        archived_at = now
    if next_status == "active":
        archived_at = None
        deleted_at = None
    if next_status == "deleted" and current["status"] != "deleted":
        deleted_at = now
    db = await _connect()
    try:
        await db.execute(
            """
            UPDATE memory_items
            SET title = ?, content = ?, category = ?, importance = ?, status = ?, updated_at = ?, archived_at = ?, deleted_at = ?
            WHERE id = ?
            """,
            (next_title, next_content, next_category, next_importance, next_status, now, archived_at, deleted_at, memory_id),
        )
        if next_status == "deleted":
            await db.execute("DELETE FROM memory_items_fts WHERE id = ?", (memory_id,))
        else:
            await _sync_fts(db, memory_id=memory_id, title=next_title, content=next_content, category=next_category, source=current["source"])
        await db.commit()
    finally:
        await db.close()
    updated = await get_memory_item(memory_id)
    if updated is None:
        raise RuntimeError("Failed to update memory item.")
    return updated


async def archive_memory_item(memory_id: str) -> dict[str, Any]:
    return await update_memory_item(memory_id, status="archived")


async def restore_memory_item(memory_id: str) -> dict[str, Any]:
    return await update_memory_item(memory_id, status="active")


async def delete_memory_item(memory_id: str) -> dict[str, Any]:
    return await update_memory_item(memory_id, status="deleted")


async def search_memory_items(*, query: str, include_archived: bool = False, limit: int = 20) -> list[dict[str, Any]]:
    await ensure_memory_center_store()
    clean_query = query.strip()
    if not clean_query:
        return []
    safe_limit = max(1, min(limit, 100))
    statuses = ["active", "archived"] if include_archived else ["active"]
    placeholders = ",".join(["?"] * len(statuses))
    db = await _connect()
    try:
        cursor = await db.execute(
            f"""
            SELECT m.* FROM memory_items_fts f
            JOIN memory_items m ON m.id = f.id
            WHERE memory_items_fts MATCH ? AND m.status IN ({placeholders})
            ORDER BY m.updated_at DESC LIMIT ?
            """,
            (clean_query, *statuses, safe_limit),
        )
        rows = await cursor.fetchall()
        return [_row_to_memory(row) for row in rows]
    finally:
        await db.close()


async def get_memory_stats() -> dict[str, Any]:
    await ensure_memory_center_store()
    db = await _connect()
    try:
        cursor = await db.execute("SELECT status, COUNT(*) AS count FROM memory_items GROUP BY status")
        rows = await cursor.fetchall()
        counts = {"active": 0, "archived": 0, "deleted": 0}
        for row in rows:
            counts[row["status"]] = int(row["count"])
        cursor = await db.execute(
            """
            SELECT category, COUNT(*) AS count
            FROM memory_items
            WHERE status != 'deleted'
            GROUP BY category
            ORDER BY count DESC, category ASC LIMIT 20
            """
        )
        categories = [{"category": row["category"], "count": int(row["count"])} for row in await cursor.fetchall()]
        return {"counts": counts, "categories": categories}
    finally:
        await db.close()


async def list_active_memories_for_agent(limit: int = 20) -> list[dict[str, Any]]:
    return await list_memory_items(status="active", limit=limit)


async def save_memory_from_agent(*, content: str, title: str | None = None, category: str = "agent", importance: str = "medium") -> dict[str, Any]:
    return await create_memory_item(content=content, title=title, category=category, importance=importance, source="agent")
