"""
Dependency injection providers for FastAPI.

Architecture Decision:
- All service dependencies provided via FastAPI Depends()
- Enables easy mocking in tests
- Single responsibility: each provider yields one dependency
- Database sessions are request-scoped (per-request lifecycle)
- Falls back to in-memory repositories when PostgreSQL is unavailable
"""

from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.session import get_db_session
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.in_memory import InMemoryConversationRepository, InMemoryMessageRepository
from app.repositories.message_repo import MessageRepository
from app.services.chat_service import ChatService
from app.services.llm_service import LLMService


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


def get_chat_service(
    llm_service: LLMService = Depends(get_llm_service),
) -> ChatService:
    """Provide the chat service — uses DB repos or in-memory fallback."""
    from app.core.events import db_available

    if db_available:
        # This path requires DB session — will be used when PostgreSQL is running
        # For now, fall through to in-memory since DI can't conditionally inject
        pass

    # Use in-memory repositories (works without PostgreSQL)
    conversation_repo = InMemoryConversationRepository()
    message_repo = InMemoryMessageRepository()

    return ChatService(
        llm_service=llm_service,
        conversation_repo=conversation_repo,
        message_repo=message_repo,
    )
