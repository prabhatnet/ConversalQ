"""
Chat API endpoints — handles synchronous and streaming chat interactions.

Phase 4: Added conversation history, summary, and status management endpoints.
Week 2: Added QA scoring endpoint and transcript replay.
Phase 6: Guardrails — prompt injection detection + optional content moderation.
"""

from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.config import Settings, get_settings
from app.core.exceptions import ContentModerationError, ConversationNotFoundError, PromptInjectionError
from app.dependencies import get_chat_service, get_qa_service
from app.guardrails.prompt_injection import detect_injection
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationHistoryResponse,
    ConversationStatusUpdate,
    ConversationSummaryResponse,
    MessageItem,
    TranscriptReplayRequest,
    TranscriptReplayResponse,
    ReplayTurnResult,
)
from app.schemas.qa import QAScoreRequest, QAScoreResponse
from app.services.chat_service import ChatService
from app.services.qa_service import QAService

router = APIRouter()
logger = structlog.get_logger(__name__)


async def _run_guardrails(message: str, settings: Settings) -> None:
    """
    Run all enabled guardrail checks on a user message.

    Order of checks (fastest → slowest):
    1. Prompt injection / jailbreak detection  — synchronous, zero latency
    2. OpenAI content moderation              — async, opt-in via MODERATION_ENABLED

    Raises ``PromptInjectionError`` or ``ContentModerationError`` on violation.
    """
    # --- 1. Prompt injection (synchronous, always on) ---
    injection = detect_injection(message)
    if injection.detected:
        logger.warning(
            "guardrail_injection_blocked",
            reason=injection.reason,
            message_preview=message[:80],
        )
        raise PromptInjectionError(reason=injection.reason or "injection attempt")

    # --- 2. Content moderation (async, opt-in) ---
    if settings.moderation_enabled:
        from app.guardrails.content_moderator import get_content_moderator
        result = await get_content_moderator().check(message)
        if result.flagged:
            logger.warning(
                "guardrail_content_blocked",
                reason=result.reason,
                message_preview=message[:80],
            )
            raise ContentModerationError(reason=result.reason or "content policy violation")


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    settings: Settings = Depends(get_settings),
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    """
    Send a message and receive a complete AI response.

    - Creates a new conversation if conversation_id is not provided.
    - Maintains conversation context across messages when conversation_id is reused.
    - Guardrails: prompt injection detection + optional content moderation.
    """
    logger.info(
        "chat_request_received",
        conversation_id=str(request.conversation_id) if request.conversation_id else None,
        message_length=len(request.message),
    )

    await _run_guardrails(request.message, settings)

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
    settings: Settings = Depends(get_settings),
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

    await _run_guardrails(request.message, settings)

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


@router.post("/replay", response_model=TranscriptReplayResponse, tags=["Transcript Replay"])
async def replay_transcript(
    request: TranscriptReplayRequest,
    chat_service: ChatService = Depends(get_chat_service),
) -> TranscriptReplayResponse:
    """
    Replay a call transcript through the multi-agent graph.

    Submit a full transcript (from `data/sample_transcripts/`) and the endpoint
    will process every **customer** turn sequentially, sharing a single
    conversation context throughout.  Agent turns in the transcript are skipped.

    Returns one `ReplayTurnResult` per customer turn containing the AI response,
    detected intent, routing agent, and confidence score.
    """
    conversation_id = None
    results: list[ReplayTurnResult] = []

    for idx, turn in enumerate(request.transcript):
        if turn.speaker != "customer":
            continue

        response = await chat_service.process_message(
            message=turn.text,
            conversation_id=conversation_id,
        )
        conversation_id = response.conversation_id

        results.append(
            ReplayTurnResult(
                turn_index=idx,
                customer_text=turn.text,
                agent_response=response.response,
                intent=response.intent,
                agent_name=response.agent_name,
                confidence=response.confidence,
                should_escalate=response.should_escalate,
                latency_ms=response.latency_ms,
            )
        )

    return TranscriptReplayResponse(
        call_id=request.call_id,
        conversation_id=conversation_id,
        total_turns=len(request.transcript),
        customer_turns_replayed=len(results),
        turns=results,
    )


@router.post(
    "/{conversation_id}/qa-score",
    response_model=QAScoreResponse,
    tags=["Quality Assurance"],
    summary="Score conversation quality",
)
async def score_conversation_quality(
    conversation_id: UUID,
    body: QAScoreRequest = QAScoreRequest(),
    qa_service: QAService = Depends(get_qa_service),
) -> QAScoreResponse:
    """
    Run the Quality Scoring Agent on a completed conversation.

    Uses OpenAI function calling with a structured four-dimension rubric:

    - **Empathy** — Did the agent acknowledge and validate customer feelings?
    - **Tone** — Was the agent professional and courteous throughout?
    - **Resolution** — Was the customer's issue fully resolved or escalated?
    - **Professionalism** — Did the agent follow correct procedures?

    Each dimension is scored 0.0–1.0. An `overall_score` (mean of all four)
    and a plain-language `overall_summary` are also returned.
    """
    try:
        return await qa_service.score_conversation(
            conversation_id=conversation_id,
            notes=body.notes,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

