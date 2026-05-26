"""
Call Session Store — Phase 5.

Module-level in-memory store mapping Twilio CallSid → CallSession.
Sessions are created on inbound call and cleaned up after call completion.
Shares the same process-lifetime singleton pattern as the in-memory repos.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

import structlog

log = structlog.get_logger(__name__)


@dataclass
class CallSession:
    """Represents a single Twilio voice call with its associated conversation."""

    call_sid: str
    conversation_id: UUID
    from_number: str
    to_number: str
    status: str                         # ringing | in-progress | completed | failed | busy | no-answer | canceled | escalated
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    transcript_log: List[str] = field(default_factory=list)  # ["USER: ...", "ASSISTANT: ..."]
    turn_count: int = 0                 # number of user speech turns processed
    escalated: bool = False


# ---------------------------------------------------------------------------
# Module-level store — process lifetime, shared across all requests
# ---------------------------------------------------------------------------
_sessions: Dict[str, CallSession] = {}


def create_session(
    call_sid: str,
    from_number: str,
    to_number: str,
    conversation_id: UUID,
) -> CallSession:
    """Create and register a new call session."""
    session = CallSession(
        call_sid=call_sid,
        conversation_id=conversation_id,
        from_number=from_number,
        to_number=to_number,
        status="in-progress",
    )
    _sessions[call_sid] = session
    log.info("call_session_created", call_sid=call_sid, from_number=from_number)
    return session


def get_session(call_sid: str) -> Optional[CallSession]:
    """Return session by CallSid, or None if not found."""
    return _sessions.get(call_sid)


def update_status(call_sid: str, status: str) -> Optional[CallSession]:
    """Update the lifecycle status of a call session."""
    session = _sessions.get(call_sid)
    if session:
        session.status = status
        session.updated_at = datetime.now(timezone.utc)
        if status in ("completed", "failed", "busy", "no-answer", "canceled"):
            log.info(
                "call_session_ended",
                call_sid=call_sid,
                status=status,
                turns=session.turn_count,
            )
    return session


def add_transcript(call_sid: str, role: str, text: str) -> None:
    """Append a line to the session transcript log and increment turn counter."""
    session = _sessions.get(call_sid)
    if session:
        session.transcript_log.append(f"{role.upper()}: {text}")
        if role == "user":
            session.turn_count += 1
        session.updated_at = datetime.now(timezone.utc)


def list_sessions(active_only: bool = True) -> List[CallSession]:
    """Return all sessions, optionally filtering to in-progress only."""
    if active_only:
        return [s for s in _sessions.values() if s.status == "in-progress"]
    return list(_sessions.values())
