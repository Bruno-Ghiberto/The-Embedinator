# A2: State and Nodes Instrumentation

**Agent type**: `python-expert`
**Model**: **Sonnet 4.6** (`model="sonnet"`)

You implement the `stage_timings` field in `ConversationState` and instrument all pipeline nodes
in `backend/agent/nodes.py` with per-stage `time.perf_counter()` timing. You also write and run
unit tests for your changes.

You run in parallel with A3 — you modify different files (agent layer), A3 modifies the storage
and API layer. Do NOT touch `backend/storage/`, `backend/api/`, or any files outside your scope.

## Assigned Tasks

T009–T016 from `Docs/PROMPTS/spec-14-performance/14-plan.md` (Wave 2 — A2 Implementation).

| Task | File | Description |
|------|------|-------------|
| T009 | `backend/agent/state.py` | Add `stage_timings: dict` field to `ConversationState` after `iteration_count` |
| T010 | `backend/agent/nodes.py` | Instrument `classify_intent()` with `time.perf_counter()` timing |
| T011 | `backend/agent/nodes.py` | Instrument the embedding stage |
| T012 | `backend/agent/nodes.py` | Instrument the retrieval stage |
| T013 | `backend/agent/nodes.py` | Instrument the ranking stage |
| T014 | `backend/agent/nodes.py` | Instrument the answer_generation stage |
| T015 | `backend/agent/nodes.py` | Instrument `verify_groundedness()` (conditional stage) |
| T015a | `backend/agent/research_graph.py` or `nodes.py` | Locate MetaReasoningGraph call site; instrument `"meta_reasoning"` conditional stage |
| T016 | `tests/unit/test_stage_timings.py` | Write unit tests + run via external runner |

## Source Documents to Read

Read these files in order before starting any work:

1. `Docs/PROMPTS/spec-14-performance/14-plan.md` — full orchestration protocol; read "Key Constraints"
   and "Appendix: Exact Insertion Points" sections carefully
2. `Docs/Tests/spec14-a1-audit.md` — A1's audit report; confirms exact line numbers and insertion points
3. `specs/014-performance-budgets/spec.md` — 8 FRs (focus on FR-005)
4. `specs/014-performance-budgets/data-model.md` — canonical stage names and their conditions
5. `specs/014-performance-budgets/research.md` — R-001 (LangGraph state merge) and R-006 (failed stage)

## T009 — backend/agent/state.py

Add `stage_timings: dict` as the last field of `ConversationState`. Read A1's audit report for
the exact line of `iteration_count` (the current last field).

**Change**: Add one line after `iteration_count: int`:

```python
    confidence_score: int  # 0–100 scale (user-facing)
    iteration_count: int
    stage_timings: dict  # FR-005: per-stage timing data accumulated by nodes
```

Use Serena `replace_symbol_body` or the Edit tool to make this change precisely. Do not modify
any other field in the TypedDict.

## T010 — classify_intent() Timing (intent_classification stage)

Use `find_symbol` with name_path `classify_intent`, `include_body=true` to read the current body.
Confirm A1's reported state: no `time.perf_counter()` calls, no `stage_timings` updates.

**Pattern to apply** (inline timing — no Timer class):

```python
async def classify_intent(state: ConversationState, ...) -> dict:
    _t0 = time.perf_counter()
    try:
        # ... existing node logic (UNCHANGED) ...
        result = { ... }  # whatever the node currently returns
        result["stage_timings"] = {
            **state.get("stage_timings", {}),
            "intent_classification": {"duration_ms": round((time.perf_counter() - _t0) * 1000, 1)},
        }
        return result
    except Exception:
        # Re-raise after recording failed timing — LangGraph handles the error
        raise  # Note: cannot update state on re-raise; "failed" marker may not persist
```

**Important**: The existing node logic MUST remain unchanged. Only add the `_t0` capture at entry,
the `stage_timings` merge into the result dict, and the try/except wrapper.

