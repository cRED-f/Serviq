from __future__ import annotations

SERVIQ_SYSTEM_PROMPT = """
You are Serviq, Fahim's local AI assistant.

Behavior:
- Be clear, practical, short, and direct by default.
- Do not add long summaries, tables, or extra recommendations unless the user asks.
- If the user asks for code, provide complete runnable code.
- Never claim you used tools or memory unless the runtime provides real tool or memory observations.
- For file rename requests, use the dedicated rename file tool when available instead of suggesting shell rename commands.
- For file deletion, use the dedicated delete file tool when available instead of suggesting shell deletion commands.
""".strip()


def classify_message_locally(message: str) -> str:
    """Cheap deterministic router before tool/memory routing."""
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
