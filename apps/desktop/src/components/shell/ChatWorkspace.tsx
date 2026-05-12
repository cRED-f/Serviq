import { FormEvent, KeyboardEvent, ReactNode, useEffect, useRef, useState } from "react";
import {
  decideApproval,
  runAgentChat,
  type AgentHistoryMessage,
  type AgentRunResponse,
  type ApprovalDecision,
  type ApprovalDecisionResponse,
} from "../../lib/chatApi";
import {
  type AgentTaskTrace,
} from "../../lib/agentApi";
import {
  deleteAssistantMessagePair,
  deleteConversationMessage,
  saveConversationMessage,
} from "../../lib/conversationApi";
import "../../styles/chat-workspace.css";
import "../../styles/chat-approval-polish.css";
import "../../styles/chat-markdown-content.css";

export type UIChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
  status?: "sending" | "done" | "error";
  steps?: string[];
  task_trace?: AgentTaskTrace[];
  metadata?: Record<string, unknown>;
};

type PendingApproval = {
  id: string;
  chatId: string;
  title: string;
  reason: string;
  risk: string;
  toolName: string;
  userMessage: string;
  userMessageId: string | null;
};

type MarkdownBlock =
  | { type: "heading"; level: number; content: string }
  | { type: "paragraph"; content: string }
  | { type: "ul"; items: string[] }
  | { type: "ol"; items: string[] }
  | { type: "code"; language: string; content: string }
  | { type: "table"; headers: string[]; rows: string[][] };

const LOADING_TEXTS = [
  "Serviq is reading your message",
  "Understanding what you need",
  "Checking whether memory is useful",
  "Looking at the conversation context",
  "Planning the safest next step",
  "Choosing whether tools are needed",
  "Preparing the local model request",
  "Asking the local model",
  "Reviewing the model response",
  "Polishing the answer",
  "Checking the final wording",
  "Making the answer easier to read",
  "Preparing the final message",
  "Almost ready",
];

const PROCESS_COMPLETE_TEXT = "Process complete";

function delay(ms: number) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function formatTime(date = new Date()) {
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function toAgentHistory(messages: UIChatMessage[]): AgentHistoryMessage[] {
  return messages
    .filter((message) => message.status !== "error")
    .map((message) => ({
      role: message.role,
      content: message.content,
    }));
}

function getAbortErrorName(error: unknown) {
  if (error instanceof DOMException) {
    return error.name;
  }

  if (error && typeof error === "object" && "name" in error) {
    return String((error as { name?: unknown }).name ?? "");
  }

  return "";
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }

  return value as Record<string, unknown>;
}

function getNestedRecord(source: Record<string, unknown>, path: string[]) {
  let current: unknown = source;

  for (const key of path) {
    const record = asRecord(current);

    if (!record) {
      return null;
    }

    current = record[key];
  }

  return asRecord(current);
}

function extractApprovalFromResponse(response: AgentRunResponse): Omit<PendingApproval, "chatId" | "userMessage" | "userMessageId"> | null {
  const metadata = asRecord(response.metadata) ?? {};
  const candidates = [
    asRecord(metadata.approval),
    asRecord(metadata.approval_request),
    asRecord(metadata.pending_approval),
    getNestedRecord(metadata, ["tool_result", "approval"]),
    getNestedRecord(metadata, ["tool_result", "metadata", "approval"]),
    getNestedRecord(metadata, ["tool_result", "output", "approval"]),
  ].filter((item): item is Record<string, unknown> => Boolean(item));

  const awaitingApproval =
    metadata.awaiting_approval === true ||
    metadata.approval_required === true ||
    Boolean(candidates.length) ||
    /approval/i.test(response.response ?? "");

  let approval = candidates[0] ?? null;

  if (!approval && awaitingApproval) {
    const match = String(response.response ?? "").match(
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i,
    );

    if (match) {
      approval = {
        id: match[0],
      };
    }
  }

  if (!approval) {
    return null;
  }

  const id = String(approval.id ?? approval.approval_id ?? approval.request_id ?? "").trim();

  if (!id) {
    return null;
  }

  const toolName = String(approval.tool_name ?? approval.tool ?? metadata.tool_name ?? "tool");
  const risk = String(approval.risk ?? metadata.risk ?? "approval");
  const reason = String(
    approval.reason ??
      metadata.approval_reason ??
      "Serviq needs your approval before continuing.",
  );

  return {
    id,
    title: "Approval needed",
    reason,
    risk,
    toolName,
  };
}

