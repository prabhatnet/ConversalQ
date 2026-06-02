"""
Content Moderation via OpenAI Moderation API — Phase 6 Guardrails.

Screens user input for harmful content before it reaches the agent graph.
Runs asynchronously; never blocks the event loop.

Graceful degradation
--------------------
If the API call fails (network error, invalid key, rate limit), the message
is *allowed through* and a warning is logged. The system stays available even
when the moderation service is degraded.

Configuration
-------------
Enable via ``MODERATION_ENABLED=true`` in .env.
Requires ``OPENAI_API_KEY`` to be set (reuses the same client as the LLM).

Categories checked (OpenAI v2 taxonomy)
----------------------------------------
  hate, hate/threatening, harassment, harassment/threatening,
  self-harm, self-harm/intent, self-harm/instructions,
  sexual, sexual/minors, violence, violence/graphic
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import structlog

log = structlog.get_logger(__name__)


@dataclass
class ModerationResult:
    """Structured result from the OpenAI Moderation API."""
    flagged: bool
    categories: dict[str, bool] = field(default_factory=dict)
    category_scores: dict[str, float] = field(default_factory=dict)
    reason: str | None = None


class ContentModerator:
    """
    Thin async wrapper around ``AsyncOpenAI.moderations.create()``.

    Process-level singleton — see ``get_content_moderator()``.
    """

    def __init__(self) -> None:
        from openai import AsyncOpenAI
        from app.config import get_settings

        settings = get_settings()
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._available = bool(settings.openai_api_key)

    async def check(self, text: str) -> ModerationResult:
        """
        Submit ``text`` to OpenAI's Moderation API.

        Always returns a ``ModerationResult`` — never raises.
        When unavailable or on error, returns ``flagged=False``.
        """
        if not self._available or not text.strip():
            return ModerationResult(flagged=False)

        try:
            response = await self._client.moderations.create(
                model="omni-moderation-latest",
                input=text,
            )
            result = response.results[0]

            cats: dict[str, bool] = result.categories.model_dump()
            scores: dict[str, float] = {
                k: round(v, 4)
                for k, v in result.category_scores.model_dump().items()
            }
            flagged_names = [k for k, v in cats.items() if v]
            reason = f"Flagged: {', '.join(flagged_names)}" if flagged_names else None

            log.debug(
                "moderation_check_complete",
                flagged=result.flagged,
                flagged_categories=flagged_names,
            )
            return ModerationResult(
                flagged=result.flagged,
                categories=cats,
                category_scores=scores,
                reason=reason,
            )

        except Exception as exc:
            log.warning("moderation_check_failed", error=str(exc))
            # Fail open — do not block the user if moderation is unavailable
            return ModerationResult(flagged=False)


@lru_cache(maxsize=1)
def get_content_moderator() -> ContentModerator:
    """Return a process-level singleton ``ContentModerator``."""
    return ContentModerator()
