"""
Conversation repository — data access for conversations.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversation import Conversation
from app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    """Repository for Conversation entities."""

    def __init__(self, session: AsyncSession):
        super().__init__(model=Conversation, session=session)

    async def get_with_messages(self, conversation_id: UUID) -> Optional[Conversation]:
        """Retrieve a conversation with its messages eagerly loaded."""
        stmt = (
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .options(selectinload(Conversation.messages))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_new(self, channel: str = "chat") -> Conversation:
        """Create and persist a new conversation."""
        conversation = Conversation(channel=channel, status="active")
        return await self.create(conversation)
