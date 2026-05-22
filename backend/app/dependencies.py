"""
Dependency injection providers for FastAPI.

Architecture Decision:
- All service dependencies provided via FastAPI Depends()
- Enables easy mocking in tests
- Single responsibility: each provider yields one dependency
- Database sessions are request-scoped (per-request lifecycle)
- Falls back to in-memory repositories when PostgreSQL is unavailable
"""

from typing import AsyncGenerator, Optional

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.session import get_db_session
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.in_memory import InMemoryConversationRepository, InMemoryMessageRepository
from app.repositories.message_repo import MessageRepository
from app.services.chat_service import ChatService
from app.services.llm_service import LLMService
from app.services.knowledge_service import KnowledgeService
from app.services.memory_service import ConversationMemoryService


async def get_db(
    settings: Settings = Depends(get_settings),
) -> AsyncGenerator[AsyncSession, None]:
    """Provide a request-scoped async database session."""
    async for session in get_db_session():
        yield session


def get_llm_service(
    settings: Settings = Depends(get_settings),
) -> LLMService:
    """Provide the LLM service."""
    return LLMService(settings=settings)


def get_conversation_repo(
    db: AsyncSession = Depends(get_db),
) -> ConversationRepository:
    """Provide the conversation repository."""
    return ConversationRepository(session=db)


def get_message_repo(
    db: AsyncSession = Depends(get_db),
) -> MessageRepository:
    """Provide the message repository."""
    return MessageRepository(session=db)


def get_knowledge_service() -> Optional[KnowledgeService]:
    """
    Provide the KnowledgeService — returns None if ChromaDB is unavailable.

    The ChatService and knowledge endpoints handle None gracefully (RAG is
    simply skipped / returns empty results).
    """
    from app.core.events import chroma_available
    from app.rag.vector_store import get_vector_store
    from app.rag.embeddings import get_embeddings_service

    if not chroma_available:
        return None

    return KnowledgeService(
        vector_store=get_vector_store(),
        embeddings_service=get_embeddings_service(),
    )


def get_memory_service() -> ConversationMemoryService:
    """Provide the ConversationMemoryService as a process-level singleton."""
    return _get_memory_service_singleton()


from functools import lru_cache as _lru_cache

@_lru_cache(maxsize=1)
def _get_memory_service_singleton() -> ConversationMemoryService:
    return ConversationMemoryService()


def get_chat_service(
    knowledge_service: Optional[KnowledgeService] = Depends(get_knowledge_service),
    memory_service: ConversationMemoryService = Depends(get_memory_service),
) -> ChatService:
    """Provide the chat service — uses in-memory repos, agent graph for LLM."""
    conversation_repo = InMemoryConversationRepository()
    message_repo = InMemoryMessageRepository()

    return ChatService(
        conversation_repo=conversation_repo,
        message_repo=message_repo,
        knowledge_service=knowledge_service,
        memory_service=memory_service,
    )
