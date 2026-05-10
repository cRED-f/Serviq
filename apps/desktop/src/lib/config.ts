const env = (import.meta as unknown as {
  env?: Record<string, string | undefined>;
}).env ?? {};

export const SERVIQ_API_BASE_URL =
  env.VITE_SERVIQ_API_BASE_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8787";

export const SERVIQ_HEALTH_ENDPOINT = `${SERVIQ_API_BASE_URL}/api/health`;
export const SERVIQ_DEEP_HEALTH_ENDPOINT = `${SERVIQ_API_BASE_URL}/api/health/deep`;

export const SERVIQ_LMSTUDIO_HEALTH_ENDPOINT = `${SERVIQ_API_BASE_URL}/api/llm/health`;
export const SERVIQ_LMSTUDIO_MODELS_ENDPOINT = `${SERVIQ_API_BASE_URL}/api/llm/models`;
export const SERVIQ_LMSTUDIO_CHAT_ENDPOINT = `${SERVIQ_API_BASE_URL}/api/llm/chat`;
