"""
Agent State Schema — Phase 3.

Defines the shared state passed between all nodes in the LangGraph workflow.
Every agent reads from and writes to this state.

Intent taxonomy
---------------
billing     — Payment, invoices, charges, refunds, pricing
technical   — Product bugs, errors, setup, configuration, connectivity
account     — Login, password, profile, subscription management
general     — FAQ, policies, general information
escalation  — Explicit escalation request or low-confidence routing
"""

from __future__ import annotations

from typing import Annotated, List, Optional
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


# Valid intent labels (used as routing keys in the graph)
INTENTS = ["billing", "technical", "account", "general", "escalation"]
Intent = str  # one of INTENTS


class AgentState(TypedDict):
    """
    Shared state for the ConversalQ multi-agent graph.

    Fields
    ------
    messages:
        Full conversation history as LangChain BaseMessage objects.
        The ``add_messages`` reducer appends new messages rather than
        replacing the list, so each node just returns the delta.
    intent:
        Classified intent from the router node.
    confidence:
        Router confidence in [0, 1].
    active_agent:
        Name of the specialist agent currently handling the request.
    rag_context:
        Pre-fetched knowledge-base context (formatted citation block).
    rag_sources:
        List of source document names from RAG retrieval.
    response:
        Final assistant response text (populated by a specialist agent).
    should_escalate:
        True if the conversation should be handed off to a human agent.
    escalation_reason:
        Human-readable reason for escalation (set by any agent node).
    handoff_count:
        Number of agent-to-agent handoffs so far (circuit-breaker guard).
    """

    messages: Annotated[List[BaseMessage], add_messages]
    intent: Optional[Intent]
    confidence: float
    active_agent: Optional[str]
    rag_context: Optional[str]
    rag_sources: List[str]
    response: Optional[str]
    should_escalate: bool
    escalation_reason: Optional[str]
    handoff_count: int
    conversation_summary: Optional[str]  # Phase 4 — LLM-generated summary of prior turns
