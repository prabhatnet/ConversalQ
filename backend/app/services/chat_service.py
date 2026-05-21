"""
Chat Service — orchestrates chat interactions via the multi-agent graph.

Phase 3 upgrade: all LLM calls go through AgentOrchestrationService which
runs the LangGraph router → specialist pipeline. The HTTP contracts
(ChatRequest / ChatResponse) are unchanged.
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

logger = structlog.get_logger(__name__)


class ChatService:
    """Orchestrates chat message processing through the multi-agent graph."""

    def __init__(
        self,
        conversation_repo: ConversationRepository,
        message_repo: MessageRepository,
        knowledge_service: Optional[KnowledgeService] = None,
    ):
        self._conversations = conversation_repo
        self._messages = message_repo
        self._knowledge = knowledge_service
        self._agent = AgentOrchestrationService(knowledge_service=knowledge_service)

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
