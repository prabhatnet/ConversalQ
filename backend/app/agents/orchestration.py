"""
Agent Orchestration Service — Phase 3.

High-level interface between the HTTP layer and the LangGraph workflow.

Responsibilities
----------------
- Convert incoming chat history (plain dicts) → LangChain BaseMessages
- Pre-fetch RAG context and inject into initial state
- Invoke the compiled graph
- Extract the final response + metadata from terminal state
- Stream tokens via ``astream_events`` for SSE endpoints
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import AsyncIterator, List, Optional

import structlog
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage

from app.agents.graph import get_compiled_graph
from app.agents.state import AgentState

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Response DTO
# ---------------------------------------------------------------------------
@dataclass
class AgentResponse:
    content: str
    intent: str
    active_agent: str
    confidence: float
    rag_sources: List[str]
    should_escalate: bool
    escalation_reason: Optional[str]
    latency_ms: int


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
class AgentOrchestrationService:
    """
    Runs the LangGraph multi-agent workflow for a single user turn.
    """

    def __init__(self, knowledge_service=None) -> None:
        """
        Parameters
        ----------
        knowledge_service:
            Optional KnowledgeService — used to pre-fetch RAG context before
            the graph runs so all agents share the same retrieved chunks.
        """
        self._knowledge = knowledge_service
        self._graph = get_compiled_graph()

    async def process(
        self,
        user_message: str,
        history: List[dict],
        conversation_summary: Optional[str] = None,
    ) -> AgentResponse:
        """
        Run the agent graph for a single user turn.

        Parameters
        ----------
        user_message:
            The latest user message text.
        history:
            Prior conversation turns as ``[{"role": "user"|"assistant", "content": "..."}]``.
            Does NOT include the current user message.
        conversation_summary:
            Optional LLM-generated summary of turns older than the active window.
            Injected into router + specialist system prompts for long-running sessions.
        """
        start = time.perf_counter()

        # Build LangChain message list from history + current message
        lc_messages = _history_to_lc_messages(history)
        lc_messages.append(HumanMessage(content=user_message))

        # Pre-fetch RAG context
        rag_context: Optional[str] = None
        rag_sources: List[str] = []
        if self._knowledge:
            try:
                retrieval = await self._knowledge.retrieve_context(user_message)
                if retrieval.has_context:
                    rag_context = retrieval.formatted_context
                    rag_sources = retrieval.sources
            except Exception as exc:
                log.warning("rag_prefetch_failed", error=str(exc))

        # Initialise state
        initial_state: AgentState = {
            "messages": lc_messages,
            "intent": None,
            "confidence": 0.0,
            "active_agent": None,
            "rag_context": rag_context,
            "rag_sources": rag_sources,
            "response": None,
            "should_escalate": False,
            "escalation_reason": None,
            "handoff_count": 0,
            "conversation_summary": conversation_summary,
        }

        # Run graph
        final_state: AgentState = await self._graph.ainvoke(initial_state)

        latency_ms = int((time.perf_counter() - start) * 1000)

        response_text = final_state.get("response") or _extract_last_ai_message(
            final_state["messages"]
        )

        log.info(
            "agent_turn_complete",
            intent=final_state.get("intent"),
            agent=final_state.get("active_agent"),
            latency_ms=latency_ms,
        )

        return AgentResponse(
            content=response_text,
            intent=final_state.get("intent") or "general",
            active_agent=final_state.get("active_agent") or "general_agent",
            confidence=final_state.get("confidence", 0.0),
            rag_sources=final_state.get("rag_sources", []),
            should_escalate=final_state.get("should_escalate", False),
            escalation_reason=final_state.get("escalation_reason"),
            latency_ms=latency_ms,
        )

    async def process_stream(
        self,
        user_message: str,
        history: List[dict],
        conversation_summary: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """
        Stream response tokens using LangGraph ``astream_events``.

        Yields raw token strings. The caller is responsible for SSE formatting.
        """
        lc_messages = _history_to_lc_messages(history)
        lc_messages.append(HumanMessage(content=user_message))

        rag_context: Optional[str] = None
        rag_sources: List[str] = []
        if self._knowledge:
            try:
                retrieval = await self._knowledge.retrieve_context(user_message)
                if retrieval.has_context:
                    rag_context = retrieval.formatted_context
                    rag_sources = retrieval.sources
            except Exception:
                pass

        initial_state: AgentState = {
            "messages": lc_messages,
            "intent": None,
            "confidence": 0.0,
            "active_agent": None,
            "rag_context": rag_context,
            "rag_sources": rag_sources,
            "response": None,
            "should_escalate": False,
            "escalation_reason": None,
            "handoff_count": 0,
            "conversation_summary": conversation_summary,
        }

        # Stream events — yield tokens from on_llm_new_token events
        # produced by specialist agents (router uses temperature=0, no streaming)
        async for event in self._graph.astream_events(initial_state, version="v2"):
            kind = event.get("event")
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield chunk.content


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _history_to_lc_messages(history: List[dict]) -> List[BaseMessage]:
    """Convert plain dict history to LangChain message objects."""
    messages: List[BaseMessage] = []
    for turn in history:
        role = turn.get("role", "user")
        content = turn.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        else:
            messages.append(AIMessage(content=content))
    return messages


def _extract_last_ai_message(messages: List[BaseMessage]) -> str:
    """Fallback: return the last AIMessage content from the message list."""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            return str(msg.content)
    return ""
