"""
ChromaDB Vector Store Wrapper.

Provides an async-friendly interface for storing and querying document
embeddings in ChromaDB.

Dev mode:  ChromaDB runs as an HTTP service via Docker (chromadb-client).
Prod mode: Same — always HTTP client mode to avoid native binary requirements.

Collection schema
-----------------
Each document chunk is stored as:
  - id:        "{source_document}::{chunk_index}"
  - embedding: List[float]  (from OpenAI text-embedding-3-small)
  - document:  chunk text   (returned in query results)
  - metadata:  {source_document, chunk_index, char_start, char_end, token_count}
"""

from __future__ import annotations

import asyncio
from typing import Dict, List, Optional
from uuid import uuid4

import chromadb
from chromadb import Collection
from chromadb.config import Settings as ChromaSettings
import structlog

from app.config import get_settings
from app.rag.chunking import DocumentChunk

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Retrieval result DTO
# ---------------------------------------------------------------------------
class RetrievedChunk:
    """A chunk returned by a similarity search."""

    def __init__(
        self,
        text: str,
        source_document: str,
        chunk_index: int,
        distance: float,
        char_start: int = 0,
        char_end: int = 0,
        token_count: int = 0,
    ) -> None:
        self.text = text
        self.source_document = source_document
        self.chunk_index = chunk_index
        self.distance = distance  # lower == more similar in L2 space
        self.char_start = char_start
        self.char_end = char_end
        self.token_count = token_count

    @property
    def relevance_score(self) -> float:
        """Normalised relevance in [0, 1] — higher is more relevant."""
        # ChromaDB returns L2 distances; convert to a loose similarity proxy.
        return max(0.0, 1.0 - self.distance)

    def __repr__(self) -> str:
        return (
            f"RetrievedChunk(source={self.source_document!r}, "
            f"idx={self.chunk_index}, score={self.relevance_score:.3f})"
        )


# ---------------------------------------------------------------------------
# Vector store
# ---------------------------------------------------------------------------
class VectorStore:
    """
    Thin async wrapper around a ChromaDB HTTP client.

    All ChromaDB calls are synchronous (the SDK has no native async support),
    so we run them via :func:`asyncio.to_thread` to avoid blocking the event
    loop.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._collection_name = settings.chroma_collection
        self._client: Optional[chromadb.HttpClient] = None
        self._collection: Optional[Collection] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Establish connection to ChromaDB and obtain/create the collection."""
        settings = get_settings()

        def _connect() -> None:
            # Suppress ChromaDB's telemetry before client init
            import os
            os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

            self._client = chromadb.HttpClient(
                host=settings.chroma_host,
                port=settings.chroma_port,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            # Verify connectivity
            self._client.heartbeat()
            # Get-or-create the named collection
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "l2"},
            )
            log.info(
                "ChromaDB connected",
                host=settings.chroma_host,
                port=settings.chroma_port,
                collection=self._collection_name,
            )

        await asyncio.to_thread(_connect)

    async def disconnect(self) -> None:
        """Clean up (no-op for HTTP client but keeps lifecycle symmetric)."""
        self._client = None
        self._collection = None

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    async def add_chunks(
        self,
        chunks: List[DocumentChunk],
        embeddings: List[List[float]],
    ) -> int:
        """
        Upsert *chunks* with their pre-computed *embeddings*.

        Returns the number of chunks stored.
        """
        if not chunks:
            return 0

        ids = [f"{c.source_document}::{c.chunk_index}" for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [
            {
                "source_document": c.source_document,
                "chunk_index": c.chunk_index,
                "char_start": c.char_start,
                "char_end": c.char_end,
                "token_count": c.token_count,
            }
            for c in chunks
        ]

        def _upsert() -> None:
            self._collection.upsert(  # type: ignore[union-attr]
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )

        await asyncio.to_thread(_upsert)
        log.info("Upserted chunks", count=len(chunks))
        return len(chunks)

    async def delete_document(self, source_document: str) -> None:
        """Remove all chunks belonging to *source_document*."""

        def _delete() -> None:
            self._collection.delete(  # type: ignore[union-attr]
                where={"source_document": source_document}
            )

        await asyncio.to_thread(_delete)
        log.info("Deleted document chunks", source_document=source_document)

    async def reset_collection(self) -> None:
        """Delete and recreate the collection — wipes all data."""

        def _reset() -> None:
            self._client.delete_collection(self._collection_name)  # type: ignore[union-attr]
            self._collection = self._client.get_or_create_collection(  # type: ignore[union-attr]
                name=self._collection_name,
                metadata={"hnsw:space": "l2"},
            )

        await asyncio.to_thread(_reset)
        log.info("Collection reset", collection=self._collection_name)

    # ------------------------------------------------------------------
    # Query operations
    # ------------------------------------------------------------------

    async def query(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        source_document_filter: Optional[str] = None,
    ) -> List[RetrievedChunk]:
        """
        Return up to *top_k* chunks most similar to *query_embedding*.

        Optionally filter by *source_document_filter*.
        """
        where: Optional[Dict] = None
        if source_document_filter:
            where = {"source_document": source_document_filter}

        def _query() -> chromadb.QueryResult:
            return self._collection.query(  # type: ignore[union-attr]
                query_embeddings=[query_embedding],
                n_results=min(top_k, self._collection.count() or 1),
                where=where,
                include=["documents", "metadatas", "distances"],
            )

        result = await asyncio.to_thread(_query)

        retrieved: List[RetrievedChunk] = []
        if not result["documents"] or not result["documents"][0]:
            return retrieved

        for doc, meta, dist in zip(
            result["documents"][0],
            result["metadatas"][0],
            result["distances"][0],
        ):
            retrieved.append(
                RetrievedChunk(
                    text=doc,
                    source_document=meta.get("source_document", "unknown"),
                    chunk_index=int(meta.get("chunk_index", 0)),
                    distance=float(dist),
                    char_start=int(meta.get("char_start", 0)),
                    char_end=int(meta.get("char_end", 0)),
                    token_count=int(meta.get("token_count", 0)),
                )
            )

        return retrieved

    async def get_collection_count(self) -> int:
        """Return the total number of chunks in the collection."""

        def _count() -> int:
            return self._collection.count()  # type: ignore[union-attr]

        return await asyncio.to_thread(_count)

    async def list_documents(self) -> List[str]:
        """Return sorted list of unique source document names."""

        def _get_all() -> chromadb.GetResult:
            return self._collection.get(  # type: ignore[union-attr]
                include=["metadatas"]
            )

        result = await asyncio.to_thread(_get_all)
        docs = {
            m.get("source_document", "")
            for m in (result["metadatas"] or [])
            if m.get("source_document")
        }
        return sorted(docs)

    @property
    def is_connected(self) -> bool:
        return self._collection is not None


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Return (or lazily create) the process-wide VectorStore."""
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
