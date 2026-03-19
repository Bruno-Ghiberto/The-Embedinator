# Agent: A2-verify-groundedness

**subagent_type**: python-expert | **Model**: Opus 4.6 | **Wave**: 2

## Mission

Implement the `verify_groundedness` node body and `_apply_groundedness_annotations` helper in `backend/agent/nodes.py`. This is the Grounded Answer Verification (GAV) system -- the core trust signal for the RAG pipeline. The node evaluates every factual claim in a generated answer against retrieved context via a structured LLM call, annotates unsupported claims, removes contradicted claims, and computes a GAV-adjusted confidence score.

## Context Files (Read FIRST)

1. `Docs/PROMPTS/spec-05-accuracy/05-implement.md` -- code specs (authoritative reference for function bodies)
2. `backend/agent/nodes.py` -- existing stub at lines 354-357 (replace with full implementation)
3. `backend/agent/schemas.py` -- `GroundednessResult`, `ClaimVerification`, `SubAnswer` models (use as-is, DO NOT modify)
4. `backend/agent/prompts.py` -- `VERIFY_PROMPT` constant (added by A1 in Wave 1)
5. `backend/agent/state.py` -- `ConversationState` TypedDict (has `groundedness_result`, `confidence_score`, `sub_answers`, `final_response`)
6. `backend/config.py` -- `settings.groundedness_check_enabled` (bool, default True)
7. `specs/005-accuracy-robustness/spec.md` -- US1 acceptance scenarios
8. `specs/005-accuracy-robustness/plan.md` -- verify_groundedness design summary
9. `specs/005-accuracy-robustness/data-model.md` -- GroundednessResult lifecycle, confidence adjustment formula

## Assigned Tasks

- T008: [P] Add `_apply_groundedness_annotations(response: str, result: GroundednessResult) -> str` helper in `backend/agent/nodes.py` -- appends `[unverified]` to UNSUPPORTED claims, removes CONTRADICTED claims with a brief explanation, and prepends a warning banner when >50% of claims are unsupported
- T009: Implement `verify_groundedness` node body in `backend/agent/nodes.py` (replaces stub at lines 354-357): (1) guard on `settings.groundedness_check_enabled`; (2) build context string from `state["sub_answers"]` chunk texts; (3) low-temperature `llm.with_structured_output(GroundednessResult)` call with `VERIFY_PROMPT`; (4) call `_apply_groundedness_annotations`; (5) compute `int(mean(sub_scores) * result.confidence_adjustment)` clamped 0-100; (6) return partial dict; (7) catch all exceptions -> return `{"groundedness_result": None}` + log warning
- T010: Add unit tests for `_apply_groundedness_annotations` in `tests/unit/test_accuracy_nodes.py`: supported claim unchanged, unsupported claim gets `[unverified]`, contradicted claim removed, >50% unsupported triggers warning banner, 0% unsupported no banner
- T011: Add unit tests for `verify_groundedness` node in `tests/unit/test_accuracy_nodes.py`: `groundedness_check_enabled=False` returns None immediately; structured LLM success returns annotated response + adjusted confidence; LLM raises exception returns None (graceful degradation); empty sub_answers returns None
- T012: Run US1 unit tests: `zsh scripts/run-tests-external.sh -n spec05-us1 --no-cov tests/unit/test_accuracy_nodes.py` -- poll `cat Docs/Tests/spec05-us1.status` until PASSED

## Files to Create/Modify

- MODIFY: `backend/agent/nodes.py` (add `_apply_groundedness_annotations` helper, replace `verify_groundedness` stub with full implementation)
- MODIFY: `tests/unit/test_accuracy_nodes.py` (fill in `TestVerifyGroundedness` test class)

## Key Patterns

