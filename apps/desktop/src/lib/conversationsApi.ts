import { SERVIQ_API_BASE_URL } from "./config";

export type ConversationSession = {
  session_id: string;
  message_count: number;
  first_message_at?: string | null;
  last_message_at?: string | null;
};

export type ConversationMessage = {
  id: string;
  session_id: string;
  role: string;
  content: string;
  model?: string | null;
  route?: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
};

export async function listConversationSessions(limit = 20): Promise<ConversationSession[]> {
  const response = await fetch(`${SERVIQ_API_BASE_URL}/api/conversations/sessions?limit=${limit}`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`List conversation sessions failed with status ${response.status}`);
  }

  const payload = (await response.json()) as { sessions: ConversationSession[] };
  return payload.sessions;
}

export async function listConversationMessages(
  sessionId: string,
  limit = 50,
): Promise<ConversationMessage[]> {
  const response = await fetch(
    `${SERVIQ_API_BASE_URL}/api/conversations/${encodeURIComponent(sessionId)}/messages?limit=${limit}`,
    {
      method: "GET",
      headers: { Accept: "application/json" },
    },
  );

  if (!response.ok) {
    throw new Error(`List conversation messages failed with status ${response.status}`);
  }

  const payload = (await response.json()) as { messages: ConversationMessage[] };
  return payload.messages;
}

export async function searchConversations(
  query: string,
  limit = 20,
): Promise<ConversationMessage[]> {
  const response = await fetch(`${SERVIQ_API_BASE_URL}/api/conversations/search`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ query, limit }),
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Search conversations failed with status ${response.status}: ${body}`);
  }

  const payload = (await response.json()) as { messages: ConversationMessage[] };
  return payload.messages;
}
