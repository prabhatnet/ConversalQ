"""
Router Agent — Intent Classification Node.

The first node in every graph execution. Uses the LLM to classify the user's
latest message into one of the defined intents, then sets ``state.intent`` and
``state.confidence`` so the graph can route to the correct specialist.

Routing logic
-------------
billing     → BillingAgent
technical   → TechnicalAgent
account     → AccountAgent
general     → GeneralAgent
escalation  → EscalationAgent  (also triggered when confidence < threshold)
"""

from __future__ import annotations

import json
import re
import structlog

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from app.agents.state import AgentState, INTENTS
from app.config import get_settings

log = structlog.get_logger(__name__)

# Confidence threshold — route to escalation if below this
_MIN_CONFIDENCE: float = 0.45

_ROUTER_SYSTEM_PROMPT = """You are a call center routing assistant. Classify the user's message into EXACTLY ONE of these intents:

- billing    : payments, invoices, charges, refunds, pricing, subscription costs
- technical  : product errors, bugs, setup, configuration, connectivity, how-to
- account    : login, password reset, profile updates, subscription management, access issues
- general    : FAQs, company policies, product information, hours, general questions
- escalation : user explicitly requests a human agent, expresses extreme frustration, threatens legal action, or the query doesn't fit any category

Respond with ONLY a JSON object, no other text:
{"intent": "<intent>", "confidence": <0.0-1.0>, "reason": "<one sentence>"}"""


async def router_node(state: AgentState) -> dict:
    """
    LangGraph node: classify intent and set routing fields.

    Returns a partial state update dict.
    """
    settings = get_settings()
    llm = ChatOpenAI(
        model=settings.openai_model,
        temperature=0.0,  # deterministic for routing
        api_key=settings.openai_api_key,
    )

    # Extract the latest human message for classification
    latest_text = _get_latest_human_text(state["messages"])

    messages = [
        SystemMessage(content=_ROUTER_SYSTEM_PROMPT),
        HumanMessage(content=latest_text),
    ]

    try:
        response = await llm.ainvoke(messages)
        raw = response.content.strip()

        # Parse JSON — handle markdown fences if model adds them
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not json_match:
            raise ValueError(f"No JSON found in router response: {raw!r}")

        parsed = json.loads(json_match.group())
        intent: str = parsed.get("intent", "general").lower()
        confidence: float = float(parsed.get("confidence", 0.5))
        reason: str = parsed.get("reason", "")

        # Validate intent
        if intent not in INTENTS:
            intent = "general"
            confidence = 0.5

        # Low-confidence → escalation
        if confidence < _MIN_CONFIDENCE:
            log.info(
                "router_low_confidence_escalating",
                intent=intent,
                confidence=confidence,
            )
            intent = "escalation"

        log.info(
            "router_classified",
            intent=intent,
            confidence=confidence,
            reason=reason,
        )

        return {
            "intent": intent,
            "confidence": confidence,
            "active_agent": "router",
        }

    except Exception as exc:
        log.exception("router_error", error=str(exc))
        return {
            "intent": "general",
            "confidence": 0.5,
            "active_agent": "router",
        }


def route_after_router(state: AgentState) -> str:
    """
    Conditional edge function — maps intent to the next node name.
    Called by LangGraph after ``router_node`` completes.
    """
    intent = state.get("intent", "general")
    should_escalate = state.get("should_escalate", False)
    handoff_count = state.get("handoff_count", 0)

    # Circuit breaker: too many handoffs → escalate
    if should_escalate or handoff_count >= 2:
        return "escalation_agent"

    mapping = {
        "billing": "billing_agent",
        "technical": "technical_agent",
        "account": "account_agent",
        "general": "general_agent",
        "escalation": "escalation_agent",
    }
    return mapping.get(intent, "general_agent")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_latest_human_text(messages: list) -> str:
    """Return the text of the most recent HumanMessage."""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return str(msg.content)
    # Fallback — use last message content
    if messages:
        return str(messages[-1].content)
    return ""
