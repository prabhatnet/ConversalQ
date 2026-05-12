"""
In-memory repository implementations for development without PostgreSQL.

These provide the same interface as the SQLAlchemy-backed repositories
but store data in Python dictionaries. Data is lost on restart.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

import structlog

logger = structlog.get_logger(__name__)


class InMemoryConversation:
    """In-memory conversation entity."""

    def __init__(self, id: UUID, channel: str = "chat", status: str = "active"):
        self.id = id
        self.channel = channel
        self.status = status
        self.sentiment_score: Optional[float] = None
        self.summary: Optional[str] = None
        self.metadata_: dict = {}
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        self.messages: List["InMemoryMessage"] = []


class InMemoryMessage:
    """In-memory message entity."""

    def __init__(
        self,
        id: UUID,
        conversation_id: UUID,
        role: str,
        content: str,
        model: Optional[str] = None,
        token_count: Optional[int] = None,
        latency_ms: Optional[int] = None,
        agent_name: Optional[str] = None,
    ):
        self.id = id
        self.conversation_id = conversation_id
        self.role = role
        self.content = content
        self.model = model
        self.token_count = token_count
        self.latency_ms = latency_ms
        self.agent_name = agent_name
        self.confidence_score: Optional[float] = None
        self.metadata_: dict = {}
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)


# Module-level in-memory stores
_conversations: Dict[UUID, InMemoryConversation] = {}
_messages: Dict[UUID, List[InMemoryMessage]] = {}


class InMemoryConversationRepository:
    """In-memory conversation repository — same interface as ConversationRepository."""

    async def get_by_id(self, entity_id: UUID) -> Optional[InMemoryConversation]:
        return _conversations.get(entity_id)

    async def get_with_messages(self, conversation_id: UUID) -> Optional[InMemoryConversation]:
        conv = _conversations.get(conversation_id)
        if conv:
            conv.messages = _messages.get(conversation_id, [])
        return conv

    async def create_new(self, channel: str = "chat") -> InMemoryConversation:
        conv = InMemoryConversation(id=uuid.uuid4(), channel=channel)
        _conversations[conv.id] = conv
        _messages[conv.id] = []
        logger.debug("in_memory_conversation_created", conversation_id=str(conv.id))
        return conv


class InMemoryMessageRepository:
    """In-memory message repository — same interface as MessageRepository."""

    async def get_by_conversation(
        self,
        conversation_id: UUID,
        limit: int = 50,
    ) -> List[InMemoryMessage]:
        msgs = _messages.get(conversation_id, [])
        return msgs[-limit:]

    async def create_message(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        model: str | None = None,
        token_count: int | None = None,
        latency_ms: int | None = None,
        agent_name: str | None = None,
    ) -> InMemoryMessage:
        msg = InMemoryMessage(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            role=role,
            content=content,
            model=model,
            token_count=token_count,
            latency_ms=latency_ms,
            agent_name=agent_name,
        )
        if conversation_id not in _messages:
            _messages[conversation_id] = []
        _messages[conversation_id].append(msg)
        return msg
