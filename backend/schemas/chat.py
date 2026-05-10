from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)
    conversation_id: int | None = None


class ChatResponse(BaseModel):
    conversation_id: int | None = None
    message: str
    process: str = "backend-core"
