from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from agent.prompts import SERVIQ_SYSTEM_PROMPT
from agent.tool_planner import AgentToolPlan, plan_next_action
from llm.lmstudio_client import LMStudioClient
from memory.service import MemoryService
from tools.base import ToolExecutionContext
from tools.registry import ToolRegistry


@dataclass(slots=True)
class AgentTaskLoopResult:
    messages: list[dict[str, str]]
    response: str
    metadata: dict[str, Any]
    steps: list[str]
    tool_result: dict[str, Any] | None = None
    task_trace: list[dict[str, Any]] = field(default_factory=list)


def get_max_tool_steps() -> int:
    raw_value = os.getenv("AGENT_MAX_TOOL_STEPS", "4")
    try:
        value = int(raw_value)
    except ValueError:
        return 4
    return max(1, min(value, 8))


def plan_to_dict(plan: AgentToolPlan) -> dict[str, Any]:
    return {
        "action": plan.action,
        "tool_name": plan.tool_name,
        "args": plan.args,
        "reason": plan.reason,
        "confidence": plan.confidence,
        "planner": plan.planner,
        "raw": plan.raw,
    }


def approval_required_response(
    tool_name: str,
    approval_id: str | None,
    reason: str | None = None,
) -> str:
    approval_line = (
        f"Approval request created: `{approval_id}`."
        if approval_id
        else "Approval request created."
    )
    reason_line = f"\n\nReason: {reason}" if reason else ""
    return (
        f"I need to use `{tool_name}` for this request, but it requires your approval first.\n\n"
        f"{approval_line}"
        f"{reason_line}\n\n"
        "Open the **Approval Layer** panel and choose **Approve, run & answer** or **Reject**. "
        "I have not executed the tool yet."
    )


def build_final_answer_messages(
    *,
    user_message: str,
    base_messages: list[dict[str, str]],
    memory_context: str,
    tool_observations: list[dict[str, Any]],
    stop_reason: str | None,
) -> list[dict[str, str]]:
    """Build an isolated final-answer prompt."""
    if not tool_observations:
        return base_messages

    return [
        {
            "role": "system",
            "content": (
                f"{SERVIQ_SYSTEM_PROMPT}\n\n"
                "You are writing the final answer after Serviq completed one or more local tool steps.\n"
                "Use only the memory context and actual tool observations below.\n"
                "Keep the answer short and direct. For a simple tool success/failure, use 1-3 sentences.\n"
                "Do not add tables, long summaries, recommendations, or extra sections unless the user asked for them.\n"
                "Do not invent files, folders, paths, command output, approval IDs, or tool results.\n"
                "Do not say an approval request was created unless an actual tool observation has approval_required=true and includes an approval_id.\n"
                "If stop_reason is duplicate_tool_call_prevented, explain that the planner repeated a completed step and no write/approval was created.\n"
                "Do not ask the user to approve an ID that is not present in the actual observations.\n"
                "Do not say you lack filesystem access if tool observations are present; Serviq just used its tools.\n"
                "If a shell command failed because a rename command was blocked, do not suggest another shell rename command. Tell the user to use the rename file request instead.\n"
                "If a shell command failed because a deletion command was blocked, do not suggest another shell deletion command. Tell the user to use the delete file tool/request instead.\n"
                "If a rename_workspace_file tool succeeds, simply say the file was renamed and include the destination path if available.\n"
                "If a delete_workspace_file tool succeeds, simply say the file was deleted and include the path if available.\n"
                "If a tool failed, explain the real failure plainly.\n"
                "If tools succeeded, summarize the real results naturally and helpfully.\n"
                "When package.json content is present, extract the scripts object and present script names and commands."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Original user request:\n{user_message}\n\n"
                f"Stop reason:\n{stop_reason or 'none'}\n\n"
                f"Retrieved memory context:\n{memory_context or 'No relevant memory context.'}\n\n"
                "Actual tool observations:\n"
                f"{json.dumps(tool_observations, ensure_ascii=False, indent=2, default=str)}\n\n"
                "Now give the final answer."
            ),
        },
    ]


def make_duplicate_key(tool_name: str | None, args: dict[str, Any]) -> str:
    return json.dumps(
        {
            "tool_name": tool_name,
            "args": args,
        },
        sort_keys=True,
        default=str,
    )


