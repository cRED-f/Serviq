import { useEffect, useMemo, useState } from "react";
import {
  ChatWorkspace,
  type UIChatMessage,
} from "./components/shell/ChatWorkspace";
import { MemoryPanel } from "./components/shell/MemoryPanel";
import { ProductHome } from "./components/shell/ProductHome";
import { SettingsPanel } from "./components/shell/SettingsPanel";
import { ToolsPanel } from "./components/shell/ToolsPanel";
import {
  LeftSidebar,
  type ChatHistoryItem,
  type SidebarView,
} from "./components/shell/LeftSidebar";
import { listChatModels, type ChatModel } from "./lib/chatApi";
import {
  getRuntimeSettings,
  updateRuntimeSettings,
  type AnswerStyle,
} from "./lib/runtimeSettingsApi";
import {
  createConversationSession,
  deleteConversationSession,
  loadConversationMessages,
  loadConversationSessions,
  updateConversationSession,
} from "./lib/conversationApi";
import "./styles/design-shell.css";
import "./styles/design-shell-db-persistence.css";
import "./styles/settings-runtime-extra.css";

const SELECTED_MODEL_STORAGE_KEY = "serviq.selectedModelId";

function createDraftChatId() {
  return `draft-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function createRealChatId() {
  return `serviq-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function createDraftChat(): ChatHistoryItem {
  return {
    id: createDraftChatId(),
    title: "New chat",
    preview: "Draft conversation. It will save only after your first message.",
    time: "Draft",
    persisted: false,
  };
}

function getChatTitleFromMessage(message: string) {
  const clean = message.trim().replace(/\s+/g, " ");

  if (!clean) {
    return "New chat";
  }

  return clean.length > 42 ? `${clean.slice(0, 42)}...` : clean;
}

function getShortPreview(message: string) {
  const clean = message.trim().replace(/\s+/g, " ");

  if (!clean) {
    return "";
  }

  return clean.length > 72 ? `${clean.slice(0, 72)}...` : clean;
}

function readStoredModelId() {
  try {
    return window.localStorage.getItem(SELECTED_MODEL_STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

function writeStoredModelId(modelId: string) {
  try {
    if (modelId) {
      window.localStorage.setItem(SELECTED_MODEL_STORAGE_KEY, modelId);
    } else {
      window.localStorage.removeItem(SELECTED_MODEL_STORAGE_KEY);
    }
  } catch {
    // localStorage can fail in restricted environments. UI state still works for this session.
  }
}

export default function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [activeView, setActiveView] = useState<SidebarView>("home");
  const [chatHistory, setChatHistory] = useState<ChatHistoryItem[]>([]);
  const [draftChat, setDraftChat] = useState<ChatHistoryItem | null>(null);
  const [selectedChatId, setSelectedChatId] = useState<string>("");
  const [messagesByChatId, setMessagesByChatId] = useState<
    Record<string, UIChatMessage[]>
  >({});
  const [chatHistoryError, setChatHistoryError] = useState<string | null>(null);

  const [availableModels, setAvailableModels] = useState<ChatModel[]>([]);
  const [selectedModelId, setSelectedModelId] = useState<string>(() =>
    readStoredModelId(),
  );
  const [selectedEmbeddingModelId, setSelectedEmbeddingModelId] =
    useState<string>("");
  const [answerStyle, setAnswerStyle] = useState<AnswerStyle>("concise");
  const [modelLoadError, setModelLoadError] = useState<string | null>(null);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [runtimeSaving, setRuntimeSaving] = useState(false);

  const visibleChatHistory = useMemo(() => {
    return draftChat ? [draftChat, ...chatHistory] : chatHistory;
  }, [chatHistory, draftChat]);

  const selectedChat =
    visibleChatHistory.find((item) => item.id === selectedChatId) ??
    visibleChatHistory[0];

  const selectedModelName = useMemo(() => {
    if (!selectedModelId) {
      return "No model selected";
    }

    return (
      availableModels.find((model) => model.id === selectedModelId)?.name ??
      selectedModelId
    );
  }, [availableModels, selectedModelId]);

  async function refreshRuntimeSettings() {
    try {
      const settings = await getRuntimeSettings();
      setSelectedEmbeddingModelId(settings.selected_embedding_model);
      setAnswerStyle(settings.answer_style);
      setModelLoadError(null);
    } catch (error) {
      setModelLoadError(
        error instanceof Error
          ? error.message
          : "Unable to load runtime settings.",
      );
    }
  }

  async function refreshModels() {
    setModelsLoading(true);

    try {
      const [models] = await Promise.all([
        listChatModels(),
        refreshRuntimeSettings(),
      ]);

      setAvailableModels(models);
      setModelLoadError(null);

      setSelectedModelId((current) => {
        const stored = readStoredModelId();
        const preferred = current || stored;
        const nextModelId =
          models.find((model) => model.id === preferred)?.id ??
          models[0]?.id ??
          "";

        writeStoredModelId(nextModelId);
        return nextModelId;
      });
    } catch (error) {
      setModelLoadError(
        error instanceof Error
          ? error.message
          : "Unable to load LM Studio models.",
      );
    } finally {
      setModelsLoading(false);
    }
  }

  function handleSelectModel(modelId: string) {
    setSelectedModelId(modelId);
    writeStoredModelId(modelId);
  }

  async function handleSelectEmbeddingModel(modelId: string) {
    setSelectedEmbeddingModelId(modelId);
    setRuntimeSaving(true);

    try {
      const settings = await updateRuntimeSettings({
        selected_embedding_model: modelId,
      });
      setSelectedEmbeddingModelId(settings.selected_embedding_model);
      setAnswerStyle(settings.answer_style);
      setModelLoadError(null);
    } catch (error) {
      setModelLoadError(
        error instanceof Error
          ? error.message
          : "Unable to save embedding model.",
      );
    } finally {
      setRuntimeSaving(false);
    }
  }

  async function handleSelectAnswerStyle(style: AnswerStyle) {
    setAnswerStyle(style);
    setRuntimeSaving(true);

    try {
      const settings = await updateRuntimeSettings({
        answer_style: style,
      });
      setSelectedEmbeddingModelId(settings.selected_embedding_model);
      setAnswerStyle(settings.answer_style);
      setModelLoadError(null);
    } catch (error) {
      setModelLoadError(
        error instanceof Error ? error.message : "Unable to save answer style.",
      );
    } finally {
      setRuntimeSaving(false);
    }
  }

  async function refreshSessions() {
    try {
      const sessions = await loadConversationSessions();
      setChatHistory(sessions);
      setChatHistoryError(null);

      if (!selectedChatId && sessions[0]) {
        setSelectedChatId(sessions[0].id);
      }
    } catch (error) {
      setChatHistoryError(
        error instanceof Error ? error.message : "Unable to load chat history.",
      );
    }
  }

  async function refreshMessages(sessionId: string) {
    if (!sessionId || sessionId.startsWith("draft-")) {
      return;
    }

    try {
      const messages = await loadConversationMessages(sessionId);
      setMessagesByChatId((current) => ({
        ...current,
        [sessionId]: messages,
      }));
    } catch (error) {
      setChatHistoryError(
        error instanceof Error ? error.message : "Unable to load messages.",
      );
    }
  }

  useEffect(() => {
    void refreshSessions();
    void refreshModels();
  }, []);

  function handleNewChat() {
    const existingDraft = draftChat;

    if (existingDraft) {
      setSelectedChatId(existingDraft.id);
      setActiveView("chat");
      return;
    }

    const newDraft = createDraftChat();
    setDraftChat(newDraft);
    setSelectedChatId(newDraft.id);
    setActiveView("chat");
  }

  async function handleFirstUserMessage(
    draftChatId: string,
    firstUserMessage: string,
  ) {
    if (!draftChat || draftChat.id !== draftChatId) {
      return draftChatId;
    }

    const realChatId = createRealChatId();
    const title = getChatTitleFromMessage(firstUserMessage);
    const preview = getShortPreview(firstUserMessage);

    const persistedChat = await createConversationSession({
      id: realChatId,
      title,
      preview,
    });

    setChatHistory((current) => [persistedChat, ...current]);
    setDraftChat(null);
    setSelectedChatId(realChatId);

    return realChatId;
  }

  function handleMessagesChange(
    chatId: string,
    updater: (messages: UIChatMessage[]) => UIChatMessage[],
  ) {
    setMessagesByChatId((current) => ({
      ...current,
      [chatId]: updater(current[chatId] ?? []),
    }));
  }

  async function handleChatPreviewChange(chatId: string, preview: string) {
    const shortPreview = getShortPreview(preview);

    setChatHistory((current) =>
      current.map((chat) =>
        chat.id === chatId
          ? {
              ...chat,
              preview: shortPreview || chat.preview,
              time: "Now",
            }
          : chat,
      ),
    );

    if (!chatId.startsWith("draft-")) {
      try {
        await updateConversationSession({
          sessionId: chatId,
          preview: shortPreview,
        });
      } catch {}
    }
  }

  async function handleDeleteChat(chatId: string) {
    const isDraft = draftChat?.id === chatId;
    const currentVisibleHistory = visibleChatHistory;
    const deletedIndex = currentVisibleHistory.findIndex(
      (chat) => chat.id === chatId,
    );

    if (isDraft) {
      setDraftChat(null);
    } else {
      setChatHistory((current) => current.filter((chat) => chat.id !== chatId));

      try {
        await deleteConversationSession(chatId);
      } catch (error) {
        setChatHistoryError(
          error instanceof Error ? error.message : "Unable to delete chat.",
        );
      }
    }

    setMessagesByChatId((current) => {
      const next = { ...current };
      delete next[chatId];
      return next;
    });

    if (selectedChatId !== chatId) {
      return;
    }

    const nextChat =
      currentVisibleHistory[deletedIndex + 1] ??
      currentVisibleHistory[deletedIndex - 1] ??
      null;

    if (nextChat && nextChat.id !== chatId) {
      setSelectedChatId(nextChat.id);
      setActiveView("chat");
      await refreshMessages(nextChat.id);
      return;
    }

    setSelectedChatId("");
    setActiveView("home");
  }

  async function handleSelectChat(chatId: string) {
    setSelectedChatId(chatId);
    setActiveView("chat");
    await refreshMessages(chatId);
  }

  const content = useMemo(() => {
    if (activeView === "home") {
      return <ProductHome />;
    }

    if (activeView === "chat") {
      return (
        <ChatWorkspace
          chatId={selectedChat?.id ?? ""}
          title={selectedChat?.title ?? "New chat"}
          isDraft={selectedChat?.persisted === false}
          messages={messagesByChatId[selectedChat?.id ?? ""] ?? []}
          selectedModelId={selectedModelId}
          selectedModelName={selectedModelName}
          onMessagesChange={handleMessagesChange}
          onFirstUserMessage={handleFirstUserMessage}
          onChatPreviewChange={handleChatPreviewChange}
          onRefreshChatMessages={refreshMessages}
        />
      );
    }

    if (activeView === "tools") {
      return <ToolsPanel />;
    }

    if (activeView === "memory") {
      return <MemoryPanel />;
    }

    return (
      <SettingsPanel
        models={availableModels}
        selectedModelId={selectedModelId}
        selectedEmbeddingModelId={selectedEmbeddingModelId}
        answerStyle={answerStyle}
        loading={modelsLoading}
        saving={runtimeSaving}
        error={modelLoadError}
        onSelectModel={handleSelectModel}
        onSelectEmbeddingModel={(modelId) =>
          void handleSelectEmbeddingModel(modelId)
        }
        onSelectAnswerStyle={(style) => void handleSelectAnswerStyle(style)}
        onRefreshModels={() => void refreshModels()}
      />
    );
  }, [
    activeView,
    answerStyle,
    availableModels,
    messagesByChatId,
    modelLoadError,
    modelsLoading,
    runtimeSaving,
    selectedChat,
    selectedEmbeddingModelId,
    selectedModelId,
    selectedModelName,
  ]);

  return (
    <main className="design-shell">
      <div className="design-shell__background" />
      <div className="design-shell__noise" />

      <div
        className={`workspace-shell ${sidebarCollapsed ? "workspace-shell--collapsed" : ""}`}
      >
        <LeftSidebar
          collapsed={sidebarCollapsed}
          activeView={activeView}
          chatHistory={visibleChatHistory}
          selectedChatId={selectedChatId}
          onToggleCollapse={() => setSidebarCollapsed((value) => !value)}
          onViewChange={(view) => setActiveView(view)}
          onNewChat={handleNewChat}
          onDeleteChat={(chatId) => void handleDeleteChat(chatId)}
          onSelectChat={(chatId) => void handleSelectChat(chatId)}
        />

        <section className="workspace-main">
          {chatHistoryError ? (
            <div className="screen-error-banner">{chatHistoryError}</div>
          ) : null}
          {content}
        </section>
      </div>
    </main>
  );
}
