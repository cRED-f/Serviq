from pathlib import Path


def find_project_root() -> Path:
    """Find the repository root from any backend module.

    We intentionally avoid depending on the current working directory because
    scripts may start the backend from the root, from backend/, or from a
    desktop process later.
    """

    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "package.json").exists() and (parent / "backend").exists():
            return parent
    return current.parents[2]


PROJECT_ROOT = find_project_root()
BACKEND_ROOT = PROJECT_ROOT / "backend"
WORKSPACE_ROOT = PROJECT_ROOT / "workspace"


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    return (PROJECT_ROOT / path).resolve()
