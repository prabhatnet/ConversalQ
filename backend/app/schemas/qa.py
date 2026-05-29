"""
QA Scoring Pydantic schemas — request/response contracts.

The rubric evaluates four dimensions on a 0.0–1.0 scale:
  - empathy:         Did the agent acknowledge and validate the customer's feelings?
  - tone:            Was the agent professional, courteous, and calm throughout?
  - resolution:      Was the customer's issue fully resolved or appropriately escalated?
  - professionalism: Did the agent follow correct procedures and communicate clearly?

Each dimension also carries a brief `reasoning` string explaining the score.
"""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DimensionScore(BaseModel):
    """Score + justification for a single rubric dimension."""

    score: float = Field(
        ge=0.0,
        le=1.0,
        description="Score between 0.0 (poor) and 1.0 (excellent).",
    )
    reasoning: str = Field(
        description="One-sentence justification for the score.",
    )


class QARubricOutput(BaseModel):
    """
    Structured output produced by the Quality Scoring Agent via function calling.
    This model is used as the OpenAI tool schema.
    """

    empathy: DimensionScore = Field(
        description="Measures how well the agent acknowledged and validated customer feelings."
    )
    tone: DimensionScore = Field(
        description="Measures professionalism, courtesy, and calmness of the agent's language."
    )
    resolution: DimensionScore = Field(
        description="Measures whether the customer's issue was fully resolved or appropriately escalated."
    )
    professionalism: DimensionScore = Field(
        description="Measures adherence to correct procedures, accurate information, and clear communication."
    )
    overall_summary: str = Field(
        description="Two-to-three sentence overall assessment of the interaction quality."
    )


class QAScoreResponse(BaseModel):
    """API response for a QA scoring request."""

    conversation_id: UUID
    overall_score: float = Field(
        description="Mean of all four dimension scores, rounded to 2 decimal places."
    )
    empathy: DimensionScore
    tone: DimensionScore
    resolution: DimensionScore
    professionalism: DimensionScore
    overall_summary: str
    model: str = Field(description="LLM model used for scoring.")
    latency_ms: int


class QAScoreRequest(BaseModel):
    """Optional request body — reserved for future per-request rubric overrides."""

    notes: Optional[str] = Field(
        default=None,
        description="Optional context or notes to pass to the scoring agent.",
    )
