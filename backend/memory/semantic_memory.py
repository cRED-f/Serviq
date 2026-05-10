from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(slots=True)
class ExtractedMemory:
    title: str
    content: str
    tags: list[str]


def _clean_fact(value: str) -> str:
    fact = value.strip()
    fact = re.sub(r"\s+", " ", fact)
    fact = fact.strip(" .")
    return fact


def extract_durable_memories_from_user_message(user_message: str) -> list[ExtractedMemory]:
    """Extract durable user facts without calling the model.

    This intentionally catches only high-confidence patterns so normal chat does
    not become memory noise.
    """

    text = user_message.strip()
    lower = text.lower()
    memories: list[ExtractedMemory] = []

    remember_match = re.search(
        r"\bremember(?:\s+in\s+this\s+chat)?\s+that\s+(.+)$",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if remember_match:
        fact = _clean_fact(remember_match.group(1))
        if fact:
            memories.append(
                ExtractedMemory(
                    title="User requested memory",
                    content=fact,
                    tags=["auto", "remembered", "user_fact"],
                )
            )

    preference_match = re.search(
        r"\bmy\s+(favorite|preferred|default)\s+(.+?)\s+is\s+(.+)$",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if preference_match:
        fact = _clean_fact(
            f"User's {preference_match.group(1).lower()} {preference_match.group(2).strip()} is {preference_match.group(3).strip()}"
        )
        memories.append(
            ExtractedMemory(
                title=f"User {preference_match.group(1).lower()} preference",
                content=fact,
                tags=["auto", "preference", "user_fact"],
            )
        )

    prefers_match = re.search(
        r"\bi\s+(prefer|like|usually use|use)\s+(.+)$",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if prefers_match and any(keyword in lower for keyword in ["for ", "backend", "frontend", "database", "stack", "project"]):
        fact = _clean_fact(f"User {prefers_match.group(1).lower()} {prefers_match.group(2).strip()}")
        memories.append(
            ExtractedMemory(
                title="User preference",
                content=fact,
                tags=["auto", "preference", "user_fact"],
            )
        )

    # De-duplicate exact content.
    unique: dict[str, ExtractedMemory] = {}
    for memory in memories:
        unique[memory.content.lower()] = memory

    return list(unique.values())
