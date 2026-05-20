"""
RAG Retriever.

Combines embedding lookup + relevance filtering to produce citation-ready
context for the LLM prompt.

Usage
-----
retriever = RAGRetriever(vector_store, embeddings_service)
context   = await retriever.retrieve("What is our refund policy?")

# context.formatted_context is ready to inject into the system prompt:
# [Source: refund_policy.pdf] Our standard refund window is 30 days...
"""

from __future__ import annotations

import structlog
from dataclasses import dataclass, field
from typing import List, Optional

from app.rag.embeddings import EmbeddingsService
from app.rag.vector_store import RetrievedChunk, VectorStore

log = structlog.get_logger(__name__)

# Minimum relevance score (0-1) to include a chunk in context.
# Chunks below this threshold are discarded as noise.
_DEFAULT_MIN_SCORE: float = 0.30

# How many chunks to retrieve from ChromaDB (more than top_k so we can
# filter by score and still have enough results).
_OVER_FETCH_MULTIPLIER: int = 3


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------
@dataclass
class RetrievalContext:
    """
    The ready-to-use output of a retrieval call.

    ``formatted_context`` can be pasted directly into the LLM system prompt.
    ``sources`` lists unique document names for citation display to the user.
    """

    chunks: List[RetrievedChunk]
    formatted_context: str   # pre-formatted, citation-tagged block
    sources: List[str]       # unique source_document names
    query: str

    @property
    def has_context(self) -> bool:
        return bool(self.chunks)


# ---------------------------------------------------------------------------
# Retriever
# ---------------------------------------------------------------------------
class RAGRetriever:
    """
    High-level retrieval interface.

    1. Embeds the user query.
    2. Queries ChromaDB for similar chunks.
    3. Filters by minimum relevance score.
    4. Formats chunks into a citation-rich context block.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        embeddings_service: EmbeddingsService,
        top_k: int = 5,
        min_score: float = _DEFAULT_MIN_SCORE,
    ) -> None:
        self._store = vector_store
        self._embeddings = embeddings_service
        self._top_k = top_k
        self._min_score = min_score

    async def retrieve(
        self,
        query: str,
        source_document_filter: Optional[str] = None,
    ) -> RetrievalContext:
        """
        Retrieve the most relevant chunks for *query*.

        Returns a :class:`RetrievalContext` — if ChromaDB is unavailable or
        the collection is empty, an empty context is returned gracefully.
        """
        if not self._store.is_connected:
            log.debug("Vector store not connected — skipping RAG retrieval")
            return self._empty_context(query)

        try:
            # Embed the query
            query_embedding = await self._embeddings.embed_text(query)

            # Fetch with over-fetch for score filtering
            raw_chunks = await self._store.query(
                query_embedding=query_embedding,
                top_k=self._top_k * _OVER_FETCH_MULTIPLIER,
                source_document_filter=source_document_filter,
            )

            # Filter by minimum relevance
            filtered = [
                c for c in raw_chunks if c.relevance_score >= self._min_score
            ][:self._top_k]

            if not filtered:
                log.debug(
                    "No chunks above relevance threshold",
                    query=query[:80],
                    min_score=self._min_score,
                    candidates=len(raw_chunks),
                )
                return self._empty_context(query)

            context = self._format_context(filtered, query)
            log.info(
                "RAG retrieval complete",
                query=query[:80],
                chunks_returned=len(filtered),
                sources=context.sources,
            )
            return context

        except Exception:
            log.exception("RAG retrieval error — falling back to no context", query=query[:80])
            return self._empty_context(query)

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    @staticmethod
    def _format_context(chunks: List[RetrievedChunk], query: str) -> RetrievalContext:
        """
        Build a human-readable, citation-tagged context block.

        Example output::

            [Source: refund_policy.pdf]
            Our standard refund window is 30 days from the purchase date...

            [Source: faq.pdf]
            For digital products, refunds are issued within 5 business days...
        """
        parts: List[str] = []
        seen_sources: List[str] = []

        for chunk in chunks:
            src = chunk.source_document
            parts.append(f"[Source: {src}]\n{chunk.text}")
            if src not in seen_sources:
                seen_sources.append(src)

        return RetrievalContext(
            chunks=chunks,
            formatted_context="\n\n".join(parts),
            sources=seen_sources,
            query=query,
        )

    @staticmethod
    def _empty_context(query: str) -> RetrievalContext:
        return RetrievalContext(
            chunks=[],
            formatted_context="",
            sources=[],
            query=query,
        )
