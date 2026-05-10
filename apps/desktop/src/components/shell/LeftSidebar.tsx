import "../../styles/sidebar-chat-actions.css";

export type SidebarView = "home" | "chat" | "tools" | "memory" | "settings";

export type ChatHistoryItem = {
  id: string;
  title: string;
  preview: string;
  time: string;
  persisted?: boolean;
};

type SidebarButton = {
  key: SidebarView;
  label: string;
  icon: string;
};

const TOP_ACTIONS: SidebarButton[] = [
  { key: "home", label: "Home", icon: "⌂" },
  { key: "tools", label: "Tools", icon: "⌘" },
  { key: "memory", label: "Memory", icon: "◌" },
];

function SidebarDeleteIcon() {
  return (
    <svg aria-hidden="true" className="sidebar-delete-icon" viewBox="0 0 24 24">
      <path d="M5 7h14" />
      <path d="M10 11v6" />
      <path d="M14 11v6" />
      <path d="M8 7l.7 12A2 2 0 0 0 10.7 21h2.6a2 2 0 0 0 2-1.9L16 7" />
      <path d="M9 7V5.5A1.5 1.5 0 0 1 10.5 4h3A1.5 1.5 0 0 1 15 5.5V7" />
    </svg>
  );
}

export function LeftSidebar({
  collapsed,
  activeView,
  chatHistory,
  selectedChatId,
  onToggleCollapse,
  onViewChange,
  onNewChat,
  onSelectChat,
  onDeleteChat,
}: {
  collapsed: boolean;
  activeView: SidebarView;
  chatHistory: ChatHistoryItem[];
  selectedChatId: string;
  onToggleCollapse: () => void;
  onViewChange: (view: SidebarView) => void;
  onNewChat: () => void;
  onSelectChat: (chatId: string) => void;
  onDeleteChat: (chatId: string) => void;
}) {
  return (
    <aside className={`sidebar-shell ${collapsed ? "sidebar-shell--collapsed" : ""}`}>
      <div className="sidebar-shell__panel">
        <header className="sidebar-shell__header">
          <button
            type="button"
            className="sidebar-toggle"
            onClick={onToggleCollapse}
            aria-label={collapsed ? "Show sidebar" : "Hide sidebar"}
          >
            {collapsed ? "›" : "‹"}
          </button>

          {!collapsed ? (
            <div className="sidebar-brand">
              <span className="sidebar-brand__label">Serviq</span>
              <strong className="sidebar-brand__title">Agent Shell</strong>
            </div>
          ) : null}
        </header>

        <section className="sidebar-section sidebar-section--top">
          {!collapsed ? <div className="sidebar-section__title">Navigate</div> : null}

          <div className="sidebar-action-list">
            <button
              type="button"
              className={`sidebar-action-button ${activeView === "home" ? "sidebar-action-button--active" : ""}`}
              onClick={() => onViewChange("home")}
            >
              <span className="sidebar-action-button__icon" aria-hidden="true">
                ⌂
              </span>
              {!collapsed ? <span className="sidebar-action-button__label">Home</span> : null}
            </button>

            <button
              type="button"
              className="sidebar-action-button sidebar-action-button--new-chat"
              onClick={onNewChat}
            >
              <span className="sidebar-action-button__icon" aria-hidden="true">
                +
              </span>
              {!collapsed ? <span className="sidebar-action-button__label">New Chat</span> : null}
            </button>

            {TOP_ACTIONS.filter((item) => item.key !== "home").map((item) => {
              const active = activeView === item.key;

              return (
                <button
                  key={item.key}
                  type="button"
                  className={`sidebar-action-button ${active ? "sidebar-action-button--active" : ""}`}
                  onClick={() => onViewChange(item.key)}
                >
                  <span className="sidebar-action-button__icon" aria-hidden="true">
                    {item.icon}
                  </span>
                  {!collapsed ? <span className="sidebar-action-button__label">{item.label}</span> : null}
                </button>
              );
            })}
          </div>
        </section>

        <section className="sidebar-section sidebar-section--middle">
          {!collapsed ? <div className="sidebar-section__title">Chat history</div> : null}

          <div className="sidebar-history-list">
            {chatHistory.map((chat) => {
              const active = selectedChatId === chat.id && activeView === "chat";
              const isDraft = chat.persisted === false;

              return (
                <div
                  key={chat.id}
                  className={`sidebar-history-row ${active ? "sidebar-history-row--active" : ""}`}
                >
                  <button
                    type="button"
                    className={`sidebar-history-item ${active ? "sidebar-history-item--active" : ""}`}
                    onClick={() => onSelectChat(chat.id)}
                  >
                    <span className="sidebar-history-item__icon" aria-hidden="true">
                      {isDraft ? "□" : "◫"}
                    </span>

                    {!collapsed ? (
                      <span className="sidebar-history-item__body">
                        <strong className="sidebar-history-item__title">{chat.title}</strong>
                        <span className="sidebar-history-item__preview">{chat.preview}</span>
                        <span className="sidebar-history-item__time">{chat.time}</span>
                      </span>
                    ) : null}
                  </button>

                  {!collapsed ? (
                    <button
                      type="button"
                      className="sidebar-history-delete"
                      onClick={(event) => {
                        event.stopPropagation();
                        onDeleteChat(chat.id);
                      }}
                      aria-label={`Delete ${chat.title}`}
                      title="Delete chat"
                    >
                      <SidebarDeleteIcon />
                    </button>
                  ) : null}
                </div>
              );
            })}
          </div>
        </section>

        <section className="sidebar-section sidebar-section--bottom">
          <button
            type="button"
            className={`sidebar-action-button sidebar-action-button--bottom ${
              activeView === "settings" ? "sidebar-action-button--active" : ""
            }`}
            onClick={() => onViewChange("settings")}
          >
            <span className="sidebar-action-button__icon" aria-hidden="true">
              ⚙
            </span>
            {!collapsed ? <span className="sidebar-action-button__label">Settings</span> : null}
          </button>
        </section>
      </div>
    </aside>
  );
}
