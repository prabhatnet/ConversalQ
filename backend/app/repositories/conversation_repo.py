"""
Conversation repository — data access for conversations.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
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

    async def update_summary(
        self,
        conversation_id: UUID,
        summary: str,
        summarized_through: int = 0,
    ) -> None:
        """Persist the LLM-generated summary and the message count it covers."""
        await self._session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(
                summary=summary,
                metadata_=Conversation.metadata_.op("||")(
                    {"summarized_through": summarized_through}
                ),
            )
        )
        await self._session.flush()

    async def update_status(
        self,
        conversation_id: UUID,
        status: str,
    ) -> None:
        """Update the conversation lifecycle status."""
        await self._session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(status=status)
        )
        await self._session.flush()
