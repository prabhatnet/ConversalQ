"""
Chat API endpoints — handles synchronous and streaming chat interactions.

Phase 4: Added conversation history, summary, and status management endpoints.
"""

from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.dependencies import get_chat_service
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationHistoryResponse,
    ConversationStatusUpdate,
    ConversationSummaryResponse,
    MessageItem,
)
from app.services.chat_service import ChatService
from app.core.exceptions import ConversationNotFoundError

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
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{conversation_id}/history", response_model=ConversationHistoryResponse)
async def get_conversation_history(
    conversation_id: UUID,
    chat_service: ChatService = Depends(get_chat_service),
) -> ConversationHistoryResponse:
    """
    Retrieve the full message history for a conversation.

    Returns all messages in chronological order along with the current
    conversation status.
    """
    try:
        conversation, messages = await chat_service.get_history(conversation_id)
    except ConversationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found.",
        )

    return ConversationHistoryResponse(
        conversation_id=conversation.id,
        status=conversation.status,
        total_messages=len(messages),
        messages=[
            MessageItem(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                agent_name=getattr(msg, "agent_name", None),
                created_at=msg.created_at,
            )
            for msg in messages
        ],
    )


@router.get("/{conversation_id}/summary", response_model=ConversationSummaryResponse)
async def get_conversation_summary(
    conversation_id: UUID,
    chat_service: ChatService = Depends(get_chat_service),
) -> ConversationSummaryResponse:
    """
    Retrieve the LLM-generated memory summary for a conversation.

    For short conversations (≤ summarization threshold), `has_summary` will be
    False and `summary` will be null.  For longer conversations the summary
    is generated lazily and cached on the conversation record.
    """
    try:
        conversation = (await chat_service.get_history(conversation_id))[0]
        memory_ctx = await chat_service.get_summary(conversation_id)
    except ConversationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found.",
        )

    return ConversationSummaryResponse(
        conversation_id=conversation_id,
        status=conversation.status,
        total_turns=memory_ctx.total_turns,
        has_summary=memory_ctx.summary is not None,
        summary=memory_ctx.summary,
    )


@router.patch("/{conversation_id}/status", response_model=dict)
async def update_conversation_status(
    conversation_id: UUID,
    body: ConversationStatusUpdate,
    chat_service: ChatService = Depends(get_chat_service),
) -> dict:
    """
    Manually update a conversation's lifecycle status.

    Valid transitions: active → resolved | escalated | closed
    """
    try:
        await chat_service.update_status(conversation_id, body.status)
    except ConversationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found.",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    return {"conversation_id": str(conversation_id), "status": body.status}

