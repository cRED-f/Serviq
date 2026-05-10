from __future__ import annotations

from typing import Any

import httpx


class LMStudioConnectionError(RuntimeError):
    """Raised when Serviq cannot connect to LM Studio."""


class LMStudioAPIError(RuntimeError):
    """Raised when LM Studio returns a non-success API response."""


class LMStudioClient:
    """Small OpenAI-compatible LM Studio client used by Serviq.

    Process 12B compatibility:
    - Restores `health()` used by `/api/llm/health`.
    - Restores `normalized_base_url` used by `/api/llm/models`.
    - Keeps embedding support for semantic memory.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str = "lm-studio",
        timeout_seconds: float = 90.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    @property
    def normalized_base_url(self) -> str:
        """Compatibility alias for older API routes."""

        return self.base_url

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def health(self) -> dict[str, Any]:
        """Compatibility health method used by `backend/api/routes/llm.py`."""

        try:
            models = await self.list_models()
        except LMStudioConnectionError as exc:
            return {
                "status": "offline",
                "base_url": self.base_url,
                "normalized_base_url": self.normalized_base_url,
                "models": [],
                "model_count": 0,
                "error": str(exc),
            }
        except LMStudioAPIError as exc:
            return {
                "status": "error",
                "base_url": self.base_url,
                "normalized_base_url": self.normalized_base_url,
                "models": [],
                "model_count": 0,
                "error": str(exc),
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "error",
                "base_url": self.base_url,
                "normalized_base_url": self.normalized_base_url,
                "models": [],
                "model_count": 0,
                "error": f"{type(exc).__name__}: {exc}",
            }

        return {
            "status": "connected",
            "base_url": self.base_url,
            "normalized_base_url": self.normalized_base_url,
            "models": models,
            "model_count": len(models),
        }

    async def list_models(self) -> list[dict[str, Any]]:
        payload = await self._get("/models")
        data = payload.get("data", [])
        return data if isinstance(data, list) else []

    async def chat_completion(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

        if max_tokens is not None:
            body["max_tokens"] = max_tokens

        return await self._post("/chat/completions", body)

    async def create_embedding(
        self,
        *,
        model: str,
        input_text: str,
    ) -> list[float]:
        payload = await self._post(
            "/embeddings",
            {
                "model": model,
                "input": input_text,
            },
        )

        data = payload.get("data")
        if not isinstance(data, list) or not data:
            raise LMStudioAPIError("LM Studio embedding response did not include data.")

        first = data[0]
        if not isinstance(first, dict):
            raise LMStudioAPIError("LM Studio embedding response item was invalid.")

        embedding = first.get("embedding")
        if not isinstance(embedding, list) or not embedding:
            raise LMStudioAPIError("LM Studio embedding response did not include an embedding vector.")

        return [float(value) for value in embedding]

    def create_embedding_sync(
        self,
        *,
        model: str,
        input_text: str,
        timeout_seconds: float | None = None,
    ) -> list[float]:
        payload = self._post_sync(
            "/embeddings",
            {
                "model": model,
                "input": input_text,
            },
            timeout_seconds=timeout_seconds,
        )

        data = payload.get("data")
        if not isinstance(data, list) or not data:
            raise LMStudioAPIError("LM Studio embedding response did not include data.")

        first = data[0]
        if not isinstance(first, dict):
            raise LMStudioAPIError("LM Studio embedding response item was invalid.")

        embedding = first.get("embedding")
        if not isinstance(embedding, list) or not embedding:
            raise LMStudioAPIError("LM Studio embedding response did not include an embedding vector.")

        return [float(value) for value in embedding]

    async def _get(self, path: str) -> dict[str, Any]:
        url = f"{self.base_url}{path}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(url, headers=self.headers)
        except httpx.HTTPError as exc:
            raise LMStudioConnectionError(f"Unable to connect to LM Studio at {url}: {exc}") from exc

        if response.status_code >= 400:
            raise LMStudioAPIError(
                f"LM Studio request failed with status {response.status_code}: {response.text}"
            )

        payload = response.json()
        return payload if isinstance(payload, dict) else {}

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(url, headers=self.headers, json=body)
        except httpx.HTTPError as exc:
            raise LMStudioConnectionError(f"Unable to connect to LM Studio at {url}: {exc}") from exc

        if response.status_code >= 400:
            raise LMStudioAPIError(
                f"LM Studio request failed with status {response.status_code}: {response.text}"
            )

        payload = response.json()
        return payload if isinstance(payload, dict) else {}

    def _post_sync(
        self,
        path: str,
        body: dict[str, Any],
        *,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"

        try:
            with httpx.Client(timeout=timeout_seconds or self.timeout_seconds) as client:
                response = client.post(url, headers=self.headers, json=body)
        except httpx.HTTPError as exc:
            raise LMStudioConnectionError(f"Unable to connect to LM Studio at {url}: {exc}") from exc

        if response.status_code >= 400:
            raise LMStudioAPIError(
                f"LM Studio request failed with status {response.status_code}: {response.text}"
            )

        payload = response.json()
        return payload if isinstance(payload, dict) else {}
