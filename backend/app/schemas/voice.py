"""
Voice API Pydantic schemas — Phase 5.

Covers:
- Twilio webhook payload documentation models (form-encoded, not JSON)
- Call session response models
- Session list response
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Twilio webhook documentation models
# These are NOT used for FastAPI body parsing (Twilio sends form-encoded data).
# They exist for OpenAPI documentation and internal type clarity.
# ---------------------------------------------------------------------------

class InboundCallWebhook(BaseModel):
    """Field reference for Twilio inbound call webhook POST."""
    CallSid: str = Field(description="Unique Twilio call identifier")
    From: str = Field(description="Caller's phone number (E.164)")
    To: str = Field(description="Called number (E.164)")
    CallStatus: str = Field(description="ringing | in-progress | etc.")
    Direction: Optional[str] = Field(default=None, description="inbound | outbound-dial")
    CallerCountry: Optional[str] = Field(default=None)


class GatherWebhook(BaseModel):
    """Field reference for Twilio Gather result webhook POST."""
    CallSid: str = Field(description="Unique Twilio call identifier")
    SpeechResult: Optional[str] = Field(default=None, description="Transcribed caller speech")
    Confidence: Optional[float] = Field(default=None, description="STT confidence score 0–1")
    From: Optional[str] = Field(default=None)
    To: Optional[str] = Field(default=None)


class CallStatusWebhook(BaseModel):
    """Field reference for Twilio call status callback POST."""
    CallSid: str
    CallStatus: str = Field(description="completed | failed | busy | no-answer | canceled")
    Duration: Optional[str] = Field(default=None, description="Call duration in seconds")
    From: Optional[str] = Field(default=None)
    To: Optional[str] = Field(default=None)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class CallSessionResponse(BaseModel):
    """Public representation of a voice call session."""

    call_sid: str = Field(description="Twilio CallSid")
    conversation_id: UUID = Field(description="Linked ConversalQ conversation ID")
    from_number: str = Field(description="Caller phone number")
    to_number: str = Field(description="Called phone number")
    status: str = Field(description="in-progress | completed | failed | escalated | ...")
    turn_count: int = Field(description="Number of user speech turns processed")
    escalated: bool = Field(description="Whether the call was escalated to a human")
    created_at: datetime
    updated_at: datetime
    transcript_log: List[str] = Field(
        default_factory=list,
        description="Ordered log of USER and ASSISTANT turns",
    )


class VoiceSessionsResponse(BaseModel):
    """Paginated list of call sessions."""
    total: int
    sessions: List[CallSessionResponse]
