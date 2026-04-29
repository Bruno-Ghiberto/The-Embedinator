"""Unit tests for ResearchGraph tool factory (spec-03).

spec-28 BUG-002 regression tests added to TestSearchChildChunksScope.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.agent._request_context import selected_collections_var
from backend.agent.schemas import ParentChunk, RetrievedChunk
from backend.agent.tools import create_research_tools


def _chunk(chunk_id="c1", rerank_score=0.8, dense_score=0.5, collection="col1"):
    return RetrievedChunk(
        chunk_id=chunk_id,
        text="test text",
        source_file="test.md",
        breadcrumb="ch1",
        parent_id="p1",
        collection=collection,
        dense_score=dense_score,
        sparse_score=0.3,
        rerank_score=rerank_score,
    )


def _parent(parent_id="p1"):
    return ParentChunk(
        parent_id=parent_id,
        text="parent text",
        source_file="test.md",
        breadcrumb="ch1",
        collection="col1",
    )


@pytest.fixture
def mock_deps():
    """Create mock searcher, reranker, parent_store."""
    searcher = AsyncMock()
    reranker = MagicMock()
    parent_store = AsyncMock()
    return searcher, reranker, parent_store


@pytest.fixture
def tools(mock_deps):
    """Create research tools with mock dependencies."""
    searcher, reranker, parent_store = mock_deps
    return create_research_tools(searcher, reranker, parent_store)


class TestCreateResearchTools:
    def test_returns_six_tools(self, tools):
        assert len(tools) == 6

    def test_tool_names(self, tools):
        names = {t.name for t in tools}
        expected = {
            "search_child_chunks",
            "retrieve_parent_chunks",
            "cross_encoder_rerank",
            "filter_by_collection",
            "filter_by_metadata",
            "semantic_search_all_collections",
        }
        assert names == expected


class TestSearchChildChunks:
    @pytest.mark.asyncio
    async def test_calls_searcher_and_reranker(self, mock_deps):
        """Authorized collection UUID → searcher.search called, reranker called."""
        searcher, reranker, parent_store = mock_deps
        chunks = [_chunk()]
        searcher.search = AsyncMock(return_value=chunks)
        reranker.rerank = MagicMock(return_value=chunks)

        tools = create_research_tools(searcher, reranker, parent_store)
        search_tool = next(t for t in tools if t.name == "search_child_chunks")

        # spec-28 BUG-002: collection UUID must be in the authorized allowlist
        token = selected_collections_var.set(["test-uuid-col1"])
        try:
            await search_tool.ainvoke({"query": "test", "collection": "test-uuid-col1", "top_k": 20})
        finally:
            selected_collections_var.reset(token)

        searcher.search.assert_awaited_once()
        reranker.rerank.assert_called_once()

    @pytest.mark.asyncio
    async def test_calls_searcher_with_emb_prefix(self, mock_deps):
        """LLM passes 'emb-{uuid}' form → prefix stripped, UUID authorized, search called."""
        searcher, reranker, parent_store = mock_deps
        chunks = [_chunk()]
        searcher.search = AsyncMock(return_value=chunks)
        reranker.rerank = MagicMock(return_value=chunks)

        tools = create_research_tools(searcher, reranker, parent_store)
        search_tool = next(t for t in tools if t.name == "search_child_chunks")

        token = selected_collections_var.set(["test-uuid-col1"])
        try:
            await search_tool.ainvoke({"query": "test", "collection": "emb-test-uuid-col1", "top_k": 20})
        finally:
            selected_collections_var.reset(token)

        searcher.search.assert_awaited_once()
        reranker.rerank.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_rerank_on_empty_results(self, mock_deps):
        """Authorized collection returns no chunks → reranker not called."""
        searcher, reranker, parent_store = mock_deps
        searcher.search = AsyncMock(return_value=[])

        tools = create_research_tools(searcher, reranker, parent_store)
        search_tool = next(t for t in tools if t.name == "search_child_chunks")

        token = selected_collections_var.set(["col1"])
        try:
            await search_tool.ainvoke({"query": "test", "collection": "col1"})
        finally:
            selected_collections_var.reset(token)

        reranker.rerank.assert_not_called()


class TestSearchChildChunksScope:
    """spec-28 BUG-002 regression tests — collection scope enforcement.

    Verifies that search_child_chunks NEVER calls search_all_collections and
    NEVER searches a collection outside the authorized allowlist.
    """

    @pytest.mark.asyncio
    async def test_unauthorized_collection_returns_empty_no_search(self, mock_deps):
        """Collection UUID not in allowlist → empty result, searcher never called."""
        searcher, reranker, parent_store = mock_deps
        searcher.search = AsyncMock(return_value=[_chunk()])
        searcher.search_all_collections = AsyncMock(return_value=[_chunk()])

        tools = create_research_tools(searcher, reranker, parent_store)
        search_tool = next(t for t in tools if t.name == "search_child_chunks")

        # Authorize a DIFFERENT collection — "other-collection" is not authorized
        token = selected_collections_var.set(["authorized-uuid"])
        try:
            result = await search_tool.ainvoke({"query": "test", "collection": "other-collection"})
        finally:
            selected_collections_var.reset(token)

        assert result == [], "Unauthorized collection must return empty list (fail-closed)"
        searcher.search.assert_not_awaited()
        searcher.search_all_collections.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_allowlist_returns_empty_no_search(self, mock_deps):
        """No allowlist set (empty contextvars default) → empty result, no search."""
        searcher, reranker, parent_store = mock_deps
        searcher.search = AsyncMock(return_value=[_chunk()])
        searcher.search_all_collections = AsyncMock(return_value=[_chunk()])

        tools = create_research_tools(searcher, reranker, parent_store)
        search_tool = next(t for t in tools if t.name == "search_child_chunks")

        # Do NOT set selected_collections_var — default is []
        result = await search_tool.ainvoke({"query": "test", "collection": "any-collection"})

        assert result == [], "Empty allowlist must fail-closed"
        searcher.search.assert_not_awaited()
        searcher.search_all_collections.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_search_all_collections_never_called_for_scoped_request(self, mock_deps):
        """Authorized collection → search() called, search_all_collections NEVER called."""
        searcher, reranker, parent_store = mock_deps
        chunks = [_chunk()]
        searcher.search = AsyncMock(return_value=chunks)
        searcher.search_all_collections = AsyncMock(return_value=chunks)
        reranker.rerank = MagicMock(return_value=chunks)

        tools = create_research_tools(searcher, reranker, parent_store)
        search_tool = next(t for t in tools if t.name == "search_child_chunks")

        token = selected_collections_var.set(["22923ab5-ea0d-4bea-8ef2-15bf0262674f"])
        try:
            await search_tool.ainvoke(
                {
                    "query": "diámetro mínimo NAG-200",
                    "collection": "22923ab5-ea0d-4bea-8ef2-15bf0262674f",
                }
            )
        finally:
            selected_collections_var.reset(token)

        searcher.search.assert_awaited_once()
        searcher.search_all_collections.assert_not_awaited()  # BUG-002: this must NEVER fire

    @pytest.mark.asyncio
    async def test_emb_prefix_with_authorized_uuid(self, mock_deps):
        """LLM passes 'emb-{uuid}', UUID is in allowlist → search called with emb-{uuid}."""
        searcher, reranker, parent_store = mock_deps
        chunks = [_chunk()]
        searcher.search = AsyncMock(return_value=chunks)
        searcher.search_all_collections = AsyncMock(return_value=[])
        reranker.rerank = MagicMock(return_value=chunks)

        tools = create_research_tools(searcher, reranker, parent_store)
        search_tool = next(t for t in tools if t.name == "search_child_chunks")

        uuid = "22923ab5-ea0d-4bea-8ef2-15bf0262674f"
        token = selected_collections_var.set([uuid])
        try:
            await search_tool.ainvoke({"query": "test", "collection": f"emb-{uuid}"})
        finally:
            selected_collections_var.reset(token)

        searcher.search.assert_awaited_once_with("test", f"emb-{uuid}", top_k=20, filters=None, embed_fn=None)
        searcher.search_all_collections.assert_not_awaited()


class TestRetrieveParentChunks:
    @pytest.mark.asyncio
    async def test_calls_parent_store(self, mock_deps):
        searcher, reranker, parent_store = mock_deps
        parents = [_parent()]
        parent_store.get_by_ids = AsyncMock(return_value=parents)

        tools = create_research_tools(searcher, reranker, parent_store)
        tool = next(t for t in tools if t.name == "retrieve_parent_chunks")

        await tool.ainvoke({"parent_ids": ["p1"]})
        parent_store.get_by_ids.assert_awaited_once_with(["p1"])


class TestFilterTools:
    @pytest.mark.asyncio
    async def test_filter_by_collection(self, mock_deps):
        searcher, reranker, parent_store = mock_deps
        tools = create_research_tools(searcher, reranker, parent_store)
        tool = next(t for t in tools if t.name == "filter_by_collection")

        result = await tool.ainvoke({"collection_name": "my_col"})
        assert result == {"active_collection_filter": "my_col"}

    @pytest.mark.asyncio
    async def test_filter_by_metadata(self, mock_deps):
        searcher, reranker, parent_store = mock_deps
        tools = create_research_tools(searcher, reranker, parent_store)
        tool = next(t for t in tools if t.name == "filter_by_metadata")

        filters = {"doc_type": "pdf"}
        result = await tool.ainvoke({"filters": filters})
        assert result == {"active_metadata_filters": filters}


class TestSemanticSearchAllCollections:
    @pytest.mark.asyncio
    async def test_calls_search_all_and_reranks(self, mock_deps):
        """No allowlist in context → unscoped fallback to search_all_collections."""
        searcher, reranker, parent_store = mock_deps
        chunks = [_chunk(collection="col1"), _chunk(chunk_id="c2", collection="col2")]
        searcher.search_all_collections = AsyncMock(return_value=chunks)
        reranker.rerank = MagicMock(return_value=chunks)

        tools = create_research_tools(searcher, reranker, parent_store)
        tool = next(t for t in tools if t.name == "semantic_search_all_collections")

        await tool.ainvoke({"query": "test", "top_k": 10})

        searcher.search_all_collections.assert_awaited_once()
        reranker.rerank.assert_called_once()

    @pytest.mark.asyncio
    async def test_scoped_fanout_calls_search_per_authorized_collection(self, mock_deps):
        """spec-28 BUG-002 amendment: allowlist set → search() called once per UUID,
        search_all_collections NEVER called."""
        searcher, reranker, parent_store = mock_deps
        uuid1 = "22923ab5-ea0d-4bea-8ef2-15bf0262674f"
        uuid2 = "aaaabbbb-cccc-dddd-eeee-ffffffffffff"
        chunks_col1 = [_chunk(chunk_id="c1", collection=f"emb-{uuid1}")]
        chunks_col2 = [_chunk(chunk_id="c2", collection=f"emb-{uuid2}")]

        # search() returns different chunks per collection; search_all_collections must NOT be called
        async def _search(query, collection, top_k=20, filters=None, embed_fn=None):
            if collection == f"emb-{uuid1}":
                return chunks_col1
            if collection == f"emb-{uuid2}":
                return chunks_col2
            return []

        searcher.search = AsyncMock(side_effect=_search)
        searcher.search_all_collections = AsyncMock(return_value=[])
        reranker.rerank = MagicMock(side_effect=lambda q, c, top_k: c)

        tools = create_research_tools(searcher, reranker, parent_store)
        tool = next(t for t in tools if t.name == "semantic_search_all_collections")

        token = selected_collections_var.set([uuid1, uuid2])
        try:
            result = await tool.ainvoke({"query": "diámetro mínimo NAG-200", "top_k": 10})
        finally:
            selected_collections_var.reset(token)

        # Exactly 2 search() calls — one per authorized UUID
        assert searcher.search.await_count == 2, f"Expected 2 scoped search() calls, got {searcher.search.await_count}"
        call_collections = {call.args[1] for call in searcher.search.await_args_list}
        assert call_collections == {f"emb-{uuid1}", f"emb-{uuid2}"}
        # search_all_collections must NEVER fire when allowlist is present
        searcher.search_all_collections.assert_not_awaited()
        # Both collection's chunks surfaced in result
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_unscoped_falls_through_to_search_all(self, mock_deps):
        """spec-28 BUG-002 amendment: no allowlist in context → search_all_collections called,
        search() NOT called (unscoped admin/dev fallback preserved)."""
        searcher, reranker, parent_store = mock_deps
        chunks = [_chunk(collection="col1")]
        searcher.search_all_collections = AsyncMock(return_value=chunks)
        searcher.search = AsyncMock(return_value=[])
        reranker.rerank = MagicMock(side_effect=lambda q, c, top_k: c)

        tools = create_research_tools(searcher, reranker, parent_store)
        tool = next(t for t in tools if t.name == "semantic_search_all_collections")

        # Do NOT set selected_collections_var — default is []
        result = await tool.ainvoke({"query": "test", "top_k": 5})

        searcher.search_all_collections.assert_awaited_once()
        searcher.search.assert_not_awaited()
        assert result == chunks
