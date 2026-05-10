import { useEffect, useMemo, useState } from "react";
import { listServiqTools, setServiqToolEnabled, type ServiqTool } from "../../lib/toolsApi";
import "../../styles/tools-panel.css";
import "../../styles/refresh-button-icon.css";

function RefreshIcon() {
  return (
    <svg aria-hidden="true" className="refresh-button-icon" viewBox="0 0 24 24">
      <path d="M20 12a8 8 0 1 1-2.34-5.66" />
      <path d="M20 4v5h-5" />
    </svg>
  );
}

function ToolIcon({ icon }: { icon: string }) {
  if (icon === "terminal") {
    return (
      <svg aria-hidden="true" className="tool-card__svg" viewBox="0 0 24 24">
        <path d="m6 8 4 4-4 4" />
        <path d="M12 17h6" />
      </svg>
    );
  }

  if (icon === "folder") {
    return (
      <svg aria-hidden="true" className="tool-card__svg" viewBox="0 0 24 24">
        <path d="M3.5 7.5A2.5 2.5 0 0 1 6 5h4l2 2h6A2.5 2.5 0 0 1 20.5 9.5v7A2.5 2.5 0 0 1 18 19H6a2.5 2.5 0 0 1-2.5-2.5v-9Z" />
      </svg>
    );
  }

  if (icon === "file-text") {
    return (
      <svg aria-hidden="true" className="tool-card__svg" viewBox="0 0 24 24">
        <path d="M7 3.5h7l3 3V20.5H7V3.5Z" />
        <path d="M14 3.5v3h3" />
        <path d="M9 11h6" />
        <path d="M9 14h6" />
        <path d="M9 17h4" />
      </svg>
    );
  }

  if (icon === "file-plus") {
    return (
      <svg aria-hidden="true" className="tool-card__svg" viewBox="0 0 24 24">
        <path d="M7 3.5h7l3 3V20.5H7V3.5Z" />
        <path d="M14 3.5v3h3" />
        <path d="M12 11v6" />
        <path d="M9 14h6" />
      </svg>
    );
  }

  if (icon === "edit") {
    return (
      <svg aria-hidden="true" className="tool-card__svg" viewBox="0 0 24 24">
        <path d="M5 18.5 6 14l9.5-9.5 4 4L10 18l-5 1Z" />
        <path d="m14 6 4 4" />
      </svg>
    );
  }

  if (icon === "search") {
    return (
      <svg aria-hidden="true" className="tool-card__svg" viewBox="0 0 24 24">
        <circle cx="10.5" cy="10.5" r="5.5" />
        <path d="m15 15 4 4" />
      </svg>
    );
  }

  if (icon === "cpu") {
    return (
      <svg aria-hidden="true" className="tool-card__svg" viewBox="0 0 24 24">
        <rect x="7" y="7" width="10" height="10" rx="2" />
        <path d="M10 3v4" />
        <path d="M14 3v4" />
        <path d="M10 17v4" />
        <path d="M14 17v4" />
        <path d="M3 10h4" />
        <path d="M3 14h4" />
        <path d="M17 10h4" />
        <path d="M17 14h4" />
      </svg>
    );
  }

  if (icon === "memory") {
    return (
      <svg aria-hidden="true" className="tool-card__svg" viewBox="0 0 24 24">
        <path d="M8 8.5a4 4 0 0 1 8 0v7a4 4 0 0 1-8 0v-7Z" />
        <path d="M8 10h8" />
        <path d="M8 14h8" />
        <path d="M5 10h3" />
        <path d="M16 10h3" />
        <path d="M5 14h3" />
        <path d="M16 14h3" />
      </svg>
    );
  }

  return (
    <svg aria-hidden="true" className="tool-card__svg" viewBox="0 0 24 24">
      <path d="M12 3.5 20.5 8v8L12 20.5 3.5 16V8L12 3.5Z" />
      <path d="M12 12 20.5 8" />
      <path d="M12 12v8.5" />
      <path d="M12 12 3.5 8" />
    </svg>
  );
}

function riskLabel(risk: string) {
  if (risk === "low") {
    return "Low risk";
  }

  if (risk === "medium") {
    return "Medium risk";
  }

  if (risk === "high") {
    return "High risk";
  }

  return risk;
}

