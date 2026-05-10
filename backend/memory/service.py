from __future__ import annotations

from typing import Any

from core.config import settings
from llm.lmstudio_client import LMStudioAPIError, LMStudioClient, LMStudioConnectionError
from memory.dynamic_manager import MemoryDecision, decide_memory_actions, dynamic_memory_enabled
from memory.semantic_memory import extract_durable_memories_from_user_message
from memory.sqlite_memory import MemoryItem, SQLiteMemoryStore
from memory.vector_store import QdrantMemoryVectorStore


class MemoryService:
    """Serviq memory service.

    Process 13:
    - semantic memory remains SQLite + Qdrant
    - dynamic memory manager decides save/update/archive/ignore
    - active memories are recalled by semantic search only when the agent asks
    """

    def __init__(self, lmstudio_client: LMStudioClient | None = None) -> None:
        self.sqlite_store = SQLiteMemoryStore()
        self.lmstudio_client = lmstudio_client or LMStudioClient(
            base_url=settings.lmstudio_base_url,
            api_key=settings.lmstudio_api_key,
            timeout_seconds=settings.lmstudio_timeout_seconds,
        )
        self.vector_store = QdrantMemoryVectorStore()

    async def health(self) -> dict[str, Any]:
        qdrant = self.vector_store.health()
        embedding = await self.embedding_health()

        return {
            "status": "ok",
            "stage": "process-13-dynamic-memory-manager",
            "sqlite": {
                "status": "connected",
                "path": str(self.sqlite_store.database_path),
            },
            "qdrant": qdrant,
            "embedding": embedding,
            "semantic_memory_enabled": qdrant["status"] in {"connected", "not_initialized"} and embedding["status"] == "available",
            "dynamic_memory_enabled": dynamic_memory_enabled(),
        }

    async def embedding_health(self) -> dict[str, Any]:
        try:
            embedding = await self.lmstudio_client.create_embedding(
                model=settings.memory_embedding_model,
                input_text="Serviq embedding health check",
            )
        except (LMStudioConnectionError, LMStudioAPIError) as exc:
            return {
                "status": "unavailable",
                "model": settings.memory_embedding_model,
                "error": str(exc),
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "error",
                "model": settings.memory_embedding_model,
                "error": f"{type(exc).__name__}: {exc}",
            }

        return {
            "status": "available",
            "model": settings.memory_embedding_model,
            "dimensions": len(embedding),
        }

    async def create_embedding(self, text: str) -> list[float]:
        return await self.lmstudio_client.create_embedding(
            model=settings.memory_embedding_model,
            input_text=text,
        )

    def create_embedding_sync(self, text: str) -> list[float]:
        return self.lmstudio_client.create_embedding_sync(
            model=settings.memory_embedding_model,
            input_text=text,
            timeout_seconds=min(float(settings.lmstudio_timeout_seconds), 20.0),
        )

    def save_note(
        self,
        *,
        title: str,
        content: str,
        tags: list[str] | None = None,
        source: str | None = "manual_note",
        metadata: dict[str, Any] | None = None,
        embed: bool = True,
    ) -> dict[str, Any]:
        item = self.sqlite_store.add_memory(
            kind="note",
            title=title,
            content=content,
            source=source,
            tags=tags or [],
            metadata=metadata or {},
            confidence=1.0,
        )

        vector_status = None
        if embed:
            vector_status = self.embed_memory_item_sync(item)

        return {
            "item": self.memory_item_to_dict(item),
            "vector_status": vector_status,
        }

    async def save_memory(
        self,
        *,
        kind: str,
        title: str,
        content: str,
        source: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        embed: bool = True,
        confidence: float | None = None,
        supersedes_id: str | None = None,
    ) -> dict[str, Any]:
        item = self.sqlite_store.add_memory(
            kind=kind,
            title=title,
            content=content,
            source=source,
            tags=tags or [],
            metadata=metadata or {},
            confidence=confidence,
            supersedes_id=supersedes_id,
        )

        if supersedes_id:
            self.sqlite_store.update_memory_lifecycle(
                memory_id=supersedes_id,
                lifecycle="superseded",
                metadata_patch={"superseded_by": item.id},
            )

        vector_status = None
        if embed:
            vector_status = await self.embed_memory_item(item)

        return {
            "item": self.memory_item_to_dict(item),
            "vector_status": vector_status,
        }

    async def embed_memory_item(self, item: MemoryItem) -> dict[str, Any]:
        text = self.memory_text_for_embedding(item)
        embedding = await self.create_embedding(text)

        return self.vector_store.upsert_memory(
            memory_id=item.id,
            embedding=embedding,
            payload=self.memory_item_to_vector_payload(item),
        )

    def embed_memory_item_sync(self, item: MemoryItem) -> dict[str, Any]:
        try:
            text = self.memory_text_for_embedding(item)
            embedding = self.create_embedding_sync(text)
            return self.vector_store.upsert_memory(
                memory_id=item.id,
                embedding=embedding,
                payload=self.memory_item_to_vector_payload(item),
            )
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "embedding_failed",
                "error": f"{type(exc).__name__}: {exc}",
                "model": settings.memory_embedding_model,
            }

    async def review_conversation_for_memory(
        self,
        *,
        session_id: str,
        user_message: str,
        assistant_message: str,
        model: str | None = None,
        route: str | None = None,
    ) -> dict[str, Any]:
        if not dynamic_memory_enabled():
            return {
                "enabled": False,
                "decisions": [],
                "saved": [],
                "archived": [],
            }

        similar = [
            self.memory_item_to_dict(item)
            for item in self.sqlite_store.find_similar_keyword_memories(
                content=user_message,
                limit=8,
            )
        ]

        decisions = await decide_memory_actions(
            lmstudio_client=self.lmstudio_client,
            model=model or "",
            user_message=user_message,
            assistant_message=assistant_message,
            similar_memories=similar,
        )

        saved: list[dict[str, Any]] = []
        archived: list[dict[str, Any]] = []

        for decision in decisions:
            self.sqlite_store.save_memory_decision(
                session_id=session_id,
                decision=decision.action,
                reason=decision.reason,
                memory_id=decision.target_memory_id or decision.supersedes_id,
                candidate=self.memory_decision_to_dict(decision),
                confidence=decision.confidence,
            )

            if decision.action in {"save", "update"} and decision.content and decision.title:
                item = self.sqlite_store.add_memory(
                    kind=decision.kind,
                    title=decision.title,
                    content=decision.content,
                    source=f"dynamic_memory:{decision.source}",
                    tags=[*decision.tags, "dynamic"],
                    metadata={
                        "session_id": session_id,
                        "model": model,
                        "route": route,
                        "decision_reason": decision.reason,
                        "dynamic_memory": True,
                    },
                    confidence=decision.confidence,
                    supersedes_id=decision.supersedes_id,
                )

                if decision.supersedes_id:
                    self.sqlite_store.update_memory_lifecycle(
                        memory_id=decision.supersedes_id,
                        lifecycle="superseded",
                        metadata_patch={"superseded_by": item.id},
                    )

                vector_status = self.embed_memory_item_sync(item)
                saved.append(
                    {
                        "item": self.memory_item_to_dict(item),
                        "vector_status": vector_status,
                    }
                )

            elif decision.action == "archive" and decision.target_memory_id:
                archived_item = self.sqlite_store.update_memory_lifecycle(
                    memory_id=decision.target_memory_id,
                    lifecycle="archived",
                    metadata_patch={
                        "archived_by": "dynamic_memory_manager",
                        "archive_reason": decision.reason,
                    },
                )

                if archived_item:
                    archived.append(self.memory_item_to_dict(archived_item))

        return {
            "enabled": True,
            "decisions": [self.memory_decision_to_dict(decision) for decision in decisions],
            "saved": saved,
            "archived": archived,
        }

    def save_conversation_pair(
        self,
        *,
        session_id: str,
        user_message: str,
        assistant_message: str,
        model: str | None = None,
        route: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.sqlite_store.save_conversation_message(
            session_id=session_id,
            role="user",
            content=user_message,
            model=model,
            route=route,
            metadata=metadata or {},
        )
        self.sqlite_store.save_conversation_message(
            session_id=session_id,
            role="assistant",
            content=assistant_message,
            model=model,
            route=route,
            metadata=metadata or {},
        )

        # Backward-compatible deterministic extractor for explicit "remember"
        # messages when async dynamic review is not called by older routes.
        extracted = extract_durable_memories_from_user_message(user_message)
        saved_memories = []

        for memory in extracted:
            existing = self.sqlite_store.find_similar_keyword_memories(content=memory.content, limit=4)
            if any(item.content.lower() == memory.content.lower() and item.lifecycle == "active" for item in existing):
                continue

            item = self.sqlite_store.add_memory(
                kind="fact",
                title=memory.title,
                content=memory.content,
                source="conversation_auto_extract_compat",
                tags=memory.tags,
                metadata={
                    "session_id": session_id,
                    "model": model,
                    "route": route,
                    "auto_extracted": True,
                },
                confidence=0.9,
            )
            vector_status = self.embed_memory_item_sync(item)
            saved_memories.append(
                {
                    "item": self.memory_item_to_dict(item),
                    "vector_status": vector_status,
                }
            )

        return {
            "conversation_saved": True,
            "auto_memory_count": len(saved_memories),
            "auto_memories": saved_memories,
        }

    async def search_memory(self, *, query: str, limit: int = 5) -> dict[str, Any]:
        keyword_items = self.sqlite_store.keyword_search(query, limit=limit, lifecycle="active")
        semantic_items: list[dict[str, Any]] = []
        semantic_error: str | None = None

        try:
            embedding = await self.create_embedding(query)
            semantic_results = await self.vector_store.search(embedding=embedding, limit=limit)

            for result in semantic_results:
                payload = result.get("payload") if isinstance(result, dict) else {}
                if not isinstance(payload, dict):
                    continue

                if payload.get("lifecycle", "active") != "active":
                    continue

                payload["score"] = result.get("score")
                semantic_items.append(payload)

        except Exception as exc:  # noqa: BLE001
            semantic_error = f"{type(exc).__name__}: {exc}"

        combined: list[dict[str, Any]] = []
        seen: set[str] = set()

        for item in semantic_items:
            memory_id = str(item.get("id", ""))
            if memory_id and memory_id not in seen:
                seen.add(memory_id)
                combined.append(item)

        for item in keyword_items:
            item_dict = self.memory_item_to_dict(item)
            memory_id = item_dict["id"]
            if memory_id not in seen:
                seen.add(memory_id)
                combined.append(item_dict)

        if semantic_items and keyword_items:
            mode = "hybrid_semantic_keyword"
        elif semantic_items:
            mode = "semantic_qdrant"
        elif keyword_items:
            mode = "keyword_sqlite_fallback"
        else:
            mode = "empty"

        if semantic_error and keyword_items:
            mode = "keyword_sqlite_fallback"

        return {
            "query": query,
            "mode": mode,
            "items": combined[:limit],
            "semantic_count": len(semantic_items),
            "keyword_count": len(keyword_items),
            "error": semantic_error,
            "embedding_model": settings.memory_embedding_model,
            "qdrant_collection": settings.qdrant_collection,
        }

    def list_memory(
        self,
        *,
        limit: int = 50,
        kind: str | None = None,
        lifecycle: str | None = "active",
    ) -> list[dict[str, Any]]:
        return [
            self.memory_item_to_dict(item)
            for item in self.sqlite_store.list_memory(limit=limit, kind=kind, lifecycle=lifecycle)
        ]

    def list_memory_decisions(self, *, session_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        return self.sqlite_store.list_memory_decisions(session_id=session_id, limit=limit)

    def memory_text_for_embedding(self, item: MemoryItem) -> str:
        tags = ", ".join(item.tags)
        return (
            f"Title: {item.title}\n"
            f"Kind: {item.kind}\n"
            f"Lifecycle: {item.lifecycle}\n"
            f"Tags: {tags}\n"
            f"Content: {item.content}"
        )

    def memory_item_to_vector_payload(self, item: MemoryItem) -> dict[str, Any]:
        payload = self.memory_item_to_dict(item)
        payload["text"] = self.memory_text_for_embedding(item)
        return payload

    def memory_item_to_dict(self, item: MemoryItem) -> dict[str, Any]:
        return {
            "id": item.id,
            "kind": item.kind,
            "title": item.title,
            "content": item.content,
            "source": item.source,
            "tags": item.tags,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "score": item.score,
            "metadata": item.metadata or {},
            "lifecycle": item.lifecycle,
            "confidence": item.confidence,
            "supersedes_id": item.supersedes_id,
        }

    def memory_decision_to_dict(self, decision: MemoryDecision) -> dict[str, Any]:
        return {
            "action": decision.action,
            "reason": decision.reason,
            "title": decision.title,
            "content": decision.content,
            "kind": decision.kind,
            "tags": decision.tags,
            "confidence": decision.confidence,
            "target_memory_id": decision.target_memory_id,
            "supersedes_id": decision.supersedes_id,
            "source": decision.source,
            "raw": decision.raw,
        }
