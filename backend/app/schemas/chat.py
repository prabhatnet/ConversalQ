"""
Chat API Pydantic schemas — request/response contracts.

Architecture Decision:
- Strict validation at the API boundary
- Optional conversation_id: None creates a new conversation
- Response includes metadata for observability (latency, tokens)
"""

from datetime import datetime
from typing import Optional
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
