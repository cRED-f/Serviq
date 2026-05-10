import { SERVIQ_API_BASE_URL } from "./config";

export type SemanticMemoryHealth = {
  status: string;
  stage?: string;
  sqlite?: Record<string, unknown>;
  qdrant?: Record<string, unknown>;
  embedding?: Record<string, unknown>;
  semantic_memory_enabled?: boolean;
};

export type SaveMemoryResponse = {
  item: Record<string, unknown>;
  vector_status?: Record<string, unknown> | null;
};

export type SearchMemoryResponse = {
  query: string;
  mode: string;
  items: Record<string, unknown>[];
  semantic_count: number;
  keyword_count: number;
  error?: string | null;
  embedding_model: string;
  qdrant_collection: string;
};

export async function getSemanticMemoryHealth(): Promise<SemanticMemoryHealth> {
  const response = await fetch(`${SERVIQ_API_BASE_URL}/api/memory/health`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Memory health failed with status ${response.status}`);
  }

  return (await response.json()) as SemanticMemoryHealth;
}

export async function saveSemanticMemory(input: {
  title: string;
  content: string;
  tags?: string[];
}): Promise<SaveMemoryResponse> {
  const response = await fetch(`${SERVIQ_API_BASE_URL}/api/memory/save`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      kind: "note",
      title: input.title,
      content: input.content,
      source: "semantic_memory_panel",
      tags: input.tags ?? ["manual", "semantic"],
      embed: true,
    }),
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Save semantic memory failed with status ${response.status}: ${body}`);
  }

  return (await response.json()) as SaveMemoryResponse;
}

export async function searchSemanticMemory(query: string, limit = 5): Promise<SearchMemoryResponse> {
  const response = await fetch(`${SERVIQ_API_BASE_URL}/api/memory/search`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ query, limit }),
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Search semantic memory failed with status ${response.status}: ${body}`);
  }

  return (await response.json()) as SearchMemoryResponse;
}
