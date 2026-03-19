# Agent: A7-integration-tests

**subagent_type**: quality-engineer | **Model**: Sonnet 4.6 | **Wave**: 3 (after A5 + A6 complete)

## Mission

Write integration tests for the accuracy, precision and robustness features: end-to-end GAV flow, citation alignment validation, query-adaptive retrieval depth, and circuit breaker behavior. These tests verify that all user stories work together in the full pipeline.

## Context Files (Read FIRST)

1. `Docs/PROMPTS/spec-05-accuracy/05-implement.md` -- code specs (verify expected behavior)
2. `backend/agent/nodes.py` -- `verify_groundedness`, `validate_citations`, `rewrite_query`, `TIER_PARAMS`, inference CB functions
3. `backend/agent/schemas.py` -- `GroundednessResult`, `ClaimVerification`, `QueryAnalysis`, `SubAnswer`, `Citation`, `RetrievedChunk`
4. `backend/storage/qdrant_client.py` -- `QdrantClientWrapper` with circuit breaker
5. `backend/api/chat.py` -- NDJSON streaming with groundedness metadata + error frames
6. `backend/agent/state.py` -- `ConversationState` TypedDict
7. `backend/config.py` -- all accuracy/robustness settings
8. `backend/errors.py` -- `CircuitOpenError`
9. `tests/integration/test_research_graph.py` -- reference for integration test patterns
10. `specs/005-accuracy-robustness/spec.md` -- acceptance scenarios for all user stories
11. `specs/005-accuracy-robustness/contracts/sse-events.md` -- NDJSON metadata frame contract

## Assigned Tasks

- T035: Add end-to-end GAV flow integration test in `tests/integration/test_accuracy_integration.py`: submit query against test state where answer includes one supported, one unsupported, one contradicted claim; mock LLM to return structured `GroundednessResult` with these verdicts; verify final response contains `[unverified]` annotation on unsupported claim, contradicted claim is absent, and the metadata state has correct groundedness counts
- T036: [P] Add citation alignment integration test in `tests/integration/test_accuracy_integration.py`: create state with citation `[1]` pointing to an irrelevant chunk; mock reranker to score it below threshold and score an alternative chunk above threshold; run `validate_citations`; verify citation is remapped to the better chunk or stripped in the response
- T037: [P] Add query-adaptive retrieval depth integration test in `tests/integration/test_accuracy_integration.py`: mock LLM to classify a query as `factoid` and another as `multi_hop`; run `rewrite_query` for each; verify returned `retrieval_params` differ -- factoid has lower `top_k` and higher `confidence_threshold` than multi_hop
- T038: Add circuit breaker integration test in `tests/integration/test_accuracy_integration.py`: create a `QdrantClientWrapper`, mock the Qdrant client to fail 5 consecutive times; verify `CircuitOpenError` raised on 6th call without the mock being called again; simulate cooldown elapsed + mock recovery; verify next call succeeds and circuit closes
- T039: Run full integration suite: `zsh scripts/run-tests-external.sh -n spec05-integration tests/integration/test_accuracy_integration.py` -- poll `cat Docs/Tests/spec05-integration.status` until PASSED

## Files to Create/Modify

- MODIFY: `tests/integration/test_accuracy_integration.py` (fill in integration test bodies; scaffolding created by A1 in Wave 1)

## Key Patterns

### Async Tests

Use `@pytest.mark.asyncio` for all tests that call async node functions.

### Mock LLM for GAV (T035)

```python
mock_llm = AsyncMock()
mock_structured = AsyncMock()
mock_llm.with_structured_output.return_value = mock_structured
mock_structured.ainvoke.return_value = GroundednessResult(
    verifications=[
        ClaimVerification(claim="Claim A", verdict="supported", evidence_chunk_id="c1", explanation="Found"),
        ClaimVerification(claim="Claim B", verdict="unsupported", evidence_chunk_id=None, explanation="Missing"),
        ClaimVerification(claim="Claim C", verdict="contradicted", evidence_chunk_id="c2", explanation="Contradicts"),
    ],
    overall_grounded=True,  # 1/3 supported > 50%? No -- 1/3 < 50%, so overall_grounded=False
    confidence_adjustment=0.33,
)
```

### Build Test State

