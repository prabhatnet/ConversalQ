"""
Specialist Agent Base + all domain agents — Phase 3.

All specialist agents share the same execution pattern:
1. Build a focused system prompt (persona + domain expertise)
2. Inject RAG context if available
3. Call the LLM with full message history
4. Return the response + agent metadata

Agents
------
BillingAgent     — billing_agent node
TechnicalAgent   — technical_agent node
AccountAgent     — account_agent node
GeneralAgent     — general_agent node
EscalationAgent  — escalation_agent node (may flag for human handoff)
"""

from __future__ import annotations

import time
import structlog

from langchain_core.messages import SystemMessage, AIMessage
from langchain_openai import ChatOpenAI

from app.agents.state import AgentState
from app.config import get_settings

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Shared base prompt header injected into every specialist
# ---------------------------------------------------------------------------
_BASE_CONTEXT = """You are ConversalQ, an enterprise AI call center assistant.
Always be professional, empathetic, and concise (under 250 words unless detail is required).
Never fabricate information. If unsure, say so and offer to escalate.
End every response with a clear next step or offer for further assistance."""

# ---------------------------------------------------------------------------
# Domain-specific system prompts
# ---------------------------------------------------------------------------
_BILLING_PROMPT = f"""{_BASE_CONTEXT}

SPECIALIST ROLE: Billing & Payments Expert
Your expertise covers:
- Explaining charges, invoices, and billing cycles
- Processing refund requests and eligibility assessment
- Subscription upgrades, downgrades, and cancellations
- Payment method updates and failed payment resolution
- Promotional credits and discount application

If a refund or account credit is requested, acknowledge the request, explain the policy,
and confirm next steps. Never promise refunds without verifying eligibility first."""

_TECHNICAL_PROMPT = f"""{_BASE_CONTEXT}

SPECIALIST ROLE: Technical Support Engineer
Your expertise covers:
- Diagnosing product errors, bugs, and unexpected behaviour
- Step-by-step setup, installation, and configuration guidance
- Connectivity, integration, and API troubleshooting
- Performance issues and workarounds
- Known issues and their status/timeline

Always ask for relevant context (error messages, OS, version) if not provided.
Provide numbered steps for complex resolutions."""

_ACCOUNT_PROMPT = f"""{_BASE_CONTEXT}

SPECIALIST ROLE: Account Management Specialist
Your expertise covers:
- Account login issues and password resets
- Profile, contact information, and preference updates
- Subscription plan management and seat/licence changes
- Access permissions and team management
- Account security concerns (suspicious activity, MFA)

For security-sensitive requests, always verify identity steps before proceeding.
Never share or confirm sensitive account details in chat."""

_GENERAL_PROMPT = f"""{_BASE_CONTEXT}

SPECIALIST ROLE: Customer Service Representative
You handle general enquiries including:
- Product features, capabilities, and limitations
- Company policies (returns, privacy, SLAs)
- Business hours, contact information, and support channels
- Onboarding guidance and getting-started help
- Routing to the right team for specialised needs

Keep responses friendly and informative."""

_ESCALATION_PROMPT = f"""{_BASE_CONTEXT}

SPECIALIST ROLE: Escalation Coordinator
You handle situations where:
- The customer explicitly requested a human agent
- Previous agents could not resolve the issue
- The query is sensitive, legal, or out of policy scope
- High frustration or urgency is detected

Your response must:
1. Acknowledge the escalation warmly
2. Confirm a human agent will be in touch (within stated SLA if known)
3. Offer a case/ticket reference (use the conversation ID if available)
4. Provide any immediate self-service alternatives if appropriate

Do NOT attempt to resolve the underlying issue — focus on the handoff."""


# ---------------------------------------------------------------------------
# Base specialist node factory
# ---------------------------------------------------------------------------
def _make_specialist_node(agent_name: str, system_prompt: str):
    """
    Returns an async LangGraph node function for a specialist agent.
    """

    async def node(state: AgentState) -> dict:
        settings = get_settings()
        llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=settings.openai_temperature,
            max_tokens=settings.openai_max_tokens,
            api_key=settings.openai_api_key,
        )

        # Build system prompt — append RAG context if available
        full_system = system_prompt
        rag_context = state.get("rag_context")
        if rag_context:
            full_system += (
                "\n\n--- Relevant Knowledge Base Context ---\n"
                + rag_context
                + "\n--- End of Context ---\n"
                "Use the above context to inform your response. "
                "Cite the source document when referencing it."
            )

        # Build message list: system + conversation history
        lc_messages = [SystemMessage(content=full_system)] + list(state["messages"])

        start = time.perf_counter()
        try:
            response = await llm.ainvoke(lc_messages)
            latency_ms = int((time.perf_counter() - start) * 1000)
            content = response.content or ""

            log.info(
                "specialist_response",
                agent=agent_name,
                latency_ms=latency_ms,
                tokens=getattr(response, "usage_metadata", {}).get("total_tokens"),
            )

            # Escalation agent flags the conversation for human handoff
            should_escalate = agent_name == "escalation_agent"

            return {
                "messages": [AIMessage(content=content, name=agent_name)],
                "response": content,
                "active_agent": agent_name,
                "should_escalate": should_escalate,
                "handoff_count": state.get("handoff_count", 0) + 1,
            }

        except Exception as exc:
            log.exception("specialist_error", agent=agent_name, error=str(exc))
            fallback = "I'm sorry, I encountered an issue processing your request. Please try again or ask to speak with a human agent."
            return {
                "messages": [AIMessage(content=fallback, name=agent_name)],
                "response": fallback,
                "active_agent": agent_name,
                "should_escalate": False,
                "handoff_count": state.get("handoff_count", 0) + 1,
            }

    node.__name__ = agent_name
    return node


# ---------------------------------------------------------------------------
# Exported node functions (referenced by name in graph.py)
# ---------------------------------------------------------------------------
billing_agent_node   = _make_specialist_node("billing_agent",   _BILLING_PROMPT)
technical_agent_node = _make_specialist_node("technical_agent", _TECHNICAL_PROMPT)
account_agent_node   = _make_specialist_node("account_agent",   _ACCOUNT_PROMPT)
general_agent_node   = _make_specialist_node("general_agent",   _GENERAL_PROMPT)
escalation_agent_node = _make_specialist_node("escalation_agent", _ESCALATION_PROMPT)
