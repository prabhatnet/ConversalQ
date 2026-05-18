"""
Chat Service — orchestrates chat interactions.

Architecture Decision:
- Service layer contains all business logic
- Coordinates between LLM service and data repositories
- Handles conversation lifecycle (create, continue)
- Builds message history for context injection
- Streaming implemented as an async generator yielding SSE-formatted data
"""

import json
import time
from datetime import datetime, timezone
from typing import AsyncIterator, Optional
from uuid import UUID

import structlog

from app.core.exceptions import ConversationNotFoundError
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.message_repo import MessageRepository
from app.schemas.chat import ChatResponse
from app.services.llm_service import LLMService
from app.services.knowledge_service import KnowledgeService

logger = structlog.get_logger(__name__)


class ChatService:
    """Orchestrates chat message processing with LLM and persistence."""

    def __init__(
        self,
        llm_service: LLMService,
        conversation_repo: ConversationRepository,
        message_repo: MessageRepository,
        knowledge_service: Optional[KnowledgeService] = None,
    ):
        self._llm = llm_service
        self._conversations = conversation_repo
        self._messages = message_repo
        self._knowledge = knowledge_service

    async def process_message(
        self,
        message: str,
        conversation_id: Optional[UUID] = None,
    ) -> ChatResponse:
        """
        Process a user message and generate a complete AI response.

        1. Load or create conversation
        2. Persist user message
        3. Build message history for context
        4. Call LLM for response
        5. Persist assistant response
        6. Return structured response
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

        # Step 3: Build context from conversation history
        history = await self._messages.get_by_conversation(conversation.id, limit=20)
        llm_messages = [{"role": msg.role, "content": msg.content} for msg in history]

        # Step 3b: RAG — retrieve relevant knowledge-base context
        rag_system_addendum = ""
        if self._knowledge:
            retrieval = await self._knowledge.retrieve_context(message)
            if retrieval.has_context:
                rag_system_addendum = (
                    "\n\n--- Relevant Knowledge Base Context ---\n"
                    + retrieval.formatted_context
                    + "\n--- End of Context ---\n"
                    + "\nUse the above context to inform your response. "
                    "Always cite the source document when referencing knowledge base content."
                )

        # Step 4: Generate LLM response
        result = await self._llm.generate_response(llm_messages, system_prompt_addendum=rag_system_addendum)

        # Step 5: Persist assistant response
        assistant_message = await self._messages.create_message(
            conversation_id=conversation.id,
            role="assistant",
            content=result["content"],
            model=result["model"],
            token_count=result["token_count"],
            latency_ms=result["latency_ms"],
        )

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        # Step 6: Return response
        return ChatResponse(
            conversation_id=conversation.id,
            message_id=assistant_message.id,
            response=result["content"],
            model=result["model"],
            token_count=result["token_count"],
            latency_ms=elapsed_ms,
            created_at=assistant_message.created_at,
        )

    async def process_message_stream(
        self,
        message: str,
        conversation_id: Optional[UUID] = None,
    ) -> AsyncIterator[str]:
        """
        Process a user message and stream the AI response via SSE.

        Yields SSE-formatted data events:
        - data: {"token": "..."} — for each content chunk
        - data: {"done": true, "conversation_id": "..."} — on completion
        """
        # Resolve conversation
        conversation = await self._resolve_conversation(conversation_id)

        # Persist user message
        await self._messages.create_message(
            conversation_id=conversation.id,
            role="user",
            content=message,
        )

        # Build context
        history = await self._messages.get_by_conversation(conversation.id, limit=20)
        llm_messages = [{"role": msg.role, "content": msg.content} for msg in history]

        # RAG context
        rag_system_addendum = ""
        if self._knowledge:
            retrieval = await self._knowledge.retrieve_context(message)
            if retrieval.has_context:
                rag_system_addendum = (
                    "\n\n--- Relevant Knowledge Base Context ---\n"
                    + retrieval.formatted_context
                    + "\n--- End of Context ---\n"
                    + "\nUse the above context to inform your response. "
                    "Always cite the source document when referencing knowledge base content."
                )

        # Stream response
        full_response = ""
        start_time = time.perf_counter()

        async for token in self._llm.generate_response_stream(llm_messages, system_prompt_addendum=rag_system_addendum):
            full_response += token
            yield f"data: {json.dumps({'token': token})}\n\n"

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        # Persist complete response
        await self._messages.create_message(
            conversation_id=conversation.id,
            role="assistant",
            content=full_response,
            model=self._llm._model,
            latency_ms=elapsed_ms,
        )

        # Signal completion
        yield f"data: {json.dumps({'done': True, 'conversation_id': str(conversation.id)})}\n\n"

    async def _resolve_conversation(self, conversation_id: Optional[UUID]):
        """Load existing conversation or create a new one."""
        if conversation_id:
            conversation = await self._conversations.get_with_messages(conversation_id)
            if not conversation:
                raise ConversationNotFoundError(str(conversation_id))
            return conversation

        # Create new conversation
        return await self._conversations.create_new(channel="chat")
