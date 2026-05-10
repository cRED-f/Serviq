import { SERVIQ_API_BASE_URL } from "./config";

export type AgentMessage = {
  role: "user" | "assistant" | "system";
  content: string;
};

export type AgentRunRequest = {
  message: string;
  model?: string;
  session_id?: string;
  history?: AgentMessage[];
};

export type AgentRunResponse = {
  session_id: string;
  model: string;
  route: string;
  response: string;
  steps: string[];
  metadata: Record<string, unknown>;
};

function getErrorMessageFromBody(rawBody: string): string {
  if (!rawBody) {
    return "No error body returned by backend.";
  }

  try {
    const parsed = JSON.parse(rawBody) as {
      detail?: unknown;
      error?: {
        message?: unknown;
        type?: unknown;
        request_id?: unknown;
      };
    };

    if (typeof parsed.detail === "string") {
      return parsed.detail;
    }

    if (parsed.error && typeof parsed.error.message === "string") {
      const type = typeof parsed.error.type === "string" ? parsed.error.type : "backend_error";
      const requestId =
        typeof parsed.error.request_id === "string"
          ? ` request_id=${parsed.error.request_id}`
          : "";
      return `${type}: ${parsed.error.message}${requestId}`;
    }
  } catch {
    return rawBody;
  }

  return rawBody;
}

export async function runServiqAgent(request: AgentRunRequest): Promise<AgentRunResponse> {
  try {
    const response = await fetch(`${SERVIQ_API_BASE_URL}/api/agent/run`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const body = await response.text();
      throw new Error(
        `Serviq agent failed with status ${response.status}: ${getErrorMessageFromBody(body)}`,
      );
    }

    return (await response.json()) as AgentRunResponse;
  } catch (unknownError) {
    if (unknownError instanceof TypeError && unknownError.message === "Failed to fetch") {
      throw new Error(
        `Failed to fetch ${SERVIQ_API_BASE_URL}/api/agent/run. Check that the backend is running and CORS is allowing the desktop origin.`,
      );
    }

    throw unknownError;
  }
}
