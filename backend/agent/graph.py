from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from langgraph.graph import END, START, StateGraph
except ModuleNotFoundError:  # pragma: no cover - runtime dependency guard.
    END = None
    START = None
    StateGraph = None  # type: ignore[assignment]

from agent.prompts import SERVIQ_SYSTEM_PROMPT, classify_message_locally
from agent.state import ServiqAgentState
from llm.lmstudio_client import LMStudioClient


class LangGraphNotInstalledError(RuntimeError):
    """Raised when the LangGraph dependency is missing."""


class ServiqAgentRuntimeError(RuntimeError):
    """Raised when the Serviq agent graph fails during execution."""


def ensure_langgraph_available() -> None:
    if StateGraph is None or START is None or END is None:
        raise LangGraphNotInstalledError(
            "LangGraph is not installed. Run: .\\.venv\\Scripts\\pip install langgraph typing_extensions"
        )


@dataclass(slots=True)
class ServiqAgentRunner:
    """Production-shaped Serviq agent runner backed by LangGraph."""

    lmstudio_client: LMStudioClient

    def __post_init__(self) -> None:
        ensure_langgraph_available()
        self.graph = self._build_graph()

    def _build_graph(self):  # noqa: ANN202 - LangGraph compiled type changes by version.
        workflow = StateGraph(ServiqAgentState)

        workflow.add_node("prepare_context", self.prepare_context)
        workflow.add_node("classify_request", self.classify_request)
        workflow.add_node("call_local_model", self.call_local_model)
        workflow.add_node("finalize_response", self.finalize_response)

        workflow.add_edge(START, "prepare_context")
        workflow.add_edge("prepare_context", "classify_request")
        workflow.add_edge("classify_request", "call_local_model")
        workflow.add_edge("call_local_model", "finalize_response")
        workflow.add_edge("finalize_response", END)

        return workflow.compile()

    async def run(
        self,
        *,
        session_id: str,
        model: str,
        user_message: str,
        history: list[dict[str, str]] | None = None,
    ) -> ServiqAgentState:
        initial_state: ServiqAgentState = {
            "session_id": session_id,
            "model": model,
            "user_message": user_message,
            "messages": history or [],
            "steps": [],
            "metadata": {
                "provider": "lmstudio",
                "runtime": "langgraph",
                "agent_version": "process-4",
            },
            "error": None,
        }

        try:
            return await self.graph.ainvoke(initial_state)
        except Exception as exc:  # noqa: BLE001
            raise ServiqAgentRuntimeError(f"{type(exc).__name__}: {exc}") from exc

    async def prepare_context(self, state: ServiqAgentState) -> ServiqAgentState:
        steps = [*state.get("steps", []), "prepare_context"]

        existing_messages = [
            message
            for message in state.get("messages", [])
            if message.get("role") in {"user", "assistant", "system"} and message.get("content")
        ]

        user_message = state.get("user_message", "")

        prepared_messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": SERVIQ_SYSTEM_PROMPT,
            },
            *existing_messages[-8:],
            {
                "role": "user",
                "content": user_message,
            },
        ]

        return {
            **state,
            "messages": prepared_messages,
            "steps": steps,
        }

    async def classify_request(self, state: ServiqAgentState) -> ServiqAgentState:
        steps = [*state.get("steps", []), "classify_request"]
        route = classify_message_locally(state.get("user_message", ""))

        metadata = {
            **state.get("metadata", {}),
            "route_reason": "local keyword classifier; LLM/router tools will be added later",
        }

        return {
            **state,
            "route": route,  # type: ignore[typeddict-item]
            "metadata": metadata,
            "steps": steps,
        }

    async def call_local_model(self, state: ServiqAgentState) -> ServiqAgentState:
        steps = [*state.get("steps", []), "call_local_model"]

        payload = await self.lmstudio_client.chat_completion(
            model=state["model"],
            messages=state["messages"],
            temperature=0.2,
        )

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ServiqAgentRuntimeError(
                f"LM Studio returned no choices. Raw response keys: {list(payload.keys())}"
            )

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ServiqAgentRuntimeError("LM Studio returned an invalid first choice object.")

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise ServiqAgentRuntimeError("LM Studio returned a choice without a message object.")

        content = message.get("content")
        response = content if isinstance(content, str) else ""

        metadata: dict[str, Any] = {
            **state.get("metadata", {}),
            "raw_model": payload.get("model"),
            "usage": payload.get("usage"),
        }

        return {
            **state,
            "response": response or "The local model returned an empty response.",
            "metadata": metadata,
            "steps": steps,
        }

    async def finalize_response(self, state: ServiqAgentState) -> ServiqAgentState:
        steps = [*state.get("steps", []), "finalize_response"]

        metadata = {
            **state.get("metadata", {}),
            "completed": True,
        }

        return {
            **state,
            "steps": steps,
            "metadata": metadata,
        }
