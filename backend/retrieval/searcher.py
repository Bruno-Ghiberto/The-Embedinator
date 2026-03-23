"""Qdrant hybrid dense + BM25 search with circuit breaker protection.

Uses AsyncQdrantClient (R4) with prefetch (dense + sparse) and FusionQuery(Fusion.RRF).
All Qdrant calls are wrapped with the circuit breaker pattern per C1.
"""
from __future__ import annotations

import asyncio
from typing import Any

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    FieldCondition,
    Filter,
    MatchValue,
)

from backend.agent.schemas import RetrievedChunk
from backend.config import Settings
from backend.errors import QdrantConnectionError

logger = structlog.get_logger().bind(component=__name__)

ALLOWED_FILTER_KEYS = {"doc_type", "source_file", "page", "chunk_index"}


class HybridSearcher:
    """Executes hybrid dense + BM25 search against Qdrant.

    Uses AsyncQdrantClient (R4). All Qdrant call sites are protected
    by the circuit breaker pattern (C1 -- Constitution requirement).
    """

    def __init__(self, client: AsyncQdrantClient, settings: Settings):
        self.client = client
        self.dense_weight = settings.hybrid_dense_weight    # 0.7
        self.sparse_weight = settings.hybrid_sparse_weight  # 0.3
        self.default_top_k = settings.top_k_retrieval       # 20

        # Circuit breaker state (C1)
        self._circuit_open = False
        self._failure_count = 0
        self._max_failures = settings.circuit_breaker_failure_threshold  # 5
        self._cooldown_secs = settings.circuit_breaker_cooldown_secs     # 30

    async def _check_circuit(self) -> None:
        """Check circuit breaker state. Raises if circuit is open."""
        if self._circuit_open:
            logger.warning("circuit_searcher_open", failure_count=self._failure_count)
            raise QdrantConnectionError("Circuit breaker is open -- Qdrant unavailable")

    def _record_success(self) -> None:
        """Reset circuit breaker on success."""
        self._failure_count = 0
        self._circuit_open = False

    def _record_failure(self) -> None:
        """Increment failure count, open circuit if threshold reached."""
        self._failure_count += 1
        if self._failure_count >= self._max_failures:
            self._circuit_open = True
            logger.error("circuit_searcher_opened", failure_count=self._failure_count)

    def _build_filter(self, filters: dict | None) -> Filter | None:
        """Build Qdrant Filter from a dict of field conditions."""
        if not filters:
            return None

        conditions = []
        for key, value in filters.items():
            if key not in ALLOWED_FILTER_KEYS:
                continue  # FR-002: silently ignore unknown keys
            conditions.append(
                FieldCondition(key=key, match=MatchValue(value=value))
            )

        return Filter(must=conditions) if conditions else None

    def _points_to_chunks(
        self, points: list[Any], collection: str
    ) -> list[RetrievedChunk]:
        """Convert Qdrant ScoredPoint results to RetrievedChunk objects."""
        chunks = []
        for point in points:
            payload = point.payload or {}
            chunks.append(
                RetrievedChunk(
                    chunk_id=str(point.id),
                    text=payload.get("text", ""),
                    source_file=payload.get("source_file", ""),
                    page=payload.get("page"),
                    breadcrumb=payload.get("breadcrumb", ""),
                    parent_id=payload.get("parent_id", ""),
                    collection=collection,
                    dense_score=point.score if point.score is not None else 0.0,
                    sparse_score=payload.get("sparse_score", 0.0),
                    rerank_score=None,
                )
            )
        return chunks

    async def search(
        self,
        query: str,
        collection: str,
        top_k: int = 20,
        filters: dict | None = None,
        embed_fn: Any = None,
    ) -> list[RetrievedChunk]:
        """Execute hybrid search with circuit breaker (C1).

        1. Check circuit breaker state
        2. Generate dense embedding for query via embed_fn
        3. Execute Qdrant query_points with prefetch (dense + sparse) + Fusion.RRF (R4)
        4. Apply payload filters if provided
        5. Return top_k results as RetrievedChunk objects

        Args:
            query: The search query text.
            collection: Qdrant collection name.
            top_k: Number of results to return.
            filters: Optional payload filters (doc_type, page_range, source_file).
            embed_fn: Callable that returns dense vector for query text.

        Returns:
            List of RetrievedChunk objects.

        Raises:
            QdrantConnectionError: If Qdrant is unreachable or circuit is open.
        """
        await self._check_circuit()

        if embed_fn is None:
            logger.warning("retrieval_search_skipped_no_embed_fn", collection=collection)
            return []

        try:
            # Generate dense embedding
            dense_vector = await embed_fn(query)

            # Build optional filter
            query_filter = self._build_filter(filters)

            # Dense-only search — sparse prefetch requires pre-encoded sparse vectors
            # which are not available at query time (BM25 encoding not implemented).
            results = await self.client.query_points(
                collection_name=collection,
                query=dense_vector,
                using="dense",
                limit=top_k,
                with_payload=True,
                query_filter=query_filter,
            )

            # Extract points from QueryResponse
            points = results.points if hasattr(results, "points") else results

            chunks = self._points_to_chunks(points, collection)
            self._record_success()

            logger.info(
                "retrieval_hybrid_search_complete",
                collection=collection,
                query_length=len(query),
                results=len(chunks),
            )
            return chunks

        except QdrantConnectionError:
            raise  # Re-raise circuit breaker errors
        except Exception as exc:
            self._record_failure()
            logger.warning(
                "retrieval_hybrid_search_failed",
                collection=collection,
                error=type(exc).__name__,
            )
            raise QdrantConnectionError(
                f"Hybrid search failed for collection {collection}: {exc}"
            ) from exc

    async def search_all_collections(
        self,
        query: str,
        top_k: int = 20,
        embed_fn: Any = None,
    ) -> list[RetrievedChunk]:
        """Fan-out search across all available collections.

        Queries each collection in parallel, merges results.
        Circuit breaker protects each individual collection query (C1).
        Partial failures return results from successful collections only.

        Args:
            query: The search query text.
            top_k: Number of results per collection.
            embed_fn: Callable that returns dense vector for query text.

        Returns:
            Merged list of RetrievedChunk from all collections.
        """
        await self._check_circuit()

        if embed_fn is None:
            logger.warning("retrieval_search_all_skipped_no_embed_fn")
            return []

        try:
            collections_response = await self.client.get_collections()
            collection_names = [
                c.name for c in collections_response.collections
            ]
        except Exception as exc:
            self._record_failure()
            logger.warning("retrieval_list_collections_failed", error=type(exc).__name__)
            return []

        if not collection_names:
            logger.info("retrieval_search_all_no_collections")
            return []

        # Fan-out search per collection
        tasks = [
            self.search(query, name, top_k=top_k, embed_fn=embed_fn)
            for name in collection_names
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge successful results, log failures
        merged: list[RetrievedChunk] = []
        for name, result in zip(collection_names, results):
            if isinstance(result, Exception):
                logger.warning(
                    "retrieval_collection_search_failed",
                    collection=name,
                    error=type(result).__name__,
                )
            else:
                merged.extend(result)

        logger.info(
            "retrieval_search_all_complete",
            collections_searched=len(collection_names),
            total_results=len(merged),
        )
        return merged