```python
state = {
    "session_id": "integration-test",
    "messages": [HumanMessage(content="test query")],
    "intent": "rag_query",
    "query_analysis": None,
    "sub_answers": [
        SubAnswer(
            sub_question="q1", answer="a1", citations=[],
            chunks=[
                RetrievedChunk(chunk_id="c1", text="Evidence for Claim A",
                              source_file="f.pdf", breadcrumb="b", parent_id="p1",
                              collection="col1", dense_score=0.5, sparse_score=0.3),
                RetrievedChunk(chunk_id="c2", text="Contradicts Claim C",
                              source_file="g.pdf", breadcrumb="b", parent_id="p2",
                              collection="col1", dense_score=0.4, sparse_score=0.2),
            ],
            confidence_score=80,
        ),
    ],
    "selected_collections": ["col1"],
    "llm_model": "test-model",
    "embed_model": "test-embed",
    "final_response": "Claim A is true. Claim B is also true. Claim C is correct.",
    "citations": [],
    "groundedness_result": None,
    "confidence_score": 0,
    "iteration_count": 0,
}
```

### Mock Reranker for Citation Tests (T036)

```python
mock_reranker = MagicMock()
mock_reranker.model = MagicMock()
# First call: original citation scores below threshold
# Second call: score all chunks, find better alternative
mock_reranker.model.rank.side_effect = [
    [{"corpus_id": 0, "score": 0.1}],                    # original citation
    [{"corpus_id": 0, "score": 0.9}, {"corpus_id": 1, "score": 0.15}],  # all chunks
]
```

### Circuit Breaker Test (T038)

```python
import time
from unittest.mock import AsyncMock, MagicMock, patch
from backend.storage.qdrant_client import QdrantClientWrapper
from backend.errors import CircuitOpenError

@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_5_failures():
    wrapper = QdrantClientWrapper("localhost", 6333)
    wrapper.client = AsyncMock()
    wrapper.client.search.side_effect = Exception("Qdrant down")

    # Fail 5 times
    for _ in range(5):
        with pytest.raises(Exception):
            await wrapper.search("col", [0.1, 0.2], limit=5)

    # 6th call should raise CircuitOpenError without calling Qdrant
    wrapper.client.search.reset_mock()
    with pytest.raises(CircuitOpenError):
        await wrapper.search("col", [0.1, 0.2], limit=5)
    wrapper.client.search.assert_not_called()  # CB rejected before Qdrant call

    # Simulate cooldown elapsed
    wrapper._last_failure_time = time.monotonic() - 31  # 31s ago
    # Next call should be allowed (half-open probe)
    wrapper.client.search.side_effect = None  # success
    wrapper.client.search.return_value = []
    result = await wrapper.search("col", [0.1, 0.2], limit=5)
    assert wrapper._circuit_open is False
    assert wrapper._failure_count == 0
```

### Retrieval Depth Test (T037)

```python
@pytest.mark.asyncio
async def test_factoid_vs_multihop_retrieval_params():
    mock_llm = AsyncMock()
    mock_structured = AsyncMock()
    mock_llm.with_structured_output.return_value = mock_structured

    # Factoid query
    mock_structured.ainvoke.return_value = QueryAnalysis(
        is_clear=True, sub_questions=["What version?"],
        complexity_tier="factoid", collections_hint=[], clarification_needed=None,
    )
    state = {"session_id": "t", "messages": [HumanMessage(content="What version?")],
             "selected_collections": ["col1"]}
    factoid_result = await rewrite_query(state, llm=mock_llm)

    # Multi-hop query
    mock_structured.ainvoke.return_value = QueryAnalysis(
        is_clear=True, sub_questions=["Compare A and B across C"],
        complexity_tier="multi_hop", collections_hint=[], clarification_needed=None,
    )
    state["messages"] = [HumanMessage(content="Compare A and B across C")]
    multihop_result = await rewrite_query(state, llm=mock_llm)

    assert factoid_result["retrieval_params"]["top_k"] < multihop_result["retrieval_params"]["top_k"]
    assert factoid_result["retrieval_params"]["confidence_threshold"] > multihop_result["retrieval_params"]["confidence_threshold"]
```

## Constraints

- NEVER run pytest inside Claude Code. Use: `zsh scripts/run-tests-external.sh -n <name> <target>`
- NEVER modify implementation files -- only modify the test file
- Integration tests should exercise real function calls with mocked external dependencies (LLM, Reranker, Qdrant)
- Use `monkeypatch.setenv()` or `monkeypatch.setattr()` for settings overrides, NOT `os.environ[]`
- Mock external dependencies (LLM, Reranker, Qdrant client) but let the application code run for real
- Test names should be descriptive: `test_gav_annotates_unsupported_and_removes_contradicted`, `test_citation_below_threshold_remapped`, `test_circuit_opens_after_threshold_failures`
- Import `from langchain_core.messages import HumanMessage` for building test state messages
- Use `from unittest.mock import AsyncMock, MagicMock` for mocks

## Checkpoint

All integration tests created and importable. Tests cover GAV flow, citation validation, retrieval depth, and circuit breaker. Running the following shows test count:
```bash
python -c "import tests.integration.test_accuracy_integration; print('imports OK')"
ruff check tests/integration/test_accuracy_integration.py
```
