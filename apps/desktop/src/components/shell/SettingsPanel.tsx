import { useEffect, useState } from "react";
import type { ChatModel } from "../../lib/chatApi";
import {
  getRuntimeSettings,
  updateRuntimeSettings,
  type AnswerStyle,
} from "../../lib/runtimeSettingsApi";

import "../../styles/settings-panel.css";
import "../../styles/refresh-button-icon.css";
import "../../styles/directory-access-settings.css";

function RefreshIcon() {
  return (
    <svg aria-hidden="true" className="refresh-button-icon" viewBox="0 0 24 24">
      <path d="M20 12a8 8 0 1 1-2.34-5.66" />
      <path d="M20 4v5h-5" />
    </svg>
  );
}

function SettingDot({ active }: { active: boolean }) {
  return (
    <span
      className={`setting-status-dot ${
        active ? "setting-status-dot--ready" : "setting-status-dot--missing"
      }`}
      aria-hidden="true"
    />
  );
}

function AnswerStyleSwitch({
  value,
  disabled,
  onChange,
}: {
  value: AnswerStyle;
  disabled: boolean;
  onChange: (style: AnswerStyle) => void;
}) {
  const concise = value === "concise";
  return (
    <button
      type="button"
      className={`settings-switch ${
        concise ? "settings-switch--on" : "settings-switch--off"
      }`}
      onClick={() => onChange(concise ? "normal" : "concise")}
      disabled={disabled}
      aria-pressed={concise}
    >
      <span className="settings-switch__track">
        <span className="settings-switch__thumb" />
      </span>
      <span className="settings-switch__text">
        {concise ? "Short and direct" : "Normal"}
      </span>
    </button>
  );
}

