import { SERVIQ_API_BASE_URL } from "./config";

export type ToolRisk = "low" | "medium" | "high" | string;

export type ServiqTool = {
  id: string;
  name: string;
  description: string;
  icon: string;
  risk: ToolRisk;
  enabled: boolean;
  created_at?: string | null;
  updated_at?: string | null;
};

async function readError(response: Response) {
  try {
    const payload = await response.json();
    const detail = payload.detail ?? payload.error ?? `HTTP ${response.status}`;

    if (typeof detail === "string") {
      return detail;
    }

    return detail.message ?? JSON.stringify(detail);
  } catch {
    return (await response.text()) || `HTTP ${response.status}`;
  }
}

export async function listServiqTools(): Promise<ServiqTool[]> {
  const response = await fetch(`${SERVIQ_API_BASE_URL}/api/tool-settings`, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  const payload = await response.json();
  return Array.isArray(payload.tools) ? payload.tools : [];
}

export async function setServiqToolEnabled(toolId: string, enabled: boolean): Promise<ServiqTool> {
  const response = await fetch(`${SERVIQ_API_BASE_URL}/api/tool-settings/${encodeURIComponent(toolId)}`, {
    method: "PATCH",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      enabled,
    }),
  });

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  const payload = await response.json();
  return payload.tool as ServiqTool;
}
