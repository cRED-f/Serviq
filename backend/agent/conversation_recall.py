from __future__ import annotations

import os
from typing import Any

from memory.service import MemoryService


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw_value = os.getenv(name, str(default))

    try:
        value = int(raw_value)
    except ValueError:
        return default

    return max(minimum, min(value, maximum))


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value

    return value[:limit] + "\n...[truncated]"


def _format_message(message: dict[str, Any], *, max_chars: int = 800) -> str:
    role = message.get("role", "unknown")
    content = str(message.get("content", ""))
    created_at = message.get("created_at", "")
    session_id = message.get("session_id", "")

    return (
        f"- [{created_at}] session={session_id} role={role}\n"
        f"  {_truncate(content, max_chars).replace(chr(10), chr(10) + '  ')}"
    )


class ConversationRecallService:
    """Builds compact conversation recall context for the agent.

    This is intentionally lightweight:
    - current session recall gives continuity across backend restarts/UI refreshes.
    - related past messages provide cross-session recall by keyword search.
    """

    def __init__(self, memory_service: MemoryService) -> None:
        self.memory_service = memory_service
        self.sqlite_store = memory_service.sqlite_store

    async def recall(
        self,
        *,
        session_id: str,
        user_message: str,
    ) -> dict[str, Any]:
        max_session_messages = _env_int(
            "CONVERSATION_RECALL_SESSION_MESSAGES",
            12,
            minimum=0,
            maximum=40,
        )
        max_related_messages = _env_int(
            "CONVERSATION_RECALL_RELATED_MESSAGES",
            6,
            minimum=0,
            maximum=20,
        )
        max_context_chars = _env_int(
            "CONVERSATION_RECALL_MAX_CONTEXT_CHARS",
            6000,
            minimum=1000,
            maximum=20000,
        )

        session_messages = []
        related_messages = []

        if max_session_messages > 0:
            session_messages = self.sqlite_store.list_conversation_messages(
                session_id=session_id,
                limit=max_session_messages,
            )

        if max_related_messages > 0:
            related_messages = self.sqlite_store.search_conversation_messages(
                query=user_message,
                limit=max_related_messages,
                exclude_session_id=session_id,
            )

        context_parts = []

        if session_messages:
            context_parts.append(
                "CURRENT SESSION RECALL\n"
                "These are previously saved messages from this same session. "
                "Use them for continuity when relevant.\n"
                + "\n".join(_format_message(message) for message in session_messages)
            )

        if related_messages:
            context_parts.append(
                "RELATED PAST CONVERSATION RECALL\n"
                "These are keyword-related messages from other sessions. "
                "Use only when clearly relevant.\n"
                + "\n".join(_format_message(message) for message in related_messages)
            )

        context_text = "\n\n".join(context_parts)
        context_text = _truncate(context_text, max_context_chars)

        return {
            "context_text": context_text,
            "session_messages": session_messages,
            "related_messages": related_messages,
            "session_message_count": len(session_messages),
            "related_message_count": len(related_messages),
        }
