# Agent: A4-tier-params-rewrite

**subagent_type**: python-expert | **Model**: Sonnet 4.6 | **Wave**: 2

## Mission

Add the `TIER_PARAMS` module-level constant to `backend/agent/nodes.py` and extend the existing `rewrite_query` function to look up tier-specific retrieval parameters and include them in the return dict. This drives query-adaptive retrieval depth -- simple factoid queries use shallow retrieval while complex analytical queries use deep retrieval.

## Context Files (Read FIRST)

1. `Docs/PROMPTS/spec-05-accuracy/05-implement.md` -- code specs (authoritative reference for TIER_PARAMS values and rewrite_query extension)
2. `backend/agent/nodes.py` -- existing `rewrite_query` function (lines 160-243). Read the FULL function body carefully.
3. `backend/agent/schemas.py` -- `QueryAnalysis` model (lines 15-22) with `complexity_tier: Literal["factoid","lookup","comparison","analytical","multi_hop"]`
4. `specs/005-accuracy-robustness/spec.md` -- US4 acceptance scenarios
5. `specs/005-accuracy-robustness/research.md` -- R4: TIER_PARAMS placement decision
6. `specs/005-accuracy-robustness/data-model.md` -- ComplexityTier values and parameter table

## Assigned Tasks

- T022: Add `TIER_PARAMS: dict[str, dict]` module-level constant to `backend/agent/nodes.py` with exactly 5 entries: `factoid` (top_k=5, max_iterations=3, max_tool_calls=3, confidence_threshold=0.7), `lookup` (top_k=10, max_iterations=5, max_tool_calls=5, confidence_threshold=0.6), `comparison` (top_k=15, max_iterations=7, max_tool_calls=6, confidence_threshold=0.55), `analytical` (top_k=25, max_iterations=10, max_tool_calls=8, confidence_threshold=0.5), `multi_hop` (top_k=30, max_iterations=10, max_tool_calls=8, confidence_threshold=0.45)
- T023: Extend `rewrite_query` in `backend/agent/nodes.py`: after EACH successful `analysis = await structured_llm.ainvoke(...)` return point, look up `tier_params = TIER_PARAMS.get(analysis.complexity_tier, TIER_PARAMS["lookup"])` and include `"retrieval_params": tier_params` in the returned state dict. Also add it to the fallback return. There are THREE return points in rewrite_query -- ALL three must include `retrieval_params`.
- T024: Add unit tests for `TIER_PARAMS` and `rewrite_query` tier lookup in `tests/unit/test_accuracy_nodes.py`: all 5 tiers present in dict; `factoid` has the shallowest config (lowest top_k); `multi_hop` has deepest config (highest top_k, lowest confidence_threshold); `rewrite_query` returns `retrieval_params` key populated from `TIER_PARAMS` for all 5 tiers
- T025: Run US4 unit tests: `zsh scripts/run-tests-external.sh -n spec05-us4 --no-cov tests/unit/test_accuracy_nodes.py` -- poll `cat Docs/Tests/spec05-us4.status` until PASSED

## Files to Create/Modify

- MODIFY: `backend/agent/nodes.py` (add `TIER_PARAMS` constant, extend `rewrite_query` at all 3 return points)
- MODIFY: `tests/unit/test_accuracy_nodes.py` (fill in `TestTierParams` test class)

## Key Patterns

- **TIER_PARAMS placement**: Module-level constant, placed near the top of `nodes.py` after existing constants like `MODEL_CONTEXT_WINDOWS`.
- **rewrite_query has THREE return points**:
  1. First successful attempt (around line 210): `return {"query_analysis": analysis}` -- change to `return {"query_analysis": analysis, "retrieval_params": tier_params}`
  2. Retry successful attempt (around line 228): `return {"query_analysis": analysis}` -- same change
  3. Fallback (around line 242): `return {"query_analysis": fallback}` -- `fallback.complexity_tier = "lookup"` so use `TIER_PARAMS["lookup"]`
