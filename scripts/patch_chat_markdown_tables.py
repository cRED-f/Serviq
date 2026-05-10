from __future__ import annotations

import re
from pathlib import Path


NEW_PARSE_MARKDOWN_BLOCKS = """function looksLikeTableRow(line: string) {
  const trimmed = line.trim();
  return trimmed.includes("|") && /^\\|?.+\\|.+\\|?$/.test(trimmed);
}

function splitTableRow(line: string) {
  let trimmed = line.trim();

  if (trimmed.startsWith("|")) {
    trimmed = trimmed.slice(1);
  }

  if (trimmed.endsWith("|")) {
    trimmed = trimmed.slice(0, -1);
  }

  return trimmed.split("|").map((cell) => cell.trim());
}

function isTableSeparatorLine(line: string) {
  if (!looksLikeTableRow(line)) {
    return false;
  }

  const cells = splitTableRow(line);

  if (cells.length < 2) {
    return false;
  }

  return cells.every((cell) => /^:?-{3,}:?$/.test(cell.replace(/\\s+/g, "")));
}

function parseMarkdownBlocks(markdown: string): MarkdownBlock[] {
  const lines = markdown.replace(/\\r\\n/g, "\\n").split("\\n");
  const blocks: MarkdownBlock[] = [];
  let paragraph: string[] = [];
  let listType: "ul" | "ol" | null = null;
  let listItems: string[] = [];
  let inCode = false;
  let codeLanguage = "";
  let codeLines: string[] = [];

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

  for (let lineIndex = 0; lineIndex < lines.length; lineIndex += 1) {
    const line = lines[lineIndex];
    const trimmed = line.trim();

    if (trimmed.startsWith("```")) {
      if (inCode) {
        blocks.push({
          type: "code",
          language: codeLanguage,
          content: codeLines.join("\\n"),
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

    const nextLine = lines[lineIndex + 1]?.trim() ?? "";

    if (looksLikeTableRow(trimmed) && isTableSeparatorLine(nextLine)) {
      flushParagraph();
      flushList();

      const headers = splitTableRow(trimmed);
      const rows: string[][] = [];
      lineIndex += 2;

      while (lineIndex < lines.length && looksLikeTableRow(lines[lineIndex])) {
        const row = splitTableRow(lines[lineIndex]);

        if (row.length > 0) {
          rows.push(row);
        }

        lineIndex += 1;
      }

      lineIndex -= 1;

      blocks.push({
        type: "table",
        headers,
        rows,
      });

      continue;
    }

    const heading = /^(#{1,6})\\s+(.+)$/.exec(trimmed);
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

    const unordered = /^[-*]\\s+(.+)$/.exec(trimmed);
    if (unordered) {
      flushParagraph();
      if (listType && listType !== "ul") {
        flushList();
      }
      listType = "ul";
      listItems.push(unordered[1].trim());
      continue;
    }

    const ordered = /^\\d+\\.\\s+(.+)$/.exec(trimmed);
    if (ordered) {
      flushParagraph();
      if (listType && listType !== "ol") {
        flushList();
      }
      listType = "ol";
      listItems.push(ordered[1].trim());
      continue;
    }

    flushList();
    paragraph.push(trimmed);
  }

  if (inCode) {
    blocks.push({
      type: "code",
      language: codeLanguage,
      content: codeLines.join("\\n"),
    });
  }

  flushParagraph();
  flushList();

  return blocks;
}
"""


NEW_MARKDOWN_CONTENT = """function MarkdownContent({ content }: { content: string }) {
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

        if (block.type === "table") {
          return (
            <div key={index} className="markdown-table-wrap">
              <table className="markdown-table">
                <thead>
                  <tr>
                    {block.headers.map((header, headerIndex) => (
                      <th key={headerIndex}>{renderInlineMarkdown(header)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {block.rows.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      {block.headers.map((_, cellIndex) => (
                        <td key={cellIndex}>
                          {renderInlineMarkdown(row[cellIndex] ?? "")}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }

        return (
          <pre key={index}>
            {block.language ? <span className="markdown-content__language">{block.language}</span> : null}
            <code>{block.content}</code>
          </pre>
        );
      })}
    </div>
  );
}
"""


def patch_file() -> None:
    project_root = Path.cwd()
    chat_path = project_root / "apps" / "desktop" / "src" / "components" / "shell" / "ChatWorkspace.tsx"
    css_path = project_root / "apps" / "desktop" / "src" / "styles" / "chat-markdown-table.css"

    if not chat_path.exists():
        raise SystemExit(f"Missing file: {chat_path}")

    original = chat_path.read_text(encoding="utf-8")
    text = original

    if 'type: "table"' not in text:
        text = text.replace(
            '| { type: "code"; language: string; content: string };',
            '| { type: "table"; headers: string[]; rows: string[][] }\n'
            '  | { type: "code"; language: string; content: string };',
        )

    text = re.sub(
        r"function parseMarkdownBlocks\(markdown: string\): MarkdownBlock\[\] \{.*?\n\}\n\nfunction renderInlineMarkdown",
        NEW_PARSE_MARKDOWN_BLOCKS + "\n\nfunction renderInlineMarkdown",
        text,
        flags=re.DOTALL,
    )

    text = re.sub(
        r"function MarkdownContent\(\{ content \}: \{ content: string \}\) \{.*?\n\}\n\nfunction SendIcon",
        NEW_MARKDOWN_CONTENT + "\n\nfunction SendIcon",
        text,
        flags=re.DOTALL,
    )

    if 'import "../../styles/chat-markdown-table.css";' not in text:
        marker = 'import "../../styles/chat-markdown-content.css";'
        if marker in text:
            text = text.replace(marker, marker + '\nimport "../../styles/chat-markdown-table.css";')
        else:
            text = 'import "../../styles/chat-markdown-table.css";\n' + text

    if text == original:
        print("No changes made. ChatWorkspace may already be patched or function names changed.")
    else:
        backup = chat_path.with_suffix(".tsx.bak_markdown_tables")
        backup.write_text(original, encoding="utf-8")
        chat_path.write_text(text, encoding="utf-8")
        print(f"Patched: {chat_path}")
        print(f"Backup:  {backup}")

    css_path.parent.mkdir(parents=True, exist_ok=True)
    css_path.write_text(
        """/* Markdown table rendering for Serviq chat output */

.markdown-table-wrap {
  width: 100%;
  max-width: 100%;
  overflow-x: auto;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.105);
  background: rgba(0, 0, 0, 0.16);
}

.markdown-table {
  width: 100%;
  min-width: 420px;
  border-collapse: collapse;
  color: rgba(255, 255, 255, 0.9);
  font-size: 0.94rem;
}

.markdown-table th,
.markdown-table td {
  border-bottom: 1px solid rgba(255, 255, 255, 0.075);
  padding: 10px 12px;
  text-align: left;
  vertical-align: top;
  line-height: 1.45;
}

.markdown-table th {
  background: rgba(255, 255, 255, 0.075);
  color: #ffffff;
  font-weight: 850;
}

.markdown-table tbody tr:last-child td {
  border-bottom: 0;
}

.markdown-table td code,
.markdown-table th code {
  white-space: nowrap;
}
""",
        encoding="utf-8",
    )
    print(f"Updated CSS: {css_path}")
    print("")
    print("Restart desktop:")
    print("pnpm desktop:dev")


if __name__ == "__main__":
    patch_file()
