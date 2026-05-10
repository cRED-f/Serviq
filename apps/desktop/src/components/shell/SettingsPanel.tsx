import type { ChatModel } from "../../lib/chatApi";
import type { AnswerStyle } from "../../lib/runtimeSettingsApi";
import "../../styles/settings-panel.css";
import "../../styles/refresh-button-icon.css";

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
      className={`setting-status-dot ${active ? "setting-status-dot--ready" : "setting-status-dot--missing"}`}
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
      className={`settings-switch ${concise ? "settings-switch--on" : "settings-switch--off"}`}
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
  const selectedModel = models.find((model) => model.id === selectedModelId) ?? null;
  const selectedEmbeddingModel = models.find((model) => model.id === selectedEmbeddingModelId) ?? null;

  const activeModelLabel = selectedModel?.name ?? (selectedModelId || "No chat model selected");
  const activeEmbeddingLabel =
    selectedEmbeddingModel?.name ?? (selectedEmbeddingModelId || "No embedding model selected");

  return (
    <section className="settings-panel">
      <header className="settings-panel__header">
        <div>
          <span className="settings-panel__eyebrow">Settings</span>
          <h2>Settings</h2>
          <p>Control Serviq model, memory embedding, and answer style.</p>
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
      </div>
    </section>
  );
}
