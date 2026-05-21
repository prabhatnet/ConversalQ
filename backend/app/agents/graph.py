"""
LangGraph Workflow — ConversalQ Multi-Agent Graph.

Graph topology
--------------

  START
    │
    ▼
  router_node  ──── (conditional) ────┐
                                      │
            ┌─────────────────────────┤
            │                         │
            ▼                         ▼
     billing_agent             escalation_agent
     technical_agent                  │
     account_agent                    │
     general_agent                    │
            │                         │
            └──────────┬──────────────┘
                       ▼
                      END

The graph is compiled once at module level and reused across requests.
``astream`` is used for streaming token support (Phase 3+).
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import StateGraph, END

from app.agents.state import AgentState
from app.agents.router import router_node, route_after_router
from app.agents.specialists import (
    billing_agent_node,
    technical_agent_node,
    account_agent_node,
    general_agent_node,
    escalation_agent_node,
)


def build_graph() -> StateGraph:
    """Construct and compile the ConversalQ agent graph."""
    graph = StateGraph(AgentState)

    # --- Nodes ---
    graph.add_node("router", router_node)
    graph.add_node("billing_agent",    billing_agent_node)
    graph.add_node("technical_agent",  technical_agent_node)
    graph.add_node("account_agent",    account_agent_node)
    graph.add_node("general_agent",    general_agent_node)
    graph.add_node("escalation_agent", escalation_agent_node)

    # --- Entry point ---
    graph.set_entry_point("router")

    # --- Conditional routing after router ---
    graph.add_conditional_edges(
        "router",
        route_after_router,
        {
            "billing_agent":    "billing_agent",
            "technical_agent":  "technical_agent",
            "account_agent":    "account_agent",
            "general_agent":    "general_agent",
            "escalation_agent": "escalation_agent",
        },
    )

    # --- All specialist agents lead to END ---
    for agent in ("billing_agent", "technical_agent", "account_agent",
                  "general_agent", "escalation_agent"):
        graph.add_edge(agent, END)

    return graph.compile()


@lru_cache(maxsize=1)
def get_compiled_graph():
    """Return the cached compiled graph (built once per process)."""
    return build_graph()
