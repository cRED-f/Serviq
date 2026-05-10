import { SERVIQ_API_BASE_URL } from "./config";

export type ChatRole = "user" | "assistant" | "system";

export type AgentHistoryMessage = {
  role: ChatRole;
  content: string;
};

export type AgentRunRequest = {
  session_id: string;
  model: string;
  message: string;
  history: AgentHistoryMessage[];
};

export type AgentRunResponse = {
  session_id?: string;
  model?: string;
  route?: string;
  response?: string;
  steps?: string[];
  metadata?: Record<string, unknown>;
};

export type ApprovalDecision = "approve" | "reject";

export type ApprovalDecisionResponse = {
  approval?: Record<string, unknown>;
  tool_result?: Record<string, unknown>;
  assistant_response?: string;
  response?: string;
  model?: string;
  metadata?: Record<string, unknown>;
};

export type ChatModel = {
  id: string;
  name: string;
};

function normalizeModels(payload: unknown): ChatModel[] {
  const record = payload as Record<string, unknown>;
  const rawModels = record.models ?? record.data;

  if (!Array.isArray(rawModels)) {
    return [];
  }

  return rawModels
    .map((item) => {
      if (typeof item === "string") {
        return {
          id: item,
          name: item,
        };
      }

      if (!item || typeof item !== "object") {
        return null;
      }

      const modelRecord = item as Record<string, unknown>;
      const id = String(modelRecord.id ?? modelRecord.name ?? modelRecord.model ?? "").trim();

      if (!id) {
        return null;
      }

      return {
        id,
        name: String(modelRecord.name ?? modelRecord.id ?? id),
      };
    })
    .filter((item): item is ChatModel => Boolean(item));
}

async function readErrorDetail(response: Response) {
  try {
    const errorPayload = await response.json();
    return (
      String((errorPayload as Record<string, unknown>)?.error ?? "") ||
      String((errorPayload as Record<string, unknown>)?.detail ?? "") ||
      `HTTP ${response.status}`
    );
  } catch {
    const text = await response.text();
    return text || `HTTP ${response.status}`;
  }
}

export async function listChatModels(): Promise<ChatModel[]> {
  const response = await fetch(`${SERVIQ_API_BASE_URL}/api/llm/models`, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Unable to load models. HTTP ${response.status}`);
  }

  const payload = await response.json();
  return normalizeModels(payload);
}

export async function runAgentChat(
  request: AgentRunRequest,
  options?: {
    signal?: AbortSignal;
  },
): Promise<AgentRunResponse> {
  const response = await fetch(`${SERVIQ_API_BASE_URL}/api/agent/run`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    signal: options?.signal,
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(`Agent request failed: ${detail}`);
  }

  return (await response.json()) as AgentRunResponse;
}

async function postApprovalCandidate(
  url: string,
  decision: ApprovalDecision,
): Promise<ApprovalDecisionResponse | null> {
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        decision,
        approved: decision === "approve",
        status: decision === "approve" ? "approved" : "rejected",
      }),
    });

    if (response.status === 404 || response.status === 405) {
      return null;
    }

    if (!response.ok) {
      const detail = await readErrorDetail(response);
      throw new Error(detail);
    }

    return (await response.json()) as ApprovalDecisionResponse;
  } catch (error) {
    if (error instanceof TypeError) {
      return null;
    }

    throw error;
  }
}

export async function decideApproval(
  approvalId: string,
  decision: ApprovalDecision,
): Promise<ApprovalDecisionResponse> {
  const action = decision === "approve" ? "approve" : "reject";
  const candidates = [
    `${SERVIQ_API_BASE_URL}/api/approvals/${approvalId}/${action}`,
    `${SERVIQ_API_BASE_URL}/api/tools/approvals/${approvalId}/${action}`,
    `${SERVIQ_API_BASE_URL}/api/agent/approvals/${approvalId}/${action}`,
    `${SERVIQ_API_BASE_URL}/api/approvals/${approvalId}/decision`,
    `${SERVIQ_API_BASE_URL}/api/tools/approvals/${approvalId}/decision`,
  ];

  let lastError: unknown = null;

  for (const url of candidates) {
    try {
      const result = await postApprovalCandidate(url, decision);

      if (result) {
        return result;
      }
    } catch (error) {
      lastError = error;
    }
  }

  if (lastError instanceof Error) {
    throw lastError;
  }

  throw new Error("No approval endpoint responded. Check the backend approval route.");
}
