"""
QA Service — orchestrates quality scoring for a completed conversation.

Retrieves the conversation message history from the repository and passes
it to the QualityScoringAgent for evaluation.
"""

from __future__ import annotations

import time
from uuid import UUID

import structlog

from app.agents.qa_scorer import QualityScoringAgent
from app.core.exceptions import ConversationNotFoundError
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.message_repo import MessageRepository
from app.schemas.qa import QAScoreResponse

log = structlog.get_logger(__name__)

# Process-level singleton — the agent holds the OpenAI client
_scorer = QualityScoringAgent()


class QAService:
    """Orchestrates QA scoring for a conversation."""

    def __init__(
        self,
        conversation_repo: ConversationRepository,
        message_repo: MessageRepository,
    ) -> None:
        self._conversations = conversation_repo
        self._messages = message_repo

    async def score_conversation(
        self,
        conversation_id: UUID,
        notes: str | None = None,
    ) -> QAScoreResponse:
        """
        Score a conversation using the QA rubric.

        1. Verify the conversation exists
        2. Fetch message history
        3. Run the QualityScoringAgent (function calling)
        4. Compute overall score and return structured response
        """
        start = time.perf_counter()

        # 1 — Verify conversation exists
        conversation = await self._conversations.get_by_id(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(str(conversation_id))

        # 2 — Fetch message history
        messages = await self._messages.get_by_conversation(conversation_id)
        if not messages:
            raise ValueError(f"Conversation {conversation_id} has no messages to score.")

        message_dicts = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        # 3 — Score
        rubric = await _scorer.score(messages=message_dicts, notes=notes)

        # 4 — Compute overall
        overall = round(
            (rubric.empathy.score + rubric.tone.score +
             rubric.resolution.score + rubric.professionalism.score) / 4,
            2,
        )

        latency_ms = round((time.perf_counter() - start) * 1000)

        log.info(
            "qa_score_complete",
            conversation_id=str(conversation_id),
            overall_score=overall,
            latency_ms=latency_ms,
        )

        return QAScoreResponse(
            conversation_id=conversation_id,
            overall_score=overall,
            empathy=rubric.empathy,
            tone=rubric.tone,
            resolution=rubric.resolution,
            professionalism=rubric.professionalism,
            overall_summary=rubric.overall_summary,
            model=_scorer._model,
            latency_ms=latency_ms,
        )
