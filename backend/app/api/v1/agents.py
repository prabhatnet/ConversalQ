"""
Agents API Endpoints — Phase 3.

Provides introspection into the multi-agent system.

Endpoints
---------
GET  /api/v1/agents          — list available agents and their descriptions
GET  /api/v1/agents/graph    — graph topology (nodes + edges) for visualisation
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/agents", tags=["Agents"])

# Static agent registry — source of truth for descriptions shown in the UI
_AGENT_REGISTRY = [
    {
        "name": "router",
        "role": "Intent Classifier",
        "description": "Classifies the user message into a domain intent and routes to the appropriate specialist.",
        "intents_handled": ["billing", "technical", "account", "general", "escalation"],
    },
    {
        "name": "billing_agent",
        "role": "Billing & Payments Expert",
        "description": "Handles payment queries, invoice questions, refund requests, and subscription billing issues.",
        "intents_handled": ["billing"],
    },
    {
        "name": "technical_agent",
        "role": "Technical Support Engineer",
        "description": "Resolves product errors, configuration issues, connectivity problems, and technical how-tos.",
        "intents_handled": ["technical"],
    },
    {
        "name": "account_agent",
        "role": "Account Management Specialist",
        "description": "Manages login issues, password resets, profile updates, and subscription plan changes.",
        "intents_handled": ["account"],
    },
    {
        "name": "general_agent",
        "role": "Customer Service Representative",
        "description": "Answers FAQs, explains policies, provides product information, and handles general enquiries.",
        "intents_handled": ["general"],
    },
    {
        "name": "escalation_agent",
        "role": "Escalation Coordinator",
        "description": "Handles requests for human handoff, sensitive issues, and cases outside automated scope.",
        "intents_handled": ["escalation"],
    },
]

_GRAPH_TOPOLOGY = {
    "nodes": [a["name"] for a in _AGENT_REGISTRY],
    "edges": [
        {"from": "router", "to": "billing_agent",    "condition": "intent == billing"},
        {"from": "router", "to": "technical_agent",  "condition": "intent == technical"},
        {"from": "router", "to": "account_agent",    "condition": "intent == account"},
        {"from": "router", "to": "general_agent",    "condition": "intent == general"},
        {"from": "router", "to": "escalation_agent", "condition": "intent == escalation OR confidence < 0.45 OR handoff_count >= 2"},
        {"from": "billing_agent",    "to": "END", "condition": "always"},
        {"from": "technical_agent",  "to": "END", "condition": "always"},
        {"from": "account_agent",    "to": "END", "condition": "always"},
        {"from": "general_agent",    "to": "END", "condition": "always"},
        {"from": "escalation_agent", "to": "END", "condition": "always"},
    ],
    "entry_point": "router",
}


@router.get(
    "",
    summary="List all available agents",
    description="Returns the registry of agents in the multi-agent system with their roles and capabilities.",
)
async def list_agents() -> list:
    return _AGENT_REGISTRY


@router.get(
    "/graph",
    summary="Agent graph topology",
    description="Returns the nodes and edges of the LangGraph workflow for visualisation.",
)
async def get_graph_topology() -> dict:
    return _GRAPH_TOPOLOGY
