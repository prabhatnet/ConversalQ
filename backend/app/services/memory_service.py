"""
Conversation Memory Service — Phase 4.

Manages sliding-window context and LLM-powered summarization for long-running
conversations.  Keeps the last N messages verbatim ("active window") and
compresses everything older into a rolling summary stored on the conversation.

Flow
----
1. On each turn, load all messages for the conversation.
2. If total messages ≤ SUMMARIZE_THRESHOLD  → return all messages as recent context.
3. If total messages  > SUMMARIZE_THRESHOLD:
   a. recent_messages = last WINDOW_SIZE messages
   b. old_messages    = everything before the window
   c. If the old window has grown by at least SUMMARIZE_STEP since the last
      summarization (tracked via conversation.metadata_["summarized_through"]):
      → generate / update the summary and persist it.
   d. Return the (possibly existing) summary + recent_messages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import get_settings

if TYPE_CHECKING:
    from app.repositories.in_memory import (
        InMemoryConversationRepository,
        InMemoryMessageRepository,
        InMemoryMessage,
    )

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# DTO
# ---------------------------------------------------------------------------
@dataclass
class MemoryContext:
    """Context package returned to ChatService and passed to the agent graph."""

    summary: Optional[str]          # LLM-generated summary of old turns (or None)
    recent_messages: List[dict]     # last N messages as [{"role": ..., "content": ...}]
    total_turns: int                # total message count (user + assistant)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
class ConversationMemoryService:
    """
    Sliding-window memory with LLM summarization.

    Configuration is read from :class:`~app.config.Settings` so it can be
    tuned via environment variables without code changes.
    """

    _SUMMARIZE_SYSTEM_PROMPT = (
        "You are a concise conversation summarizer for a customer support system. "
        "Create a brief, factual summary covering: customer's issue, what was discussed, "
        "any resolutions attempted, and current status. "
        "Be precise and under 200 words. Use bullet points."
    )

    def __init__(self) -> None:
        settings = get_settings()
        self._window_size: int = settings.memory_window_size
        self._threshold: int = settings.memory_summarize_threshold
        self._step: int = settings.memory_summarize_step
        self._llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=0.0,
            api_key=settings.openai_api_key,
        )

    async def get_context(
        self,
        conversation_id,
        message_repo,
        conversation_repo,
    ) -> MemoryContext:
        """
        Return a :class:`MemoryContext` for the given conversation.

        Automatically triggers re-summarization when the "old window" has grown
        by at least ``SUMMARIZE_STEP`` messages since the last summary.
        """
        all_msgs = await message_repo.get_by_conversation(conversation_id, limit=500)
        total = len(all_msgs)

        if total <= self._threshold:
            # Short conversation — pass everything verbatim
            return MemoryContext(
                summary=None,
                recent_messages=_msgs_to_dicts(all_msgs),
                total_turns=total,
            )

        # Split into old (to summarize) and recent (to pass verbatim)
        recent_msgs = all_msgs[-self._window_size :]
        old_msgs = all_msgs[: -self._window_size]
        old_count = len(old_msgs)

        # Load current summary + last summarized count from conversation metadata
        conv = await conversation_repo.get_by_id(conversation_id)
        existing_summary: Optional[str] = None
        last_summarized_through: int = 0

        if conv:
            existing_summary = conv.summary
            last_summarized_through = int(
                (conv.metadata_ or {}).get("summarized_through", 0)
            )

        # Re-summarize if we haven't yet or the old window has grown enough
        needs_update = (
            existing_summary is None
            or (old_count - last_summarized_through) >= self._step
        )

        if needs_update:
            log.info(
                "memory_generating_summary",
                conversation_id=str(conversation_id),
                old_count=old_count,
                last_summarized_through=last_summarized_through,
            )
            existing_summary = await self._generate_summary(old_msgs, existing_summary)
            await conversation_repo.update_summary(
                conversation_id=conversation_id,
                summary=existing_summary,
                summarized_through=old_count,
            )

        return MemoryContext(
            summary=existing_summary,
            recent_messages=_msgs_to_dicts(recent_msgs),
            total_turns=total,
        )

    async def _generate_summary(
        self,
        messages: list,
        previous_summary: Optional[str],
    ) -> str:
        """Invoke the LLM to create/update the rolling summary."""
        turns_text = "\n".join(
            f"{m.role.upper()}: {m.content}" for m in messages
        )

        if previous_summary:
            user_prompt = (
                f"Previous summary:\n{previous_summary}\n\n"
                f"New conversation turns to incorporate:\n{turns_text}\n\n"
                "Update the summary to include the new information, keeping it under 200 words."
            )
        else:
            user_prompt = (
                f"Summarize this customer support conversation:\n{turns_text}"
            )

        try:
            response = await self._llm.ainvoke(
                [
                    SystemMessage(content=self._SUMMARIZE_SYSTEM_PROMPT),
                    HumanMessage(content=user_prompt),
                ]
            )
            return response.content.strip()
        except Exception as exc:
            log.warning("memory_summarization_failed", error=str(exc))
            # Fallback: keep previous summary rather than losing it
            return previous_summary or ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _msgs_to_dicts(messages: list) -> List[dict]:
    return [{"role": m.role, "content": m.content} for m in messages]
