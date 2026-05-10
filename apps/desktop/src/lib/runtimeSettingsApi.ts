import { SERVIQ_API_BASE_URL } from "./config";

export type AnswerStyle = "concise" | "normal";

export type RuntimeSettings = {
  selected_embedding_model: string;
  answer_style: AnswerStyle;
  workspace_path: string;
  accessible_directories: string[];
  directory_caution?: string;
  shell_run_as_administrator: boolean;
  shell_admin_caution?: string;
};

export type RuntimeSettingsUpdate = {
  selected_embedding_model?: string;
  answer_style?: AnswerStyle;
  accessible_directories?: string[];
  shell_run_as_administrator?: boolean;
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

function normalizeRuntimeSettings(payload: unknown): RuntimeSettings {
  const record = payload as Record<string, unknown>;
  const settings = (record.settings ?? record) as Record<string, unknown>;
  const answerStyle = settings.answer_style === "normal" ? "normal" : "concise";
  const directories = Array.isArray(settings.accessible_directories)
    ? settings.accessible_directories.map((value) => String(value)).filter(Boolean)
    : [];

  return {
    selected_embedding_model: String(settings.selected_embedding_model ?? ""),
    answer_style: answerStyle,
    workspace_path: String(settings.workspace_path ?? ""),
    accessible_directories: directories,
    directory_caution:
      typeof settings.directory_caution === "string"
        ? settings.directory_caution
        : undefined,
    shell_run_as_administrator: Boolean(settings.shell_run_as_administrator),
    shell_admin_caution:
      typeof settings.shell_admin_caution === "string"
        ? settings.shell_admin_caution
        : undefined,
  };
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
  return normalizeRuntimeSettings(payload);
}

export async function updateRuntimeSettings(
  update: RuntimeSettingsUpdate,
): Promise<RuntimeSettings> {
  const response = await fetch(`${SERVIQ_API_BASE_URL}/api/runtime-settings`, {
    method: "PATCH",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(update),
  });

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  const payload = await response.json();
  return normalizeRuntimeSettings(payload);
}