function DirectoryAccessSettings() {
  const [workspacePath, setWorkspacePath] = useState("");
  const [directories, setDirectories] = useState<string[]>([]);
  const [newDirectory, setNewDirectory] = useState("");
  const [caution, setCaution] = useState(
    "Only add specific project folders. Do not add root, drive, Windows, or system directories.",
  );
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadDirectorySettings() {
    setLoading(true);
    try {
      const settings = await getRuntimeSettings();
      setWorkspacePath(settings.workspace_path);
      setDirectories(settings.accessible_directories);
      if (settings.directory_caution) {
        setCaution(settings.directory_caution);
      }
      setError(null);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to load directory access settings.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function saveDirectories(nextDirectories: string[]) {
    setSaving(true);
    try {
      const settings = await updateRuntimeSettings({
        accessible_directories: nextDirectories,
      });
      setWorkspacePath(settings.workspace_path);
      setDirectories(settings.accessible_directories);
      setNewDirectory("");
      if (settings.directory_caution) {
        setCaution(settings.directory_caution);
      }
      setError(null);
    } catch (saveError) {
      setError(
        saveError instanceof Error
          ? saveError.message
          : "Unable to save directory access settings.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleAddDirectory() {
    const value = newDirectory.trim();
    if (!value) {
      setError("Enter a directory path first.");
      return;
    }

    const duplicate = directories.some(
      (directory) => directory.toLowerCase() === value.toLowerCase(),
    );
    if (duplicate) {
      setError("This directory is already added.");
      return;
    }

    await saveDirectories([...directories, value]);
  }

  async function handleRemoveDirectory(directoryToRemove: string) {
    await saveDirectories(
      directories.filter((directory) => directory !== directoryToRemove),
    );
  }

  useEffect(() => {
    void loadDirectorySettings();
  }, []);

  return (
    <article className="setting-row setting-row--directory-access">
      <div className="setting-row__main">
        <div className="setting-row__title">
          <SettingDot active />
          <div>
            <h3>Directory access</h3>
            <p>Add folders Serviq can read, write, list, and use as shell cwd.</p>
          </div>
        </div>

        <div className="directory-access-caution" role="note">
          <strong>Caution</strong>
          <span>{caution}</span>
        </div>

        <div className="directory-access-default">
          <span>Default workspace</span>
          <strong>{workspacePath || "Loading workspace..."}</strong>
        </div>
      </div>

      <div className="directory-access-control">
        <label className="directory-access-input">
          <span>Add directory</span>
          <input
            value={newDirectory}
            onChange={(event) => setNewDirectory(event.target.value)}
            placeholder="Example: D:\\Projects\\MyApp or /home/fahim/projects/my-app"
            disabled={loading || saving}
          />
        </label>
        <button
          type="button"
          className="directory-access-add"
          onClick={() => void handleAddDirectory()}
          disabled={loading || saving || !newDirectory.trim()}
        >
          {saving ? "Saving..." : "Add"}
        </button>
      </div>

      {error ? <p className="directory-access-error">{error}</p> : null}

      <div className="directory-access-list">
        {directories.length === 0 ? (
          <p className="directory-access-empty">
            No custom directories added. Serviq can only access the default workspace.
          </p>
        ) : (
          directories.map((directory) => (
            <div className="directory-access-item" key={directory}>
              <code>{directory}</code>
              <button
                type="button"
                onClick={() => void handleRemoveDirectory(directory)}
                disabled={saving}
              >
                Remove
              </button>
            </div>
          ))
        )}
      </div>
    </article>
  );
}

function AdminShellSettings() {
  const [enabled, setEnabled] = useState(false);
  const [caution, setCaution] = useState(
    "Windows only. Enabled shell commands launch with a UAC administrator prompt after approval.",
  );
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadAdminShellSettings() {
    setLoading(true);
    try {
      const settings = await getRuntimeSettings();
      setEnabled(settings.shell_run_as_administrator);
      if (settings.shell_admin_caution) {
        setCaution(settings.shell_admin_caution);
      }
      setError(null);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to load administrator shell settings.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleToggle() {
    const nextEnabled = !enabled;
    setSaving(true);
    try {
      const settings = await updateRuntimeSettings({
        shell_run_as_administrator: nextEnabled,
      });
      setEnabled(settings.shell_run_as_administrator);
      if (settings.shell_admin_caution) {
        setCaution(settings.shell_admin_caution);
      }
      setError(null);
    } catch (saveError) {
      setError(
        saveError instanceof Error
          ? saveError.message
          : "Unable to save administrator shell settings.",
      );
    } finally {
      setSaving(false);
    }
  }

  useEffect(() => {
    void loadAdminShellSettings();
  }, []);

  return (
    <article className="setting-row setting-row--admin-shell">
      <div className="setting-row__main">
        <div className="setting-row__title">
          <SettingDot active={enabled} />
          <div>
            <h3>Run shell as administrator</h3>
            <p>Use Windows UAC elevation for approved shell commands.</p>
          </div>
        </div>

        <div className="directory-access-caution admin-shell-caution" role="note">
          <strong>Caution</strong>
          <span>{caution}</span>
        </div>
      </div>

      <button
        type="button"
        className={`settings-switch admin-shell-switch ${
          enabled ? "settings-switch--on" : "settings-switch--off"
        }`}
        onClick={() => void handleToggle()}
        disabled={loading || saving}
        aria-pressed={enabled}
      >
        <span className="settings-switch__track">
          <span className="settings-switch__thumb" />
        </span>
        <span className="settings-switch__text">
          {enabled ? "Administrator shell on" : "Administrator shell off"}
        </span>
      </button>

      {error ? <p className="directory-access-error">{error}</p> : null}
    </article>
  );
}

export function SettingsPanel({
  models,
  selectedModelId,
  selectedEmbeddingModelId,
  answerStyle,
  loading,
  saving,
  error,
  onSelectModel,
  onSelectEmbeddingModel,
  onSelectAnswerStyle,
  onRefreshModels,
}: {
  models: ChatModel[];
  selectedModelId: string;
  selectedEmbeddingModelId: string;
  answerStyle: AnswerStyle;
  loading: boolean;
  saving: boolean;
  error: string | null;
  onSelectModel: (modelId: string) => void;
  onSelectEmbeddingModel: (modelId: string) => void;
  onSelectAnswerStyle: (style: AnswerStyle) => void;
  onRefreshModels: () => void;
}) {
  const selectedModel =
    models.find((model) => model.id === selectedModelId) ?? null;
  const selectedEmbeddingModel =
    models.find((model) => model.id === selectedEmbeddingModelId) ?? null;
  const activeModelLabel =
    selectedModel?.name ?? (selectedModelId || "No chat model selected");
  const activeEmbeddingLabel =
    selectedEmbeddingModel?.name ??
    (selectedEmbeddingModelId || "No embedding model selected");

  return (
    <section className="settings-panel">
      <header className="settings-panel__header">
        <div>
          <span className="settings-panel__eyebrow">Settings</span>
          <h2>Settings</h2>
          <p>
            Control Serviq model, memory embedding, answer style, directory access,
            and administrator shell mode.
          </p>
        </div>
        <button
          type="button"
          className="settings-panel__refresh"
          onClick={onRefreshModels}
          disabled={loading}
        >
          <RefreshIcon />
          <span>{loading ? "Refreshing..." : "Refresh"}</span>
        </button>
      </header>

      {error ? <p className="settings-panel__error">{error}</p> : null}

      <div className="settings-list">
        <article className="setting-row">
          <div className="setting-row__main">
            <div className="setting-row__title">
              <SettingDot active={Boolean(selectedModelId)} />
              <div>
                <h3>Chat model</h3>
                <p>The local model Serviq uses to answer chat messages.</p>
              </div>
            </div>
            <div className="setting-row__current">
              <span>Selected</span>
              <strong>{activeModelLabel}</strong>
            </div>
          </div>

          <label className="settings-select">
            <span>Choose chat model</span>
            <select
              value={selectedModelId}
              onChange={(event) => onSelectModel(event.target.value)}
              disabled={loading || models.length === 0}
            >
              {models.length === 0 ? <option value="">No models found</option> : null}
              {models.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name}
                </option>
              ))}
            </select>
          </label>
        </article>

        <article className="setting-row">
          <div className="setting-row__main">
            <div className="setting-row__title">
              <SettingDot active={Boolean(selectedEmbeddingModelId)} />
              <div>
                <h3>Embedding model</h3>
                <p>The model used for memory search and semantic recall.</p>
              </div>
            </div>
            <div className="setting-row__current">
              <span>Selected</span>
              <strong>{activeEmbeddingLabel}</strong>
            </div>
          </div>

          <label className="settings-select">
            <span>Choose embedding model</span>
            <select
              value={selectedEmbeddingModelId}
              onChange={(event) => onSelectEmbeddingModel(event.target.value)}
              disabled={loading || saving || models.length === 0}
            >
              {models.length === 0 ? <option value="">No models found</option> : null}
              {models.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name}
                </option>
              ))}
            </select>
          </label>
        </article>

        <article className="setting-row setting-row--switch">
          <div className="setting-row__main">
            <div className="setting-row__title">
              <SettingDot active />
              <div>
                <h3>Answer style</h3>
                <p>Short and direct keeps answers precise. Normal allows longer explanations.</p>
              </div>
            </div>
            <AnswerStyleSwitch
              value={answerStyle}
              disabled={saving}
              onChange={onSelectAnswerStyle}
            />
          </div>
        </article>

        <DirectoryAccessSettings />
        <AdminShellSettings />
      </div>
    </section>
  );
}
