from __future__ import annotations

from typing import Any

import httpx

from core.config import settings


class QdrantMemoryVectorStore:
    """Minimal Qdrant HTTP client for Serviq semantic memory."""

    def __init__(
        self,
        *,
        url: str | None = None,
        collection: str | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.url = (url or settings.qdrant_url).rstrip("/")
        self.collection = collection or settings.qdrant_collection
        self.timeout_seconds = timeout_seconds

    def health(self) -> dict[str, Any]:
        try:
            response = httpx.get(f"{self.url}/collections/{self.collection}", timeout=self.timeout_seconds)
        except httpx.HTTPError as exc:
            return {
                "status": "unavailable",
                "url": self.url,
                "collection": self.collection,
                "error": str(exc),
            }

        if response.status_code == 404:
            return {
                "status": "not_initialized",
                "url": self.url,
                "collection": self.collection,
            }

        if response.status_code >= 400:
            return {
                "status": "error",
                "url": self.url,
                "collection": self.collection,
                "error": response.text,
            }

        payload = response.json()
        result = payload.get("result", {}) if isinstance(payload, dict) else {}

        return {
            "status": "connected",
            "url": self.url,
            "collection": self.collection,
            "result": result,
        }

    def ensure_collection(self, *, vector_size: int) -> dict[str, Any]:
        health = self.health()

        if health["status"] == "connected":
            return health

        if health["status"] not in {"not_initialized", "error"}:
            return health

        body = {
            "vectors": {
                "size": vector_size,
                "distance": "Cosine",
            }
        }

        try:
            response = httpx.put(
                f"{self.url}/collections/{self.collection}",
                json=body,
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            return {
                "status": "unavailable",
                "url": self.url,
                "collection": self.collection,
                "error": str(exc),
            }

        if response.status_code >= 400:
            return {
                "status": "error",
                "url": self.url,
                "collection": self.collection,
                "error": response.text,
            }

        return {
            "status": "created",
            "url": self.url,
            "collection": self.collection,
            "vector_size": vector_size,
        }

    def upsert_memory(
        self,
        *,
        memory_id: str,
        embedding: list[float],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        collection_status = self.ensure_collection(vector_size=len(embedding))

        if collection_status["status"] not in {"connected", "created"}:
            return {
                "status": "skipped",
                "reason": "Qdrant collection is unavailable.",
                "collection_status": collection_status,
            }

        body = {
            "points": [
                {
                    "id": memory_id,
                    "vector": embedding,
                    "payload": payload,
                }
            ]
        }

        try:
            response = httpx.put(
                f"{self.url}/collections/{self.collection}/points?wait=true",
                json=body,
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            return {
                "status": "unavailable",
                "error": str(exc),
            }

        if response.status_code >= 400:
            return {
                "status": "error",
                "error": response.text,
            }

        return {
            "status": "upserted",
            "memory_id": memory_id,
            "vector_size": len(embedding),
        }

    async def search(
        self,
        *,
        embedding: list[float],
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        body = {
            "vector": embedding,
            "limit": limit,
            "with_payload": True,
            "with_vector": False,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.url}/collections/{self.collection}/points/search",
                    json=body,
                )
        except httpx.HTTPError:
            return []

        if response.status_code >= 400:
            return []

        payload = response.json()
        result = payload.get("result", []) if isinstance(payload, dict) else []
        return result if isinstance(result, list) else []
