from __future__ import annotations

from typing import Any

from services.tool_settings_store import ToolDisabledError, require_tool_enabled
from tools.approval_store import ToolApprovalStore
from tools.base import ToolDefinition, ToolExecutionContext, ToolResult
from tools.execution_log import ToolExecutionLogStore
from tools.policy import evaluate_tool_policy
from tools.safe_tools import SAFE_TOOL_DEFINITIONS
from tools.shell_tools import SHELL_TOOL_DEFINITIONS
from tools.write_tools import WRITE_TOOL_DEFINITIONS
from tools.web_tools import WEB_TOOL_DEFINITIONS


class ToolNotFoundError(RuntimeError):
    """Raised when a tool name is not registered."""


class ToolRegistry:
    def __init__(
        self,
        *,
        definitions: list[ToolDefinition] | None = None,
        log_store: ToolExecutionLogStore | None = None,
        approval_store: ToolApprovalStore | None = None,
    ) -> None:
        all_definitions = definitions or [
            *SAFE_TOOL_DEFINITIONS,
            *WRITE_TOOL_DEFINITIONS,
            *SHELL_TOOL_DEFINITIONS,
            *WEB_TOOL_DEFINITIONS,
        ]
        self.definitions = {tool.name: tool for tool in all_definitions}
        self.log_store = log_store or ToolExecutionLogStore()
        self.approval_store = approval_store or ToolApprovalStore()

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "risk": tool.risk.value,
                "parameters": tool.parameters,
                "enabled": tool.enabled,
            }
            for tool in self.definitions.values()
        ]

    def get_tool(self, name: str) -> ToolDefinition:
        tool = self.definitions.get(name)
        if not tool:
            raise ToolNotFoundError(f"Tool not found: {name}")
        return tool

    async def execute_tool(
        self,
        *,
        name: str,
        args: dict[str, Any],
        context: ToolExecutionContext,
        approved: bool = False,
    ) -> ToolResult:
        tool = self.get_tool(name)

        if not tool.enabled:
            result = ToolResult(
                name=name,
                ok=False,
                risk=tool.risk,
                error="Tool is disabled.",
            )
            self._log(context=context, args=args, result=result)
            return result

        try:
            await require_tool_enabled(tool.name)
        except ToolDisabledError as exc:
            result = ToolResult(
                name=name,
                ok=False,
                risk=tool.risk,
                error=str(exc),
                metadata={"policy_reason": "Tool disabled by Serviq Tools settings."},
            )
            self._log(context=context, args=args, result=result)
            return result

        decision = evaluate_tool_policy(tool.risk)
        if decision.approval_required and not approved:
            approval = self.approval_store.create_request(
                session_id=context.session_id,
                tool_name=tool.name,
                risk=tool.risk.value,
                args=args,
                reason=decision.reason,
            )
            result = ToolResult(
                name=name,
                ok=False,
                risk=tool.risk,
                output={
                    "approval_id": approval["id"],
                    "status": approval["status"],
                    "tool_name": approval["tool_name"],
                    "args": approval["args"],
                },
                error=decision.reason,
                approval_required=True,
                metadata={
                    "policy_reason": decision.reason,
                    "approval_id": approval["id"],
                },
            )
            self._log(context=context, args=args, result=result)
            return result

        if not decision.allowed and not approved:
            result = ToolResult(
                name=name,
                ok=False,
                risk=tool.risk,
                error=decision.reason,
                approval_required=decision.approval_required,
                metadata={
                    "policy_reason": decision.reason,
                },
            )
            self._log(context=context, args=args, result=result)
            return result

        result = await tool.handler(args, context)
        self._log(context=context, args=args, result=result)
        return result

    async def execute_approved_request(
        self,
        *,
        approval_id: str,
        context: ToolExecutionContext,
    ) -> tuple[dict[str, Any], ToolResult]:
        approval = self.approval_store.mark_approved(approval_id)
        result = await self.execute_tool(
            name=approval["tool_name"],
            args=approval["args"],
            context=context,
            approved=True,
        )
        updated = self.approval_store.mark_executed(
            approval_id,
            ok=result.ok,
            result=result.output,
            error=result.error,
        )
        return updated, result

    def reject_request(self, approval_id: str) -> dict[str, Any]:
        return self.approval_store.mark_rejected(approval_id)

    def _log(
        self,
        *,
        context: ToolExecutionContext,
        args: dict[str, Any],
        result: ToolResult,
    ) -> None:
        self.log_store.add_log(
            session_id=context.session_id,
            tool_name=result.name,
            risk=result.risk.value,
            args=args,
            ok=result.ok,
            approval_required=result.approval_required,
            output=result.output,
            error=result.error,
            metadata=result.metadata,
        )
