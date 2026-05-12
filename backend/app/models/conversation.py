"""
Conversation database model.

Represents a customer support conversation session.
A conversation contains multiple messages and tracks overall state.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Float, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Conversation(Base, TimestampMixin):
    """Represents a customer support conversation session."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    channel: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="chat",
        doc="Interaction channel: chat, voice, api",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
        doc="Conversation status: active, resolved, escalated, closed",
    )
    sentiment_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        doc="Overall sentiment score (-1.0 to 1.0)",
    )
    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="AI-generated conversation summary",
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        doc="Extensible metadata (customer info, tags, etc.)",
    )

    # Relationships
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        order_by="Message.created_at",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, status={self.status}, channel={self.channel})>"
