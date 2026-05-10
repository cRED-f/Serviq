import {
  SERVIQ_LMSTUDIO_CHAT_ENDPOINT,
  SERVIQ_LMSTUDIO_HEALTH_ENDPOINT,
  SERVIQ_LMSTUDIO_MODELS_ENDPOINT,
} from "./config";

export type LMStudioHealthResponse = {
  status: "connected" | "offline";
  base_url: string;
  model_count: number;
  models: Array<Record<string, unknown>>;
  error?: string | null;
};

export type LMStudioModelsResponse = {
  provider: "lmstudio";
  base_url: string;
  models: Array<Record<string, unknown>>;
};

export type ChatMessage = {
  role: "system" | "user" | "assistant";
  content: string;
};

export type LMStudioChatResponse = {
  model: string;
  content: string;
  raw: Record<string, unknown>;
};

export async function fetchLMStudioHealth(
  signal?: AbortSignal,
): Promise<LMStudioHealthResponse> {
  const response = await fetch(SERVIQ_LMSTUDIO_HEALTH_ENDPOINT, {
    method: "GET",
    headers: { Accept: "application/json" },
    signal,
  });

  if (!response.ok) {
    throw new Error(`LM Studio health check failed with status ${response.status}`);
  }

  return (await response.json()) as LMStudioHealthResponse;
}

export async function fetchLMStudioModels(
  signal?: AbortSignal,
): Promise<LMStudioModelsResponse> {
  const response = await fetch(SERVIQ_LMSTUDIO_MODELS_ENDPOINT, {
    method: "GET",
    headers: { Accept: "application/json" },
    signal,
  });

  if (!response.ok) {
    throw new Error(`LM Studio model list failed with status ${response.status}`);
  }

  return (await response.json()) as LMStudioModelsResponse;
}

export async function sendLMStudioChat(params: {
  model: string;
  messages: ChatMessage[];
  temperature?: number;
  max_tokens?: number;
}): Promise<LMStudioChatResponse> {
  const response = await fetch(SERVIQ_LMSTUDIO_CHAT_ENDPOINT, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      temperature: 0.2,
      ...params,
    }),
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`LM Studio chat failed with status ${response.status}: ${body}`);
  }

  return (await response.json()) as LMStudioChatResponse;
}
