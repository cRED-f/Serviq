from __future__ import annotations

import json
import os
from typing import Any

from agent.prompts import get_merged_system_prompt
from agent.state import TaskStateManager
from agent.tool_planner import AgentToolPlan, EnhancedPlanner
from agent.types import OrchestratorResult, TaskStatus
from llm.lmstudio_client import LMStudioClient
from memory.service import MemoryService
from tools.base import ToolExecutionContext
from tools.registry import ToolRegistry


def get_orchestrator_max_steps(requested_max_steps: int | None = None) -> int:
    if requested_max_steps is not None:
        return max(1, min(int(requested_max_steps), 20))

    raw_value = os.getenv("AGENT_ORCHESTRATOR_MAX_STEPS", "10")
    try:
        value = int(raw_value)
    except ValueError:
        return 10
    return max(1, min(value, 20))


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


def result_to_dict(result: Any) -> dict[str, Any]:
    return {
        "name": result.name,
        "ok": result.ok,
        "risk": result.risk.value,
        "output": result.output,
        "error": result.error,
        "approval_required": result.approval_required,
        "metadata": result.metadata,
    }


def duplicate_key(tool_name: str | None, args: dict[str, Any]) -> str:
    return json.dumps({"tool_name": tool_name, "args": args}, sort_keys=True, default=str)