- **Function signature**: `async def verify_groundedness(state: ConversationState, *, llm: Any = None) -> dict:` -- keep the existing `*, llm` keyword arg pattern. Do NOT change to config DI.
- **Structured output**: `llm.with_structured_output(GroundednessResult)` -- this is a LangChain pattern that instructs the LLM to return a Pydantic model. The LLM call returns a `GroundednessResult` instance directly.
- **VERIFY_PROMPT**: Format with `VERIFY_PROMPT.format(context=context, answer=final_response)`. Invoke via `await structured_llm.ainvoke(prompt)`.
- **Confidence adjustment formula**: `int(mean(sub_answer.confidence_score for sa in sub_answers) * result.confidence_adjustment)`, clamped to [0, 100]. `SubAnswer.confidence_score` is an int 0-100. `confidence_adjustment` is a float 0.0-1.0.
- **Return partial dict**: `return {"groundedness_result": result, "confidence_score": adjusted, "final_response": annotated}` -- NOT `{**state, ...}`.
- **Graceful degradation (FR-005)**: On ANY exception in the LLM call, return `{"groundedness_result": None}` and log warning. Never block answer delivery.
- **Inference circuit breaker**: Call `_check_inference_circuit()` before the LLM call and `_record_inference_success()` after. On exception, call `_record_inference_failure()`. These functions are added by A5 in Wave 3 -- but you can reference them now since A5 adds them as module-level functions in the same file. If they don't exist yet (Wave 2), wrap the calls in `try: _check_inference_circuit() except NameError: pass`.
- **Annotations helper**: `_apply_groundedness_annotations` is a sync function (not async). It modifies the response string in-place by replacing claim text. Use `str.replace(claim, new_text, 1)` to replace only the first occurrence.
- **Warning banner**: When `result.overall_grounded` is False (>50% unsupported), prepend a warning banner to the response.

## CRITICAL: Shared File with A3 and A4

A1 (Wave 1) ensures the file is in its current state. You (A2) add `_apply_groundedness_annotations` and replace the `verify_groundedness` stub. A3 (running in parallel) adds `_extract_claim_for_citation` and replaces the `validate_citations` stub. A4 (running in parallel) adds `TIER_PARAMS` and extends `rewrite_query`. You all work on DIFFERENT functions in the SAME file. Do NOT touch:
- `validate_citations` (A3's responsibility)
- `_extract_claim_for_citation` (A3's responsibility)
- `TIER_PARAMS` (A4's responsibility)
- `rewrite_query` (A4's responsibility)
- Any other existing functions

## Test Patterns

```python
# Mock LLM for structured output:
mock_llm = AsyncMock()
mock_structured = AsyncMock()
mock_llm.with_structured_output.return_value = mock_structured
mock_structured.ainvoke.return_value = GroundednessResult(
    verifications=[
        ClaimVerification(claim="Claim A", verdict="supported", evidence_chunk_id="c1", explanation="Found in context"),
        ClaimVerification(claim="Claim B", verdict="unsupported", evidence_chunk_id=None, explanation="Not in context"),
    ],
    overall_grounded=True,
    confidence_adjustment=0.8,
)

# Build test state:
state = {
    "session_id": "test-123",
    "final_response": "Claim A is true. Claim B is also true.",
    "sub_answers": [
        SubAnswer(sub_question="q1", answer="a1", citations=[], chunks=[
            RetrievedChunk(chunk_id="c1", text="Evidence for Claim A", source_file="f.pdf",
                          breadcrumb="b", parent_id="p1", collection="col1",
                          dense_score=0.5, sparse_score=0.3)
        ], confidence_score=80),
    ],
    "groundedness_result": None,
    "confidence_score": 0,
}

# Test disabled check:
with monkeypatch.context() as m:
    m.setattr("backend.agent.nodes.settings.groundedness_check_enabled", False)
    result = await verify_groundedness(state, llm=mock_llm)
    assert result["groundedness_result"] is None
```

## Constraints

- NEVER run pytest inside Claude Code. Use: `zsh scripts/run-tests-external.sh -n <name> <target>`
- NEVER touch `validate_citations`, `rewrite_query`, `TIER_PARAMS`, or any function outside your scope
- NEVER modify `schemas.py`, `state.py`, `config.py`, `confidence.py`, or `conversation_graph.py`
- NEVER use LLM self-assessment for confidence -- the base score comes from `SubAnswer.confidence_score` (retrieval signals from spec-03 R8), and `confidence_adjustment` is a mechanical ratio of verdict counts
- `_apply_groundedness_annotations` is a regular sync function, NOT async
- Place `_apply_groundedness_annotations` BEFORE `verify_groundedness` in the file (helper before consumer)
- Use `monkeypatch.setattr()` or `monkeypatch.setenv()` for settings overrides in tests, NOT `os.environ[]`
- Place the `import re` at the top of `nodes.py` if not already present (A3 also needs it)

## Checkpoint

`verify_groundedness` replaces the stub, `_apply_groundedness_annotations` is functional. Running the following succeeds:
```bash
python -c "from backend.agent.nodes import verify_groundedness, _apply_groundedness_annotations; print('OK')"
ruff check backend/agent/nodes.py
```
