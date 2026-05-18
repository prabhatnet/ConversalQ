"""
Knowledge Base Pydantic Schemas.

Request/response contracts for the /api/v1/knowledge endpoints.
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------
class IngestResponse(BaseModel):
    """Response from POST /knowledge/ingest."""

    source_document: str
    chunks_stored: int
    total_tokens: int
    success: bool
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
class KnowledgeSearchRequest(BaseModel):
    """Request body for POST /knowledge/search."""

    query: str = Field(..., min_length=1, max_length=2000, description="Natural language search query")
    top_k: int = Field(default=5, ge=1, le=20, description="Maximum number of results to return")


class ChunkResult(BaseModel):
    """A single retrieved chunk in search results."""

    text: str
    source_document: str
    chunk_index: int
    relevance_score: float


class KnowledgeSearchResponse(BaseModel):
    """Response from POST /knowledge/search."""

    query: str
    results: List[ChunkResult]
    sources: List[str]
    total_results: int


# ---------------------------------------------------------------------------
# Collection stats
# ---------------------------------------------------------------------------
class KnowledgeStatsResponse(BaseModel):
    """Response from GET /knowledge/stats."""

    connected: bool
    chunk_count: int
    document_count: int
    documents: List[str]


# ---------------------------------------------------------------------------
# Document deletion
# ---------------------------------------------------------------------------
class DeleteDocumentResponse(BaseModel):
    """Response from DELETE /knowledge/documents/{filename}."""

    source_document: str
    deleted: bool
