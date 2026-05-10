import { SERVIQ_API_BASE_URL } from "./config";

export type AnswerStyle = "concise" | "normal";

export type RuntimeSettings = {
  selected_embedding_model: string;
  answer_style: AnswerStyle;
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

export async function getRuntimeSettings(): Promise<RuntimeSettings> {
  const response = await fetch(`${SERVIQ_API_BASE_URL}/api/runtime-settings`, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  const payload = await response.json();

  return {
    selected_embedding_model: String(payload.settings?.selected_embedding_model ?? ""),
    answer_style: payload.settings?.answer_style === "normal" ? "normal" : "concise",
  };
}

export async function updateRuntimeSettings(input: Partial<RuntimeSettings>): Promise<RuntimeSettings> {
  const response = await fetch(`${SERVIQ_API_BASE_URL}/api/runtime-settings`, {
    method: "PATCH",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(input),
  });

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  const payload = await response.json();

  return {
    selected_embedding_model: String(payload.settings?.selected_embedding_model ?? ""),
    answer_style: payload.settings?.answer_style === "normal" ? "normal" : "concise",
  };
}
