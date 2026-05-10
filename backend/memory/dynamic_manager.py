from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from llm.lmstudio_client import LMStudioAPIError, LMStudioClient
from memory.semantic_memory import extract_durable_memories_from_user_message


MemoryDecisionAction = Literal["save", "update", "archive", "ignore"]


@dataclass(slots=True)
class MemoryDecision:
    action: MemoryDecisionAction
    reason: str
    title: str | None = None
    content: str | None = None
    kind: str = "fact"
    tags: list[str] = field(default_factory=list)
    confidence: float = 0.0
    target_memory_id: str | None = None
    supersedes_id: str | None = None
    raw: str | None = None
    source: str = "unknown"


def dynamic_memory_enabled() -> bool:
    return os.getenv("DYNAMIC_MEMORY_ENABLED", "true").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def memory_manager_model_enabled() -> bool:
    return os.getenv("DYNAMIC_MEMORY_USE_MODEL", "true").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def memory_save_threshold() -> float:
    raw = os.getenv("DYNAMIC_MEMORY_SAVE_THRESHOLD", "0.74")
    try:
        value = float(raw)
    except ValueError:
        return 0.74

    return max(0.0, min(value, 1.0))


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()

    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped, flags=re.IGNORECASE).strip()
        stripped = re.sub(r"```$", "", stripped).strip()

    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    end = stripped.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError("Memory manager response did not contain JSON.")

    parsed = json.loads(stripped[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Memory manager response JSON was not an object.")

    return parsed


def _as_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, int | float):
        return max(0.0, min(float(value), 1.0))

    return default


def _is_sensitive_or_temporary(text: str) -> bool:
    lower = text.lower()

    sensitive_terms = [
        "password",
        "secret key",
        "api key",
        "token",
        "otp",
        "credit card",
        "private key",
        "seed phrase",
    ]

    if any(term in lower for term in sensitive_terms):
        return True

    temporary_terms = [
        "today i feel",
        "right now",
        "for now",
        "temporary",
        "just now",
        "currently tired",
    ]

    return any(term in lower for term in temporary_terms)


def _deterministic_decisions(
    *,
    user_message: str,
    assistant_message: str,
    similar_memories: list[dict[str, Any]],
) -> list[MemoryDecision]:
    decisions: list[MemoryDecision] = []

    if _is_sensitive_or_temporary(user_message):
        return [
            MemoryDecision(
                action="ignore",
                reason="Message appears sensitive or temporary.",
                confidence=0.95,
                source="deterministic_safety",
            )
        ]

    extracted = extract_durable_memories_from_user_message(user_message)

    for memory in extracted:
        supersedes_id = None
        lower_content = memory.content.lower()

        for existing in similar_memories:
            existing_content = str(existing.get("content", "")).lower()
            existing_id = str(existing.get("id", ""))

            # Simple supersede heuristic: same broad subject and new statement.
            if existing_id and (
                ("prefer" in lower_content and "prefer" in existing_content)
                or ("favorite" in lower_content and "favorite" in existing_content)
                or ("backend" in lower_content and "backend" in existing_content)
                or ("database" in lower_content and "database" in existing_content)
            ):
                if existing_content != lower_content:
                    supersedes_id = existing_id
                    break

        decisions.append(
            MemoryDecision(
                action="save",
                title=memory.title,
                content=memory.content,
                kind="fact",
                tags=memory.tags,
                confidence=0.9,
                supersedes_id=supersedes_id,
                reason="High-confidence durable memory pattern found in user message.",
                source="deterministic_extractor",
            )
        )

    if decisions:
        return decisions

    return [
        MemoryDecision(
            action="ignore",
            reason="No high-confidence durable memory found.",
            confidence=0.7,
            source="deterministic_default",
        )
    ]


def _normalize_model_decision(parsed: dict[str, Any], *, raw: str) -> MemoryDecision:
    action = parsed.get("action")
    if action not in {"save", "update", "archive", "ignore"}:
        return MemoryDecision(
            action="ignore",
            reason="Memory manager returned invalid action.",
            confidence=0.0,
            raw=raw,
            source="llm_memory_manager_invalid",
        )

    tags = parsed.get("tags", [])
    if not isinstance(tags, list):
        tags = []

    return MemoryDecision(
        action=action,
        reason=str(parsed.get("reason") or "No reason provided."),
        title=str(parsed.get("title") or "") or None,
        content=str(parsed.get("content") or "") or None,
        kind=str(parsed.get("kind") or "fact"),
        tags=[str(tag) for tag in tags if str(tag).strip()],
        confidence=_as_float(parsed.get("confidence"), 0.0),
        target_memory_id=str(parsed.get("target_memory_id") or "") or None,
        supersedes_id=str(parsed.get("supersedes_id") or "") or None,
        raw=raw,
        source="llm_memory_manager",
    )


async def decide_memory_actions(
    *,
    lmstudio_client: LMStudioClient,
    model: str,
    user_message: str,
    assistant_message: str,
    similar_memories: list[dict[str, Any]],
) -> list[MemoryDecision]:
    """Decide whether a conversation should update long-term semantic memory.

    High-confidence deterministic extractor always runs. The LLM manager can
    improve decisions, but it cannot force saving low-confidence/noisy memory.
    """

    deterministic = _deterministic_decisions(
        user_message=user_message,
        assistant_message=assistant_message,
        similar_memories=similar_memories,
    )

    # Explicit remember/preference patterns should be saved without needing a
    # second model call.
    if any(decision.action == "save" for decision in deterministic):
        return deterministic

    if not memory_manager_model_enabled() or not model:
        return deterministic

    system_prompt = """
You are Serviq's memory manager.

Decide whether the latest user/assistant exchange should update long-term memory.

Return ONLY valid JSON.

Allowed actions:
- "save": save a new durable memory.
- "update": save a new memory and optionally supersede an old one.
- "archive": archive an old active memory only when the user clearly says it is no longer true.
- "ignore": do not save anything.

Save only durable information:
- stable user preferences
- project decisions
- coding stack choices
- explicit "remember that..." instructions
- long-term personal workflow preferences

Do NOT save:
- greetings
- casual chat
- one-time questions
- temporary feelings
- secrets, tokens, passwords, API keys
- tool output unless it represents a durable project decision

Never hard delete memory. Use archive/update/supersede only.

Schema:
{
  "action": "save" | "update" | "archive" | "ignore",
  "title": string | null,
  "content": string | null,
  "kind": "fact" | "preference" | "project" | "instruction" | "note",
  "tags": string[],
  "target_memory_id": string | null,
  "supersedes_id": string | null,
  "confidence": number,
  "reason": string
}
""".strip()

    user_prompt = f"""
Latest user message:
{user_message}

Latest assistant message:
{assistant_message}

Similar active memories:
{json.dumps(similar_memories, ensure_ascii=False, indent=2, default=str)}

Decide memory action now.
""".strip()

    try:
        payload = await lmstudio_client.chat_completion(
            model=model,
            temperature=0.0,
            max_tokens=700,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = (
            payload.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        parsed = _extract_json_object(str(content))
        decision = _normalize_model_decision(parsed, raw=str(content))

        if decision.action in {"save", "update"} and decision.confidence < memory_save_threshold():
            decision.action = "ignore"
            decision.reason = (
                f"Memory manager confidence {decision.confidence:.2f} is below threshold "
                f"{memory_save_threshold():.2f}."
            )

        if decision.action in {"save", "update"} and not decision.content:
            decision.action = "ignore"
            decision.reason = "Memory manager wanted to save/update but provided no content."

        if decision.action == "archive" and not decision.target_memory_id:
            decision.action = "ignore"
            decision.reason = "Memory manager wanted to archive but provided no target_memory_id."

        if _is_sensitive_or_temporary(user_message) and decision.action != "ignore":
            decision.action = "ignore"
            decision.reason = "Safety filter blocked sensitive or temporary memory save."

        return [decision]

    except (LMStudioAPIError, Exception) as exc:  # noqa: BLE001
        return [
            MemoryDecision(
                action="ignore",
                reason=f"LLM memory manager failed; fallback ignored non-explicit memory: {type(exc).__name__}: {exc}",
                confidence=0.0,
                source="llm_memory_manager_failure",
            )
        ]