function friendlyStepLabel(step: string) {
  const normalized = step.trim().toLowerCase();

  const labels: Record<string, string> = {
    prepare_context: "Understood your request",
    classify_request: "Decided what kind of help is needed",
    retrieve_memory: "Checked saved memory",
    skip_retrieve_memory_tool_controlled: "Kept memory ready only if needed",
    recall_conversation: "Checked recent chat context",
    skip_recall_conversation_fast_path: "Skipped old chat lookup because it was not needed",
    run_task_loop: "Planned the next action",
    plan_next_action_1: "Chose the first action",
    plan_next_action_2: "Chose the next action",
    plan_next_action_3: "Checked if another action was needed",
    plan_next_action_4: "Finished action planning",
    maybe_use_tool: "Checked whether a local tool was needed",
    execute_tool_1: "Used a local tool safely",
    execute_tool_2: "Used another local tool safely",
    execute_tool_3: "Used another local tool safely",
    execute_tool_4: "Used another local tool safely",
    call_local_model: "Asked the local model",
    skip_model_call_pending_approval: "Paused because approval is needed",
    save_conversation: "Saved the conversation",
    finalize_response: "Prepared the final answer",
    skip_task_loop_fast_path: "Answered directly without tools",
  };

  if (labels[normalized]) {
    return labels[normalized];
  }

  if (normalized.startsWith("plan_next_action")) {
    return "Planned what to do next";
  }

  if (normalized.startsWith("execute_tool")) {
    return "Used a local tool safely";
  }

  return normalized
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function copyMarkdownContent(message: UIChatMessage) {
  const title = message.role === "user" ? "## User message" : "## Serviq answer";
  const parts = [title, "", message.content.trim()];

  if (message.role === "assistant" && message.steps?.length) {
    parts.push("", "### How Serviq handled it", "");
    message.steps.forEach((step, index) => {
      parts.push(`- ${index + 1}. ${friendlyStepLabel(step)}`);
    });
  }

  return parts.join("\n");
}

function parseMarkdownBlocks(markdown: string): MarkdownBlock[] {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const blocks: MarkdownBlock[] = [];
  let paragraph: string[] = [];
  let listType: "ul" | "ol" | null = null;
  let listItems: string[] = [];
  let inCode = false;
  let codeLanguage = "";
  let codeLines: string[] = [];
  // Table state
  let inTable = false;
  let tableHeaders: string[] = [];
  let tableRows: string[][] = [];

  function flushParagraph() {
    if (paragraph.length > 0) {
      blocks.push({
        type: "paragraph",
        content: paragraph.join(" ").trim(),
      });
      paragraph = [];
    }
  }

  function flushList() {
    if (listType && listItems.length > 0) {
      blocks.push({
        type: listType,
        items: listItems,
      });
      listType = null;
      listItems = [];
    }
  }

  function flushTable() {
    if (inTable && tableHeaders.length > 0) {
      blocks.push({
        type: "table",
        headers: tableHeaders,
        rows: tableRows,
      });
    }
    inTable = false;
    tableHeaders = [];
    tableRows = [];
  }

  function parseTableCell(cell: string): string {
    return cell.trim().replace(/^\||\|$/g, "").trim();
  }

  for (const line of lines) {
    const trimmed = line.trim();

    if (trimmed.startsWith("```")) {
      if (inCode) {
        blocks.push({
          type: "code",
          language: codeLanguage,
          content: codeLines.join("\n"),
        });
        inCode = false;
        codeLanguage = "";
        codeLines = [];
      } else {
        flushParagraph();
        flushList();
        inCode = true;
        codeLanguage = trimmed.slice(3).trim();
      }
      continue;
    }

    if (inCode) {
      codeLines.push(line);
      continue;
    }

    if (!trimmed) {
      flushParagraph();
      flushList();
      continue;
    }

    const heading = /^(#{1,6})\s+(.+)$/.exec(trimmed);
    if (heading) {
      flushParagraph();
      flushList();
      blocks.push({
        type: "heading",
        level: heading[1].length,
        content: heading[2].trim(),
      });
      continue;
    }

    const unordered = /^[-*]\s+(.+)$/.exec(trimmed);
    if (unordered) {
      flushParagraph();
      if (listType && listType !== "ul") {
        flushList();
      }
      listType = "ul";
      listItems.push(unordered[1].trim());
      continue;
    }

    const ordered = /^\d+\.\s+(.+)$/.exec(trimmed);
    if (ordered) {
      flushParagraph();
      flushTable();
      if (listType && listType !== "ol") {
        flushList();
      }
      listType = "ol";
      listItems.push(ordered[1].trim());
      continue;
    }

    // Table detection: line starts with | or ends with |
    if (trimmed.startsWith("|") || trimmed.endsWith("|")) {
      // Check if it's a table separator row (contains only |, -, :, and spaces)
      if (/^[\|\-:\s]+$/.test(trimmed.replace(/\|/g, "-"))) {
        // This is the separator row, skip it
        continue;
      }

      // Parse table row
      const cells = trimmed.split("|").filter((c) => c.trim() !== "");

      if (!inTable) {
        // First row could be header
        flushParagraph();
        flushList();
        tableHeaders = cells.map(parseTableCell);
        inTable = true;
      } else {
        // Data row
        tableRows.push(cells.map(parseTableCell));
      }
      continue;
    }

    // End table when we hit a non-table line
    if (inTable && !trimmed.startsWith("|")) {
      flushTable();
    }

    flushList();
    paragraph.push(trimmed);
  }

  if (inCode) {
    blocks.push({
      type: "code",
      language: codeLanguage,
      content: codeLines.join("\n"),
    });
  }

  flushParagraph();
  flushList();
  flushTable();

  return blocks;
}

function renderInlineMarkdown(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  // Pattern matches: `code`, **bold**, [text](url) links, and raw URLs
  // Raw URL pattern: matches http:// or https:// URLs
  const pattern = /(`[^`]+`|\*\*[^*]+\*\*|\[([^\]]+)\]\(([^)]+)\)|(https?:\/\/[^\s<>\)\]]+))/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null = pattern.exec(text);
  let index = 0;

  while (match) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }

    const token = match[0];

    if (token.startsWith("`")) {
      nodes.push(<code key={`inline-${index}`}>{token.slice(1, -1)}</code>);
    } else if (token.startsWith("**")) {
      nodes.push(<strong key={`bold-${index}`}>{token.slice(2, -2)}</strong>);
    } else if (token.startsWith("[")) {
      // Handle markdown links: [text](url)
      const linkText = match[2];
      const linkUrl = match[3];
      const isExternal = linkUrl.startsWith("http://") || linkUrl.startsWith("https://");
      nodes.push(
        <a
          key={`link-${index}`}
          href={linkUrl}
          target={isExternal ? "_blank" : undefined}
          rel={isExternal ? "noopener noreferrer" : undefined}
          className="markdown-link"
        >
          {linkText}
        </a>
      );
    } else if (token.startsWith("http://") || token.startsWith("https://")) {
      // Handle raw URLs - make them clickable
      const url = token;
      nodes.push(
        <a
          key={`url-${index}`}
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="markdown-link"
        >
          {url}
        </a>
      );
    }

    lastIndex = match.index + token.length;
    index += 1;
    match = pattern.exec(text);
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes;
}

function MarkdownContent({ content }: { content: string }) {
  const blocks = parseMarkdownBlocks(content);

  return (
    <div className="markdown-content">
      {blocks.map((block, index) => {
        if (block.type === "heading") {
          const level = Math.min(block.level, 4);

          if (level === 1) {
            return <h1 key={index}>{renderInlineMarkdown(block.content)}</h1>;
          }

          if (level === 2) {
            return <h2 key={index}>{renderInlineMarkdown(block.content)}</h2>;
          }

          if (level === 3) {
            return <h3 key={index}>{renderInlineMarkdown(block.content)}</h3>;
          }

          return <h4 key={index}>{renderInlineMarkdown(block.content)}</h4>;
        }

        if (block.type === "paragraph") {
          return <p key={index}>{renderInlineMarkdown(block.content)}</p>;
        }

        if (block.type === "ul") {
          return (
            <ul key={index}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>{renderInlineMarkdown(item)}</li>
              ))}
            </ul>
          );
        }

        if (block.type === "ol") {
          return (
            <ol key={index}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>{renderInlineMarkdown(item)}</li>
              ))}
            </ol>
          );
        }

        if (block.type === "code") {
          return (
            <pre key={index}>
              {block.language ? <span className="markdown-content__language">{block.language}</span> : null}
              <code>{block.content}</code>
            </pre>
          );
        }

        if (block.type === "table") {
          return (
            <table key={index} className="markdown-table">
              <thead>
                <tr>
                  {block.headers.map((header, hi) => (
                    <th key={hi}>{renderInlineMarkdown(header)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {block.rows.map((row, ri) => (
                  <tr key={ri}>
                    {row.map((cell, ci) => (
                      <td key={ci}>{renderInlineMarkdown(cell)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          );
        }

        return null;
      })}
    </div>
  );
}

function SendIcon() {
  return (
    <svg aria-hidden="true" className="chat-button-icon" viewBox="0 0 24 24">
      <path d="M4.2 19.4 20.8 12 4.2 4.6l1.5 6.1 8.2 1.3-8.2 1.3-1.5 6.1Z" />
    </svg>
  );
}

function StopIcon() {
  return (
    <svg aria-hidden="true" className="chat-button-icon" viewBox="0 0 24 24">
      <rect x="7" y="7" width="10" height="10" rx="2" />
    </svg>
  );
}

function CopyIcon() {
  return (
    <svg aria-hidden="true" className="chat-action-icon" viewBox="0 0 24 24">
      <path d="M8 8.5A2.5 2.5 0 0 1 10.5 6H17a2.5 2.5 0 0 1 2.5 2.5V17a2.5 2.5 0 0 1-2.5 2.5h-6.5A2.5 2.5 0 0 1 8 17V8.5Z" />
      <path d="M5 14.5V6.75A1.75 1.75 0 0 1 6.75 5H14.5" />
    </svg>
  );
}

function TryAgainIcon() {
  return (
    <svg aria-hidden="true" className="chat-action-icon" viewBox="0 0 24 24">
      <path d="M19 12a7 7 0 0 1-11.9 5H5v-5h5l-2.2 2.2A4.5 4.5 0 1 0 7.9 9" />
      <path d="M5 12A7 7 0 0 1 16.9 7H19v5h-5l2.2-2.2A4.5 4.5 0 1 0 16.1 15" />
    </svg>
  );
}

function DeleteIcon() {
  return (
    <svg aria-hidden="true" className="chat-action-icon" viewBox="0 0 24 24">
      <path d="M5 7h14" />
      <path d="M10 11v6" />
      <path d="M14 11v6" />
      <path d="M8 7l.7 12A2 2 0 0 0 10.7 21h2.6a2 2 0 0 0 2-1.9L16 7" />
      <path d="M9 7V5.5A1.5 1.5 0 0 1 10.5 4h3A1.5 1.5 0 0 1 15 5.5V7" />
    </svg>
  );
}

function StepsPreview({ steps, task_trace }: { steps?: string[]; task_trace?: AgentTaskTrace[] }) {
  if (!steps?.length && !task_trace?.length) {
    return null;
  }

  // If we have detailed task_trace, use it for richer display
  const hasDetailedTrace = task_trace && task_trace.length > 0;

  return (
    <details className="chat-message-steps">
      <summary>
        <span className="chat-message-steps__summary-icon" aria-hidden="true">↳</span>
        <span>How Serviq handled it</span>
      </summary>

      <ol className="agent-step-tree">
        {hasDetailedTrace
          ? task_trace.map((trace, index) => {
              const stepLabel = trace.type === "plan"
                ? `Step ${trace.step}: Planning (${trace.plan?.action || "unknown"})`
                : trace.type === "tool_call"
                  ? `Step ${trace.step}: Executing ${trace.plan?.tool_name || "tool"}`
                  : trace.type === "tool_result"
                    ? `Step ${trace.step}: ${trace.tool_result?.ok ? "Success" : "Failed"}`
                    : `Step ${trace.step}: ${trace.type}`;

              return (
                <li key={`trace-${index}`} className="agent-step-tree__item">
                  <span className="agent-step-tree__line" aria-hidden="true" />
                  <span className="agent-step-tree__node" aria-hidden="true" />
                  <span className="agent-step-tree__text">{stepLabel}</span>
                  {trace.plan?.reason && (
                    <div className="agent-step-tree__detail">
                      Reason: {trace.plan.reason}
                    </div>
                  )}
                  {trace.tool_result?.output && (
                    <div className="agent-step-tree__detail">
                      Output: {typeof trace.tool_result.output === "string"
                        ? trace.tool_result.output.slice(0, 100)
                        : JSON.stringify(trace.tool_result.output).slice(0, 100)}
                    </div>
                  )}
                </li>
              );
            })
          : steps.map((step, index) => (
              <li key={`${step}-${index}`} className="agent-step-tree__item">
                <span className="agent-step-tree__line" aria-hidden="true" />
                <span className="agent-step-tree__node" aria-hidden="true" />
                <span className="agent-step-tree__text">{friendlyStepLabel(step)}</span>
              </li>
            ))}
      </ol>
    </details>
  );
}

function EmptyChatState({ isDraft }: { isDraft: boolean }) {
  return (
    <div className="empty-chat-state">
      <div className="empty-chat-state__orb" aria-hidden="true" />
      <span className="empty-chat-state__eyebrow">{isDraft ? "Draft chat" : "Serviq chat"}</span>
      <h2>{isDraft ? "Start when you are ready." : "Ask Serviq anything."}</h2>
      <p>
        {isDraft
          ? "This draft is not saved anywhere. It becomes a real session only after your first message."
          : "Serviq can chat normally, recall memory when needed, and use tools through approval-safe agent flow."}
      </p>
    </div>
  );
}

function AgentLoadingState({ text, complete }: { text: string; complete: boolean }) {
  return (
    <div
      className={`agent-loading-state ${complete ? "agent-loading-state--complete" : ""}`}
      role="status"
      aria-live="polite"
    >
      <span className="agent-loading-state__spinner" aria-hidden="true" />
      <span className="agent-loading-state__text">{text}</span>
    </div>
  );
}

function ApprovalCard({
  approval,
  busy,
  error,
  onDecide,
}: {
  approval: PendingApproval;
  busy: boolean;
  error: string | null;
  onDecide: (decision: ApprovalDecision) => void;
}) {
  return (
    <section className="approval-card">
      <div className="approval-card__body">
        <span className="approval-card__label">{approval.title}</span>
        <strong>{approval.toolName}</strong>
        <p>{approval.reason}</p>
        {error ? <span className="approval-card__error">{error}</span> : null}
      </div>

      <div className="approval-card__actions">
        <button type="button" onClick={() => onDecide("approve")} disabled={busy}>
          Approve
        </button>
        <button type="button" className="approval-card__reject" onClick={() => onDecide("reject")} disabled={busy}>
          Reject
        </button>
      </div>
    </section>
  );
}

function extractAssistantResponseFromApproval(result: ApprovalDecisionResponse) {
  return (
    result.assistant_response?.trim() ||
    result.response?.trim() ||
    String(asRecord(result.metadata)?.assistant_response ?? "").trim()
  );
}

export function ChatWorkspace({
  chatId,
  title,
  isDraft,
  messages,
  selectedModelId,
  selectedModelName,
  onMessagesChange,
  onFirstUserMessage,
  onChatPreviewChange,
  onRefreshChatMessages,
}: {
  chatId: string;
  title: string;
  isDraft: boolean;
  messages: UIChatMessage[];
  selectedModelId: string;
  selectedModelName: string;
  onMessagesChange: (chatId: string, updater: (messages: UIChatMessage[]) => UIChatMessage[]) => void;
  onFirstUserMessage: (draftChatId: string, firstUserMessage: string) => Promise<string>;
  onChatPreviewChange: (chatId: string, preview: string) => Promise<void> | void;
  onRefreshChatMessages: (chatId: string) => Promise<void>;
}) {
  const [input, setInput] = useState("");
  const [modelError, setModelError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [approvalBusy, setApprovalBusy] = useState(false);
  const [approvalError, setApprovalError] = useState<string | null>(null);
  const [approvalLoadingText, setApprovalLoadingText] = useState<string | null>(null);
  const [pendingApproval, setPendingApproval] = useState<PendingApproval | null>(null);
  const [processComplete, setProcessComplete] = useState(false);
  const [loadingTextIndex, setLoadingTextIndex] = useState(0);
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const stoppedByUserRef = useRef(false);

  useEffect(() => {
    if (!busy || processComplete) {
      setLoadingTextIndex(0);
      return;
    }

    const timer = window.setInterval(() => {
      setLoadingTextIndex((current) => Math.min(current + 1, LOADING_TEXTS.length - 1));
    }, 5200);

    return () => {
      window.clearInterval(timer);
    };
  }, [busy, processComplete]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "auto",
    });
  }, [messages.length, busy, loadingTextIndex, processComplete, pendingApproval, approvalLoadingText]);

  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  async function submitMessage(
    rawMessage: string,
    options?: {
      tryAgainAssistantId?: string;
    },
  ) {
    const trimmedInput = rawMessage.trim();

    if (!trimmedInput || busy || approvalBusy) {
      return;
    }

    if (!selectedModelId) {
      setModelError("Choose a model in Settings first.");
      return;
    }

    setPendingApproval(null);
    setApprovalError(null);
    setApprovalLoadingText(null);
    setBusy(true);
    setProcessComplete(false);
    setLoadingTextIndex(0);
    setModelError(null);
    stoppedByUserRef.current = false;

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    let realChatId = chatId;
    let historyBeforeRequest: UIChatMessage[] = [];
    let triggeringUserMessageId: string | null = null;

    if (options?.tryAgainAssistantId) {
      const assistantIndex = messages.findIndex((message) => message.id === options.tryAgainAssistantId);
      let userIndex = -1;

      for (let index = assistantIndex - 1; index >= 0; index -= 1) {
        if (messages[index]?.role === "user") {
          userIndex = index;
          break;
        }
      }

      if (assistantIndex === -1 || userIndex === -1) {
        setBusy(false);
        abortControllerRef.current = null;
        return;
      }

      triggeringUserMessageId = messages[userIndex]?.id ?? null;
      await deleteConversationMessage(options.tryAgainAssistantId);
      historyBeforeRequest = messages.slice(0, userIndex);

      onMessagesChange(realChatId, () => messages.slice(0, userIndex + 1));
    } else {
      realChatId = isDraft ? await onFirstUserMessage(chatId, trimmedInput) : chatId;
      historyBeforeRequest = isDraft ? [] : messages;

      const savedUserMessage = await saveConversationMessage({
        sessionId: realChatId,
        role: "user",
        content: trimmedInput,
      });

      triggeringUserMessageId = savedUserMessage.id;
      onMessagesChange(realChatId, (currentMessages) => [...currentMessages, savedUserMessage]);
      await onChatPreviewChange(realChatId, trimmedInput);
    }

    try {
      const response = await runAgentChat(
        {
          session_id: realChatId,
          model: selectedModelId,
          message: trimmedInput,
          history: toAgentHistory(historyBeforeRequest),
        },
        {
          signal: abortController.signal,
        },
      );

      const approval = extractApprovalFromResponse(response);

      if (approval) {
        setPendingApproval({
          ...approval,
          chatId: realChatId,
          userMessage: trimmedInput,
          userMessageId: triggeringUserMessageId,
        });
        return;
      }

      setProcessComplete(true);
      await delay(1650);

      const assistantResponse = response.response?.trim() || "Serviq returned an empty response.";
      const savedAssistantMessage = await saveConversationMessage({
        sessionId: realChatId,
        role: "assistant",
        content: assistantResponse,
        steps: response.steps ?? [],
        metadata: response.metadata ?? {},
        task_trace: response.task_trace ?? [],
      });

      onMessagesChange(realChatId, (currentMessages) => [...currentMessages, savedAssistantMessage]);
      await onChatPreviewChange(realChatId, assistantResponse);
    } catch (error) {
      const wasAborted = getAbortErrorName(error) === "AbortError";
      const errorMessage = wasAborted && stoppedByUserRef.current
        ? "Response stopped."
        : error instanceof Error
          ? error.message
          : "Unknown chat error.";

      const assistantMessage: UIChatMessage = {
        id: `error-${Date.now()}`,
        role: "assistant",
        content: errorMessage,
        createdAt: formatTime(),
        status: wasAborted ? "done" : "error",
      };

      onMessagesChange(realChatId, (currentMessages) => [...currentMessages, assistantMessage]);
    } finally {
      setBusy(false);
      setProcessComplete(false);
      abortControllerRef.current = null;
      stoppedByUserRef.current = false;
    }
  }

  async function handleSubmit(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();

    const trimmedInput = input.trim();

    if (!trimmedInput) {
      return;
    }

    setInput("");
    await submitMessage(trimmedInput);
  }

  async function deleteRejectedApprovalUserMessage(approval: PendingApproval) {
    const userMessageId =
      approval.userMessageId ??
      [...messages].reverse().find(
        (message) => message.role === "user" && message.content.trim() === approval.userMessage.trim(),
      )?.id ??
      null;

    if (!userMessageId) {
      return;
    }

    try {
      await deleteConversationMessage(userMessageId);
    } finally {
      onMessagesChange(approval.chatId, (currentMessages) =>
        currentMessages.filter((message) => message.id !== userMessageId),
      );
      await onRefreshChatMessages(approval.chatId);
    }
  }

  async function handleApprovalDecision(decision: ApprovalDecision) {
    if (!pendingApproval || approvalBusy) {
      return;
    }

    const approvalSnapshot = pendingApproval;

    setApprovalBusy(true);
    setApprovalError(null);
    setApprovalLoadingText(decision === "approve" ? "Running approved action" : "Rejecting request");

    try {
      const result = await decideApproval(approvalSnapshot.id, decision);

      if (decision === "reject") {
        await deleteRejectedApprovalUserMessage(approvalSnapshot);
        setApprovalLoadingText(PROCESS_COMPLETE_TEXT);
        await delay(700);
        setPendingApproval(null);
        setApprovalLoadingText(null);
        return;
      }

      const assistantResponse = extractAssistantResponseFromApproval(result);

      if (assistantResponse) {
        setApprovalLoadingText(PROCESS_COMPLETE_TEXT);
        await delay(1200);

        // Extract actual steps from approval result
        const resultMetadata = result.metadata ?? {};
        const approvalData = result.approval ?? {};
        const toolName = approvalData.tool_name ?? "tool";
        const steps = [
          `execute_${toolName}`,
          "finalize_response"
        ];

        const savedAssistantMessage = await saveConversationMessage({
          sessionId: approvalSnapshot.chatId,
          role: "assistant",
          content: assistantResponse,
          steps: steps,
          task_trace: resultMetadata.task_trace ?? [],
          metadata: resultMetadata,
        });

        onMessagesChange(approvalSnapshot.chatId, (currentMessages) => [...currentMessages, savedAssistantMessage]);
        await onChatPreviewChange(approvalSnapshot.chatId, assistantResponse);
      }

      setPendingApproval(null);
      setApprovalLoadingText(null);
      await onRefreshChatMessages(approvalSnapshot.chatId);
    } catch (error) {
      setApprovalError(error instanceof Error ? error.message : "Approval decision failed.");
      setApprovalLoadingText(null);
    } finally {
      setApprovalBusy(false);
    }
  }

  function handleStop() {
    stoppedByUserRef.current = true;
    abortControllerRef.current?.abort();
  }

  function handleInputKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSubmit();
    }
  }

  async function handleCopy(message: UIChatMessage) {
    try {
      await navigator.clipboard.writeText(copyMarkdownContent(message));
      setCopiedMessageId(message.id);
      window.setTimeout(() => {
        setCopiedMessageId((current) => (current === message.id ? null : current));
      }, 1400);
    } catch {
      setCopiedMessageId(null);
    }
  }

  function handleTryAgain(message: UIChatMessage) {
    const assistantIndex = messages.findIndex((item) => item.id === message.id);
    let previousUserMessage: UIChatMessage | null = null;

    for (let index = assistantIndex - 1; index >= 0; index -= 1) {
      if (messages[index]?.role === "user") {
        previousUserMessage = messages[index];
        break;
      }
    }

    if (!previousUserMessage) {
      return;
    }

    void submitMessage(previousUserMessage.content, {
      tryAgainAssistantId: message.id,
    });
  }

  async function handleDeleteAssistantPair(message: UIChatMessage) {
    const deletedIds = await deleteAssistantMessagePair(message.id);
    const deleted = new Set(deletedIds);

    onMessagesChange(chatId, (currentMessages) =>
      currentMessages.filter((item) => !deleted.has(item.id)),
    );

    await onRefreshChatMessages(chatId);
  }

  const loadingText = processComplete ? PROCESS_COMPLETE_TEXT : LOADING_TEXTS[loadingTextIndex];
  const showStopButton = busy && !processComplete;

  return (
    <section className="chat-workspace">
      <header className="chat-workspace__header">
        <div>
          <span className="chat-workspace__eyebrow">{isDraft ? "Unsaved draft" : "Active chat"}</span>
          <h2>{title}</h2>
        </div>
      </header>

      <div className="chat-workspace__model-strip">
        <span>{selectedModelName}</span>
        <strong>{isDraft ? "Not saved until first message" : "Saved chat"}</strong>
      </div>

      {modelError ? <p className="chat-workspace__error">{modelError}</p> : null}

      <div className="chat-message-list" ref={scrollRef}>
        {messages.length === 0 && !busy && !pendingApproval ? (
          <EmptyChatState isDraft={isDraft} />
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              className={`chat-message-row chat-message-row--${message.role}`}
            >
              <article
                className={`chat-message chat-message--${message.role} ${
                  message.status === "error" ? "chat-message--error" : ""
                }`}
              >
                <div className="chat-message__meta">
                  <span>{message.role === "user" ? "You" : "Serviq"}</span>
                  <time>{message.createdAt}</time>
                </div>

                <div className="chat-message__content">
                  <MarkdownContent content={message.content} />
                </div>

                <StepsPreview steps={message.steps} task_trace={message.task_trace} />

                {message.role === "user" ? (
                  <div className="chat-message-actions chat-message-actions--user">
                    <button type="button" onClick={() => void handleCopy(message)}>
                      <CopyIcon />
                      <span>{copiedMessageId === message.id ? "Copied" : "Copy"}</span>
                    </button>
                  </div>
                ) : null}

                {message.role === "assistant" && message.status !== "error" ? (
                  <div className="chat-message-actions">
                    <button type="button" onClick={() => void handleCopy(message)}>
                      <CopyIcon />
                      <span>{copiedMessageId === message.id ? "Copied" : "Copy"}</span>
                    </button>
                    <button type="button" onClick={() => handleTryAgain(message)} disabled={busy || approvalBusy}>
                      <TryAgainIcon />
                      <span>Try again</span>
                    </button>
                    <button
                      type="button"
                      className="chat-message-action--danger"
                      onClick={() => void handleDeleteAssistantPair(message)}
                      disabled={busy || approvalBusy}
                    >
                      <DeleteIcon />
                      <span>Delete</span>
                    </button>
                  </div>
                ) : null}
              </article>
            </div>
          ))
        )}

        {busy ? <AgentLoadingState text={loadingText} complete={processComplete} /> : null}

        {pendingApproval ? (
          <ApprovalCard
            approval={pendingApproval}
            busy={approvalBusy}
            error={approvalError}
            onDecide={(decision) => void handleApprovalDecision(decision)}
          />
        ) : null}

        {approvalLoadingText ? (
          <AgentLoadingState
            text={approvalLoadingText}
            complete={approvalLoadingText === PROCESS_COMPLETE_TEXT}
          />
        ) : null}
      </div>

      <form className="chat-input-form" onSubmit={handleSubmit}>
        <textarea
          value={input}
          rows={1}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={handleInputKeyDown}
          placeholder="Message Serviq..."
          disabled={busy || approvalBusy}
        />

        <button
          className={`chat-submit-button ${showStopButton ? "chat-submit-button--stop" : ""}`}
          type={showStopButton ? "button" : "submit"}
          disabled={!showStopButton && (busy || approvalBusy || !input.trim())}
          onClick={showStopButton ? handleStop : undefined}
          aria-label={showStopButton ? "Stop response" : "Send message"}
          title={showStopButton ? "Stop" : "Send"}
        >
          {showStopButton ? <StopIcon /> : <SendIcon />}
        </button>
      </form>
    </section>
  );
}