function ToolSwitch({
  checked,
  disabled,
  onChange,
}: {
  checked: boolean;
  disabled: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <button
      type="button"
      className={`tool-switch ${checked ? "tool-switch--on" : "tool-switch--off"}`}
      onClick={() => onChange(!checked)}
      disabled={disabled}
      aria-pressed={checked}
      aria-label={checked ? "Disable tool" : "Enable tool"}
    >
      <span />
    </button>
  );
}

export function ToolsPanel() {
  const [tools, setTools] = useState<ServiqTool[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingToolId, setSavingToolId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const enabledCount = useMemo(() => tools.filter((tool) => tool.enabled).length, [tools]);
  const disabledCount = tools.length - enabledCount;

  async function loadTools() {
    setLoading(true);

    try {
      const loadedTools = await listServiqTools();
      setTools(loadedTools);
      setError(null);
    } catch (toolError) {
      setError(toolError instanceof Error ? toolError.message : "Unable to load tools.");
    } finally {
      setLoading(false);
    }
  }

  async function updateTool(toolId: string, enabled: boolean) {
    setSavingToolId(toolId);

    setTools((currentTools) =>
      currentTools.map((tool) =>
        tool.id === toolId
          ? {
              ...tool,
              enabled,
            }
          : tool,
      ),
    );

    try {
      const updatedTool = await setServiqToolEnabled(toolId, enabled);
      setTools((currentTools) =>
        currentTools.map((tool) => (tool.id === toolId ? updatedTool : tool)),
      );
      setError(null);
    } catch (toolError) {
      setError(toolError instanceof Error ? toolError.message : "Unable to update tool.");

      setTools((currentTools) =>
        currentTools.map((tool) =>
          tool.id === toolId
            ? {
                ...tool,
                enabled: !enabled,
              }
            : tool,
        ),
      );
    } finally {
      setSavingToolId(null);
    }
  }

  useEffect(() => {
    void loadTools();
  }, []);

  return (
    <section className="tools-panel">
      <header className="tools-panel__header">
        <div>
          <span className="tools-panel__eyebrow">Tools</span>
          <h2>Tool control center</h2>
          <p>
            Turn tools on or off. Disabled tools are blocked by the backend before execution.
          </p>
        </div>

        <button
          type="button"
          className="tools-panel__refresh"
          onClick={() => void loadTools()}
          disabled={loading}
        >
          <RefreshIcon />
          <span>{loading ? "Refreshing..." : "Refresh"}</span>
        </button>
      </header>

      <div className="tools-summary">
        <article>
          <span>Total tools</span>
          <strong>{tools.length}</strong>
        </article>
        <article>
          <span>Enabled</span>
          <strong>{enabledCount}</strong>
        </article>
        <article>
          <span>Disabled</span>
          <strong>{disabledCount}</strong>
        </article>
      </div>

      {error ? <p className="tools-panel__error">{error}</p> : null}

      <div className="tools-grid">
        {loading && tools.length === 0 ? (
          <div className="tools-empty-state">Loading Serviq tools...</div>
        ) : null}

        {!loading && tools.length === 0 ? (
          <div className="tools-empty-state">
            No tools found. Check whether the backend tool settings route is registered.
          </div>
        ) : null}

        {tools.map((tool) => {
          const saving = savingToolId === tool.id;

          return (
            <article
              key={tool.id}
              className={`tool-card ${tool.enabled ? "tool-card--enabled" : "tool-card--disabled"}`}
            >
              <div className="tool-card__top">
                <div className="tool-card__icon">
                  <ToolIcon icon={tool.icon} />
                </div>

                <ToolSwitch
                  checked={tool.enabled}
                  disabled={saving}
                  onChange={(checked) => void updateTool(tool.id, checked)}
                />
              </div>

              <div className="tool-card__body">
                <span className={`tool-card__risk tool-card__risk--${tool.risk}`}>
                  {riskLabel(tool.risk)}
                </span>
                <h3>{tool.name}</h3>
                <p>{tool.description}</p>
              </div>

              <footer className="tool-card__footer">
                <code>{tool.id}</code>
                <strong>{tool.enabled ? "On" : "Off"}</strong>
              </footer>
            </article>
          );
        })}
      </div>
    </section>
  );
}
