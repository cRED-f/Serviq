from __future__ import annotations

from typing import Any

from agent.prompts import get_merged_system_prompt, classify_message_locally
from llm.lmstudio_client import LMStudioClient


async def run_direct_agent(
    *,
    lmstudio_client: LMStudioClient,
    session_id: str,
    model: str,
    user_message: str,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Production-shaped direct agent runner.

    This runner intentionally avoids LangGraph so we can verify the Serviq
    agent API contract is stable before reintroducing graph orchestration.
    """

    steps = [
        "prepare_context",
        "classify_request",
        "call_local_model",
        "finalize_response",
    ]

    cleaned_history = [
        message
        for message in (history or [])
        if message.get("role") in {"user", "assistant", "system"} and message.get("content")
    ]

    route = classify_message_locally(user_message)

    messages = [
        {
            "role": "system",
            "content": get_merged_system_prompt(),
        },
        *cleaned_history[-8:],
        {
            "role": "user",
            "content": user_message,
        },
    ]

    payload = await lmstudio_client.chat_completion(
        model=model,
        messages=messages,
        temperature=0.2,
    )

    content = (
        payload.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )

    return {
        "session_id": session_id,
        "model": model,
        "route": route,
        "response": content or "The local model returned an empty response.",
        "steps": steps,
        "metadata": {
            "provider": "lmstudio",
            "runtime": "direct-agent",
            "agent_version": "process-4b-direct-unblock",
            "raw_model": payload.get("model"),
            "usage": payload.get("usage"),
            "completed": True,
        },
    }
