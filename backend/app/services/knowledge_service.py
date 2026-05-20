"""
Knowledge Service.

High-level orchestration for the knowledge base:
- Document ingestion (delegates to IngestionPipeline)
- Semantic search (delegates to RAGRetriever)
- Collection statistics

This service is injected into the chat endpoint (via dependencies.py) to
provide context-aware responses, and into the knowledge API endpoints for
direct KB management operations.
"""

from __future__ import annotations

import structlog
from typing import List, Optional

from app.rag.embeddings import EmbeddingsService
from app.rag.ingestion import IngestionPipeline, IngestionResult
from app.rag.retriever import RAGRetriever, RetrievalContext
from app.rag.vector_store import VectorStore

log = structlog.get_logger(__name__)


class KnowledgeService:
    """Orchestrates document ingestion and retrieval."""

    def __init__(
        self,
        vector_store: VectorStore,
        embeddings_service: EmbeddingsService,
        top_k: int = 5,
        min_relevance_score: float = 0.30,
    ) -> None:
        self._store = vector_store
        self._embeddings = embeddings_service
        self._pipeline = IngestionPipeline(
            vector_store=vector_store,
            embeddings_service=embeddings_service,
        )
        self._retriever = RAGRetriever(
            vector_store=vector_store,
            embeddings_service=embeddings_service,
            top_k=top_k,
            min_score=min_relevance_score,
        )

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    async def ingest_document(
        self,
        file_bytes: bytes,
        filename: str,
        replace_existing: bool = True,
    ) -> IngestionResult:
        """
        Ingest a document into the knowledge base.

        Parameters
        ----------
        file_bytes:
            Raw file content (PDF / DOCX / TXT / MD).
        filename:
            Original filename — used as the unique source identifier.
        replace_existing:
            Remove prior chunks for this document before re-ingesting.
        """
        log.info("Starting document ingestion", filename=filename, size_bytes=len(file_bytes))
        result = await self._pipeline.ingest(
            file_bytes=file_bytes,
            filename=filename,
            replace_existing=replace_existing,
        )
        if result.success:
            log.info(
                "Ingestion succeeded",
                filename=filename,
                chunks=result.chunks_stored,
                tokens=result.total_tokens,
            )
        else:
            log.warning("Ingestion failed", filename=filename, error=result.error)
        return result

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    async def retrieve_context(
        self,
        query: str,
        source_document_filter: Optional[str] = None,
    ) -> RetrievalContext:
        """
        Retrieve relevant knowledge-base context for a query.

        Returns a :class:`RetrievalContext` — empty if no relevant chunks
        found or ChromaDB is unavailable.
        """
        return await self._retriever.retrieve(
            query=query,
            source_document_filter=source_document_filter,
        )

    async def search_knowledge(
        self,
        query: str,
        top_k: int = 5,
    ) -> RetrievalContext:
        """
        Direct semantic search — used by the /knowledge/search endpoint.

        Uses a temporary retriever configured with the requested top_k.
        """
        searcher = RAGRetriever(
            vector_store=self._store,
            embeddings_service=self._embeddings,
            top_k=top_k,
            min_score=0.0,  # Return all results for explicit search
        )
        return await searcher.retrieve(query=query)

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------

    async def list_documents(self) -> List[str]:
        """Return sorted list of source document names in the KB."""
        if not self._store.is_connected:
            return []
        return await self._store.list_documents()

    async def delete_document(self, filename: str) -> None:
        """Remove all chunks for *filename* from the knowledge base."""
        if not self._store.is_connected:
            log.warning("Vector store not connected — cannot delete", filename=filename)
            return
        await self._store.delete_document(filename)
        log.info("Document deleted from KB", filename=filename)

    async def get_stats(self) -> dict:
        """Return basic KB statistics."""
        if not self._store.is_connected:
            return {
                "connected": False,
                "chunk_count": 0,
                "document_count": 0,
                "documents": [],
            }
        count = await self._store.get_collection_count()
        documents = await self._store.list_documents()
        return {
            "connected": True,
            "chunk_count": count,
            "document_count": len(documents),
            "documents": documents,
        }
