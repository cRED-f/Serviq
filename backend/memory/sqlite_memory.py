from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.config import settings


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class MemoryItem:
    id: str
    kind: str
    title: str
    content: str
    source: str | None
    tags: list[str]
    created_at: str
    updated_at: str
    score: float | None = None
    metadata: dict[str, Any] | None = None
    lifecycle: str = "active"
    confidence: float | None = None
    supersedes_id: str | None = None


class SQLiteMemoryStore:
    """SQLite-backed structured memory and conversation store.

    Process 13 adds memory lifecycle support:
    - active
    - archived
    - superseded
    - deleted
    """

    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path or settings.workspace_path / "serviq_memory.sqlite3"
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.ensure_schema()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def ensure_schema(self) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_items (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source TEXT,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            self._ensure_column(connection, "memory_items", "lifecycle", "TEXT NOT NULL DEFAULT 'active'")
            self._ensure_column(connection, "memory_items", "confidence", "REAL")
            self._ensure_column(connection, "memory_items", "supersedes_id", "TEXT")

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    model TEXT,
                    route TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_decisions (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    memory_id TEXT,
                    candidate_json TEXT NOT NULL DEFAULT '{}',
                    confidence REAL,
                    created_at TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_items_kind
                ON memory_items(kind)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_items_lifecycle
                ON memory_items(lifecycle)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_items_created_at
                ON memory_items(created_at)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_conversation_session
                ON conversation_messages(session_id, created_at)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_conversation_created_at
                ON conversation_messages(created_at)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_decisions_session
                ON memory_decisions(session_id, created_at)
                """
            )

            connection.commit()

    def _ensure_column(
        self,
        connection: sqlite3.Connection,
        table_name: str,
        column_name: str,
        column_definition: str,
    ) -> None:
        columns = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        existing = {row["name"] for row in columns}

        if column_name not in existing:
            connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")

    def add_memory(
        self,
        *,
        kind: str,
        title: str,
        content: str,
        source: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        lifecycle: str = "active",
        confidence: float | None = None,
        supersedes_id: str | None = None,
    ) -> MemoryItem:
        now = utc_now_iso()
        item = MemoryItem(
            id=str(uuid4()),
            kind=kind,
            title=title,
            content=content,
            source=source,
            tags=tags or [],
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
            lifecycle=lifecycle,
            confidence=confidence,
            supersedes_id=supersedes_id,
        )

        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO memory_items (
                    id, kind, title, content, source, tags_json, metadata_json,
                    created_at, updated_at, lifecycle, confidence, supersedes_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.kind,
                    item.title,
                    item.content,
                    item.source,
                    json.dumps(item.tags),
                    json.dumps(item.metadata or {}),
                    item.created_at,
                    item.updated_at,
                    item.lifecycle,
                    item.confidence,
                    item.supersedes_id,
                ),
            )
            connection.commit()

        return item

    def get_memory(self, memory_id: str) -> MemoryItem | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM memory_items WHERE id = ?",
                (memory_id,),
            ).fetchone()

        return self._row_to_memory(row) if row else None

    def list_memory(
        self,
        *,
        limit: int = 50,
        kind: str | None = None,
        lifecycle: str | None = "active",
    ) -> list[MemoryItem]:
        query = "SELECT * FROM memory_items"
        clauses: list[str] = []
        params: list[Any] = []

        if kind:
            clauses.append("kind = ?")
            params.append(kind)

        if lifecycle:
            clauses.append("lifecycle = ?")
            params.append(lifecycle)

        if clauses:
            query += " WHERE " + " AND ".join(clauses)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()

        return [self._row_to_memory(row) for row in rows]

    def keyword_search(
        self,
        query: str,
        *,
        limit: int = 5,
        lifecycle: str | None = "active",
    ) -> list[MemoryItem]:
        normalized = f"%{query.strip()}%"

        if not query.strip():
            return []

        clauses = ["(title LIKE ? OR content LIKE ? OR tags_json LIKE ?)"]
        params: list[Any] = [normalized, normalized, normalized]

        if lifecycle:
            clauses.append("lifecycle = ?")
            params.append(lifecycle)

        params.append(limit)

        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM memory_items
                WHERE {' AND '.join(clauses)}
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()

        results = [self._row_to_memory(row) for row in rows]

        for item in results:
            item.score = 0.25

        return results

    def find_similar_keyword_memories(
        self,
        *,
        content: str,
        limit: int = 6,
    ) -> list[MemoryItem]:
        terms = [
            term.strip().lower()
            for term in content.replace(".", " ").replace(",", " ").split()
            if len(term.strip()) >= 4
        ]

        if not terms:
            return []

        clauses = []
        params: list[Any] = []

        for term in terms[:8]:
            clauses.append("(title LIKE ? OR content LIKE ? OR tags_json LIKE ?)")
            pattern = f"%{term}%"
            params.extend([pattern, pattern, pattern])

        params.append(limit)

        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM memory_items
                WHERE lifecycle = 'active'
                  AND ({' OR '.join(clauses)})
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()

        return [self._row_to_memory(row) for row in rows]

    def update_memory_lifecycle(
        self,
        *,
        memory_id: str,
        lifecycle: str,
        metadata_patch: dict[str, Any] | None = None,
    ) -> MemoryItem | None:
        item = self.get_memory(memory_id)

        if not item:
            return None

        metadata = item.metadata or {}
        metadata.update(metadata_patch or {})

        with self.connect() as connection:
            connection.execute(
                """
                UPDATE memory_items
                SET lifecycle = ?, metadata_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    lifecycle,
                    json.dumps(metadata),
                    utc_now_iso(),
                    memory_id,
                ),
            )
            connection.commit()

        return self.get_memory(memory_id)

    def save_memory_decision(
        self,
        *,
        session_id: str,
        decision: str,
        reason: str,
        memory_id: str | None = None,
        candidate: dict[str, Any] | None = None,
        confidence: float | None = None,
    ) -> str:
        decision_id = str(uuid4())

        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO memory_decisions (
                    id, session_id, decision, reason, memory_id, candidate_json, confidence, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision_id,
                    session_id,
                    decision,
                    reason,
                    memory_id,
                    json.dumps(candidate or {}),
                    confidence,
                    utc_now_iso(),
                ),
            )
            connection.commit()

        return decision_id

    def list_memory_decisions(
        self,
        *,
        session_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        params: list[Any] = []
        query = "SELECT * FROM memory_decisions"

        if session_id:
            query += " WHERE session_id = ?"
            params.append(session_id)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()

        return [
            {
                "id": row["id"],
                "session_id": row["session_id"],
                "decision": row["decision"],
                "reason": row["reason"],
                "memory_id": row["memory_id"],
                "candidate": json.loads(row["candidate_json"] or "{}"),
                "confidence": row["confidence"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def save_conversation_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        model: str | None = None,
        route: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        message_id = str(uuid4())

        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO conversation_messages (
                    id, session_id, role, content, model, route, metadata_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    session_id,
                    role,
                    content,
                    model,
                    route,
                    json.dumps(metadata or {}),
                    utc_now_iso(),
                ),
            )
            connection.commit()

        return message_id

    def list_conversation_messages(
        self,
        *,
        session_id: str,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM conversation_messages
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()

        return [self._conversation_row_to_dict(row) for row in reversed(rows)]

    def list_recent_conversation_messages(
        self,
        *,
        limit: int = 30,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        params: list[Any] = []
        query = "SELECT * FROM conversation_messages"

        if session_id:
            query += " WHERE session_id = ?"
            params.append(session_id)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()

        return [self._conversation_row_to_dict(row) for row in rows]

    def list_conversation_sessions(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    session_id,
                    COUNT(*) AS message_count,
                    MAX(created_at) AS last_message_at,
                    MIN(created_at) AS first_message_at
                FROM conversation_messages
                GROUP BY session_id
                ORDER BY last_message_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            {
                "session_id": row["session_id"],
                "message_count": row["message_count"],
                "first_message_at": row["first_message_at"],
                "last_message_at": row["last_message_at"],
            }
            for row in rows
        ]

    def search_conversation_messages(
        self,
        *,
        query: str,
        limit: int = 10,
        exclude_session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        terms = [term.strip() for term in query.split() if len(term.strip()) >= 3]

        if not terms:
            terms = [query.strip()] if query.strip() else []

        if not terms:
            return []

        where_clauses = []
        params: list[Any] = []

        for term in terms[:6]:
            where_clauses.append("content LIKE ?")
            params.append(f"%{term}%")

        sql = f"""
            SELECT *
            FROM conversation_messages
            WHERE ({' OR '.join(where_clauses)})
        """

        if exclude_session_id:
            sql += " AND session_id != ?"
            params.append(exclude_session_id)

        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self.connect() as connection:
            rows = connection.execute(sql, params).fetchall()

        return [self._conversation_row_to_dict(row) for row in rows]

    def _conversation_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "session_id": row["session_id"],
            "role": row["role"],
            "content": row["content"],
            "model": row["model"],
            "route": row["route"],
            "metadata": json.loads(row["metadata_json"] or "{}"),
            "created_at": row["created_at"],
        }

    def _row_to_memory(self, row: sqlite3.Row) -> MemoryItem:
        return MemoryItem(
            id=row["id"],
            kind=row["kind"],
            title=row["title"],
            content=row["content"],
            source=row["source"],
            tags=json.loads(row["tags_json"] or "[]"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=json.loads(row["metadata_json"] or "{}"),
            lifecycle=row["lifecycle"] if "lifecycle" in row.keys() else "active",
            confidence=row["confidence"] if "confidence" in row.keys() else None,
            supersedes_id=row["supersedes_id"] if "supersedes_id" in row.keys() else None,
        )
