"""
Embeddings Service.

Wraps OpenAI's async embeddings API with:
- Batch processing to stay within API rate limits
- Retry/back-off handled by the openai SDK
- Simple caching of embeddings by text hash to avoid redundant API calls
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Dict, List

from openai import AsyncOpenAI

from app.config import get_settings

log = logging.getLogger(__name__)

# Maximum texts per batch call — OpenAI supports up to 2 048 inputs but
# smaller batches are friendlier on rate limits and memory.
_BATCH_SIZE = 100


class EmbeddingsService:
    """Async wrapper around OpenAI Embeddings API."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.embedding_model
        self._cache: Dict[str, List[float]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def embed_text(self, text: str) -> List[float]:
        """Return a single embedding vector for *text*."""
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Return embedding vectors for all *texts*.

        Handles deduplication via in-process cache and splits large lists
        into batches to stay within API limits.
        """
        if not texts:
            return []

        all_embeddings: List[List[float] | None] = [None] * len(texts)
        uncached_indices: List[int] = []
        uncached_texts: List[str] = []

        # Separate cached from uncached
        for i, text in enumerate(texts):
            key = self._cache_key(text)
            if key in self._cache:
                all_embeddings[i] = self._cache[key]
            else:
                uncached_indices.append(i)
                uncached_texts.append(text)

        # Fetch uncached in batches
        if uncached_texts:
            fetched = await self._fetch_in_batches(uncached_texts)
            for idx, (orig_idx, embedding) in enumerate(zip(uncached_indices, fetched)):
                key = self._cache_key(uncached_texts[idx])
                self._cache[key] = embedding
                all_embeddings[orig_idx] = embedding

        return [e for e in all_embeddings if e is not None]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_in_batches(self, texts: List[str]) -> List[List[float]]:
        results: List[List[float]] = []
        for batch_start in range(0, len(texts), _BATCH_SIZE):
            batch = texts[batch_start : batch_start + _BATCH_SIZE]
            batch_embeddings = await self._call_api(batch)
            results.extend(batch_embeddings)
        return results

    async def _call_api(self, texts: List[str]) -> List[List[float]]:
        log.debug("Fetching embeddings", model=self._model, batch_size=len(texts))
        response = await self._client.embeddings.create(
            model=self._model,
            input=texts,
        )
        # Sort by index to preserve order (API returns items in order, but be safe)
        sorted_data = sorted(response.data, key=lambda d: d.index)
        return [item.embedding for item in sorted_data]

    @staticmethod
    def _cache_key(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Module-level singleton — shared across requests in the same process
# ---------------------------------------------------------------------------
_service: EmbeddingsService | None = None


def get_embeddings_service() -> EmbeddingsService:
    """Return (or lazily create) the process-wide EmbeddingsService."""
    global _service
    if _service is None:
        _service = EmbeddingsService()
    return _service
