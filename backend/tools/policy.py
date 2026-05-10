from __future__ import annotations

from dataclasses import dataclass

from tools.base import ToolRisk


@dataclass(slots=True)
class ToolPolicyDecision:
    allowed: bool
    approval_required: bool
    reason: str


def evaluate_tool_policy(risk: ToolRisk) -> ToolPolicyDecision:
    """Evaluate current production-safe tool policy.

    Current policy:
    - safe/low tools can run automatically.
    - medium/high tools require approval.
    - blocked tools never run.
    """

    if risk in {ToolRisk.SAFE, ToolRisk.LOW}:
        return ToolPolicyDecision(
            allowed=True,
            approval_required=False,
            reason="Tool is safe/low risk and can run automatically.",
        )

    if risk in {ToolRisk.MEDIUM, ToolRisk.HIGH}:
        return ToolPolicyDecision(
            allowed=False,
            approval_required=True,
            reason="Tool requires approval before execution.",
        )

    return ToolPolicyDecision(
        allowed=False,
        approval_required=False,
        reason="Tool is blocked by policy.",
    )
