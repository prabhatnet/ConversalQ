"""
Document Ingestion Pipeline.

Supports: PDF, DOCX, plain-text (.txt), Markdown (.md).

Pipeline
--------
1. Receive file bytes + filename
2. Extract plain text based on file type
3. Chunk text into overlapping token windows
4. Embed chunks via OpenAI
5. Upsert into ChromaDB vector store

Returns an IngestionResult with counts for observability.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pypdf
import docx  # python-docx

from app.rag.chunking import DocumentChunk, chunk_text
from app.rag.embeddings import EmbeddingsService
from app.rag.vector_store import VectorStore

log = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


# ---------------------------------------------------------------------------
# DTO
# ---------------------------------------------------------------------------
@dataclass
class IngestionResult:
    source_document: str
    chunks_stored: int
    total_tokens: int
    success: bool
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------
def _extract_pdf(data: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(data))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text.strip())
    return "\n\n".join(pages)


def _extract_docx(data: bytes) -> str:
    doc = docx.Document(io.BytesIO(data))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)


def _extract_text(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


_EXTRACTORS = {
    ".pdf": _extract_pdf,
    ".docx": _extract_docx,
    ".txt": _extract_text,
    ".md": _extract_text,
}


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
class IngestionPipeline:
    """
    Orchestrates the full document ingestion flow:
    extract → chunk → embed → store.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        embeddings_service: EmbeddingsService,
        chunk_tokens: int = 500,
        overlap_tokens: int = 50,
    ) -> None:
        self._store = vector_store
        self._embeddings = embeddings_service
        self._chunk_tokens = chunk_tokens
        self._overlap_tokens = overlap_tokens

    async def ingest(
        self,
        file_bytes: bytes,
        filename: str,
        replace_existing: bool = True,
    ) -> IngestionResult:
        """
        Ingest a document from raw bytes.

        Parameters
        ----------
        file_bytes:
            Raw file content.
        filename:
            Original filename (used as source identifier and to detect type).
        replace_existing:
            If True, delete any existing chunks for this document before
            re-ingesting so the knowledge base stays fresh.
        """
        ext = Path(filename).suffix.lower()
        if ext not in _SUPPORTED_EXTENSIONS:
            return IngestionResult(
                source_document=filename,
                chunks_stored=0,
                total_tokens=0,
                success=False,
                error=f"Unsupported file type: {ext!r}. Supported: {sorted(_SUPPORTED_EXTENSIONS)}",
            )

        try:
            # Step 1 — Extract text
            extractor = _EXTRACTORS[ext]
            text = extractor(file_bytes)
            if not text.strip():
                return IngestionResult(
                    source_document=filename,
                    chunks_stored=0,
                    total_tokens=0,
                    success=False,
                    error="Document appears to be empty or has no extractable text.",
                )

            # Step 2 — Chunk
            chunks: list[DocumentChunk] = chunk_text(
                text=text,
                source_document=filename,
                chunk_tokens=self._chunk_tokens,
                overlap_tokens=self._overlap_tokens,
            )
            if not chunks:
                return IngestionResult(
                    source_document=filename,
                    chunks_stored=0,
                    total_tokens=0,
                    success=False,
                    error="No chunks produced from document.",
                )

            log.info(
                "Chunked document",
                filename=filename,
                chunk_count=len(chunks),
            )

            # Step 3 — Embed
            texts = [c.text for c in chunks]
            embeddings = await self._embeddings.embed_batch(texts)

            # Step 4 — (Optional) delete existing version
            if replace_existing and self._store.is_connected:
                await self._store.delete_document(filename)

            # Step 5 — Store
            stored = await self._store.add_chunks(chunks, embeddings)

            total_tokens = sum(c.token_count for c in chunks)
            log.info(
                "Ingestion complete",
                filename=filename,
                chunks_stored=stored,
                total_tokens=total_tokens,
            )

            return IngestionResult(
                source_document=filename,
                chunks_stored=stored,
                total_tokens=total_tokens,
                success=True,
            )

        except Exception as exc:
            log.exception("Ingestion failed", filename=filename, error=str(exc))
            return IngestionResult(
                source_document=filename,
                chunks_stored=0,
                total_tokens=0,
                success=False,
                error=str(exc),
            )
