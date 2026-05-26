"""
TwiML Builder — Phase 5.

Generates Twilio Markup Language (TwiML) XML for voice call flows.

Call flow
---------
1. Inbound call  → welcome_response()   → <Gather> + greeting
2. Gather POST   → agent_response()     → <Say> reply + next <Gather>
3. Escalation    → escalation_response()→ <Say> + optional <Dial>
4. Natural end   → hangup_response()    → <Say> goodbye + <Hangup>
5. Error         → error_response()     → <Say> apology + <Hangup>

TTS notes
---------
Twilio's built-in <Say voice="alice"> is free and requires no external calls.
It is the default. When tts_enabled=True the VoiceService generates an mp3 via
OpenAI TTS, stores it, and TwiML uses <Play> instead — see voice_service.py.
"""

from __future__ import annotations

import re
from typing import Optional

import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

# Twilio's built-in voice — clear, free, no extra latency
_DEFAULT_SAY_VOICE = "alice"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clean_for_speech(text: str) -> str:
    """
    Strip markdown and formatting so text reads naturally when spoken aloud.

    Handles: bold/italic, headers, bullet/numbered lists, inline code,
    code fences, URLs, and excess whitespace.
    """
    # Bold / italic
    text = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"_{1,2}(.*?)_{1,2}", r"\1", text, flags=re.DOTALL)
    # Markdown headers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Bullet / numbered list markers
    text = re.sub(r"^\s*[-*•]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    # Code fences and inline code
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]+`", "", text)
    # URLs
    text = re.sub(r"https?://\S+", "", text)
    # Collapse newlines into natural pauses
    text = re.sub(r"\n{2,}", ". ", text)
    text = re.sub(r"\n", " ", text)
    # Collapse spaces
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def _xml_escape(text: str) -> str:
    """Escape special XML/HTML characters to prevent TwiML injection."""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

class TwiMLBuilder:
    """
    Builds complete TwiML XML strings for each stage of a voice call.

    All generated TwiML uses relative action URLs combined with the configured
    ``twilio_webhook_base_url`` so it works both locally (via ngrok) and in
    production without code changes.
    """

    def __init__(self) -> None:
        settings = get_settings()
        base = settings.twilio_webhook_base_url.rstrip("/")
        self._gather_url = f"{base}/api/v1/voice/gather"
        self._voice = _DEFAULT_SAY_VOICE
        self._language = settings.voice_language
        self._timeout = settings.voice_timeout

    # ------------------------------------------------------------------
    # Public TwiML factories
    # ------------------------------------------------------------------

    def welcome_response(self) -> str:
        """
        Initial call greeting.  Opens the first <Gather> so the caller can speak.
        """
        settings = get_settings()
        greeting = _xml_escape(clean_for_speech(settings.voice_greeting))
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<Response>\n"
            f'  <Gather input="speech" action="{self._gather_url}" method="POST"\n'
            f'          timeout="{self._timeout}" speechTimeout="auto"\n'
            f'          language="{self._language}">\n'
            f'    <Say voice="{self._voice}">{greeting}</Say>\n'
            "  </Gather>\n"
            f'  <Say voice="{self._voice}">I did not catch that. Please call back. Goodbye.</Say>\n'
            "  <Hangup/>\n"
            "</Response>"
        )

    def agent_response(self, agent_text: str) -> str:
        """
        Speak the agent reply, then re-open <Gather> for the next caller turn.
        A second safety <Gather> catches cases where the first one times out.
        """
        speech_text = clean_for_speech(agent_text)
        # Twilio <Say> has a ~4096 char limit; truncate gracefully
        if len(speech_text) > 3900:
            speech_text = speech_text[:3850] + "... Would you like me to continue?"

        safe_text = _xml_escape(speech_text)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<Response>\n"
            f'  <Gather input="speech" action="{self._gather_url}" method="POST"\n'
            f'          timeout="{self._timeout}" speechTimeout="auto"\n'
            f'          language="{self._language}">\n'
            f'    <Say voice="{self._voice}">{safe_text}</Say>\n'
            "  </Gather>\n"
            # Fallback: no speech detected after agent reply
            f'  <Say voice="{self._voice}">Is there anything else I can help you with?</Say>\n'
            f'  <Gather input="speech" action="{self._gather_url}" method="POST"\n'
            f'          timeout="{self._timeout}" speechTimeout="auto"\n'
            f'          language="{self._language}"/>\n'
            f'  <Say voice="{self._voice}">Thank you for calling. Goodbye.</Say>\n'
            "  <Hangup/>\n"
            "</Response>"
        )

    def escalation_response(
        self,
        agent_text: str = "",
        escalation_number: str = "",
    ) -> str:
        """
        Inform the caller of human escalation and optionally dial a transfer number.
        If no escalation number is configured, offer a self-service message.
        """
        speech = clean_for_speech(agent_text) if agent_text else (
            "I am connecting you to a human agent now. Please hold."
        )
        twiml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<Response>\n"
            f'  <Say voice="{self._voice}">{_xml_escape(speech)}</Say>\n'
        )
        if escalation_number:
            twiml += f"  <Dial>{_xml_escape(escalation_number)}</Dial>\n"
        else:
            twiml += (
                f'  <Say voice="{self._voice}">'
                "Unfortunately no agents are available right now. "
                "We will follow up with you shortly. Goodbye."
                "</Say>\n"
                "  <Hangup/>\n"
            )
        twiml += "</Response>"
        return twiml

    def hangup_response(
        self,
        farewell: str = "Thank you for calling ConversalQ. Goodbye.",
    ) -> str:
        """Speak a farewell and hang up cleanly."""
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<Response>\n"
            f'  <Say voice="{self._voice}">{_xml_escape(clean_for_speech(farewell))}</Say>\n'
            "  <Hangup/>\n"
            "</Response>"
        )

    def error_response(self) -> str:
        """Fallback TwiML when an internal error prevents normal processing."""
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<Response>\n"
            f'  <Say voice="{self._voice}">'
            "I am sorry, I encountered a technical issue. "
            "Please try calling back in a few moments."
            "</Say>\n"
            "  <Hangup/>\n"
            "</Response>"
        )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_builder: Optional[TwiMLBuilder] = None


def get_twiml_builder() -> TwiMLBuilder:
    """Return a process-level singleton TwiMLBuilder."""
    global _builder
    if _builder is None:
        _builder = TwiMLBuilder()
    return _builder
