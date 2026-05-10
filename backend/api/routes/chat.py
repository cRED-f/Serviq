from fastapi import APIRouter

from schemas.chat import ChatRequest, ChatResponse
from schemas.common import ApiResponse

router = APIRouter()


@router.post("/message", response_model=ApiResponse[ChatResponse])
async def create_chat_message(payload: ChatRequest) -> ApiResponse[ChatResponse]:
    """Backend-core placeholder.

    The endpoint shape is final, but real LM Studio/LangGraph execution starts
    in the next process. Keeping the contract now prevents UI/backend churn.
    """

    return ApiResponse(
        data=ChatResponse(
            conversation_id=payload.conversation_id,
            message=(
                "Serviq backend core is running. "
                "LM Studio and LangGraph integration will be added in the next process."
            ),
        )
    )
