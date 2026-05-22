"""
Chat Service — orchestrates chat interactions via the multi-agent graph.

Phase 3 upgrade: all LLM calls go through AgentOrchestrationService which
runs the LangGraph router → specialist pipeline.

Phase 4 upgrade: ConversationMemoryService injects sliding-window context and
LLM-generated summaries into each turn. Conversation status auto-transitions
to "escalated" when the agent flags should_escalate=True.
"""

import json
import time
from datetime import datetime, timezone
from typing import AsyncIterator, Optional
from uuid import UUID

import structlog

from app.agents.orchestration import AgentOrchestrationService
from app.config import get_settings
from app.core.exceptions import ConversationNotFoundError
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.message_repo import MessageRepository
from app.schemas.chat import ChatResponse
from app.services.knowledge_service import KnowledgeService
from app.services.memory_service import ConversationMemoryService

logger = structlog.get_logger(__name__)


class ChatService:
    """Orchestrates chat message processing through the multi-agent graph."""

    def __init__(
        self,
        conversation_repo: ConversationRepository,
        message_repo: MessageRepository,
        knowledge_service: Optional[KnowledgeService] = None,
        memory_service: Optional[ConversationMemoryService] = None,
    ):
        self._conversations = conversation_repo
        self._messages = message_repo
        self._knowledge = knowledge_service
        self._agent = AgentOrchestrationService(knowledge_service=knowledge_service)
        self._memory = memory_service or ConversationMemoryService()

    async def process_message(
        self,
        message: str,
        conversation_id: Optional[UUID] = None,
    ) -> ChatResponse:
        """
        Process a user message through the multi-agent graph.

        1. Load or create conversation
        2. Persist user message
        3. Get memory context (sliding window + optional summary)
        4. Run agent graph (router → specialist) with memory context
        5. Persist assistant response
        6. Auto-update conversation status if escalated
        7. Return enriched ChatResponse
        """
        start_time = time.perf_counter()

        # Step 1: Resolve conversation
        conversation = await self._resolve_conversation(conversation_id)

        # Step 2: Persist user message
        await self._messages.create_message(
            conversation_id=conversation.id,
            role="user",
            content=message,
        )

        # Step 3: Get memory context (excludes the message we just saved via window slicing)
        memory_ctx = await self._memory.get_context(
            conversation_id=conversation.id,
            message_repo=self._messages,
            conversation_repo=self._conversations,
        )
        # recent_messages includes the current user msg at the end — exclude it
        # so the agent receives prior turns only as history
        history = memory_ctx.recent_messages[:-1] if memory_ctx.recent_messages else []

        logger.debug(
            "memory_context_ready",
            conversation_id=str(conversation.id),
            total_turns=memory_ctx.total_turns,
            has_summary=memory_ctx.summary is not None,
            history_window=len(history),
        )

        # Step 4: Run agent graph with memory context
        agent_response = await self._agent.process(
            user_message=message,
            history=history,
            conversation_summary=memory_ctx.summary,
        )

        # Step 5: Persist assistant response
        settings = get_settings()
        assistant_message = await self._messages.create_message(
            conversation_id=conversation.id,
            role="assistant",
            content=agent_response.content,
            model=settings.openai_model,
            agent_name=agent_response.active_agent,
            latency_ms=agent_response.latency_ms,
        )

        # Step 6: Auto-transition status on escalation
        if agent_response.should_escalate and conversation.status == "active":
            await self._conversations.update_status(conversation.id, "escalated")
            logger.info(
                "conversation_escalated",
                conversation_id=str(conversation.id),
                reason=agent_response.escalation_reason,
            )

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        return ChatResponse(
            conversation_id=conversation.id,
            message_id=assistant_message.id,
            response=agent_response.content,
            model=settings.openai_model,
            latency_ms=elapsed_ms,
            created_at=assistant_message.created_at,
            intent=agent_response.intent,
            agent_name=agent_response.active_agent,
            confidence=agent_response.confidence,
            rag_sources=agent_response.rag_sources,
            should_escalate=agent_response.should_escalate,
        )

    async def process_message_stream(
        self,
        message: str,
        conversation_id: Optional[UUID] = None,
    ) -> AsyncIterator[str]:
        """
        Process a user message and stream tokens via SSE.

        Yields:
        - ``data: {"token": "..."}`` for each content chunk
        - ``data: {"done": true, "conversation_id": "..."}`` on completion
        """
        conversation = await self._resolve_conversation(conversation_id)

        await self._messages.create_message(
            conversation_id=conversation.id,
            role="user",
            content=message,
        )

        # Get memory context for stream path too
        memory_ctx = await self._memory.get_context(
            conversation_id=conversation.id,
            message_repo=self._messages,
            conversation_repo=self._conversations,
        )
        history = memory_ctx.recent_messages[:-1] if memory_ctx.recent_messages else []

        full_response = ""
        start_time = time.perf_counter()

        async for token in self._agent.process_stream(
            user_message=message,
            history=history,
            conversation_summary=memory_ctx.summary,
        ):
            full_response += token
            yield f"data: {json.dumps({'token': token})}\n\n"

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        settings = get_settings()
        await self._messages.create_message(
            conversation_id=conversation.id,
            role="assistant",
            content=full_response,
            model=settings.openai_model,
            latency_ms=elapsed_ms,
        )

        yield f"data: {json.dumps({'done': True, 'conversation_id': str(conversation.id)})}\n\n"

    async def get_history(self, conversation_id: UUID):
        """Return conversation metadata + full message list."""
        conversation = await self._conversations.get_by_id(conversation_id)
        if not conversation:
            raise ConversationNotFoundError(str(conversation_id))
        messages = await self._messages.get_by_conversation(conversation_id, limit=500)
        return conversation, messages

    async def get_summary(self, conversation_id: UUID):
        """Return the current memory context (summary + turn count)."""
        conversation = await self._conversations.get_by_id(conversation_id)
        if not conversation:
            raise ConversationNotFoundError(str(conversation_id))
        memory_ctx = await self._memory.get_context(
            conversation_id=conversation_id,
            message_repo=self._messages,
            conversation_repo=self._conversations,
        )
        return memory_ctx

    async def update_status(self, conversation_id: UUID, status: str):
        """Manually transition conversation status (e.g. resolve or close)."""
        valid = {"active", "resolved", "escalated", "closed"}
        if status not in valid:
            raise ValueError(f"Invalid status '{status}'. Must be one of {valid}.")
        conversation = await self._conversations.get_by_id(conversation_id)
        if not conversation:
            raise ConversationNotFoundError(str(conversation_id))
        await self._conversations.update_status(conversation_id, status)

    async def _resolve_conversation(self, conversation_id: Optional[UUID]):
        """Load existing conversation or create a new one."""
        if conversation_id:
            conversation = await self._conversations.get_with_messages(conversation_id)
            if not conversation:
                raise ConversationNotFoundError(str(conversation_id))
            return conversation
        return await self._conversations.create_new(channel="chat")

    async def process_message(
        self,
        message: str,
        conversation_id: Optional[UUID] = None,
    ) -> ChatResponse:
        """
        Process a user message through the multi-agent graph.

        1. Load or create conversation
        2. Persist user message
        3. Build history for graph context
        4. Run agent graph (router → specialist)
        5. Persist assistant response
        6. Return enriched ChatResponse
        """
        start_time = time.perf_counter()

        # Step 1: Resolve conversation
        conversation = await self._resolve_conversation(conversation_id)

        # Step 2: Persist user message
        await self._messages.create_message(
            conversation_id=conversation.id,
            role="user",
            content=message,
        )

        # Step 3: Build history (exclude the message we just saved)
        history_msgs = await self._messages.get_by_conversation(conversation.id, limit=20)
        # history_msgs includes the user message we just saved; exclude it
        # so the agent gets prior turns only
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in history_msgs[:-1]  # all but last (which is the current user msg)
        ]

        # Step 4: Run agent graph
        agent_response = await self._agent.process(
            user_message=message,
            history=history,
        )

        # Step 5: Persist assistant response
        settings = get_settings()
        assistant_message = await self._messages.create_message(
            conversation_id=conversation.id,
            role="assistant",
            content=agent_response.content,
            model=settings.openai_model,
            agent_name=agent_response.active_agent,
            latency_ms=agent_response.latency_ms,
        )

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        return ChatResponse(
            conversation_id=conversation.id,
            message_id=assistant_message.id,
            response=agent_response.content,
            model=settings.openai_model,
            latency_ms=elapsed_ms,
            created_at=assistant_message.created_at,
            intent=agent_response.intent,
            agent_name=agent_response.active_agent,
            confidence=agent_response.confidence,
            rag_sources=agent_response.rag_sources,
            should_escalate=agent_response.should_escalate,
        )

    async def process_message_stream(
        self,
        message: str,
        conversation_id: Optional[UUID] = None,
    ) -> AsyncIterator[str]:
        """
        Process a user message and stream tokens via SSE.

        Yields:
        - ``data: {"token": "..."}`` for each content chunk
        - ``data: {"done": true, "conversation_id": "...", "intent": "...", "agent_name": "..."}`` on completion
        """
        conversation = await self._resolve_conversation(conversation_id)

        await self._messages.create_message(
            conversation_id=conversation.id,
            role="user",
            content=message,
        )

        history_msgs = await self._messages.get_by_conversation(conversation.id, limit=20)
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in history_msgs[:-1]
        ]

        full_response = ""
        start_time = time.perf_counter()

        # First, run a non-streaming pass to get routing metadata
        # then stream a second pass for the actual response tokens.
        # We use process_stream which streams from the specialist LLM call.
        async for token in self._agent.process_stream(
            user_message=message,
            history=history,
        ):
            full_response += token
            yield f"data: {json.dumps({'token': token})}\n\n"

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        # Persist the complete response
        settings = get_settings()
        await self._messages.create_message(
            conversation_id=conversation.id,
            role="assistant",
            content=full_response,
            model=settings.openai_model,
            latency_ms=elapsed_ms,
        )

        yield f"data: {json.dumps({'done': True, 'conversation_id': str(conversation.id)})}\n\n"

    async def _resolve_conversation(self, conversation_id: Optional[UUID]):
        """Load existing conversation or create a new one."""
        if conversation_id:
            conversation = await self._conversations.get_with_messages(conversation_id)
            if not conversation:
                raise ConversationNotFoundError(str(conversation_id))
            return conversation
        return await self._conversations.create_new(channel="chat")
