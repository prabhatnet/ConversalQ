"""
Chat API endpoints — handles synchronous and streaming chat interactions.

Architecture Decision:
- Thin controller layer: validates input, delegates to ChatService, formats output
- Streaming uses Server-Sent Events (SSE) via StreamingResponse
- Conversation ID returned for session continuity
- All business logic lives in the service layer
"""

from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.dependencies import get_chat_service
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    """
    Send a message and receive a complete AI response.

    - Creates a new conversation if conversation_id is not provided.
    - Maintains conversation context across messages when conversation_id is reused.
    """
    logger.info(
        "chat_request_received",
        conversation_id=str(request.conversation_id) if request.conversation_id else None,
        message_length=len(request.message),
    )

    response = await chat_service.process_message(
        message=request.message,
        conversation_id=request.conversation_id,
    )

    logger.info(
        "chat_response_sent",
        conversation_id=str(response.conversation_id),
        response_length=len(response.response),
        latency_ms=response.latency_ms,
    )

    return response


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    """
    Send a message and receive a streaming AI response via Server-Sent Events (SSE).

    The stream emits:
    - `data: {"token": "..."}` for each token
    - `data: {"done": true, "conversation_id": "..."}` when complete
    """
    logger.info(
        "chat_stream_request_received",
        conversation_id=str(request.conversation_id) if request.conversation_id else None,
        message_length=len(request.message),
    )

    return StreamingResponse(
        chat_service.process_message_stream(
            message=request.message,
            conversation_id=request.conversation_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
