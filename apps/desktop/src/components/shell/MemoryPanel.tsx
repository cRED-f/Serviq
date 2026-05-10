import { FormEvent, useEffect, useMemo, useState } from 'react';
import {
  archiveMemoryItem,
  createMemoryItem,
  deleteMemoryItem,
  listMemoryItems,
  restoreMemoryItem,
  updateMemoryItem,
  type MemoryImportance,
  type MemoryItem,
  type MemoryStats,
  type MemoryStatus,
} from '../../lib/memoryApi';
import '../../styles/memory-panel.css';
import '../../styles/refresh-button-icon.css';

const EMPTY_STATS: MemoryStats = { counts: { active: 0, archived: 0, deleted: 0 }, categories: [] };

function RefreshIcon() {
  return <svg aria-hidden="true" className="refresh-button-icon" viewBox="0 0 24 24"><path d="M20 12a8 8 0 1 1-2.34-5.66"/><path d="M20 4v5h-5"/></svg>;
}

function SearchIcon() {
  return <svg aria-hidden="true" className="memory-search-icon" viewBox="0 0 24 24"><circle cx="10.5" cy="10.5" r="5.5"/><path d="m15 15 4 4"/></svg>;
}

function MemoryIcon() {
  return <svg aria-hidden="true" className="memory-card__svg" viewBox="0 0 24 24"><path d="M8 8.5a4 4 0 0 1 8 0v7a4 4 0 0 1-8 0v-7Z"/><path d="M8 10h8"/><path d="M8 14h8"/><path d="M5 10h3"/><path d="M16 10h3"/><path d="M5 14h3"/><path d="M16 14h3"/></svg>;
}

function formatDate(value?: string | null) {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function getPreview(content: string) {
  const clean = content.trim().replace(/\s+/g, ' ');
  return clean.length > 190 ? `${clean.slice(0, 190)}...` : clean;
}

function statusLabel(status: MemoryStatus) {
  return status === 'active' ? 'Active' : status === 'archived' ? 'Archived' : 'Deleted';
}

function importanceLabel(importance: MemoryImportance) {
  return importance === 'low' ? 'Low' : importance === 'medium' ? 'Medium' : 'High';
}

function MemoryForm({ saving, onSubmit }: { saving: boolean; onSubmit: (input: { title: string; content: string; category: string; importance: MemoryImportance }) => void }) {
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [category, setCategory] = useState('general');
  const [importance, setImportance] = useState<MemoryImportance>('medium');

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanContent = content.trim();
    if (!cleanContent) return;
    onSubmit({ title: title.trim(), content: cleanContent, category: category.trim() || 'general', importance });
    setTitle('');
    setContent('');
    setCategory('general');
    setImportance('medium');
  }

  return (
    <form className="memory-form" onSubmit={handleSubmit}>
      <div className="memory-form__top">
        <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Optional title" disabled={saving}/>
        <input value={category} onChange={(event) => setCategory(event.target.value)} placeholder="Category" disabled={saving}/>
        <select value={importance} onChange={(event) => setImportance(event.target.value as MemoryImportance)} disabled={saving}>
          <option value="low">Low importance</option>
          <option value="medium">Medium importance</option>
          <option value="high">High importance</option>
        </select>
      </div>
      <textarea value={content} onChange={(event) => setContent(event.target.value)} placeholder="Save a memory manually..." disabled={saving}/>
      <div className="memory-form__footer">
        <span>Manual memories become active immediately.</span>
        <button type="submit" disabled={saving || !content.trim()}>{saving ? 'Saving...' : 'Save memory'}</button>
      </div>
    </form>
  );
}

