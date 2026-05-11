import { SERVIQ_API_BASE_URL } from "./config";
import type { UIChatMessage } from "../components/shell/ChatWorkspace";
import type { ChatHistoryItem } from "../components/shell/LeftSidebar";
import type { AgentTaskTrace } from "./agentApi";

type SessionRecord = {
  id: string;
  title: string;
  preview: string;
  created_at: string;
  updated_at: string;
};

type MessageRecord = {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  steps?: string[];
  task_trace?: AgentTaskTrace[];
  metadata?: Record<string, unknown>;
};

function formatSessionTime(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "";
  }

  const now = new Date();
  const sameDay =
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate();

  if (sameDay) {
    return date.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  return date.toLocaleDateString([], {
    month: "short",
    day: "numeric",
  });
}

function formatMessageTime(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function sessionToChatHistoryItem(session: SessionRecord): ChatHistoryItem {
  return {
    id: session.id,
    title: session.title || "New chat",
    preview: session.preview || "No preview yet.",
    time: formatSessionTime(session.updated_at || session.created_at),
    persisted: true,
  };
}

function messageToUIMessage(message: MessageRecord): UIChatMessage {
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    createdAt: formatMessageTime(message.created_at),
    status: "done",
    steps: message.steps ?? [],
    task_trace: message.task_trace ?? [],
    metadata: message.metadata ?? {},
  };
}

async function readError(response: Response) {
  try {
    const payload = await response.json();
    return String(payload.detail ?? payload.error ?? `HTTP ${response.status}`);
  } catch {
    return (await response.text()) || `HTTP ${response.status}`;
  }
}

export async function loadConversationSessions(): Promise<ChatHistoryItem[]> {
  const response = await fetch(`${SERVIQ_API_BASE_URL}/api/conversations/sessions`, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  const payload = await response.json();
  const sessions = Array.isArray(payload.sessions) ? payload.sessions : [];

  return sessions.map(sessionToChatHistoryItem);
}

export async function createConversationSession({
  id,
  title,
  preview,
}: {
  id: string;
  title: string;
  preview: string;
}): Promise<ChatHistoryItem> {
  const response = await fetch(`${SERVIQ_API_BASE_URL}/api/conversations/sessions`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      id,
      title,
      preview,
    }),
  });

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  const payload = await response.json();
  return sessionToChatHistoryItem(payload.session);
}

export async function updateConversationSession({
  sessionId,
  title,
  preview,
}: {
  sessionId: string;
  title?: string;
  preview?: string;
}): Promise<void> {
  const response = await fetch(`${SERVIQ_API_BASE_URL}/api/conversations/sessions/${encodeURIComponent(sessionId)}`, {
    method: "PATCH",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      title,
      preview,
    }),
  });

  if (!response.ok) {
    throw new Error(await readError(response));
  }
}

export async function loadConversationMessages(sessionId: string): Promise<UIChatMessage[]> {
  const response = await fetch(
    `${SERVIQ_API_BASE_URL}/api/conversations/sessions/${encodeURIComponent(sessionId)}/messages`,
    {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    },
  );

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  const payload = await response.json();
  const messages = Array.isArray(payload.messages) ? payload.messages : [];

  return messages.map(messageToUIMessage);
}

export async function saveConversationMessage({
  sessionId,
  role,
  content,
  steps,
  metadata,
  task_trace,
}: {
  sessionId: string;
  role: "user" | "assistant";
  content: string;
  steps?: string[];
  metadata?: Record<string, unknown>;
  task_trace?: AgentTaskTrace[];
}): Promise<UIChatMessage> {
  const response = await fetch(
    `${SERVIQ_API_BASE_URL}/api/conversations/sessions/${encodeURIComponent(sessionId)}/messages`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        role,
        content,
        steps: steps ?? [],
        metadata: metadata ?? {},
        task_trace: task_trace ?? [],
      }),
    },
  );

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  const payload = await response.json();
  return messageToUIMessage(payload.message);
}

export async function deleteConversationSession(sessionId: string): Promise<void> {
  const response = await fetch(`${SERVIQ_API_BASE_URL}/api/conversations/sessions/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(await readError(response));
  }
}

export async function deleteConversationMessage(messageId: string): Promise<void> {
  const response = await fetch(`${SERVIQ_API_BASE_URL}/api/conversations/messages/${encodeURIComponent(messageId)}`, {
    method: "DELETE",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(await readError(response));
  }
}

export async function deleteAssistantMessagePair(messageId: string): Promise<string[]> {
  const response = await fetch(
    `${SERVIQ_API_BASE_URL}/api/conversations/messages/${encodeURIComponent(messageId)}/pair`,
    {
      method: "DELETE",
      headers: {
        Accept: "application/json",
      },
    },
  );

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  const payload = await response.json();
  return Array.isArray(payload.deleted) ? payload.deleted : [messageId];
}
