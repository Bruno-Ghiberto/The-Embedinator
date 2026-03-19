# Agent: A6-ndjson-metadata

**subagent_type**: python-expert | **Model**: Sonnet 4.6 | **Wave**: 3

## Mission

Update the NDJSON metadata frame in `backend/api/chat.py` to include the `groundedness` object and write unit tests for the confidence indicator (US3). The metadata frame is the final line emitted in the chat streaming response and must reflect the GAV-adjusted confidence score and groundedness summary.

## Context Files (Read FIRST)

1. `Docs/PROMPTS/spec-05-accuracy/05-implement.md` -- code specs (authoritative reference for metadata frame structure)
2. `backend/api/chat.py` -- existing metadata frame emission (around lines 149-156). Read the FULL `generate()` function.
3. `specs/005-accuracy-robustness/contracts/sse-events.md` -- NDJSON streaming contract with exact field definitions
4. `backend/agent/schemas.py` -- `GroundednessResult`, `ClaimVerification` models
5. `backend/agent/state.py` -- `ConversationState` with `groundedness_result` and `confidence_score` fields
6. `specs/005-accuracy-robustness/spec.md` -- US3 acceptance scenarios
7. `specs/005-accuracy-robustness/data-model.md` -- GroundednessResult field definitions

## Assigned Tasks

- T018: Update NDJSON metadata frame emission in `backend/api/chat.py`: read `groundedness_result` from the final `ConversationState` dict returned by the graph run (key `"groundedness_result"`); serialize it into `{"supported": N, "unsupported": N, "contradicted": N, "overall_grounded": bool}` (or `null` when `groundedness_result is None` or verification was skipped); include as `"groundedness"` field in the `metadata` NDJSON frame alongside existing `confidence`, `citations`, `latency_ms` -- the `"confidence"` value must use the GAV-adjusted `confidence_score` from `ConversationState`, not the pre-GAV raw score
- T019: Add unit tests for confidence adjustment formula in `tests/unit/test_accuracy_nodes.py`: `confidence_adjustment=1.0` -> score unchanged; `confidence_adjustment=0.7` -> score reduced proportionally; `confidence_adjustment=0.0` -> score clamped to 0; result clamped to 100 when adjustment would exceed
- T020: Add unit test for NDJSON metadata frame structure in `tests/unit/test_accuracy_nodes.py`: with groundedness result -> `groundedness` object has all 4 fields (`supported`, `unsupported`, `contradicted`, `overall_grounded`); without groundedness result -> `groundedness` is `null`; confidence value is GAV-adjusted int 0-100
- T021: Run US3 unit tests: `zsh scripts/run-tests-external.sh -n spec05-us3 --no-cov tests/unit/test_accuracy_nodes.py` -- poll `cat Docs/Tests/spec05-us3.status` until PASSED

## Files to Create/Modify

- MODIFY: `backend/api/chat.py` (update metadata frame emission to include `groundedness` object)
- MODIFY: `tests/unit/test_accuracy_nodes.py` (fill in `TestConfidenceIndicator` test class)

## Key Patterns

### Metadata Frame Structure (from contracts/sse-events.md)

When groundedness result is available:
```json
{
  "type": "metadata",
  "trace_id": "uuid-v4",
  "confidence": 75,
  "groundedness": {
    "supported": 4,
    "unsupported": 1,
    "contradicted": 0,
    "overall_grounded": true
  },
  "citations": [...],
  "latency_ms": 1240
}
```

When groundedness is null (disabled, failed, or no verifiable claims):
```json
{
  "type": "metadata",
  "trace_id": "uuid-v4",
  "confidence": 75,
  "groundedness": null,
  "citations": [...],
  "latency_ms": 1240
}
```

### Building the groundedness Object

```python
groundedness_result = final_state.get("groundedness_result")
groundedness_obj = None
if groundedness_result is not None:
    groundedness_obj = {
        "supported": sum(
            1 for v in groundedness_result.verifications
            if v.verdict == "supported"
        ),
        "unsupported": sum(
            1 for v in groundedness_result.verifications
            if v.verdict == "unsupported"
        ),
        "contradicted": sum(
            1 for v in groundedness_result.verifications
            if v.verdict == "contradicted"
        ),
        "overall_grounded": groundedness_result.overall_grounded,
    }
```

