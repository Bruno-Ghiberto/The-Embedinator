"""LangChain tool definitions for ResearchGraph.

Tools are created via create_research_tools() factory which closes over
infrastructure dependencies (HybridSearcher, Reranker, ParentStore).
This avoids module-level singletons and supports testing with mocks.
"""

from __future__ import annotations

import structlog
from langchain_core.tools import tool

from backend.agent._request_context import selected_collections_var
from backend.agent.schemas import ParentChunk, RetrievedChunk
from backend.retrieval.reranker import Reranker
from backend.retrieval.score_normalizer import normalize_scores
from backend.retrieval.searcher import HybridSearcher
from backend.storage.parent_store import ParentStore

logger = structlog.get_logger().bind(component=__name__)


def create_research_tools(
    searcher: HybridSearcher,
    reranker: Reranker,
    parent_store: ParentStore,
    embed_provider=None,
) -> list:
    """Factory that creates tool instances with injected dependencies.

    Args:
        searcher: HybridSearcher for Qdrant queries.
        reranker: CrossEncoder reranker.
        parent_store: SQLite parent chunk reader.

    Returns:
        List of 6 LangChain tool objects ready for llm.bind_tools().
    """

    # Create embed_fn closure if embed_provider is available
    async def _embed_fn(text: str):
        if embed_provider is None:
            return None
        return await embed_provider.embed_single(text)

    embed_fn = _embed_fn if embed_provider is not None else None

    @tool
    async def search_child_chunks(
        query: str,
        collection: str,
        top_k: int = 20,
        filters: dict | None = None,
    ) -> list[RetrievedChunk]:
        """Hybrid dense+BM25 search in Qdrant on child chunk collection,
        followed by cross-encoder reranking.

        Args:
            query: The search query text.
            collection: Name of the Qdrant collection to search.
            top_k: Number of results to return after reranking.
            filters: Optional Qdrant payload filters.

        Returns:
            List of RetrievedChunk objects sorted by rerank score descending.
        """
        # Resolve and AUTHORIZE the collection name.
        # spec-28 BUG-002 fix: enforce the request-scope allowlist
        # (selected_collections_var, bound in backend/api/chat.py from
        # body.collection_ids). The LLM may pass:
        #   - the proper Qdrant name "emb-{uuid}"  → strip prefix, check UUID
        #   - the raw UUID (most common in practice) → check UUID directly
        #   - some other string (hallucination)      → rejected; fail-closed
        # The previous fallback to search_all_collections is REMOVED — it broke
        # the user's API-level collection_ids contract and leaked cross-tenant
        # chunks into user-visible citations (BUG-002, blast-radius: Blocker).
        try:
            authorized = selected_collections_var.get() or []
        except LookupError:
            authorized = []

        if collection.startswith("emb-"):
            uuid_part = collection[len("emb-"):]
        else:
            uuid_part = collection

        if uuid_part in authorized:
            qdrant_name = f"emb-{uuid_part}"
        else:
            # Unauthorized — fail closed. Empty result triggers the agent's
            # confidence floor; no cross-collection data leaks to the user.
            qdrant_name = None

        if qdrant_name:
            raw_chunks = await searcher.search(query, qdrant_name, top_k=top_k, filters=filters, embed_fn=embed_fn)
        else:
            raw_chunks = []  # fail-closed: do NOT fall back to search_all_collections (BUG-002)
        if raw_chunks:
            raw_chunks = reranker.rerank(query, raw_chunks, top_k=top_k)
        return raw_chunks

    @tool
    async def retrieve_parent_chunks(
        parent_ids: list[str],
    ) -> list[ParentChunk]:
        """Fetch parent chunks from SQLite by parent_id list.
        Parent chunks contain the full surrounding context for child chunks.

        Args:
            parent_ids: List of parent chunk IDs to retrieve.

        Returns:
            List of ParentChunk objects. Missing IDs are silently skipped.
        """
        return await parent_store.get_by_ids(parent_ids)

    @tool
    async def cross_encoder_rerank(
        query: str,
        chunks: list[RetrievedChunk],
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        """Score (query, chunk) pairs with cross-encoder and return top-k ranked.

        Args:
            query: The search query text.
            chunks: List of chunks to rerank.
            top_k: Number of top results to return.

        Returns:
            List of RetrievedChunk objects sorted by cross-encoder score descending.
        """
        return reranker.rerank(query, chunks, top_k=top_k)

    @tool
    async def filter_by_collection(
        collection_name: str,
    ) -> dict:
        """Constrain subsequent searches to a specific named collection.

        Args:
            collection_name: The collection to constrain to.

        Returns:
            Confirmation dict with the active collection filter.
        """
        return {"active_collection_filter": collection_name}

    @tool
    async def filter_by_metadata(
        filters: dict,
    ) -> dict:
        """Apply Qdrant payload filter to narrow search results.
        Supported filter keys: doc_type, page_range, source_file, breadcrumb.

        Args:
            filters: Dictionary of payload filter conditions.

        Returns:
            Confirmation dict with the active metadata filters.
        """
        return {"active_metadata_filters": filters}

    @tool
    async def semantic_search_all_collections(
        query: str,
        top_k: int = 20,
    ) -> list[RetrievedChunk]:
        """Fan-out search across all enabled collections simultaneously.
        Results are normalized per-collection (min-max) before merging.

        Args:
            query: The search query text.
            top_k: Number of results to return after merge.

        Returns:
            List of RetrievedChunk objects merged from all collections.
        """
        # spec-28 BUG-002 amendment: enforce the same allowlist as search_child_chunks.
        # When an allowlist is present (every API-layer request sets one), fan out ONLY
        # to authorized collections — prevents cross-tenant chunk leakage on the clean path.
        # When no allowlist is in context (admin/dev direct calls), fall through to
        # unscoped search_all_collections and emit a warning so log watchers can audit.
        try:
            authorized = selected_collections_var.get() or []
        except LookupError:
            authorized = []

        if authorized:
            logger.info("retrieval_scoped_fanout", authorized_count=len(authorized))
            all_chunks = []
            for uuid in authorized:
                chunks = await searcher.search(query, f"emb-{uuid}", top_k=top_k, embed_fn=embed_fn)
                all_chunks.extend(chunks)
            raw_chunks = all_chunks
        else:
            logger.warning("retrieval_unscoped_fanout", reason="no_allowlist_in_context")
            raw_chunks = await searcher.search_all_collections(query, top_k=top_k, embed_fn=embed_fn)

        normalized = normalize_scores(raw_chunks)
        if normalized:
            normalized = reranker.rerank(query, normalized, top_k=top_k)
        return normalized

    return [
        search_child_chunks,
        retrieve_parent_chunks,
        cross_encoder_rerank,
        filter_by_collection,
        filter_by_metadata,
        semantic_search_all_collections,
    ]