async def run_agent_task_loop(
    *,
    lmstudio_client: LMStudioClient,
    memory_service: MemoryService,
    model: str,
    session_id: str,
    user_message: str,
    base_messages: list[dict[str, str]],
    memory_items: list[dict[str, Any]],
    memory_context: str,
) -> AgentTaskLoopResult:
    registry = ToolRegistry()
    context = ToolExecutionContext(
        session_id=session_id,
        lmstudio_client=lmstudio_client,
        memory_service=memory_service,
    )
    max_steps = get_max_tool_steps()
    steps: list[str] = []
    task_trace: list[dict[str, Any]] = []
    tool_observations: list[dict[str, Any]] = []
    seen_tool_calls: set[str] = set()
    metadata: dict[str, Any] = {
        "task_mode": "multi_step_tool_loop",
        "max_tool_steps": max_steps,
        "tool_used": False,
        "awaiting_approval": False,
    }
    last_tool_result: dict[str, Any] | None = None

    for step_index in range(1, max_steps + 1):
        steps.append(f"plan_next_action_{step_index}")
        plan = await plan_next_action(
            lmstudio_client=lmstudio_client,
            model=model,
            user_message=user_message,
            history=base_messages,
            memory_items=memory_items,
            registry=registry,
            tool_observations=tool_observations,
            step_index=step_index,
            max_steps=max_steps,
        )
        plan_payload = plan_to_dict(plan)
        task_trace.append(
            {
                "step": step_index,
                "type": "plan",
                "plan": plan_payload,
            }
        )
        metadata["planner"] = plan.planner
        metadata["planned_action"] = plan.action
        metadata["planned_tool"] = plan.tool_name
        metadata["planner_confidence"] = plan.confidence
        metadata["planner_reason"] = plan.reason

        if plan.action != "tool_call":
            metadata["stop_reason"] = "planner_direct_answer"
            break

        duplicate_key = make_duplicate_key(plan.tool_name, plan.args)
        if duplicate_key in seen_tool_calls:
            metadata["stop_reason"] = "duplicate_tool_call_prevented"
            metadata["duplicate_tool_call"] = {
                "tool_name": plan.tool_name,
                "args": plan.args,
            }
            task_trace.append(
                {
                    "step": step_index,
                    "type": "duplicate_prevented",
                    "tool_name": plan.tool_name,
                    "args": plan.args,
                }
            )
            break
        seen_tool_calls.add(duplicate_key)

        if not plan.tool_name:
            metadata["stop_reason"] = "invalid_tool_plan"
            break

        steps.append(f"execute_tool_{step_index}")
        result = await registry.execute_tool(
            name=plan.tool_name,
            args=plan.args,
            context=context,
        )
        result_payload = {
            "name": result.name,
            "ok": result.ok,
            "risk": result.risk.value,
            "output": result.output,
            "error": result.error,
            "approval_required": result.approval_required,
            "metadata": result.metadata,
        }
        last_tool_result = result_payload
        metadata["tool_used"] = True
        metadata["tool_name"] = result.name
        metadata["tool_ok"] = result.ok
        metadata["tool_approval_required"] = result.approval_required
        metadata["tool_reason"] = plan.reason
        task_trace.append(
            {
                "step": step_index,
                "type": "tool_result",
                "tool_result": result_payload,
            }
        )

        if result.approval_required:
            approval_id = result.metadata.get("approval_id") if result.metadata else None
            approval_id = str(approval_id) if approval_id else None
            metadata["awaiting_approval"] = True
            metadata["approval_id"] = approval_id
            metadata["model_call_skipped"] = True
            metadata["skip_reason"] = "Tool requires approval before execution."
            metadata["stop_reason"] = "awaiting_approval"
            metadata["task_trace"] = task_trace
            return AgentTaskLoopResult(
                messages=base_messages,
                response=approval_required_response(result.name, approval_id, plan.reason),
                metadata=metadata,
                steps=steps,
                tool_result=result_payload,
                task_trace=task_trace,
            )

        tool_observations.append(
            {
                "step": step_index,
                "tool_name": result.name,
                "args": plan.args,
                "ok": result.ok,
                "risk": result.risk.value,
                "output": result.output,
                "error": result.error,
                "approval_required": result.approval_required,
                "metadata": result.metadata,
            }
        )
        if not result.ok:
            metadata["stop_reason"] = "tool_failed"
            break
    else:
        metadata["stop_reason"] = "max_tool_steps_reached"

    metadata["tool_observation_count"] = len(tool_observations)
    metadata["task_trace"] = task_trace
    final_messages = build_final_answer_messages(
        user_message=user_message,
        base_messages=base_messages,
        memory_context=memory_context,
        tool_observations=tool_observations,
        stop_reason=str(metadata.get("stop_reason") or ""),
    )
    return AgentTaskLoopResult(
        messages=final_messages,
        response="",
        metadata=metadata,
        steps=steps,
        tool_result=last_tool_result,
        task_trace=task_trace,
    )
