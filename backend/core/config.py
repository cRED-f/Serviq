from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def find_project_root() -> Path:
    current = Path(__file__).resolve()

    for parent in current.parents:
        if (parent / "package.json").exists() and (parent / "backend").exists():
            return parent

    return current.parents[2]


PROJECT_ROOT = find_project_root()


def normalize_sqlite_url(value: str) -> str:
    """Normalize SQLite URLs so relative workspace paths work from any cwd."""
    if value == "sqlite+aiosqlite:///workspace/serviq.sqlite3":
        return f"sqlite+aiosqlite:///{PROJECT_ROOT / 'workspace' / 'serviq.sqlite3'}"

    if value.startswith("sqlite+aiosqlite:///workspace/"):
        relative_part = value.replace("sqlite+aiosqlite:///workspace/", "", 1)
        return f"sqlite+aiosqlite:///{PROJECT_ROOT / 'workspace' / relative_part}"

    return value


class Settings(BaseSettings):
    app_name: str = "Serviq"
    app_version: str = "0.8.0"
    environment: str = Field(default="development", alias="SERVIQ_ENVIRONMENT")

    api_host: str = Field(default="127.0.0.1", alias="SERVIQ_API_HOST")
    api_port: int = Field(default=8787, alias="SERVIQ_API_PORT")

    database_url: str = Field(
        default=f"sqlite+aiosqlite:///{PROJECT_ROOT / 'workspace' / 'serviq.sqlite3'}",
        alias="DATABASE_URL",
    )

    qdrant_url: str = Field(default="http://127.0.0.1:6333", alias="QDRANT_URL")
    qdrant_collection: str = Field(default="serviq_memory", alias="QDRANT_COLLECTION")

    lmstudio_base_url: str = Field(
        default="http://127.0.0.1:1234/v1",
        alias="LMSTUDIO_BASE_URL",
    )
    lmstudio_api_key: str = Field(default="lm-studio", alias="LMSTUDIO_API_KEY")
    lmstudio_timeout_seconds: float = Field(default=90.0, alias="LMSTUDIO_TIMEOUT_SECONDS")

    memory_embedding_model: str = Field(
        default="nomic-embed-text-v1.5",
        alias="MEMORY_EMBEDDING_MODEL",
    )

    tool_timeout_seconds: int = Field(default=20, alias="TOOL_TIMEOUT_SECONDS")
    shell_max_output_chars: int = Field(default=16000, alias="SHELL_MAX_OUTPUT_CHARS")
    shell_max_command_chars: int = Field(default=2000, alias="SHELL_MAX_COMMAND_CHARS")

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://127.0.0.1:1420",
            "http://localhost:1420",
            "tauri://localhost",
        ]
    )

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    def model_post_init(self, __context: object) -> None:
        self.database_url = normalize_sqlite_url(self.database_url)

    @property
    def is_development(self) -> bool:
        return self.environment.lower() in {"dev", "development", "local"}

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"prod", "production"}

    @property
    def app_env(self) -> str:
        return self.environment

    @property
    def env(self) -> str:
        return self.environment

    @property
    def service_name(self) -> str:
        return self.app_name

    @property
    def version(self) -> str:
        return self.app_version

    @property
    def host(self) -> str:
        return self.api_host

    @property
    def port(self) -> int:
        return self.api_port

    @property
    def backend_host(self) -> str:
        return self.api_host

    @property
    def backend_port(self) -> int:
        return self.api_port

    @property
    def allowed_origins(self) -> list[str]:
        return self.cors_origins

    @property
    def cors_allow_origins(self) -> list[str]:
        return self.cors_origins

    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT

    @property
    def backend_dir(self) -> Path:
        return PROJECT_ROOT / "backend"

    @property
    def workspace_dir(self) -> Path:
        return PROJECT_ROOT / "workspace"

    @property
    def notes_dir(self) -> Path:
        return self.workspace_dir / "notes"

    @property
    def projects_dir(self) -> Path:
        return self.workspace_dir / "projects"

    @property
    def uploads_dir(self) -> Path:
        return self.workspace_dir / "uploads"

    @property
    def generated_dir(self) -> Path:
        return self.workspace_dir / "generated"

    @property
    def logs_dir(self) -> Path:
        return self.workspace_dir / "logs"

    @property
    def runtime_dir(self) -> Path:
        return self.workspace_dir / "runtime"

    @property
    def data_dir(self) -> Path:
        return self.workspace_dir / "data"

    @property
    def cache_dir(self) -> Path:
        return self.workspace_dir / "cache"

    @property
    def temp_dir(self) -> Path:
        return self.workspace_dir / "temp"

    @property
    def db_dir(self) -> Path:
        return self.workspace_dir / "db"

    @property
    def workspace_path(self) -> Path:
        return self.workspace_dir

    @property
    def notes_path(self) -> Path:
        return self.notes_dir

    @property
    def projects_path(self) -> Path:
        return self.projects_dir

    @property
    def uploads_path(self) -> Path:
        return self.uploads_dir

    @property
    def generated_path(self) -> Path:
        return self.generated_dir

    @property
    def logs_path(self) -> Path:
        return self.logs_dir

    @property
    def runtime_path(self) -> Path:
        return self.runtime_dir

    @property
    def data_path(self) -> Path:
        return self.data_dir

    @property
    def cache_path(self) -> Path:
        return self.cache_dir

    @property
    def temp_path(self) -> Path:
        return self.temp_dir

    @property
    def db_path(self) -> Path:
        return self.db_dir

    @property
    def sqlite_database_url(self) -> str:
        return self.database_url

    @property
    def db_url(self) -> str:
        return self.database_url

    @property
    def lm_studio_base_url(self) -> str:
        return self.lmstudio_base_url

    @property
    def lm_studio_api_key(self) -> str:
        return self.lmstudio_api_key

    @property
    def lm_studio_timeout_seconds(self) -> float:
        return self.lmstudio_timeout_seconds


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
