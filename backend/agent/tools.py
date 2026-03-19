"""LangChain tool definitions for ResearchGraph.

Tools are created via create_research_tools() factory which closes over
infrastructure dependencies (HybridSearcher, Reranker, ParentStore).
This avoids module-level singletons and supports testing with mocks.
"""
from __future__ import annotations

from langchain_core.tools import tool

from backend.agent.schemas import ParentChunk, RetrievedChunk
from backend.retrieval.reranker import Reranker
from backend.retrieval.score_normalizer import normalize_scores
from backend.retrieval.searcher import HybridSearcher
from backend.storage.parent_store import ParentStore


def create_research_tools(
    searcher: HybridSearcher,
    reranker: Reranker,
    parent_store: ParentStore,
) -> list:
    """Factory that creates tool instances with injected dependencies.

    Args:
        searcher: HybridSearcher for Qdrant queries.
        reranker: CrossEncoder reranker.
        parent_store: SQLite parent chunk reader.

    Returns:
        List of 6 LangChain tool objects ready for llm.bind_tools().
    """

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
        raw_chunks = await searcher.search(query, collection, top_k=top_k, filters=filters)
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
        raw_chunks = await searcher.search_all_collections(query, top_k=top_k)
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
