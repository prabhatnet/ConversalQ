"""
Quality Scoring Agent — Phase Week 2.

Uses OpenAI function calling (structured outputs via tool_choice="required")
to evaluate a completed conversation against a four-dimension QA rubric:

  Empathy | Tone | Resolution | Professionalism

The agent receives a formatted conversation transcript and returns a
QARubricOutput Pydantic model, scored 0.0–1.0 per dimension with reasoning.

Architecture Decision:
- Pure function — no LangGraph state needed; scoring is a one-shot evaluation
- Uses openai.AsyncOpenAI directly (not LangChain) to leverage pydantic tool
  schema generation cleanly via model_json_schema()
- Gracefully returns a neutral 0.5 score on any LLM/parse failure so the
  rest of the request pipeline is never blocked by scoring errors
"""

from __future__ import annotations

import json
import time
from typing import Any

import structlog
from openai import AsyncOpenAI

from app.config import get_settings
from app.schemas.qa import DimensionScore, QARubricOutput

log = structlog.get_logger(__name__)

_SYSTEM_PROMPT = """\
You are a Quality Assurance evaluator for an AI call center assistant.

Your task is to assess a conversation between a customer and an AI agent using a
structured rubric. Be objective, evidence-based, and specific in your reasoning.

Scoring guide:
  0.0 – 0.3 : Poor — significant failures on this dimension
  0.4 – 0.6 : Adequate — partially met, noticeable gaps
  0.7 – 0.85: Good — mostly met with minor shortcomings
  0.86 – 1.0: Excellent — fully met, exemplary performance

Always call the `score_conversation` tool with your evaluation.
"""

_TOOL_NAME = "score_conversation"


def _build_tool_schema() -> dict[str, Any]:
    """Generate the OpenAI function tool schema from the QARubricOutput Pydantic model."""
    return {
        "type": "function",
        "function": {
            "name": _TOOL_NAME,
            "description": "Score the conversation quality across four QA dimensions.",
            "parameters": QARubricOutput.model_json_schema(),
        },
    }


def _format_transcript(messages: list[dict[str, str]]) -> str:
    """Format message history into a readable transcript string."""
    lines: list[str] = []
    for msg in messages:
        role = msg.get("role", "unknown").upper()
        content = msg.get("content", "").strip()
        if content:
            lines.append(f"[{role}]: {content}")
    return "\n".join(lines) if lines else "(empty conversation)"


class QualityScoringAgent:
    """One-shot QA evaluation agent using OpenAI function calling."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model
        self._tool_schema = _build_tool_schema()

    async def score(
        self,
        messages: list[dict[str, str]],
        notes: str | None = None,
    ) -> QARubricOutput:
        """
        Score a conversation.

        Parameters
        ----------
        messages:
            List of {"role": "user"|"assistant", "content": "..."} dicts.
        notes:
            Optional analyst notes injected into the user prompt.

        Returns
        -------
        QARubricOutput with scores and reasoning for all four dimensions.
        Falls back to neutral 0.5 scores on any error.
        """
        start = time.perf_counter()

        transcript = _format_transcript(messages)
        user_content = f"Please evaluate the following conversation:\n\n{transcript}"
        if notes:
            user_content += f"\n\nAdditional context from analyst:\n{notes}"

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                temperature=0.2,          # low temperature → more consistent scoring
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user",   "content": user_content},
                ],
                tools=[self._tool_schema],
                tool_choice={"type": "function", "function": {"name": _TOOL_NAME}},
            )

            tool_call = response.choices[0].message.tool_calls[0]
            raw = json.loads(tool_call.function.arguments)
            result = QARubricOutput.model_validate(raw)

            elapsed = round((time.perf_counter() - start) * 1000)
            log.info(
                "qa_scoring_complete",
                model=self._model,
                latency_ms=elapsed,
                overall=round(
                    (result.empathy.score + result.tone.score +
                     result.resolution.score + result.professionalism.score) / 4,
                    2,
                ),
            )
            return result

        except Exception as exc:  # noqa: BLE001
            log.warning("qa_scoring_failed", error=str(exc))
            return _neutral_rubric(reason=f"Scoring unavailable: {exc}")


def _neutral_rubric(reason: str = "Scoring unavailable.") -> QARubricOutput:
    """Return a neutral 0.5 rubric when scoring fails."""
    neutral = DimensionScore(score=0.5, reasoning=reason)
    return QARubricOutput(
        empathy=neutral,
        tone=neutral,
        resolution=neutral,
        professionalism=neutral,
        overall_summary=reason,
    )