- **Safe lookup**: `TIER_PARAMS.get(analysis.complexity_tier, TIER_PARAMS["lookup"])` -- the `Literal` type on `complexity_tier` enforces valid values, but `.get()` with default is a safety net.
- **tier_params passed via Send() config**: The `retrieval_params` dict is stored in ConversationState and used downstream by the fan-out/Send mechanism to configure ResearchGraph invocations. This spec only adds the dict to the return -- the downstream consumption is already handled.
- **Do NOT add retrieval_params to ConversationState TypedDict**: The field is carried in the state dict dynamically. LangGraph allows extra keys that are not in the TypedDict.

## CRITICAL: Shared File with A2 and A3

You (A4) add `TIER_PARAMS` constant and extend `rewrite_query`. A2 (running in parallel) adds `_apply_groundedness_annotations` and replaces `verify_groundedness`. A3 (running in parallel) adds `_extract_claim_for_citation` and replaces `validate_citations`. You all work on DIFFERENT functions in the SAME file. Do NOT touch:
- `verify_groundedness` (A2's responsibility)
- `_apply_groundedness_annotations` (A2's responsibility)
- `validate_citations` (A3's responsibility)
- `_extract_claim_for_citation` (A3's responsibility)
- Any other existing functions except `rewrite_query`

## CRITICAL: Extending rewrite_query, NOT Rewriting

You are EXTENDING the existing `rewrite_query` function. The function already has full retry + fallback logic (lines 160-243). Your ONLY changes are:
1. Add `tier_params = TIER_PARAMS.get(analysis.complexity_tier, TIER_PARAMS["lookup"])` line after each `analysis = await structured_llm.ainvoke(...)` line
2. Change each `return {"query_analysis": analysis}` to `return {"query_analysis": analysis, "retrieval_params": tier_params}`
3. Add the same for the fallback return

Do NOT rewrite the function body. Do NOT change the retry logic, simplified prompt, or fallback QueryAnalysis construction.

## Test Patterns

```python
# Test TIER_PARAMS structure:
def test_tier_params_has_all_five_tiers():
    assert set(TIER_PARAMS.keys()) == {"factoid", "lookup", "comparison", "analytical", "multi_hop"}

def test_factoid_shallowest():
    assert TIER_PARAMS["factoid"]["top_k"] == 5
    assert TIER_PARAMS["factoid"]["confidence_threshold"] == 0.7

def test_multi_hop_deepest():
    assert TIER_PARAMS["multi_hop"]["top_k"] == 30
    assert TIER_PARAMS["multi_hop"]["confidence_threshold"] == 0.45

# Test rewrite_query returns retrieval_params:
@pytest.mark.asyncio
async def test_rewrite_query_includes_retrieval_params():
    mock_llm = AsyncMock()
    mock_structured = AsyncMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_structured.ainvoke.return_value = QueryAnalysis(
        is_clear=True, sub_questions=["q1"], complexity_tier="analytical",
        collections_hint=[], clarification_needed=None,
    )

    state = {
        "session_id": "test", "messages": [HumanMessage(content="complex query")],
        "selected_collections": ["col1"],
    }

    result = await rewrite_query(state, llm=mock_llm)
    assert "retrieval_params" in result
    assert result["retrieval_params"]["top_k"] == 25  # analytical tier
```

## Constraints

- NEVER run pytest inside Claude Code. Use: `zsh scripts/run-tests-external.sh -n <name> <target>`
- NEVER rewrite rewrite_query -- only EXTEND it with tier_params lookup at each return point
- NEVER modify `schemas.py`, `state.py`, `config.py`, or `conversation_graph.py`
- NEVER touch `verify_groundedness`, `validate_citations`, or their helpers
- Place `TIER_PARAMS` near the top of nodes.py, after existing module-level constants (after `_DEFAULT_CONTEXT_WINDOW`)
- All 5 tier entries must have exactly 4 keys: `top_k`, `max_iterations`, `max_tool_calls`, `confidence_threshold`
- Use `monkeypatch` for settings in tests

## Checkpoint

`TIER_PARAMS` exists with 5 entries. `rewrite_query` returns `retrieval_params` in all code paths. Running the following succeeds:
```bash
python -c "from backend.agent.nodes import TIER_PARAMS; print(list(TIER_PARAMS.keys())); assert len(TIER_PARAMS) == 5"
ruff check backend/agent/nodes.py
```
