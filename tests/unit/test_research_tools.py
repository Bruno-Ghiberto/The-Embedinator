"""Unit tests for ResearchGraph tool factory (spec-03)."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.agent.schemas import ParentChunk, RetrievedChunk
from backend.agent.tools import create_research_tools


def _chunk(chunk_id="c1", rerank_score=0.8, dense_score=0.5, collection="col1"):
    return RetrievedChunk(
        chunk_id=chunk_id, text="test text", source_file="test.md",
        breadcrumb="ch1", parent_id="p1", collection=collection,
        dense_score=dense_score, sparse_score=0.3, rerank_score=rerank_score,
    )


def _parent(parent_id="p1"):
    return ParentChunk(
        parent_id=parent_id, text="parent text", source_file="test.md",
        breadcrumb="ch1", collection="col1",
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
        searcher, reranker, parent_store = mock_deps
        chunks = [_chunk()]
        searcher.search = AsyncMock(return_value=chunks)
        reranker.rerank = MagicMock(return_value=chunks)

        tools = create_research_tools(searcher, reranker, parent_store)
        search_tool = next(t for t in tools if t.name == "search_child_chunks")

        result = await search_tool.ainvoke({
            "query": "test", "collection": "col1", "top_k": 20
        })

        searcher.search.assert_awaited_once()
        reranker.rerank.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_rerank_on_empty_results(self, mock_deps):
        searcher, reranker, parent_store = mock_deps
        searcher.search = AsyncMock(return_value=[])

        tools = create_research_tools(searcher, reranker, parent_store)
        search_tool = next(t for t in tools if t.name == "search_child_chunks")

        result = await search_tool.ainvoke({
            "query": "test", "collection": "col1"
        })

        reranker.rerank.assert_not_called()


class TestRetrieveParentChunks:
    @pytest.mark.asyncio
    async def test_calls_parent_store(self, mock_deps):
        searcher, reranker, parent_store = mock_deps
        parents = [_parent()]
        parent_store.get_by_ids = AsyncMock(return_value=parents)

        tools = create_research_tools(searcher, reranker, parent_store)
        tool = next(t for t in tools if t.name == "retrieve_parent_chunks")

        result = await tool.ainvoke({"parent_ids": ["p1"]})
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
        searcher, reranker, parent_store = mock_deps
        chunks = [_chunk(collection="col1"), _chunk(chunk_id="c2", collection="col2")]
        searcher.search_all_collections = AsyncMock(return_value=chunks)
        reranker.rerank = MagicMock(return_value=chunks)

        tools = create_research_tools(searcher, reranker, parent_store)
        tool = next(t for t in tools if t.name == "semantic_search_all_collections")

        result = await tool.ainvoke({"query": "test", "top_k": 10})

        searcher.search_all_collections.assert_awaited_once()
        reranker.rerank.assert_called_once()
