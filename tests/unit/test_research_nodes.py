"""Unit tests for ResearchGraph node functions."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.agent.research_nodes import (
    collect_answer,
    compress_context,
    dedup_key,
    fallback_response,
    normalize_query,
    orchestrator,
    should_compress_context,
    tools_node,
)
from backend.agent.schemas import RetrievedChunk


def _chunk(
    chunk_id="c1",
    text="test text",
    rerank_score=0.8,
    dense_score=0.5,
    collection="col1",
    parent_id="p1",
    source_file="test.md",
):
    return RetrievedChunk(
        chunk_id=chunk_id,
        text=text,
        source_file=source_file,
        breadcrumb="ch1",
        parent_id=parent_id,
        collection=collection,
        dense_score=dense_score,
        sparse_score=0.3,
        rerank_score=rerank_score,
    )


def _make_state(**overrides):
    base = {
        "sub_question": "What is X?",
        "session_id": "test-session",
        "selected_collections": ["col1"],
        "llm_model": "qwen2.5:7b",
        "embed_model": "nomic-embed-text",
        "retrieved_chunks": [],
        "retrieval_keys": set(),
        "tool_call_count": 0,
        "iteration_count": 0,
        "confidence_score": 0.0,
        "answer": None,
        "citations": [],
        "context_compressed": False,
        "messages": [],
        "_no_new_tools": False,
        "_needs_compression": False,
    }
    base.update(overrides)
    return base


class TestNormalizeQuery:
    def test_lowercases(self):
        assert normalize_query("Hello World") == "hello world"

    def test_strips_whitespace(self):
        assert normalize_query("  hello  ") == "hello"

    def test_collapses_spaces(self):
        assert normalize_query("hello   world") == "hello world"

    def test_combined(self):
        assert normalize_query("  Hello   World  ") == "hello world"


class TestDedupKey:
    def test_format(self):
        assert dedup_key("Hello World", "p1") == "hello world:p1"

    def test_normalization_applied(self):
        assert dedup_key("  HELLO  ", "p1") == "hello:p1"


class TestOrchestrator:
    @pytest.mark.asyncio
    async def test_increments_iteration_count(self):
        state = _make_state(iteration_count=3)
        result = await orchestrator(state, config=None)
        assert result["iteration_count"] == 4

    @pytest.mark.asyncio
    async def test_sets_no_new_tools_when_no_llm(self):
        """When no LLM in config, sets _no_new_tools=True"""
        state = _make_state()
        result = await orchestrator(state, config=None)
        assert result["_no_new_tools"] is True

    @pytest.mark.asyncio
    async def test_with_mock_llm_returning_tool_calls(self):
        mock_response = MagicMock()
        mock_response.tool_calls = [
            {"name": "search_child_chunks", "args": {"query": "test", "collection": "col1"}, "id": "call_1"}
        ]

        mock_llm = AsyncMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = _make_state()
        config = {"configurable": {"llm": mock_llm, "tools": []}}
        result = await orchestrator(state, config=config)

        assert result["iteration_count"] == 1
        assert result["_no_new_tools"] is False
        assert len(result["messages"]) == 1

    @pytest.mark.asyncio
    async def test_sets_no_new_tools_when_llm_returns_no_tool_calls(self):
        mock_response = MagicMock()
        mock_response.tool_calls = []

        mock_llm = AsyncMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = _make_state()
        config = {"configurable": {"llm": mock_llm, "tools": []}}
        result = await orchestrator(state, config=config)

        assert result["_no_new_tools"] is True


class TestToolsNode:
    @pytest.mark.asyncio
    async def test_no_messages_returns_unchanged(self):
        state = _make_state(messages=[])
        result = await tools_node(state, config=None)
        assert result["tool_call_count"] == 0

    @pytest.mark.asyncio
    async def test_executes_tool_and_deduplicates(self):
        chunk1 = _chunk(chunk_id="c1", parent_id="p1")
        chunk2 = _chunk(chunk_id="c2", parent_id="p1")  # Same parent_id

        mock_tool = AsyncMock()
        mock_tool.name = "search_child_chunks"
        mock_tool.ainvoke = AsyncMock(return_value=[chunk1, chunk2])

        mock_ai_msg = MagicMock()
        mock_ai_msg.tool_calls = [{"name": "search_child_chunks", "args": {"query": "test"}, "id": "call_1"}]

        state = _make_state(messages=[mock_ai_msg])
        config = {"configurable": {"tools": [mock_tool]}}
        result = await tools_node(state, config=config)

        assert result["tool_call_count"] == 1
        # Both chunks have same dedup key (same query + parent_id), so only 1 kept
        assert len(result["retrieved_chunks"]) == 1

    @pytest.mark.asyncio
    async def test_retry_once_on_failure(self):
        """FR-016: retry once, both attempts count against budget"""
        chunk = _chunk()

        mock_tool = AsyncMock()
        mock_tool.name = "search_child_chunks"
        mock_tool.ainvoke = AsyncMock(side_effect=[Exception("fail"), [chunk]])

        mock_ai_msg = MagicMock()
        mock_ai_msg.tool_calls = [{"name": "search_child_chunks", "args": {"query": "test"}, "id": "call_1"}]

        state = _make_state(messages=[mock_ai_msg])
        config = {"configurable": {"tools": [mock_tool]}}
        result = await tools_node(state, config=config)

        # Original attempt (1) + retry (1) = 2
        assert result["tool_call_count"] == 2
        assert len(result["retrieved_chunks"]) == 1

    @pytest.mark.asyncio
    async def test_unknown_tool_skipped(self):
        mock_ai_msg = MagicMock()
        mock_ai_msg.tool_calls = [{"name": "nonexistent_tool", "args": {}, "id": "call_1"}]

        state = _make_state(messages=[mock_ai_msg])
        config = {"configurable": {"tools": []}}
        result = await tools_node(state, config=config)

        assert result["tool_call_count"] == 0


class TestRerankScoreUpdate:
    """spec-28 BUG-006 regression tests — cross_encoder_rerank special-cased in dedup loop.

    Before the fix, reranked chunks were deduplicated by (query, parent_id) against
    their own pre-rerank selves, zeroing out citations on ~75% of queries.
    After the fix, the rerank tool updates rerank_score in-place on existing new_chunks.
    """

    @pytest.mark.asyncio
    async def test_rerank_updates_score_on_existing_chunks(self):
        """spec-28 BUG-006: search→rerank in same batch → 3 chunks survive, scores updated."""
        chunk_a = _chunk(chunk_id="a", parent_id="p1", rerank_score=None)
        chunk_b = _chunk(chunk_id="b", parent_id="p2", rerank_score=None)
        chunk_c = _chunk(chunk_id="c", parent_id="p3", rerank_score=None)

        reranked_a = _chunk(chunk_id="a", parent_id="p1", rerank_score=0.8)
        reranked_b = _chunk(chunk_id="b", parent_id="p2", rerank_score=0.5)
        reranked_c = _chunk(chunk_id="c", parent_id="p3", rerank_score=0.2)

        mock_search = AsyncMock()
        mock_search.name = "search_child_chunks"
        mock_search.ainvoke = AsyncMock(return_value=[chunk_a, chunk_b, chunk_c])

        mock_rerank = AsyncMock()
        mock_rerank.name = "cross_encoder_rerank"
        mock_rerank.ainvoke = AsyncMock(return_value=[reranked_a, reranked_b, reranked_c])

        mock_ai_msg = MagicMock()
        mock_ai_msg.tool_calls = [
            {"name": "search_child_chunks", "args": {"query": "test"}, "id": "call_1"},
            {"name": "cross_encoder_rerank", "args": {"query": "test", "chunks": []}, "id": "call_2"},
        ]

        state = _make_state(messages=[mock_ai_msg])
        config = {"configurable": {"tools": [mock_search, mock_rerank]}}
        result = await tools_node(state, config=config)

        # BUG-006: chunks must NOT be discarded as duplicates
        assert len(result["retrieved_chunks"]) == 3, (
            f"Expected 3 chunks (BUG-006: rerank was zeroing out all), got {len(result['retrieved_chunks'])}"
        )
        scores = {c.chunk_id: c.rerank_score for c in result["retrieved_chunks"]}
        assert scores == {"a": 0.8, "b": 0.5, "c": 0.2}, f"Unexpected scores: {scores}"

    @pytest.mark.asyncio
    async def test_rerank_skipped_no_match_when_chunk_not_in_state(self):
        """Rerank returns chunk 'z' not in search results → 'a' unchanged, 'z' silently skipped."""
        chunk_a = _chunk(chunk_id="a", parent_id="p1", rerank_score=None)
        chunk_z_reranked = _chunk(chunk_id="z", parent_id="p99", rerank_score=0.9)

        mock_search = AsyncMock()
        mock_search.name = "search_child_chunks"
        mock_search.ainvoke = AsyncMock(return_value=[chunk_a])

        mock_rerank = AsyncMock()
        mock_rerank.name = "cross_encoder_rerank"
        mock_rerank.ainvoke = AsyncMock(return_value=[chunk_z_reranked])

        mock_ai_msg = MagicMock()
        mock_ai_msg.tool_calls = [
            {"name": "search_child_chunks", "args": {"query": "test"}, "id": "call_1"},
            {"name": "cross_encoder_rerank", "args": {"query": "test", "chunks": []}, "id": "call_2"},
        ]

        state = _make_state(messages=[mock_ai_msg])
        config = {"configurable": {"tools": [mock_search, mock_rerank]}}
        result = await tools_node(state, config=config)

        assert len(result["retrieved_chunks"]) == 1
        assert result["retrieved_chunks"][0].chunk_id == "a"
        assert result["retrieved_chunks"][0].rerank_score is None  # not updated (no match)

    @pytest.mark.asyncio
    async def test_search_tool_dedup_unchanged_for_non_rerank_tools(self):
        """Non-rerank tools still use dedup-by-(query, parent_id) — regression guard."""
        chunk1 = _chunk(chunk_id="c1", parent_id="p1")
        chunk2 = _chunk(chunk_id="c2", parent_id="p1")  # Same parent_id → deduped out

        mock_tool = AsyncMock()
        mock_tool.name = "search_child_chunks"
        mock_tool.ainvoke = AsyncMock(return_value=[chunk1, chunk2])

        mock_ai_msg = MagicMock()
        mock_ai_msg.tool_calls = [
            {"name": "search_child_chunks", "args": {"query": "test"}, "id": "call_1"},
        ]

        state = _make_state(messages=[mock_ai_msg])
        config = {"configurable": {"tools": [mock_tool]}}
        result = await tools_node(state, config=config)

        # Dedup by (query, parent_id) still removes the second chunk
        assert len(result["retrieved_chunks"]) == 1


class TestShouldCompressContext:
    @pytest.mark.asyncio
    async def test_no_compression_needed_with_small_context(self):
        state = _make_state(retrieved_chunks=[_chunk(text="short")])
        result = await should_compress_context(state)
        assert result["_needs_compression"] is False

    @pytest.mark.asyncio
    async def test_compression_needed_with_large_context(self):
        # Create chunks with very large text to exceed threshold
        big_chunks = [_chunk(text="x" * 50000, chunk_id=f"c{i}") for i in range(10)]
        state = _make_state(retrieved_chunks=big_chunks)
        result = await should_compress_context(state)
        assert result["_needs_compression"] is True


class TestCompressContext:
    @pytest.mark.asyncio
    async def test_skips_compression_without_llm(self):
        state = _make_state(retrieved_chunks=[_chunk()])
        result = await compress_context(state, config=None)
        assert result == {}

    @pytest.mark.asyncio
    async def test_compresses_with_llm(self):
        mock_response = MagicMock()
        mock_response.content = "Compressed summary of retrieved passages."

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        chunks = [_chunk(chunk_id=f"c{i}") for i in range(3)]
        state = _make_state(retrieved_chunks=chunks)
        config = {"configurable": {"llm": mock_llm}}

        result = await compress_context(state, config=config)
        assert result["context_compressed"] is True
        assert len(result["retrieved_chunks"]) == 1
        assert result["retrieved_chunks"][0].text == "Compressed summary of retrieved passages."

    @pytest.mark.asyncio
    async def test_skips_on_llm_failure(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM down"))

        state = _make_state(retrieved_chunks=[_chunk()])
        config = {"configurable": {"llm": mock_llm}}

        result = await compress_context(state, config=config)
        assert result == {}


class TestCollectAnswer:
    @pytest.mark.asyncio
    async def test_computes_confidence_from_chunks(self):
        # spec-26: FR-003 BUG-010 — confidence unified to int 0-100 across writers (commit 4d1f421)
        chunks = [_chunk(rerank_score=0.9, chunk_id=f"c{i}") for i in range(3)]
        state = _make_state(retrieved_chunks=chunks)
        result = await collect_answer(state, config=None)
        assert isinstance(result["confidence_score"], int)
        assert 0 <= result["confidence_score"] <= 100

    @pytest.mark.asyncio
    async def test_returns_answer_text(self):
        chunks = [_chunk(rerank_score=0.8)]
        state = _make_state(retrieved_chunks=chunks)
        result = await collect_answer(state, config=None)
        # Production writes answer into sub_answers[-1].answer, not result["answer"]
        assert result["sub_answers"] and len(result["sub_answers"]) > 0
        assert result["sub_answers"][-1].answer is not None
        assert len(result["sub_answers"][-1].answer) > 0

    @pytest.mark.asyncio
    async def test_returns_citations(self):
        chunks = [_chunk(rerank_score=0.8)]
        state = _make_state(retrieved_chunks=chunks)
        result = await collect_answer(state, config=None)
        assert "citations" in result

    @pytest.mark.asyncio
    async def test_empty_chunks_returns_zero_confidence(self):
        state = _make_state(retrieved_chunks=[])
        result = await collect_answer(state, config=None)
        assert result["confidence_score"] == 0.0


class TestFallbackResponse:
    @pytest.mark.asyncio
    async def test_zero_confidence(self):
        state = _make_state()
        result = await fallback_response(state)
        assert result["confidence_score"] == 0.0

    @pytest.mark.asyncio
    async def test_empty_citations(self):
        state = _make_state()
        result = await fallback_response(state)
        assert result["citations"] == []

    @pytest.mark.asyncio
    async def test_answer_mentions_sub_question(self):
        state = _make_state(sub_question="How does auth work?")
        result = await fallback_response(state)
        # Production writes answer into sub_answers[-1].answer
        assert "How does auth work?" in result["sub_answers"][-1].answer

    @pytest.mark.asyncio
    async def test_with_some_chunks_mentions_collection_count(self):
        chunks = [_chunk(collection="col1"), _chunk(collection="col2", chunk_id="c2")]
        state = _make_state(retrieved_chunks=chunks)
        result = await fallback_response(state)
        assert "2 collection(s)" in result["sub_answers"][-1].answer

    @pytest.mark.asyncio
    async def test_with_no_chunks(self):
        state = _make_state(retrieved_chunks=[])
        result = await fallback_response(state)
        assert "could not find" in result["sub_answers"][-1].answer.lower()


class _NonExceptionBaseError(BaseException):
    """Custom BaseException subclass that is NOT an Exception.

    Used in BUG-T4 tests to simulate BaseException from asyncio.gather
    without triggering pytest's KeyboardInterrupt / SystemExit handlers.
    """


class TestToolsNodeBaseExceptionHandling:
    """BUG-T4: asyncio.gather(return_exceptions=True) can return BaseException
    instances (e.g. KeyboardInterrupt, SystemExit). The original guard
    isinstance(outcome, Exception) does NOT catch BaseException subclasses that
    are not Exception subclasses, causing a TypeError when the code tries to
    unpack the outcome as a 4-tuple.
    """

    @pytest.mark.asyncio
    async def test_base_exception_is_handled_in_loop_not_via_outer_except(self):
        """BUG-T4: tools_node must handle BaseException from gather in the loop.

        With the buggy isinstance(outcome, Exception) guard:
          _NonExceptionBaseError passes the guard → TypeError at tuple-unpack
          → caught by outer except Exception → messages=[](empty)

        With the fix isinstance(outcome, BaseException):
          _NonExceptionBaseError IS caught in the loop → ToolMessage appended
          → messages=[ToolMessage(...)] (non-empty)
        """
        mock_tool = AsyncMock()
        mock_tool.name = "search_child_chunks"
        # Raise a BaseException that is NOT an Exception
        mock_tool.ainvoke = AsyncMock(side_effect=_NonExceptionBaseError("simulated"))

        mock_ai_msg = MagicMock()
        mock_ai_msg.tool_calls = [{"name": "search_child_chunks", "args": {"query": "test"}, "id": "call_1"}]

        state = _make_state(messages=[mock_ai_msg])
        config = {"configurable": {"tools": [mock_tool]}}

        result = await tools_node(state, config=config)

        # The exception path in the loop must be taken: a ToolMessage is appended.
        # With the buggy code, messages would be empty because TypeError is caught
        # by the outer except and the loop never finishes building tool_messages.
        assert isinstance(result, dict)
        assert len(result.get("messages", [])) == 1, (
            "Expected 1 ToolMessage for the failed tool call; "
            "got empty messages — indicates outer except caught TypeError instead of "
            "the loop handling the BaseException"
        )


# ---------------------------------------------------------------------------
# BUG-088 — the in-flight LLM deadline must reach the caller (RED)
#
# Production change that makes these pass: replace each `await ...ainvoke(...)`
# in research_nodes.py with `await invoke_with_deadline(...)` and place
# `except LLMDeadlineExceeded: raise` before the node's catch-all.
# ---------------------------------------------------------------------------

_DEADLINE_TEST_TIMEOUT = 0.05
_TEST_LEVEL_BUDGET = 2.0


class _HangingLLMCall:
    """Stands in for the object a node calls `ainvoke` on. Never resolves."""

    def __init__(self) -> None:
        self.cancelled = False
        self.started = False

    async def ainvoke(self, *_args, **_kwargs):
        import asyncio

        self.started = True
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise


class TestLLMDeadlinePropagation:
    """BUG-088: a stalled research LLM call must not outlive the deadline."""

    @pytest.mark.asyncio
    async def test_maybe_summarize_research_messages_propagates_the_deadline(self, monkeypatch):
        """research_nodes.py:64 — ENH-008 summarisation must run under the deadline."""
        import asyncio

        from langchain_core.messages import HumanMessage

        from backend.agent.research_nodes import _maybe_summarize_research_messages
        from backend.config import settings
        from backend.errors import LLMDeadlineExceeded

        monkeypatch.setattr(settings, "llm_call_timeout_seconds", _DEADLINE_TEST_TIMEOUT, raising=False)

        hang = _HangingLLMCall()
        messages = [HumanMessage(content=f"m{i}") for i in range(20)]

        with pytest.raises(LLMDeadlineExceeded):
            await asyncio.wait_for(
                _maybe_summarize_research_messages(messages, hang, MagicMock()),
                _TEST_LEVEL_BUDGET,
            )

        assert hang.cancelled, "the in-flight summarisation call must be cancelled"

    @pytest.mark.asyncio
    async def test_orchestrator_propagates_the_deadline(self, monkeypatch):
        """research_nodes.py:190 — the orchestrator tool-selection call must run under the deadline.

        The hang is installed on the llm's OWN `ainvoke`, not behind `bind_tools`:
        `research_nodes.py:164` is `llm_with_tools = llm.bind_tools(tools_list) if tools_list
        else llm`, so with the empty tool list this suite uses elsewhere `bind_tools` is never
        called and a `bind_tools`-only mock leaves the bare MagicMock to be awaited — its
        TypeError is swallowed by the node's fallback and the deadline is never reached.
        """
        import asyncio

        from backend.config import settings
        from backend.errors import LLMDeadlineExceeded

        monkeypatch.setattr(settings, "llm_call_timeout_seconds", _DEADLINE_TEST_TIMEOUT, raising=False)

        hang = _HangingLLMCall()
        llm = MagicMock()
        llm.ainvoke = hang.ainvoke

        state = _make_state()
        config = {"configurable": {"llm": llm, "tools": []}}

        with pytest.raises(LLMDeadlineExceeded):
            await asyncio.wait_for(orchestrator(state, config=config), _TEST_LEVEL_BUDGET)

        assert hang.cancelled, "the in-flight orchestrator call must be cancelled"

    @pytest.mark.asyncio
    async def test_compress_context_propagates_the_deadline(self, monkeypatch):
        """research_nodes.py:529 — context compression must run under the deadline."""
        import asyncio

        from backend.config import settings
        from backend.errors import LLMDeadlineExceeded

        monkeypatch.setattr(settings, "llm_call_timeout_seconds", _DEADLINE_TEST_TIMEOUT, raising=False)

        hang = _HangingLLMCall()
        state = _make_state(retrieved_chunks=[_chunk(chunk_id=f"c{i}") for i in range(3)])
        config = {"configurable": {"llm": hang}}

        with pytest.raises(LLMDeadlineExceeded):
            await asyncio.wait_for(compress_context(state, config=config), _TEST_LEVEL_BUDGET)

        assert hang.cancelled, "the in-flight compress_context call must be cancelled"

    @pytest.mark.asyncio
    async def test_collect_answer_propagates_the_deadline(self, monkeypatch):
        """research_nodes.py:686 — answer synthesis must run under the deadline."""
        import asyncio

        from backend.config import settings
        from backend.errors import LLMDeadlineExceeded

        monkeypatch.setattr(settings, "llm_call_timeout_seconds", _DEADLINE_TEST_TIMEOUT, raising=False)

        hang = _HangingLLMCall()
        state = _make_state(retrieved_chunks=[_chunk(rerank_score=0.8)])
        config = {"configurable": {"llm": hang}}

        with pytest.raises(LLMDeadlineExceeded):
            await asyncio.wait_for(collect_answer(state, config=config), _TEST_LEVEL_BUDGET)

        assert hang.cancelled, "the in-flight collect_answer call must be cancelled"
