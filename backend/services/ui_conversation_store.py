from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project_root() -> Path:
    # backend/services/ui_conversation_store.py -> project root
    return Path(__file__).resolve().parents[2]


def _workspace_dir() -> Path:
    workspace = Path(os.getenv("WORKSPACE_DIR", "./workspace"))

    if not workspace.is_absolute():
        workspace = _project_root() / str(workspace).lstrip("./\\")

    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def _db_path() -> Path:
    return _workspace_dir() / "serviq_ui_conversations.sqlite3"


async def _connect() -> aiosqlite.Connection:
    # Important:
    # aiosqlite.connect(...) returns an awaitable connection.
    # We await it exactly once here, then use try/finally + close().
    # Do NOT use: async with await _connect() as db
    # That can start the same worker thread twice.
    connection = await aiosqlite.connect(_db_path())
    connection.row_factory = aiosqlite.Row
    return connection


async def ensure_ui_conversation_store() -> None:
    db = await _connect()
    try:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS ui_chat_sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                preview TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                is_deleted INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS ui_chat_messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                sort_index INTEGER NOT NULL,
                steps_json TEXT,
                metadata_json TEXT,
                is_deleted INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(session_id) REFERENCES ui_chat_sessions(id)
            )
            """
        )
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ui_chat_sessions_updated
            ON ui_chat_sessions(is_deleted, updated_at DESC)
            """
        )
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ui_chat_messages_session
            ON ui_chat_messages(session_id, is_deleted, sort_index ASC)
            """
        )
        await db.commit()
    finally:
        await db.close()


async def list_sessions() -> list[dict[str, Any]]:
    await ensure_ui_conversation_store()

    db = await _connect()
    try:
        cursor = await db.execute(
            """
            SELECT id, title, preview, created_at, updated_at
            FROM ui_chat_sessions
            WHERE is_deleted = 0
            ORDER BY updated_at DESC
            """
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def upsert_session(
    *,
    session_id: str,
    title: str,
    preview: str = "",
) -> dict[str, Any]:
    await ensure_ui_conversation_store()

    now = _utcnow()
    clean_title = title.strip() or "New chat"
    clean_preview = preview.strip()

    db = await _connect()
    try:
        await db.execute(
            """
            INSERT INTO ui_chat_sessions(id, title, preview, created_at, updated_at, is_deleted)
            VALUES (?, ?, ?, ?, ?, 0)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                preview = excluded.preview,
                updated_at = excluded.updated_at,
                is_deleted = 0
            """,
            (session_id, clean_title, clean_preview, now, now),
        )
        await db.commit()

        cursor = await db.execute(
            """
            SELECT id, title, preview, created_at, updated_at
            FROM ui_chat_sessions
            WHERE id = ? AND is_deleted = 0
            """,
            (session_id,),
        )
        row = await cursor.fetchone()

        if row is None:
            raise RuntimeError("Failed to create or load UI chat session.")

        return dict(row)
    finally:
        await db.close()


async def touch_session(
    *,
    session_id: str,
    preview: str | None = None,
    title: str | None = None,
) -> None:
    await ensure_ui_conversation_store()

    now = _utcnow()

    db = await _connect()
    try:
        existing = await db.execute(
            "SELECT id FROM ui_chat_sessions WHERE id = ? AND is_deleted = 0",
            (session_id,),
        )
        row = await existing.fetchone()

        if row is None:
            await db.execute(
                """
                INSERT INTO ui_chat_sessions(id, title, preview, created_at, updated_at, is_deleted)
                VALUES (?, ?, ?, ?, ?, 0)
                """,
                (session_id, title or "New chat", preview or "", now, now),
            )
        else:
            if title is not None and preview is not None:
                await db.execute(
                    """
                    UPDATE ui_chat_sessions
                    SET title = ?, preview = ?, updated_at = ?
                    WHERE id = ? AND is_deleted = 0
                    """,
                    (title, preview, now, session_id),
                )
            elif title is not None:
                await db.execute(
                    """
                    UPDATE ui_chat_sessions
                    SET title = ?, updated_at = ?
                    WHERE id = ? AND is_deleted = 0
                    """,
                    (title, now, session_id),
                )
            elif preview is not None:
                await db.execute(
                    """
                    UPDATE ui_chat_sessions
                    SET preview = ?, updated_at = ?
                    WHERE id = ? AND is_deleted = 0
                    """,
                    (preview, now, session_id),
                )
            else:
                await db.execute(
                    """
                    UPDATE ui_chat_sessions
                    SET updated_at = ?
                    WHERE id = ? AND is_deleted = 0
                    """,
                    (now, session_id),
                )

        await db.commit()
    finally:
        await db.close()


async def list_messages(session_id: str) -> list[dict[str, Any]]:
    await ensure_ui_conversation_store()

    db = await _connect()
    try:
        cursor = await db.execute(
            """
            SELECT id, session_id, role, content, created_at, sort_index, steps_json, metadata_json
            FROM ui_chat_messages
            WHERE session_id = ? AND is_deleted = 0
            ORDER BY sort_index ASC
            """,
            (session_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def append_message(
    *,
    session_id: str,
    role: str,
    content: str,
    message_id: str | None = None,
    steps_json: str | None = None,
    metadata_json: str | None = None,
) -> dict[str, Any]:
    await ensure_ui_conversation_store()

    if role not in {"user", "assistant"}:
        raise ValueError("role must be 'user' or 'assistant'")

    clean_content = content.strip()

    if not clean_content:
        raise ValueError("message content cannot be empty")

    await touch_session(session_id=session_id)

    now = _utcnow()
    final_message_id = message_id or str(uuid.uuid4())

    db = await _connect()
    try:
        cursor = await db.execute(
            """
            SELECT COALESCE(MAX(sort_index), 0) + 1 AS next_sort_index
            FROM ui_chat_messages
            WHERE session_id = ?
            """,
            (session_id,),
        )
        row = await cursor.fetchone()
        sort_index = int(row["next_sort_index"])

        await db.execute(
            """
            INSERT INTO ui_chat_messages(
                id, session_id, role, content, created_at, sort_index,
                steps_json, metadata_json, is_deleted
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
            ON CONFLICT(id) DO UPDATE SET
                content = excluded.content,
                steps_json = excluded.steps_json,
                metadata_json = excluded.metadata_json,
                is_deleted = 0
            """,
            (
                final_message_id,
                session_id,
                role,
                clean_content,
                now,
                sort_index,
                steps_json,
                metadata_json,
            ),
        )
        await db.commit()

        cursor = await db.execute(
            """
            SELECT id, session_id, role, content, created_at, sort_index, steps_json, metadata_json
            FROM ui_chat_messages
            WHERE id = ?
            """,
            (final_message_id,),
        )
        message = await cursor.fetchone()

        if message is None:
            raise RuntimeError("Failed to create or load UI chat message.")

    finally:
        await db.close()

    await touch_session(session_id=session_id, preview=clean_content)
    return dict(message)


async def soft_delete_session(session_id: str) -> None:
    await ensure_ui_conversation_store()

    now = _utcnow()

    db = await _connect()
    try:
        await db.execute(
            """
            UPDATE ui_chat_sessions
            SET is_deleted = 1, updated_at = ?
            WHERE id = ?
            """,
            (now, session_id),
        )
        await db.execute(
            """
            UPDATE ui_chat_messages
            SET is_deleted = 1
            WHERE session_id = ?
            """,
            (session_id,),
        )
        await db.commit()
    finally:
        await db.close()


async def soft_delete_message(message_id: str) -> None:
    await ensure_ui_conversation_store()

    db = await _connect()
    try:
        await db.execute(
            """
            UPDATE ui_chat_messages
            SET is_deleted = 1
            WHERE id = ?
            """,
            (message_id,),
        )
        await db.commit()
    finally:
        await db.close()


async def soft_delete_assistant_pair(assistant_message_id: str) -> dict[str, Any]:
    await ensure_ui_conversation_store()

    db = await _connect()
    try:
        cursor = await db.execute(
            """
            SELECT id, session_id, role, sort_index
            FROM ui_chat_messages
            WHERE id = ? AND is_deleted = 0
            """,
            (assistant_message_id,),
        )
        assistant = await cursor.fetchone()

        if assistant is None:
            return {"deleted": []}

        deleted_ids = [assistant["id"]]

        await db.execute(
            """
            UPDATE ui_chat_messages
            SET is_deleted = 1
            WHERE id = ?
            """,
            (assistant["id"],),
        )

        if assistant["role"] == "assistant":
            cursor = await db.execute(
                """
                SELECT id
                FROM ui_chat_messages
                WHERE session_id = ?
                  AND role = 'user'
                  AND sort_index < ?
                  AND is_deleted = 0
                ORDER BY sort_index DESC
                LIMIT 1
                """,
                (assistant["session_id"], assistant["sort_index"]),
            )
            user_row = await cursor.fetchone()

            if user_row is not None:
                deleted_ids.append(user_row["id"])
                await db.execute(
                    """
                    UPDATE ui_chat_messages
                    SET is_deleted = 1
                    WHERE id = ?
                    """,
                    (user_row["id"],),
                )

        await db.commit()
        return {"deleted": deleted_ids}
    finally:
        await db.close()
