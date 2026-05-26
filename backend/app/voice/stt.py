"""
Speech-to-Text Service — Phase 5.

Wraps Deepgram for pre-recorded audio transcription and live WebSocket streaming.

When to use this service
------------------------
- Twilio Gather flow: Twilio itself handles STT and posts ``SpeechResult`` as
  plain text — this service is NOT needed.
- WebSocket Media Stream flow: Twilio streams mulaw audio in real time to our
  WebSocket endpoint.  This service forwards audio chunks to Deepgram and
  emits transcript events for live monitoring / analytics.
- Recording-based workflows: transcribe a Twilio recording URL after the call.

Graceful degradation
--------------------
If ``DEEPGRAM_API_KEY`` is not set, ``is_available`` returns False and all
transcription methods return empty results without raising.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import List

import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)


@dataclass
class TranscriptionResult:
    """Result from a pre-recorded or streaming transcription."""
    transcript: str
    confidence: float = 1.0
    words: List[dict] = field(default_factory=list)
    duration_seconds: float = 0.0


class STTService:
    """
    Deepgram STT wrapper.

    Supports:
    - ``transcribe_url``   — pre-recorded audio from a publicly accessible URL
    - ``transcribe_bytes`` — raw audio bytes (e.g. decoded Twilio mulaw chunks)
    The live WebSocket path is handled directly in the ``/stream`` endpoint
    using the Deepgram async live client.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.deepgram_api_key
        self._available = bool(self._api_key)
        if not self._available:
            log.warning("stt_service_unavailable", reason="DEEPGRAM_API_KEY not configured")

    @property
    def is_available(self) -> bool:
        return self._available

    async def transcribe_url(
        self,
        audio_url: str,
        language: str = "en-US",
    ) -> TranscriptionResult:
        """
        Transcribe audio from a publicly accessible URL (e.g. Twilio recording).
        """
        if not self._available:
            return TranscriptionResult(transcript="", confidence=0.0)

        try:
            from deepgram import DeepgramClient, PrerecordedOptions
        except ImportError:
            log.error("deepgram_sdk_not_installed", hint="pip install deepgram-sdk")
            return TranscriptionResult(transcript="", confidence=0.0)

        try:
            client = DeepgramClient(api_key=self._api_key)
            options = PrerecordedOptions(
                model="nova-2",
                smart_format=True,
                language=language,
                punctuate=True,
            )
            response = await client.listen.asyncrest.v("1").transcribe_url(
                {"url": audio_url}, options
            )
            alt = response.results.channels[0].alternatives[0]
            return TranscriptionResult(
                transcript=alt.transcript,
                confidence=float(alt.confidence or 1.0),
                words=[w.to_dict() for w in (alt.words or [])],
            )
        except Exception as exc:
            log.error("stt_transcribe_url_failed", error=str(exc))
            return TranscriptionResult(transcript="", confidence=0.0)

    async def transcribe_bytes(
        self,
        audio_bytes: bytes,
        encoding: str = "mulaw",
        sample_rate: int = 8000,
        language: str = "en-US",
    ) -> TranscriptionResult:
        """
        Transcribe raw audio bytes.

        Parameters
        ----------
        audio_bytes:
            Raw audio data (e.g. base64-decoded Twilio media stream chunk).
        encoding:
            Audio encoding — ``"mulaw"`` for Twilio, ``"linear16"`` for PCM.
        sample_rate:
            Samples per second — Twilio streams at 8000 Hz.
        """
        if not self._available:
            return TranscriptionResult(transcript="", confidence=0.0)

        try:
            from deepgram import DeepgramClient, PrerecordedOptions
        except ImportError:
            log.error("deepgram_sdk_not_installed")
            return TranscriptionResult(transcript="", confidence=0.0)

        try:
            client = DeepgramClient(api_key=self._api_key)
            options = PrerecordedOptions(
                model="nova-2",
                smart_format=True,
                language=language,
                encoding=encoding,
                sample_rate=sample_rate,
                channels=1,
            )
            response = await client.listen.asyncrest.v("1").transcribe_file(
                {"buffer": audio_bytes, "mimetype": f"audio/{encoding}"},
                options,
            )
            alt = response.results.channels[0].alternatives[0]
            return TranscriptionResult(
                transcript=alt.transcript,
                confidence=float(alt.confidence or 1.0),
            )
        except Exception as exc:
            log.error("stt_transcribe_bytes_failed", error=str(exc))
            return TranscriptionResult(transcript="", confidence=0.0)


@lru_cache(maxsize=1)
def get_stt_service() -> STTService:
    """Return a process-level singleton STTService."""
    return STTService()
