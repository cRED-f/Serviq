import { SERVIQ_API_BASE_URL } from "./config";
import type { ToolRunResponse } from "./toolsApi";

export type ApprovalRequest = {
  id: string;
  session_id: string;
  tool_name: string;
  risk: string;
  args: Record<string, unknown>;
  reason: string;
  status: string;
  result?: unknown;
  error?: string | null;
  created_at: string;
  decided_at?: string | null;
  executed_at?: string | null;
};

export type ApprovalDecisionResponse = {
  approval: ApprovalRequest;
  tool_result: ToolRunResponse | null;
  assistant_response?: string | null;
  model?: string | null;
};

export async function listApprovals(status = "pending"): Promise<ApprovalRequest[]> {
  const response = await fetch(`${SERVIQ_API_BASE_URL}/api/approvals?status=${encodeURIComponent(status)}`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`List approvals failed with status ${response.status}`);
  }

  const payload = (await response.json()) as { approvals: ApprovalRequest[] };
  return payload.approvals;
}

export async function approveRequest(approvalId: string): Promise<ApprovalDecisionResponse> {
  const response = await fetch(`${SERVIQ_API_BASE_URL}/api/approvals/${approvalId}/approve`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Approve request failed with status ${response.status}: ${body}`);
  }

  return (await response.json()) as ApprovalDecisionResponse;
}

export async function rejectRequest(approvalId: string): Promise<ApprovalDecisionResponse> {
  const response = await fetch(`${SERVIQ_API_BASE_URL}/api/approvals/${approvalId}/reject`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Reject request failed with status ${response.status}: ${body}`);
  }

  return (await response.json()) as ApprovalDecisionResponse;
}
