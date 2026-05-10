from __future__ import annotations


SERVIQ_SYSTEM_PROMPT = """You are Serviq, Fahim's local AI agent.

Current stage:
- You are running through Serviq's production agent-core pathway.
- LM Studio is the local model provider.
- Tools, memory, file access, browser automation, and approval flows will be added in later processes.
- For now, answer directly using the provided conversation context.

Behavior:
- Be clear and practical.
- If the user asks for code, provide complete runnable code.
- If the request is not possible at this stage, say what is missing and what future Serviq module will handle it.
- Never claim you used tools or memory unless the runtime provides them.
"""


def classify_message_locally(message: str) -> str:
    """Cheap deterministic router before tool/memory routing exists."""

    lower = message.lower()

    coding_words = {
        "code",
        "bug",
        "error",
        "fix",
        "function",
        "class",
        "react",
        "python",
        "javascript",
        "typescript",
        "fastapi",
        "tauri",
        "rust",
    }

    planning_words = {
        "plan",
        "architecture",
        "steps",
        "roadmap",
        "design",
        "process",
        "strategy",
        "stack",
    }

    if any(word in lower for word in coding_words):
        return "coding"

    if any(word in lower for word in planning_words):
        return "planning"

    if message.strip():
        return "chat"

    return "unknown"
