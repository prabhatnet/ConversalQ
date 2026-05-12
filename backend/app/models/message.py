"""
Message database model.

Represents a single message within a conversation.
Tracks role, content, agent info, and performance metrics.
"""

import uuid
from typing import Optional

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Message(Base, TimestampMixin):
    """Represents a single message in a conversation."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Message role: user, assistant, system, agent",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Message content text",
    )
    agent_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="Name of the AI agent that generated this message",
    )
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        doc="AI confidence score for this response (0.0 to 1.0)",
    )
    model: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="LLM model used for generation",
    )
    token_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Total tokens consumed for this message",
    )
    latency_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Processing latency in milliseconds",
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages",
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, role={self.role}, conversation_id={self.conversation_id})>"
