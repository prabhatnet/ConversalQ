"""
Text-to-Speech Service — Phase 5.

Wraps OpenAI TTS API to synthesize speech from text.
Used as an opt-in upgrade over Twilio's built-in <Say> TTS.

Default flow (tts_enabled=False): agent text returned as TwiML <Say> — free,
  zero latency, no extra API calls.
Premium flow (tts_enabled=True): this service generates an mp3, the URL is
  served via a /audio endpoint, and TwiML uses <Play> for natural-sounding voice.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal, Optional

import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

# Supported OpenAI TTS voices
TTS_VOICES = Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
TTS_FORMATS = Literal["mp3", "opus", "aac", "flac", "pcm", "wav"]


class TTSService:
    """
    OpenAI TTS wrapper.

    Synthesizes speech and returns raw audio bytes.  The caller decides
    how to deliver the audio (serve via HTTP, pipe to Twilio, etc.).
    """

    def __init__(self) -> None:
        from openai import AsyncOpenAI
        settings = get_settings()
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.tts_model
        self._default_voice = settings.tts_voice

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        response_format: TTS_FORMATS = "mp3",
    ) -> bytes:
        """
        Generate audio bytes from text.

        Parameters
        ----------
        text:
            Plain text to synthesize (markdown stripped by the caller).
        voice:
            Override the configured default voice.
        response_format:
            Output audio format.  ``"mp3"`` for Twilio <Play>,
            ``"pcm"`` / ``"wav"`` for raw audio pipelines.

        Returns
        -------
        bytes
            Raw audio bytes in the requested format.
        """
        used_voice = voice or self._default_voice
        log.debug("tts_synthesizing", chars=len(text), voice=used_voice, model=self._model)

        response = await self._client.audio.speech.create(
            model=self._model,
            voice=used_voice,       # type: ignore[arg-type]
            input=text,
            response_format=response_format,   # type: ignore[arg-type]
        )

        audio_bytes = response.content
        log.debug("tts_complete", bytes_produced=len(audio_bytes))
        return audio_bytes


@lru_cache(maxsize=1)
def get_tts_service() -> TTSService:
    """Return a process-level singleton TTSService."""
    return TTSService()