### Confidence Semantics

The `"confidence"` value in the metadata frame is the GAV-adjusted score:
- When GAV runs: `int(mean(sub_answer_scores) * confidence_adjustment)`, clamped [0, 100]
- When GAV is disabled or fails: the raw `confidence_score` from ConversationState (which defaults to 0 for the stub)
- Always an integer 0-100

This value is already set by the `verify_groundedness` node (A2's work) and stored in `ConversationState["confidence_score"]`. The chat.py code simply reads it: `final_state.get("confidence_score", 0)`.

### Location in chat.py

The metadata frame is emitted around lines 149-156 in the existing code. The current code is:
```python
yield json.dumps({
    "type": "metadata",
    "trace_id": db_trace_id,
    "confidence": final_state.get("confidence_score", 0),
    "citations": [
        c.model_dump() for c in final_state.get("citations", [])
    ],
    "latency_ms": latency_ms,
}) + "\n"
```

Replace with the extended version that includes `"groundedness": groundedness_obj`. Build `groundedness_obj` BEFORE the `yield` statement.

## CRITICAL: Shared File with A5

A5 (running in parallel) modifies the ERROR HANDLING section of `chat.py` (adding `CircuitOpenError` catch). You modify the METADATA FRAME section. These are different parts of the `generate()` function.

- You work around lines 140-160 (metadata frame emission)
- A5 works around lines 96-170 (error handling `except` blocks)

Do NOT touch the `except` blocks at the bottom of `generate()`.

## Test Patterns

```python
# Test confidence adjustment formula (T019):
# These test the formula used in verify_groundedness
def test_confidence_unchanged_when_fully_grounded():
    """confidence_adjustment=1.0 means score unchanged."""
    base_scores = [80, 90]  # mean = 85
    adjustment = 1.0
    result = int(sum(base_scores) / len(base_scores) * adjustment)
    assert result == 85

def test_confidence_reduced_proportionally():
    """confidence_adjustment=0.7 reduces score."""
    base_scores = [80, 90]  # mean = 85
    adjustment = 0.7
    result = int(sum(base_scores) / len(base_scores) * adjustment)
    assert result == 59  # int(85 * 0.7) = 59

# Test metadata frame structure (T020):
def test_metadata_frame_with_groundedness():
    """Metadata frame includes groundedness object when result available."""
    result = GroundednessResult(
        verifications=[
            ClaimVerification(claim="A", verdict="supported", evidence_chunk_id="c1", explanation="ok"),
            ClaimVerification(claim="B", verdict="unsupported", evidence_chunk_id=None, explanation="missing"),
        ],
        overall_grounded=True,
        confidence_adjustment=0.8,
    )
    groundedness_obj = {
        "supported": 1,
        "unsupported": 1,
        "contradicted": 0,
        "overall_grounded": True,
    }
    # Verify structure matches contract

def test_metadata_frame_groundedness_null():
    """Metadata frame has groundedness=null when result is None."""
    groundedness_result = None
    groundedness_obj = None
    # Verify null serialized correctly
```

## Constraints

- NEVER run pytest inside Claude Code. Use: `zsh scripts/run-tests-external.sh -n <name> <target>`
- NEVER modify `nodes.py`, `schemas.py`, `state.py`, `config.py`, or `conversation_graph.py`
- NEVER touch the error handling `except` blocks in `chat.py` (A5's responsibility)
- The `groundedness` field MUST be `null` (not omitted) when groundedness result is None -- this is a backwards-compatible addition per the SSE events contract
- The `confidence` field must continue to be the integer from `final_state.get("confidence_score", 0)` -- no new computation here, just read the already-adjusted value
- Use `monkeypatch` for settings overrides in tests

## Checkpoint

Metadata frame includes `groundedness` object. Running the following succeeds:
```bash
ruff check backend/api/chat.py
```