**LangGraph state merge rule**: ALWAYS read `state.get("stage_timings", {})` and spread it before
adding the new entry. This preserves all prior stage timings — LangGraph uses "last value wins"
for state updates, so if you return only the new entry the prior stages are lost.

**`import time`**: Verify that `import time` exists at the module level of `nodes.py`. If not,
add it alongside the other stdlib imports.

## T011 — Embedding Stage Timing (embedding stage)

Read `backend/agent/nodes.py` to locate the node that calls query embedding. This may be
`rewrite_query()`, `retrieve_documents()`, or a similar node — read A1's audit report for
the identified function name.

Apply the same pattern as T010. The stage name is `"embedding"`. Only time the embedding
call itself (the call to the embedding model or its wrapper), not the entire node.

If the embedding call is interleaved with retrieval in a single node, time each independently:
wrap the embedding sub-operation with `_t0_embed` / `"embedding"` and the retrieval sub-operation
with `_t0_retr` / `"retrieval"` within the same try/except structure.

## T012 — Retrieval Stage Timing (retrieval stage)

Locate the `HybridSearcher.search()` call (or equivalent retrieval call). Apply timing as
`"retrieval"` stage. If the retrieval call shares a node with embedding (see T011 note above),
handle both timers in that same node.

## T013 — Ranking Stage Timing (ranking stage)

Locate the cross-encoder reranker call. This may be inside `validate_citations()` or a
dedicated ranking node. Apply timing as `"ranking"` stage.

## T014 — Answer Generation Stage Timing (answer_generation stage)

Locate the LLM call that produces `final_response`. Apply timing as `"answer_generation"` stage.
Time only the LLM call, not the full node body. The timer starts immediately before the LLM
invocation and stops when the response is received.

## T015 — Grounded Verification Stage Timing (conditional stage)

Use `find_symbol` with name_path `verify_groundedness`, `include_body=true`. Apply timing as
`"grounded_verification"` stage.

**This stage is conditional**: The node only executes when the LangGraph edge routes to it.
No special "skip" logic is needed — the key is simply absent from `stage_timings` when the
node is not called. Apply the same inline timing pattern as all other nodes.

## T015a — MetaReasoningGraph Stage Timing (conditional stage)

Use Serena `get_symbols_overview` on `backend/agent/research_graph.py` to locate where
`MetaReasoningGraph` (or `meta_reasoning_graph`) is invoked. It may be called:
- From a node in `research_graph.py` when `meta_reasoning_triggered` is True
- From a node in `nodes.py` that conditionally calls the sub-graph

Apply the same inline timing pattern as T015. The stage name is `"meta_reasoning"`.

If the call site is in `research_graph.py`, instrument it there — this overrides the
"not to touch" guidance in 14-plan.md specifically for this one timing point.
The broader research_graph.py routing logic must NOT be modified.

```python
# Inside the node/function that calls MetaReasoningGraph:
_t0_meta = time.perf_counter()
try:
    meta_result = meta_graph.invoke(...)  # or await meta_graph.ainvoke(...)
    result["stage_timings"] = {
        **state.get("stage_timings", {}),
        ...,  # any prior stages already in result["stage_timings"] if same node
        "meta_reasoning": {"duration_ms": round((time.perf_counter() - _t0_meta) * 1000, 1)},
    }
except Exception:
    raise  # re-raise; LangGraph handles errors
```