function MemoryCard({ memory, actionBusy, onArchive, onRestore, onDelete, onUpdate }: {
  memory: MemoryItem;
  actionBusy: boolean;
  onArchive: (memory: MemoryItem) => void;
  onRestore: (memory: MemoryItem) => void;
  onDelete: (memory: MemoryItem) => void;
  onUpdate: (memory: MemoryItem, input: { title: string; content: string; category: string; importance: MemoryImportance }) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(memory.title);
  const [content, setContent] = useState(memory.content);
  const [category, setCategory] = useState(memory.category);
  const [importance, setImportance] = useState<MemoryImportance>(memory.importance);

  useEffect(() => {
    setTitle(memory.title);
    setContent(memory.content);
    setCategory(memory.category);
    setImportance(memory.importance);
  }, [memory]);

  function saveEdit() {
    onUpdate(memory, { title, content, category, importance });
    setEditing(false);
  }

  return (
    <article className={`memory-card memory-card--${memory.status}`}>
      <div className="memory-card__top">
        <div className="memory-card__icon"><MemoryIcon /></div>
        <div className="memory-card__badges">
          <span className={`memory-card__importance memory-card__importance--${memory.importance}`}>{importanceLabel(memory.importance)}</span>
          <span className={`memory-card__status memory-card__status--${memory.status}`}>{statusLabel(memory.status)}</span>
        </div>
      </div>

      {editing ? (
        <div className="memory-edit">
          <input value={title} onChange={(event) => setTitle(event.target.value)} disabled={actionBusy}/>
          <textarea value={content} onChange={(event) => setContent(event.target.value)} disabled={actionBusy}/>
          <div className="memory-edit__row">
            <input value={category} onChange={(event) => setCategory(event.target.value)} disabled={actionBusy}/>
            <select value={importance} onChange={(event) => setImportance(event.target.value as MemoryImportance)} disabled={actionBusy}>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </div>
        </div>
      ) : (
        <div className="memory-card__body">
          <h3>{memory.title}</h3>
          <p>{getPreview(memory.content)}</p>
        </div>
      )}

      <footer className="memory-card__footer">
        <div className="memory-card__meta">
          <span>{memory.category}</span>
          <span>{memory.source}</span>
          <span>{formatDate(memory.updated_at)}</span>
        </div>
        <div className="memory-card__actions">
          {editing ? (
            <>
              <button type="button" onClick={saveEdit} disabled={actionBusy || !content.trim()}>Save</button>
              <button type="button" onClick={() => setEditing(false)} disabled={actionBusy}>Cancel</button>
            </>
          ) : (
            <>
              {memory.status === 'active' ? <button type="button" onClick={() => onArchive(memory)} disabled={actionBusy}>Archive</button> : null}
              {memory.status === 'archived' ? <button type="button" onClick={() => onRestore(memory)} disabled={actionBusy}>Restore</button> : null}
              {memory.status !== 'deleted' ? <button type="button" onClick={() => setEditing(true)} disabled={actionBusy}>Edit</button> : null}
              {memory.status !== 'deleted' ? <button type="button" className="memory-card__danger" onClick={() => onDelete(memory)} disabled={actionBusy}>Delete</button> : null}
            </>
          )}
        </div>
      </footer>
    </article>
  );
}

export function MemoryPanel() {
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [stats, setStats] = useState<MemoryStats>(EMPTY_STATS);
  const [activeStatus, setActiveStatus] = useState<MemoryStatus>('active');
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [busyMemoryId, setBusyMemoryId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const statusTabs = useMemo(() => [
    { status: 'active' as MemoryStatus, label: 'Active', count: stats.counts.active },
    { status: 'archived' as MemoryStatus, label: 'Archived', count: stats.counts.archived },
    { status: 'deleted' as MemoryStatus, label: 'Deleted', count: stats.counts.deleted },
  ], [stats]);

  async function loadMemories(nextStatus = activeStatus, nextQuery = query) {
    setLoading(true);
    try {
      const result = await listMemoryItems({ status: nextStatus, query: nextQuery });
      setMemories(result.memories);
      setStats(result.stats);
      setError(null);
    } catch (memoryError) {
      setError(memoryError instanceof Error ? memoryError.message : 'Unable to load memory.');
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(input: { title: string; content: string; category: string; importance: MemoryImportance }) {
    setSaving(true);
    try {
      await createMemoryItem(input);
      setActiveStatus('active');
      await loadMemories('active', query);
      setError(null);
    } catch (memoryError) {
      setError(memoryError instanceof Error ? memoryError.message : 'Unable to save memory.');
    } finally {
      setSaving(false);
    }
  }

  async function runAction(memory: MemoryItem, action: () => Promise<unknown>, fallback: string) {
    setBusyMemoryId(memory.id);
    try {
      await action();
      await loadMemories(activeStatus, query);
    } catch (memoryError) {
      setError(memoryError instanceof Error ? memoryError.message : fallback);
    } finally {
      setBusyMemoryId(null);
    }
  }

  useEffect(() => { void loadMemories(activeStatus, query); }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => { void loadMemories(activeStatus, query); }, 350);
    return () => window.clearTimeout(timer);
  }, [query, activeStatus]);

  return (
    <section className="memory-panel">
      <header className="memory-panel__header">
        <div>
          <span className="memory-panel__eyebrow">Memory</span>
          <h2>Memory center</h2>
          <p>Review what Serviq remembers, add manual memories, and archive or delete anything that should not be reused.</p>
        </div>
        <button type="button" className="memory-panel__refresh" onClick={() => void loadMemories(activeStatus, query)} disabled={loading}>
          <RefreshIcon />
          <span>{loading ? 'Refreshing...' : 'Refresh'}</span>
        </button>
      </header>

      <div className="memory-summary">
        <article><span>Active</span><strong>{stats.counts.active}</strong></article>
        <article><span>Archived</span><strong>{stats.counts.archived}</strong></article>
        <article><span>Visible</span><strong>{memories.length}</strong></article>
      </div>

      <MemoryForm saving={saving} onSubmit={(input) => void handleCreate(input)} />

      <div className="memory-controls">
        <div className="memory-tabs">
          {statusTabs.map((tab) => (
            <button key={tab.status} type="button" className={activeStatus === tab.status ? 'memory-tab memory-tab--active' : 'memory-tab'} onClick={() => setActiveStatus(tab.status)}>
              <span>{tab.label}</span><strong>{tab.count}</strong>
            </button>
          ))}
        </div>
        <label className="memory-search"><SearchIcon /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search memory..." /></label>
      </div>

      {error ? <p className="memory-panel__error">{error}</p> : null}

      <div className="memory-grid">
        {loading && memories.length === 0 ? <div className="memory-empty-state">Loading memory...</div> : null}
        {!loading && memories.length === 0 ? <div className="memory-empty-state">No {activeStatus} memories found.</div> : null}
        {memories.map((memory) => (
          <MemoryCard
            key={memory.id}
            memory={memory}
            actionBusy={busyMemoryId === memory.id}
            onArchive={(item) => void runAction(item, () => archiveMemoryItem(item.id), 'Unable to archive memory.')}
            onRestore={(item) => void runAction(item, () => restoreMemoryItem(item.id), 'Unable to restore memory.')}
            onDelete={(item) => void runAction(item, () => deleteMemoryItem(item.id), 'Unable to delete memory.')}
            onUpdate={(item, input) => void runAction(item, () => updateMemoryItem({ memoryId: item.id, ...input }), 'Unable to update memory.')}
          />
        ))}
      </div>
    </section>
  );
}
