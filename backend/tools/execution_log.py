from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

from memory.sqlite_memory import utc_now_iso
from core.config import settings


class ToolExecutionLogStore:
    """SQLite log store for tool executions and approval decisions."""

    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path or settings.workspace_path / "serviq_tools.sqlite3"
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
                CREATE TABLE IF NOT EXISTS tool_execution_logs (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    risk TEXT NOT NULL,
                    args_json TEXT NOT NULL,
                    ok INTEGER NOT NULL,
                    approval_required INTEGER NOT NULL,
                    output_json TEXT,
                    error TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tool_logs_session
                ON tool_execution_logs(session_id, created_at)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tool_logs_tool
                ON tool_execution_logs(tool_name, created_at)
                """
            )
            connection.commit()

    def add_log(
        self,
        *,
        session_id: str,
        tool_name: str,
        risk: str,
        args: dict[str, Any],
        ok: bool,
        approval_required: bool,
        output: Any = None,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        log_id = str(uuid4())

        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO tool_execution_logs (
                    id, session_id, tool_name, risk, args_json, ok, approval_required,
                    output_json, error, metadata_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log_id,
                    session_id,
                    tool_name,
                    risk,
                    json.dumps(args),
                    1 if ok else 0,
                    1 if approval_required else 0,
                    json.dumps(output, default=str) if output is not None else None,
                    error,
                    json.dumps(metadata or {}),
                    utc_now_iso(),
                ),
            )
            connection.commit()

        return log_id

    def list_logs(self, *, limit: int = 50, session_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM tool_execution_logs"
        params: list[Any] = []

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
                "tool_name": row["tool_name"],
                "risk": row["risk"],
                "args": json.loads(row["args_json"] or "{}"),
                "ok": bool(row["ok"]),
                "approval_required": bool(row["approval_required"]),
                "output": json.loads(row["output_json"]) if row["output_json"] else None,
                "error": row["error"],
                "metadata": json.loads(row["metadata_json"] or "{}"),
                "created_at": row["created_at"],
            }
            for row in rows
        ]