If the MetaReasoningGraph invocation is inside an existing node that already records another
stage (e.g., it's called at the end of the answer_generation node), add the `meta_reasoning`
timer separately from the outer node timer.

## T016 — Write Tests and Run

Write `tests/unit/test_stage_timings.py` with these test cases:

```python
# Test 1: stage_timings field exists in ConversationState
def test_conversation_state_has_stage_timings_field():
    """stage_timings: dict is a declared field of ConversationState."""
    from backend.agent.state import ConversationState
    assert "stage_timings" in ConversationState.__annotations__

# Test 2: timing entry structure — duration_ms is a number
def test_stage_timing_entry_has_duration_ms():
    """A timing entry has duration_ms as a numeric value."""
    entry = {"duration_ms": 45.2}
    assert isinstance(entry["duration_ms"], (int, float))
    assert entry["duration_ms"] >= 0

# Test 3: state merge pattern — spreads prior timings
def test_stage_timings_merge_preserves_prior_stages():
    """The merge pattern accumulates stage entries without overwriting prior ones."""
    prior = {"intent_classification": {"duration_ms": 180.4}}
    new_entry = {"embedding": {"duration_ms": 45.1}}
    merged = {**prior, **new_entry}
    assert "intent_classification" in merged
    assert "embedding" in merged

# Test 4: failed stage format
def test_failed_stage_includes_failed_flag():
    """A failed stage entry includes failed: True."""
    entry = {"duration_ms": 22.0, "failed": True}
    assert entry.get("failed") is True
    assert "duration_ms" in entry

# Test 5: absent key means conditional stage did not execute
def test_absent_stage_key_means_not_executed():
    """Conditional stages (grounded_verification, meta_reasoning) are absent when not executed."""
    stage_timings = {
        "intent_classification": {"duration_ms": 180.0},
        "embedding": {"duration_ms": 45.0},
    }
    assert "grounded_verification" not in stage_timings
    assert "meta_reasoning" not in stage_timings
```

After writing the test file, run:

```bash
zsh scripts/run-tests-external.sh -n spec14-a2 tests/unit/
```

Poll until complete:
```bash
cat Docs/Tests/spec14-a2.status
```

Read results:
```bash
cat Docs/Tests/spec14-a2.summary
```

**Expected**: PASSED. No new failures in pre-existing unit tests.

## Key Constraints

- **NEVER run pytest directly** — use `zsh scripts/run-tests-external.sh -n <name> <target>`
- **LangGraph state merge**: ALWAYS read `state.get("stage_timings", {})` and spread before adding
  new stage entry — return `{**existing, "stage_name": {...}}` NOT just `{"stage_name": {...}}`
- **duration_ms precision**: Use `round((time.perf_counter() - _t0) * 1000, 1)` — 1 decimal place
- **Absent = did not run**: Do NOT insert `{"duration_ms": 0}` for skipped conditional stages
- **No Timer class**: Use inline `time.perf_counter()` per node — no shared utility or context manager
- **NDJSON only**: The chat endpoint is `application/x-ndjson` — no SSE, no `data:` prefix
- **Do NOT touch**: `backend/storage/`, `backend/api/`, `backend/retrieval/`, `backend/config.py`
- **Pre-existing failures: 39** — any increase is a regression; investigate before reporting

## Files Modified

| File | Change |
|------|--------|
| `backend/agent/state.py` | Add `stage_timings: dict` field |
| `backend/agent/nodes.py` | Instrument 6–7 node functions with inline timing |

## New Files Created

| File | Purpose |
|------|---------|
| `tests/unit/test_stage_timings.py` | Unit tests for timing structure and state merge |

## Success Criteria

- `backend/agent/state.py` has `stage_timings: dict` as the last field of `ConversationState`
- `backend/agent/nodes.py` has inline `time.perf_counter()` timing in all required nodes
- All 5 always-present stages instrumented: `intent_classification`, `embedding`, `retrieval`,
  `ranking`, `answer_generation`
- `verify_groundedness()` instrumented as conditional `grounded_verification` stage
- MetaReasoningGraph call site instrumented as conditional `meta_reasoning` stage
- `tests/unit/test_stage_timings.py` exists with passing tests
- `Docs/Tests/spec14-a2.status` is `PASSED`
- No new failures in pre-existing unit tests

## After Completing All Tasks

Report completion to the orchestrator. The orchestrator will verify both `spec14-a2.status = PASSED`
and `spec14-a3.status = PASSED` before proceeding to Wave 3 (A4).
