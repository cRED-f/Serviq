from __future__ import annotations
from pathlib import Path

def find_import_block(lines):
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith('from api.routes import'):
            continue
        if '(' not in stripped:
            return i, i
        j = i
        while j < len(lines):
            if ')' in lines[j]:
                return i, j
            j += 1
        return i, i
    return None

def ensure_import(lines):
    if 'memory_center' in '\n'.join(lines):
        return lines
    block = find_import_block(lines)
    if block is None:
        at = 0
        for i, line in enumerate(lines):
            if line.startswith('from ') or line.startswith('import '):
                at = i + 1
        lines.insert(at, 'from api.routes import memory_center')
        return lines
    start, end = block
    if start == end:
        lines[start] = lines[start] + (', memory_center' if not lines[start].rstrip().endswith(',') else ' memory_center')
    else:
        indent = '    '
        for line in lines[start + 1:end]:
            if line.strip():
                indent = line[: len(line) - len(line.lstrip())]
                break
        lines.insert(end, f'{indent}memory_center,')
    return lines

def ensure_include(lines):
    include_line = 'api_router.include_router(memory_center.router)'
    if include_line in '\n'.join(lines):
        return lines
    at = None
    for i, line in enumerate(lines):
        if 'api_router.include_router' in line:
            at = i + 1
    if at is None:
        for i, line in enumerate(lines):
            if 'api_router' in line and 'APIRouter' in line:
                at = i + 1
                break
    lines.insert(at if at is not None else len(lines), include_line)
    return lines

router_path = Path('backend/api/router.py')
if not router_path.exists():
    raise SystemExit('Run from project root. Missing backend/api/router.py')
if not Path('backend/api/routes/memory_center.py').exists():
    raise SystemExit('Missing backend/api/routes/memory_center.py')
if not Path('backend/services/memory_center_store.py').exists():
    raise SystemExit('Missing backend/services/memory_center_store.py')
original = router_path.read_text(encoding='utf-8')
lines = ensure_include(ensure_import(original.splitlines()))
updated = '\n'.join(lines) + ('\n' if original.endswith('\n') else '')
if updated != original:
    backup = router_path.with_suffix('.py.bak_memory_center')
    backup.write_text(original, encoding='utf-8')
    router_path.write_text(updated, encoding='utf-8')
    print(f'Updated {router_path}; backup {backup}')
else:
    print('router.py already registered memory_center.')
print('Restart backend, then test: Invoke-RestMethod "http://127.0.0.1:8787/api/memory-center"')
