"""
Knowledge Base API Endpoints.

Provides document ingestion and semantic search for the ConversalQ knowledge
base.

Endpoints
---------
POST   /api/v1/knowledge/ingest          — upload and index a document
POST   /api/v1/knowledge/search          — semantic search
GET    /api/v1/knowledge/stats           — collection statistics
GET    /api/v1/knowledge/documents       — list indexed documents
DELETE /api/v1/knowledge/documents/{fn}  — remove a document
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status

from app.dependencies import get_knowledge_service
from app.schemas.knowledge import (
    ChunkResult,
    DeleteDocumentResponse,
    IngestResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeStatsResponse,
)
from app.services.knowledge_service import KnowledgeService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base"])

# Maximum upload size: 20 MB
_MAX_UPLOAD_BYTES = 20 * 1024 * 1024


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------
@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a document into the knowledge base",
    description=(
        "Upload a PDF, DOCX, TXT, or Markdown file. The file is chunked, "
        "embedded, and stored in ChromaDB for retrieval-augmented generation."
    ),
)
async def ingest_document(
    file: UploadFile = File(..., description="Document to ingest (PDF/DOCX/TXT/MD)"),
    replace_existing: bool = Query(
        default=True,
        description="Replace existing chunks if a document with the same name already exists",
    ),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
) -> IngestResponse:
    filename = file.filename or "upload"

    # Guard: size check
    file_bytes = await file.read()
    if len(file_bytes) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {_MAX_UPLOAD_BYTES // (1024*1024)} MB.",
        )

    logger.info("knowledge_ingest_request", filename=filename, size_bytes=len(file_bytes))

    result = await knowledge_service.ingest_document(
        file_bytes=file_bytes,
        filename=filename,
        replace_existing=replace_existing,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result.error or "Ingestion failed.",
        )

    return IngestResponse(
        source_document=result.source_document,
        chunks_stored=result.chunks_stored,
        total_tokens=result.total_tokens,
        success=result.success,
    )


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
@router.post(
    "/search",
    response_model=KnowledgeSearchResponse,
    summary="Semantic search over the knowledge base",
    description="Run a natural-language query against all indexed documents.",
)
async def search_knowledge(
    request: KnowledgeSearchRequest,
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
) -> KnowledgeSearchResponse:
    logger.info("knowledge_search_request", query=request.query[:80], top_k=request.top_k)

    retrieval = await knowledge_service.search_knowledge(
        query=request.query,
        top_k=request.top_k,
    )

    chunk_results = [
        ChunkResult(
            text=chunk.text,
            source_document=chunk.source_document,
            chunk_index=chunk.chunk_index,
            relevance_score=round(chunk.relevance_score, 4),
        )
        for chunk in retrieval.chunks
    ]

    return KnowledgeSearchResponse(
        query=retrieval.query,
        results=chunk_results,
        sources=retrieval.sources,
        total_results=len(chunk_results),
    )


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------
@router.get(
    "/stats",
    response_model=KnowledgeStatsResponse,
    summary="Knowledge base statistics",
)
async def get_stats(
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
) -> KnowledgeStatsResponse:
    stats = await knowledge_service.get_stats()
    return KnowledgeStatsResponse(**stats)


# ---------------------------------------------------------------------------
# List documents
# ---------------------------------------------------------------------------
@router.get(
    "/documents",
    response_model=list[str],
    summary="List all indexed documents",
)
async def list_documents(
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
) -> list[str]:
    return await knowledge_service.list_documents()


# ---------------------------------------------------------------------------
# Delete document
# ---------------------------------------------------------------------------
@router.delete(
    "/documents/{filename:path}",
    response_model=DeleteDocumentResponse,
    summary="Delete a document from the knowledge base",
)
async def delete_document(
    filename: str,
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
) -> DeleteDocumentResponse:
    await knowledge_service.delete_document(filename)
    return DeleteDocumentResponse(source_document=filename, deleted=True)
