# Research: Performance Budgets and Pipeline Instrumentation

**Phase**: 0 — Outline & Research
**Date**: 2026-03-18
**Branch**: `014-performance-budgets`

All implementation details were resolved from existing codebase context and confirmed against
the spec clarifications recorded on 2026-03-18. No external research was required.

---

## R-001: LangGraph Partial State Merge Semantics

**Decision**: Each instrumented node reads `state.get("stage_timings", {})`, merges its new
entry into the accumulated dict, and returns the merged dict as its partial state update.

**Rationale**: LangGraph applies node return values as state updates using a default "last value
wins" reducer for TypedDict fields without explicit reducers. This means if node A returns
`{"stage_timings": {"intent_classification": {...}}}` and node B independently returns
`{"stage_timings": {"embedding": {...}}}`, node B's update would overwrite node A's, losing
the intent_classification entry.

The correct pattern spreads the existing accumulated timings before adding the new entry:

```python
result["stage_timings"] = {
    **state.get("stage_timings", {}),       # preserve all prior stage entries
    "intent_classification": {"duration_ms": round((time.perf_counter() - _t0) * 1000, 1)},
}
```

This ensures the `stage_timings` dict grows monotonically as each node executes in sequence.

**Alternatives considered**:
- Custom reducer on `stage_timings` field: Would require `Annotated[dict, operator.or_]` in
  the TypedDict. Rejected — adds complexity and the merge-on-return pattern is simpler and
  already used by existing nodes for other partial-dict fields.
- Post-hoc assembly in `chat.py`: Rejected — requires tracking timing externally rather than
  within the graph, complicating the data flow and making test isolation harder.

---

## R-002: time.perf_counter() vs time.monotonic()

**Decision**: Use `time.perf_counter()` for per-stage timing within node functions.
`time.monotonic()` is retained for total wall-clock latency in `chat.py`.

**Rationale**: `time.perf_counter()` is the highest-resolution timer available in Python,
suitable for measuring sub-millisecond durations within async function bodies. It is process-
relative and not affected by system clock adjustments. `time.monotonic()` is already used in
`chat.py` for total `latency_ms` and should remain there for consistency. Using both in
different contexts is a standard Python pattern and not a contradiction.

**Alternatives considered**:
- Using `time.monotonic()` for per-stage timing: Acceptable but lower resolution; `perf_counter`
  is the conventional choice for profiling. Rejected in favour of consistency with profiling
  conventions.
- Using `asyncio.get_event_loop().time()`: Equivalent to `time.monotonic()`; no advantage.

---

## R-003: Schema Migration Idempotency

**Decision**: Wrap `ALTER TABLE query_traces ADD COLUMN stage_timings_json TEXT` in a
`try/except aiosqlite.OperationalError` block to handle the case where the column already
exists (e.g., migration re-run or test database re-use).

**Rationale**: SQLite raises `OperationalError: duplicate column name: stage_timings_json`
if `ALTER TABLE ADD COLUMN` is attempted on a column that already exists. The existing
codebase pattern (used for `provider_name` in spec-10) wraps the ALTER in a try/except.
This is the idiomatic approach for SQLite schema migrations without a migration framework.

**Alternatives considered**:
- `IF NOT EXISTS` clause: SQLite's `ALTER TABLE ADD COLUMN` does not support `IF NOT EXISTS`
  syntax (unlike `CREATE TABLE`). Not applicable.
- Schema version tracking table: Overkill for a single column addition. Rejected per
  Constitution VII (Simplicity by Default).

---

## R-004: stage_timings_json Default Value in API Response

**Decision**: When `stage_timings_json` is NULL in the database (legacy traces), the
`GET /api/traces/{id}` response returns `"stage_timings": {}` (empty dict), not `null`,
not `[]`, and not omitted.

**Rationale**: An empty dict `{}` clearly communicates "no per-stage data available" to API
consumers without requiring a null check. Using `[]` (empty list) would be semantically wrong
since `stage_timings` is a key→entry mapping, not a sequence. Using `null` would require
consumers to handle two types (null or dict). The existing `parse_json(val, {})` helper
in `traces.py` already supports custom default values, making this a one-argument change.

**Alternatives considered**:
- Return `null`: Forces consumers to branch on null vs dict. Rejected.
- Omit the key for legacy traces: Makes the response schema variable. Rejected — consistent
  key presence simplifies frontend consumption.
- Return `[]`: Semantically incorrect for a mapping. Rejected.

---

## R-005: Conditional Stage Omission vs Zero-Duration Entry

**Decision**: Stages that do not execute (e.g., `grounded_verification` when the LLM
determines the answer is factoid-tier and skips verification, `meta_reasoning` when
confidence is sufficient) MUST be absent from `stage_timings_json`. An absent key means
"did not run." A zero-duration entry `{"duration_ms": 0}` must NOT be inserted.

**Rationale**: SC-007 explicitly requires that conditional stages "appear only when executed."
Frontend and observability consumers can distinguish between "stage not run" (key absent) and
"stage ran instantly" (key present, small `duration_ms`) without special-casing. Inserting
`duration_ms: 0` for un-executed stages would pollute the timing data and make it impossible
to know whether a stage ran.

**Implementation**: Since `verify_groundedness` only records its timing when it executes,
and it's only invoked when the conditional edge routes to it, no special "skip" logic is
needed — the node simply records its timing when called, and the key is absent when not called.

---

## R-006: Failed Stage Error Handling

**Decision**: If a node raises an exception that escapes the node body, a try/except around
the timing logic records `{"duration_ms": X.X, "failed": true}` before re-raising. The
timing wrapper MUST NOT suppress the original exception.

**Rationale**: Partial timing data (duration up to the point of failure) is more useful than
no data — it allows diagnosis of which stage failed and how long it ran before failing. The
spec (FR-005) explicitly requires this behavior. The re-raise pattern ensures LangGraph's
error handling continues to function normally.

**Pattern**:
```python
_t0 = time.perf_counter()
try:
    # ... node logic ...
    # ... record timing on success ...
    return result
except Exception:
    stage_timings = {
        **state.get("stage_timings", {}),
        "stage_name": {
            "duration_ms": round((time.perf_counter() - _t0) * 1000, 1),
            "failed": True,
        },
    }
    # Note: cannot update state here since we're about to re-raise.
    # LangGraph may not persist the partial state update.
    # A4 must verify this behavior in integration tests.
    raise
```

**Open note for A4**: Verify in integration tests whether LangGraph persists partial state
updates from a node that raises. If not, the `failed` marker may be absent from the final
state even when a node errors. A4 should document the observed behavior in the final report.

---

## R-007: Benchmark Test Classification (Unit vs Integration)

**Decision**: All new benchmark tests (T028–T031) go in `tests/integration/test_performance.py`
and are marked `@pytest.mark.integration` if they require live services (Qdrant, Ollama).
The `test_legacy_trace_readable()` test (T030) requires only SQLite and may be an undecorated
integration test.

**Rationale**: SC-001 through SC-005 require live inference models and indexed documents to
produce meaningful latency measurements. The existing `tests/integration/test_performance.py`
file already contains two tests with this pattern. The concurrent query test (T031) requires
live NDJSON streaming endpoints. All new tests extend the existing file without modifying it.

**Alternatives considered**:
- New file `tests/integration/test_stage_timings_integration.py`: Rejected — the spec-14
  benchmark tests logically belong with the existing performance tests, not in a separate file.
- Mixing unit and integration tests: Rejected — unit tests in `tests/unit/` must run without
  external services (Constitution's Development Standards).
