from __future__ import annotations
from pathlib import Path

p = Path('apps/desktop/src/App.tsx')
if not p.exists():
    raise SystemExit('Run from project root. Missing apps/desktop/src/App.tsx')
text = p.read_text(encoding='utf-8')
original = text
if 'components/shell/MemoryPanel' not in text:
    marker = 'import { ProductHome } from "./components/shell/ProductHome";'
    if marker in text:
        text = text.replace(marker, marker + '\nimport { MemoryPanel } from "./components/shell/MemoryPanel";')
    else:
        marker2 = "import { ProductHome } from './components/shell/ProductHome';"
        text = text.replace(marker2, marker2 + "\nimport { MemoryPanel } from './components/shell/MemoryPanel';")
old = '''if (activeView === "memory") {
      return (
        <PlaceholderPanel
          eyebrow="Memory"
          title="Memory center"
          description="This area will show dynamic memory items, recall behavior, lifecycle states, and semantic search."
          meta={["Saved memory timeline", "Semantic recall panel", "Archive / supersede states"]}
        />
      );
    }'''
if old in text:
    text = text.replace(old, '''if (activeView === "memory") {
      return <MemoryPanel />;
    }''')
old2 = """if (activeView === 'memory') {
      return (
        <PlaceholderPanel
          eyebrow="Memory"
          title="Memory center"
          description="This area will show dynamic memory items, recall behavior, lifecycle states, and semantic search."
          meta={["Saved memory timeline", "Semantic recall panel", "Archive / supersede states"]}
        />
      );
    }"""
if old2 in text:
    text = text.replace(old2, """if (activeView === 'memory') {
      return <MemoryPanel />;
    }""")
# Fallback: replace the memory branch block from if memory to next if settings/return settings.
if '<MemoryPanel />' not in text:
    for needle in ['if (activeView === "memory")', "if (activeView === 'memory')"]:
        start = text.find(needle)
        if start == -1:
            continue
        next_settings = text.find('return (\n      <SettingsPanel', start)
        if next_settings == -1:
            next_settings = text.find('return (\r\n      <SettingsPanel', start)
        if next_settings != -1:
            prefix = text[:start]
            suffix = text[next_settings:]
            quote = '"' if '"memory"' in needle else "'"
            text = prefix + f"if (activeView === {quote}memory{quote}) {{\n      return <MemoryPanel />;\n    }}\n\n    " + suffix
            break
if text != original:
    backup = p.with_suffix('.tsx.bak_memory_panel')
    backup.write_text(original, encoding='utf-8')
    p.write_text(text, encoding='utf-8')
    print(f'Updated {p}; backup {backup}')
else:
    print('No frontend changes needed or exact placeholder not found. Check App.tsx manually.')
