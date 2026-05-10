import { SERVIQ_API_BASE_URL } from './config';

export type MemoryStatus = 'active' | 'archived' | 'deleted';
export type MemoryImportance = 'low' | 'medium' | 'high';

export type MemoryItem = {
  id: string;
  title: string;
  content: string;
  category: string;
  importance: MemoryImportance;
  source: string;
  status: MemoryStatus;
  created_at: string;
  updated_at: string;
  archived_at?: string | null;
  deleted_at?: string | null;
};

export type MemoryStats = {
  counts: { active: number; archived: number; deleted: number };
  categories: Array<{ category: string; count: number }>;
};

async function readError(response: Response) {
  try {
    const payload = await response.json();
    const detail = payload.detail ?? payload.error ?? `HTTP ${response.status}`;
    return typeof detail === 'string' ? detail : detail.message ?? JSON.stringify(detail);
  } catch {
    return (await response.text()) || `HTTP ${response.status}`;
  }
}

export async function listMemoryItems({ status = 'active', query = '' }: { status?: MemoryStatus; query?: string } = {}): Promise<{ memories: MemoryItem[]; stats: MemoryStats }> {
  const url = new URL(`${SERVIQ_API_BASE_URL}/api/memory-center`);
  url.searchParams.set('status', status);
  if (query.trim()) url.searchParams.set('query', query.trim());
  const response = await fetch(url.toString(), { method: 'GET', headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error(await readError(response));
  const payload = await response.json();
  return {
    memories: Array.isArray(payload.memories) ? payload.memories : [],
    stats: payload.stats ?? { counts: { active: 0, archived: 0, deleted: 0 }, categories: [] },
  };
}

export async function createMemoryItem(input: { title?: string; content: string; category: string; importance: MemoryImportance }): Promise<MemoryItem> {
  const response = await fetch(`${SERVIQ_API_BASE_URL}/api/memory-center`, {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...input, source: 'manual' }),
  });
  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()).memory as MemoryItem;
}

export async function updateMemoryItem(input: { memoryId: string; title?: string; content?: string; category?: string; importance?: MemoryImportance }): Promise<MemoryItem> {
  const { memoryId, ...body } = input;
  const response = await fetch(`${SERVIQ_API_BASE_URL}/api/memory-center/${encodeURIComponent(memoryId)}`, {
    method: 'PATCH',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()).memory as MemoryItem;
}

export async function archiveMemoryItem(memoryId: string): Promise<MemoryItem> {
  const response = await fetch(`${SERVIQ_API_BASE_URL}/api/memory-center/${encodeURIComponent(memoryId)}/archive`, { method: 'POST', headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()).memory as MemoryItem;
}

export async function restoreMemoryItem(memoryId: string): Promise<MemoryItem> {
  const response = await fetch(`${SERVIQ_API_BASE_URL}/api/memory-center/${encodeURIComponent(memoryId)}/restore`, { method: 'POST', headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()).memory as MemoryItem;
}

export async function deleteMemoryItem(memoryId: string): Promise<void> {
  const response = await fetch(`${SERVIQ_API_BASE_URL}/api/memory-center/${encodeURIComponent(memoryId)}`, { method: 'DELETE', headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error(await readError(response));
}
