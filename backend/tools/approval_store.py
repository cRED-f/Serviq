from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.config import settings
from memory.sqlite_memory import utc_now_iso


class ApprovalNotFoundError(RuntimeError):
    """Raised when an approval request cannot be found."""


class ApprovalStateError(RuntimeError):
    """Raised when an approval request is in the wrong state."""


class ToolApprovalStore:
    """SQLite store for human approval requests."""

    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path or settings.workspace_path / "serviq_approvals.sqlite3"
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
                CREATE TABLE IF NOT EXISTS tool_approval_requests (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    risk TEXT NOT NULL,
                    args_json TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    decided_at TEXT,
                    executed_at TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_approval_status
                ON tool_approval_requests(status, created_at)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_approval_session
                ON tool_approval_requests(session_id, created_at)
                """
            )
            connection.commit()

    def create_request(
        self,
        *,
        session_id: str,
        tool_name: str,
        risk: str,
        args: dict[str, Any],
        reason: str,
    ) -> dict[str, Any]:
        approval_id = str(uuid4())
        now = utc_now_iso()

        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO tool_approval_requests (
                    id, session_id, tool_name, risk, args_json, reason, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    approval_id,
                    session_id,
                    tool_name,
                    risk,
                    json.dumps(args),
                    reason,
                    "pending",
                    now,
                ),
            )
            connection.commit()

        request = self.get_request(approval_id)
        if not request:
            raise ApprovalNotFoundError(f"Approval request was not created: {approval_id}")

        return request

    def list_requests(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM tool_approval_requests"
        params: list[Any] = []

        if status:
            query += " WHERE status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()

        return [self._row_to_dict(row) for row in rows]

    def get_request(self, approval_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM tool_approval_requests WHERE id = ?",
                (approval_id,),
            ).fetchone()

        return self._row_to_dict(row) if row else None

    def mark_rejected(self, approval_id: str) -> dict[str, Any]:
        request = self.get_request(approval_id)
        if not request:
            raise ApprovalNotFoundError(f"Approval request not found: {approval_id}")

        if request["status"] != "pending":
            raise ApprovalStateError(
                f"Only pending requests can be rejected. Current status: {request['status']}"
            )

        with self.connect() as connection:
            connection.execute(
                """
                UPDATE tool_approval_requests
                SET status = ?, decided_at = ?
                WHERE id = ?
                """,
                ("rejected", utc_now_iso(), approval_id),
            )
            connection.commit()

        updated = self.get_request(approval_id)
        if not updated:
            raise ApprovalNotFoundError(f"Approval request not found after reject: {approval_id}")

        return updated

    def mark_approved(self, approval_id: str) -> dict[str, Any]:
        request = self.get_request(approval_id)
        if not request:
            raise ApprovalNotFoundError(f"Approval request not found: {approval_id}")

        if request["status"] != "pending":
            raise ApprovalStateError(
                f"Only pending requests can be approved. Current status: {request['status']}"
            )

        with self.connect() as connection:
            connection.execute(
                """
                UPDATE tool_approval_requests
                SET status = ?, decided_at = ?
                WHERE id = ?
                """,
                ("approved", utc_now_iso(), approval_id),
            )
            connection.commit()

        updated = self.get_request(approval_id)
        if not updated:
            raise ApprovalNotFoundError(f"Approval request not found after approve: {approval_id}")

        return updated

    def mark_executed(
        self,
        approval_id: str,
        *,
        ok: bool,
        result: Any = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        request = self.get_request(approval_id)
        if not request:
            raise ApprovalNotFoundError(f"Approval request not found: {approval_id}")

        with self.connect() as connection:
            connection.execute(
                """
                UPDATE tool_approval_requests
                SET status = ?, result_json = ?, error = ?, executed_at = ?
                WHERE id = ?
                """,
                (
                    "executed" if ok else "failed",
                    json.dumps(result, default=str) if result is not None else None,
                    error,
                    utc_now_iso(),
                    approval_id,
                ),
            )
            connection.commit()

        updated = self.get_request(approval_id)
        if not updated:
            raise ApprovalNotFoundError(f"Approval request not found after execution: {approval_id}")

        return updated

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "session_id": row["session_id"],
            "tool_name": row["tool_name"],
            "risk": row["risk"],
            "args": json.loads(row["args_json"] or "{}"),
            "reason": row["reason"],
            "status": row["status"],
            "result": json.loads(row["result_json"]) if row["result_json"] else None,
            "error": row["error"],
            "created_at": row["created_at"],
            "decided_at": row["decided_at"],
            "executed_at": row["executed_at"],
        }
