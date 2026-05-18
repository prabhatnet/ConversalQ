"""
RAG Chunking Pipeline.

Splits raw document text into overlapping chunks optimised for embedding and
retrieval.  Uses LangChain's RecursiveCharacterTextSplitter under the hood so
that natural boundaries (paragraphs → sentences → words) are preferred over
hard character cuts.

Chunk size is measured in tokens via tiktoken so that downstream embedding
calls never exceed the model's context window.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter


# ---------------------------------------------------------------------------
# Chunk size constants
# ---------------------------------------------------------------------------
DEFAULT_CHUNK_TOKENS: int = 500   # target tokens per chunk
DEFAULT_OVERLAP_TOKENS: int = 50  # overlap between consecutive chunks
TIKTOKEN_ENCODING: str = "cl100k_base"  # used by text-embedding-3-* models


# ---------------------------------------------------------------------------
# Data transfer object
# ---------------------------------------------------------------------------
@dataclass
class DocumentChunk:
    """A single text chunk with its metadata."""

    text: str
    chunk_index: int
    source_document: str   # filename / URI of the source
    char_start: int        # character offset in the original document
    char_end: int
    token_count: int


# ---------------------------------------------------------------------------
# Tokeniser helper
# ---------------------------------------------------------------------------
def _count_tokens(text: str, encoding: str = TIKTOKEN_ENCODING) -> int:
    enc = tiktoken.get_encoding(encoding)
    return len(enc.encode(text))


def _tiktoken_len(text: str) -> int:
    """Callable used by LangChain splitter for accurate token-based sizing."""
    return _count_tokens(text)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def chunk_text(
    text: str,
    source_document: str,
    chunk_tokens: int = DEFAULT_CHUNK_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> List[DocumentChunk]:
    """
    Split *text* into overlapping chunks and return a list of
    :class:`DocumentChunk` objects.

    Parameters
    ----------
    text:
        Raw document content (plain text, already extracted from PDF / DOCX).
    source_document:
        Logical name of the document (used for citations in answers).
    chunk_tokens:
        Target token count per chunk.
    overlap_tokens:
        Number of tokens shared between consecutive chunks for context
        continuity.
    """
    if not text or not text.strip():
        return []

    # Normalise whitespace: collapse multiple blank lines to a single one
    text = re.sub(r"\n{3,}", "\n\n", text)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_tokens,
        chunk_overlap=overlap_tokens,
        length_function=_tiktoken_len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    raw_chunks: List[str] = splitter.split_text(text)

    chunks: List[DocumentChunk] = []
    search_start = 0
    for idx, chunk_text_content in enumerate(raw_chunks):
        # Find character offset of this chunk within the original text
        char_start = text.find(chunk_text_content, search_start)
        if char_start == -1:
            # Fallback — can happen after normalisation
            char_start = 0
        char_end = char_start + len(chunk_text_content)
        # Advance search cursor with overlap so consecutive finds are correct
        search_start = max(0, char_end - (overlap_tokens * 4))

        chunks.append(
            DocumentChunk(
                text=chunk_text_content.strip(),
                chunk_index=idx,
                source_document=source_document,
                char_start=char_start,
                char_end=char_end,
                token_count=_count_tokens(chunk_text_content),
            )
        )

    return chunks
