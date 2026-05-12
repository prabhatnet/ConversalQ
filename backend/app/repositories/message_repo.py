"""
Message repository — data access for messages.
"""

from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message
from app.repositories.base import BaseRepository


class MessageRepository(BaseRepository[Message]):
    """Repository for Message entities."""

    def __init__(self, session: AsyncSession):
        super().__init__(model=Message, session=session)

    async def get_by_conversation(
        self,
        conversation_id: UUID,
        limit: int = 50,
    ) -> List[Message]:
        """Retrieve messages for a conversation, ordered by creation time."""
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create_message(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        model: str | None = None,
        token_count: int | None = None,
        latency_ms: int | None = None,
        agent_name: str | None = None,
    ) -> Message:
        """Create and persist a new message."""
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            model=model,
            token_count=token_count,
            latency_ms=latency_ms,
            agent_name=agent_name,
        )
        return await self.create(message)
