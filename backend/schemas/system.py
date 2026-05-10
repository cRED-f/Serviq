from pydantic import BaseModel


class SystemInfo(BaseModel):
    app_name: str
    app_env: str
    backend_status: str
    process: str
    workspace_dir: str
    lm_studio_base_url: str
    qdrant_url: str
