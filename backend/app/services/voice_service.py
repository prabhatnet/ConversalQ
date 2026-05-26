"""
Voice Service — Phase 5.

Orchestrates inbound voice call processing:
  Twilio webhook → call session → agent graph → TwiML response

Flow per turn
-------------
1. Inbound:  create conversation + call session → welcome TwiML
2. Gather:   transcript → ChatService → agent graph → TwiML reply
3. Status:   keep session status in sync with Twilio lifecycle events

Escalation
----------
If the agent sets ``should_escalate=True``, the service generates an
escalation TwiML that dials the configured human-agent transfer number.

The backing conversation is created via ChatService so every voice call
participates in the full memory pipeline (sliding-window context, LLM
summarization, history/summary endpoints).
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

import structlog

from app.config import get_settings
from app.services.chat_service import ChatService
from app.voice.call_session import (
    CallSession,
    add_transcript,
    create_session,
    get_session,
    list_sessions,
    update_status,
)
from app.voice.twiml_handler import get_twiml_builder

log = structlog.get_logger(__name__)


class VoiceService:
    """
    Bridges Twilio webhook events and the ConversalQ multi-agent graph.

    Injected by FastAPI's dependency system; one instance per request but the
    underlying call session store and ChatService repos are module-level
    singletons so state persists across requests.
    """

    def __init__(self, chat_service: ChatService) -> None:
        self._chat = chat_service
        self._twiml = get_twiml_builder()

    # ------------------------------------------------------------------
    # Webhook handlers
    # ------------------------------------------------------------------

    async def handle_inbound_call(
        self,
        call_sid: str,
        from_number: str,
        to_number: str,
    ) -> str:
        """
        Handle an inbound call from Twilio.

        Creates a backing conversation (for full memory support) and a call
        session, then returns the TwiML welcome + first Gather.
        """
        # Create a conversation so the voice call uses the full memory pipeline
        conversation = await self._chat._conversations.create_new(channel="voice")

        create_session(
            call_sid=call_sid,
            from_number=from_number,
            to_number=to_number,
            conversation_id=conversation.id,
        )

        log.info(
            "voice_inbound_handled",
            call_sid=call_sid,
            from_number=from_number,
            conversation_id=str(conversation.id),
        )
        return self._twiml.welcome_response()

    async def handle_gather(
        self,
        call_sid: str,
        speech_result: Optional[str],
        confidence: Optional[float] = None,
    ) -> str:
        """
        Process a Gather POST from Twilio.

        Passes the caller's speech transcript through the agent graph and
        returns TwiML containing the agent's spoken response.
        """
        session = get_session(call_sid)
        if not session:
            log.warning("voice_gather_unknown_session", call_sid=call_sid)
            return self._twiml.error_response()

        transcript = (speech_result or "").strip()
        if len(transcript) < 2:
            # Empty or very short speech — re-prompt
            log.debug("voice_gather_empty_speech", call_sid=call_sid)
            return self._twiml.welcome_response()

        log.info(
            "voice_gather_processing",
            call_sid=call_sid,
            transcript_length=len(transcript),
            confidence=confidence,
        )
        add_transcript(call_sid, "user", transcript)

        try:
            chat_response = await self._chat.process_message(
                message=transcript,
                conversation_id=session.conversation_id,
            )
        except Exception as exc:
            log.exception("voice_agent_error", call_sid=call_sid, error=str(exc))
            return self._twiml.error_response()

        add_transcript(call_sid, "assistant", chat_response.response)

        # Escalation path
        if chat_response.should_escalate:
            session.escalated = True
            update_status(call_sid, "escalated")
            settings = get_settings()
            log.info("voice_escalating", call_sid=call_sid, to=settings.twilio_escalation_number)
            return self._twiml.escalation_response(
                agent_text=chat_response.response,
                escalation_number=settings.twilio_escalation_number,
            )

        return self._twiml.agent_response(chat_response.response)

    async def handle_call_status(
        self,
        call_sid: str,
        call_status: str,
    ) -> None:
        """
        Sync session status with Twilio's call lifecycle event.

        Twilio posts: ringing | in-progress | completed | busy | failed |
                      no-answer | canceled
        """
        session = update_status(call_sid, call_status)
        if session:
            log.info(
                "voice_status_updated",
                call_sid=call_sid,
                status=call_status,
                turns=session.turn_count,
            )
            # Mirror terminal status onto the backing conversation
            if call_status in ("completed", "failed", "busy", "no-answer", "canceled"):
                final_status = "resolved" if call_status == "completed" else call_status
                try:
                    await self._chat._conversations.update_status(
                        session.conversation_id, final_status
                    )
                except Exception:
                    pass  # best-effort; don't fail a status callback

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    def get_session(self, call_sid: str) -> Optional[CallSession]:
        """Return the CallSession for the given CallSid, or None."""
        return get_session(call_sid)

    def list_active_sessions(self) -> List[CallSession]:
        """Return all currently in-progress call sessions."""
        return list_sessions(active_only=True)

    def list_all_sessions(self) -> List[CallSession]:
        """Return all sessions (active + completed)."""
        return list_sessions(active_only=False)