class ConfirmationHandler:
    """Builds user-facing pauses for approval/confirmation-required actions."""

    transactional_words = {
        "checkout",
        "payment",
        "pay",
        "purchase",
        "buy",
        "book now",
        "confirm booking",
        "place order",
        "submit",
        "reserve",
    }

    def is_transactional_plan(self, plan: AgentToolPlan) -> bool:
        text = json.dumps({"reason": plan.reason, "args": plan.args}, default=str).lower()
        return any(word in text for word in self.transactional_words)

    def build_approval_pause(
        self,
        *,
        plan: AgentToolPlan,
        tool_result: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        metadata = tool_result.get("metadata") if isinstance(tool_result.get("metadata"), dict) else {}
        approval_id = metadata.get("approval_id")
        approval_payload = {
            "id": approval_id,
            "approval_id": approval_id,
            "tool_name": tool_result.get("name") or plan.tool_name,
            "risk": tool_result.get("risk"),
            "args": plan.args,
            "reason": plan.reason or tool_result.get("error") or "Serviq needs approval before continuing.",
            "transactional": self.is_transactional_plan(plan),
        }

        approval_line = f"Approval request created: `{approval_id}`." if approval_id else "Approval request created."
        response = (
            f"I need approval before running `{approval_payload['tool_name']}`.\n\n"
            f"{approval_line}\n\n"
            f"Reason: {approval_payload['reason']}\n\n"
            "Approve it from the Approval Layer to continue, or reject it to stop this action."
        )
        return response, approval_payload


class AgentOrchestrator:
    """Autonomous multi-step agent loop.

    This orchestrator is intentionally separate from the existing LangGraph chat
    runner. It can run longer task workflows, maintain task state, use browser
    tools, and pause cleanly when approval is required.
    """

    def __init__(
        self,
        *,
        lmstudio_client: LMStudioClient,
        memory_service: MemoryService,
        model: str,
        session_id: str,
        registry: ToolRegistry | None = None,
        max_steps: int | None = None,
    ) -> None:
        self.lmstudio_client = lmstudio_client
        self.memory_service = memory_service
        self.model = model
        self.session_id = session_id
        self.registry = registry or ToolRegistry()
        self.max_steps = get_orchestrator_max_steps(max_steps)
        self.confirmation_handler = ConfirmationHandler()
        self.planner = EnhancedPlanner(
            lmstudio_client=lmstudio_client,
            model=model,
            registry=self.registry,
        )

    async def run(
        self,
        *,
        user_message: str,
        history: list[dict[str, str]] | None = None,
    ) -> OrchestratorResult:
        manager = TaskStateManager(
            session_id=self.session_id,
            goal=user_message,
            max_steps=self.max_steps,
        )
        context = ToolExecutionContext(
            session_id=self.session_id,
            lmstudio_client=self.lmstudio_client,
            memory_service=self.memory_service,
        )
        base_messages = self._build_base_messages(user_message=user_message, history=history or [])
        trace: list[dict[str, Any]] = []
        steps: list[str] = ["orchestrator_start"]
        seen_calls: set[str] = set()
        final_response = ""
        metadata: dict[str, Any] = {
            "runtime": "agent_orchestrator",
            "task_mode": "autonomous_multi_step",
            "max_steps": self.max_steps,
            "tool_used": False,
            "awaiting_approval": False,
        }

        # Preload relevant memories for the first step
        memory_items = []
        try:
            memory_result = await self.memory_service.search_memory(
                query=user_message,
                limit=8,
            )
            memory_items = memory_result.get("items", [])
        except Exception as exc:  # noqa: BLE001
            metadata["memory_preload_error"] = str(exc)

        for _ in range(self.max_steps):
            step_index = manager.start_step()
            steps.append(f"orchestrator_plan_{step_index}")

            # Refresh memory context periodically (every 4 steps)
            if step_index > 1 and step_index % 4 == 1:
                try:
                    memory_result = await self.memory_service.search_memory(
                        query=user_message,
                        limit=5,
                    )
                    memory_items = memory_result.get("items", [])
                except Exception:  # noqa: BLE001
                    pass  # Keep previous memory items on error

            plan = await self.planner.plan_next_action(
                user_message=user_message,
                history=base_messages,
                memory_items=memory_items,
                tool_observations=manager.observations,
                step_index=step_index,
                max_steps=self.max_steps,
                task_context=manager.to_planner_context(),
            )
            plan_payload = plan_to_dict(plan)
            manager.add_step("plan", "Planner selected next action", plan_payload)
            trace.append({"step": step_index, "type": "plan", "plan": plan_payload})

            metadata.update(
                {
                    "planned_action": plan.action,
                    "planned_tool": plan.tool_name,
                    "planner": plan.planner,
                    "planner_reason": plan.reason,
                    "planner_confidence": plan.confidence,
                }
            )

            if plan.action != "tool_call":
                manager.set_status(TaskStatus.COMPLETED)
                metadata["stop_reason"] = "planner_direct_answer"
                break

            if not plan.tool_name:
                manager.set_status(TaskStatus.FAILED)
                metadata["stop_reason"] = "invalid_tool_plan"
                final_response = "I could not continue because the planner did not choose a valid tool."
                break

            call_key = duplicate_key(plan.tool_name, plan.args)
            if call_key in seen_calls:
                manager.set_status(TaskStatus.STOPPED)
                metadata["stop_reason"] = "duplicate_tool_call_prevented"
                trace.append(
                    {
                        "step": step_index,
                        "type": "duplicate_prevented",
                        "tool_name": plan.tool_name,
                        "args": plan.args,
                    }
                )
                break
            seen_calls.add(call_key)

            steps.append(f"orchestrator_execute_{plan.tool_name}")
            manager.add_step(
                "tool_call",
                f"Executing {plan.tool_name}",
                {"tool_name": plan.tool_name, "args": plan.args},
            )
            trace.append(
                {
                    "step": step_index,
                    "type": "tool_call",
                    "plan": plan_payload,
                }
            )

            result = await self.registry.execute_tool(
                name=plan.tool_name,
                args=plan.args,
                context=context,
            )
            result_payload = result_to_dict(result)
            manager.record_tool_result(tool_name=plan.tool_name, args=plan.args, result=result_payload)
            manager.add_step("tool_result", f"{plan.tool_name} returned", result_payload)
            trace.append(
                {
                    "step": step_index,
                    "type": "tool_result",
                    "tool_result": result_payload,
                }
            )

            metadata.update(
                {
                    "tool_used": True,
                    "tool_name": result.name,
                    "tool_ok": result.ok,
                    "tool_approval_required": result.approval_required,
                }
            )

            if result.approval_required:
                response, approval_payload = self.confirmation_handler.build_approval_pause(
                    plan=plan,
                    tool_result=result_payload,
                )
                manager.set_status(TaskStatus.AWAITING_APPROVAL)
                manager.set_pending_confirmation(approval_payload)
                manager.add_step("approval_pause", "Paused for user approval", approval_payload)
                metadata.update(
                    {
                        "awaiting_approval": True,
                        "approval": approval_payload,
                        "approval_id": approval_payload.get("approval_id"),
                        "stop_reason": "awaiting_approval",
                    }
                )
                final_response = response
                break

            if not result.ok:
                manager.set_status(TaskStatus.FAILED)
                metadata["stop_reason"] = "tool_failed"
                final_response = ""
                break
        else:
            manager.set_status(TaskStatus.STOPPED)
            metadata["stop_reason"] = "max_steps_reached"

        if not final_response:
            final_response = await self._build_final_response(
                user_message=user_message,
                history=history or [],
                manager=manager,
                stop_reason=str(metadata.get("stop_reason") or "completed"),
            )

        if manager.status == TaskStatus.RUNNING:
            manager.set_status(TaskStatus.COMPLETED)

        steps.append("orchestrator_finalize")
        manager.add_step("final_answer", "Prepared final response", {"response": final_response})
        trace.append(
            {
                "step": manager.current_step,
                "type": "final_answer",
                "response": final_response,
            }
        )

        metadata.update(
            {
                "completed": manager.status == TaskStatus.COMPLETED,
                "task_id": manager.task_id,
                "observation_count": len(manager.observations),
            }
        )

        self._save_conversation(
            user_message=user_message,
            assistant_message=final_response,
            metadata=metadata,
        )

        # Clean up browser session if one was created
        try:
            from tools.browser_tools import cleanup_stale_browser_sessions, close_browser_session_for_session

            # Close browser for this specific session
            await close_browser_session_for_session(self.session_id)

            # Also cleanup any other stale sessions
            cleanup_result = await cleanup_stale_browser_sessions()
            metadata["browser_cleanup"] = cleanup_result
        except Exception:  # noqa: BLE001 - Browser cleanup must not fail the agent response.
            pass

        return OrchestratorResult(
            session_id=self.session_id,
            model=self.model,
            route="autonomous_agent",
            response=final_response,
            status=manager.status,
            steps=steps,
            task_trace=trace,
            task_state=manager.to_dict(),
            metadata=metadata,
        )

    def _build_base_messages(
        self,
        *,
        user_message: str,
        history: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        normalized_history = []
        for item in history[-8:]:
            role = item.get("role")
            content = item.get("content")
            if role in {"user", "assistant", "system"} and isinstance(content, str) and content:
                normalized_history.append({"role": role, "content": content})

        return [
            {
                "role": "system",
                "content": (
                    f"{get_merged_system_prompt()}\n\n"
                    "You are running in Serviq autonomous agent mode. "
                    "Plan step by step, use tools only when needed, and pause before risky or transactional actions. "
                    "Do not claim a task is done unless a tool observation proves it."
                ),
            },
            *normalized_history,
            {"role": "user", "content": user_message},
        ]

    async def _build_final_response(
        self,
        *,
        user_message: str,
        history: list[dict[str, str]],
        manager: TaskStateManager,
        stop_reason: str,
    ) -> str:
        task_state = manager.to_dict()
        prompt = {
            "original_user_request": user_message,
            "stop_reason": stop_reason,
            "task_state": task_state,
            "observations": manager.observations[-10:],
        }
        messages = [
            {
                "role": "system",
                "content": (
                    f"{get_merged_system_prompt()}\n\n"
                    "Write the final response for Serviq's autonomous task. "
                    "Use only the actual task state and tool observations. "
                    "Be direct and practical. If approval is needed, say exactly what needs approval. "
                    "If the task could not be completed, explain the real blocker. "
                    "If you found options or links, present the useful options without inventing details."
                ),
            },
            *history[-6:],
            {
                "role": "user",
                "content": json.dumps(prompt, ensure_ascii=False, indent=2, default=str),
            },
        ]

        payload = await self.lmstudio_client.chat_completion(
            model=self.model,
            messages=messages,
            temperature=0.2,
        )
        content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
        return str(content).strip() or "I finished the task loop, but the local model returned an empty response."

    def _save_conversation(
        self,
        *,
        user_message: str,
        assistant_message: str,
        metadata: dict[str, Any],
    ) -> None:
        try:
            self.memory_service.save_conversation_pair(
                session_id=self.session_id,
                user_message=user_message,
                assistant_message=assistant_message,
                model=self.model,
                route="autonomous_agent",
                metadata=metadata,
            )
        except Exception:  # noqa: BLE001 - persistence must not fail the agent response.
            metadata["conversation_saved"] = False
        else:
            metadata["conversation_saved"] = True
