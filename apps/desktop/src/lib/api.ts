import { SERVIQ_HEALTH_ENDPOINT } from "./config";

export type BackendHealthResponse = {
  status?: string;
  service?: string;
  version?: string;
  environment?: string;
  timestamp?: string;
  [key: string]: unknown;
};

export async function fetchBackendHealth(
  signal?: AbortSignal,
): Promise<BackendHealthResponse> {
  const response = await fetch(SERVIQ_HEALTH_ENDPOINT, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
    signal,
  });

  if (!response.ok) {
    throw new Error(`Backend health check failed with status ${response.status}`);
  }

  return (await response.json()) as BackendHealthResponse;
}
