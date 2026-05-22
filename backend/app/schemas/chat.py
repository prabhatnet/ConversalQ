"""
Chat API Pydantic schemas — request/response contracts.

Architecture Decision:
- Strict validation at the API boundary
- Optional conversation_id: None creates a new conversation
- Response includes metadata for observability (latency, tokens)
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Incoming chat message from the client."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="The user's message to the AI assistant.",
        examples=["I need help with my billing issue"],
    )
    conversation_id: Optional[UUID] = Field(
        default=None,
        description="Existing conversation ID for context continuity. Omit to start a new conversation.",
    )

    model_config = {"json_schema_extra": {
        "examples": [
            {
                "message": "I need help with my billing issue",
                "conversation_id": None,
            }
        ]
    }}


class ChatResponse(BaseModel):
    """AI assistant response returned to the client."""

    conversation_id: UUID = Field(description="Conversation ID for session tracking.")
    message_id: UUID = Field(description="Unique ID of this response message.")
    response: str = Field(description="The AI assistant's response text.")
    model: str = Field(description="LLM model used for generation.")
    token_count: Optional[int] = Field(default=None, description="Total tokens consumed.")
    latency_ms: int = Field(description="Processing time in milliseconds.")
    created_at: datetime = Field(description="Timestamp of response generation.")
    # Phase 3 — agent metadata
    intent: Optional[str] = Field(default=None, description="Classified intent (billing, technical, account, general, escalation).")
    agent_name: Optional[str] = Field(default=None, description="Specialist agent that generated the response.")
    confidence: Optional[float] = Field(default=None, description="Router confidence score.")
    rag_sources: List[str] = Field(default_factory=list, description="Source documents used for RAG context.")
    should_escalate: bool = Field(default=False, description="True if the conversation should be escalated to a human agent.")


# ---------------------------------------------------------------------------
# Phase 4 — Memory & Session schemas
# ---------------------------------------------------------------------------

class MessageItem(BaseModel):
    """A single message in a conversation history response."""

    id: UUID
    role: str = Field(description="Message role: user or assistant.")
    content: str
    agent_name: Optional[str] = Field(default=None)
    created_at: datetime


class ConversationHistoryResponse(BaseModel):
    """Full message history for a conversation."""

    conversation_id: UUID
    status: str = Field(description="Conversation lifecycle status: active, resolved, escalated, closed.")
    total_messages: int
    messages: List[MessageItem]


class ConversationSummaryResponse(BaseModel):
    """LLM-generated memory summary for a conversation."""

    conversation_id: UUID
    status: str
    total_turns: int
    has_summary: bool
    summary: Optional[str] = Field(default=None, description="Rolling LLM summary of prior turns (None for short conversations).")


class ConversationStatusUpdate(BaseModel):
    """Request body for manually updating conversation status."""

    status: str = Field(
        description="New lifecycle status: active, resolved, escalated, or closed.",
        examples=["resolved"],
    )
