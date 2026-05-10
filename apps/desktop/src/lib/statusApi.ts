import { SERVIQ_API_BASE_URL } from "./config";

export type ServiceHealth = {
  status: string;
  endpoint: string;
  detail: string;
};

async function safeFetchJson(url: string): Promise<Record<string, unknown> | null> {
  try {
    const response = await fetch(url, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      return {
        status: "error",
        detail: `HTTP ${response.status}`,
      };
    }

    return (await response.json()) as Record<string, unknown>;
  } catch (error) {
    return {
      status: "offline",
      detail: error instanceof Error ? error.message : "Unknown fetch error",
    };
  }
}

export async function getBackendStatus(): Promise<ServiceHealth> {
  const endpoint = `${SERVIQ_API_BASE_URL}/api/health`;
  const result = await safeFetchJson(endpoint);
  const status = String(result?.status ?? "offline");

  return {
    status,
    endpoint: "/api/health",
    detail:
      status === "ok"
        ? "Backend API responded successfully"
        : String(result?.detail ?? result?.error ?? "Backend is not responding"),
  };
}

export async function getLMStudioStatus(): Promise<ServiceHealth> {
  const endpoint = `${SERVIQ_API_BASE_URL}/api/llm/health`;
  const result = await safeFetchJson(endpoint);
  const status = String(result?.status ?? "offline");
  const modelCount = Number(result?.model_count ?? 0);

  return {
    status,
    endpoint: "/api/llm/health",
    detail:
      status === "connected"
        ? `${modelCount} model${modelCount === 1 ? "" : "s"} visible in LM Studio`
        : String(result?.detail ?? result?.error ?? "LM Studio is not responding"),
  };
}
