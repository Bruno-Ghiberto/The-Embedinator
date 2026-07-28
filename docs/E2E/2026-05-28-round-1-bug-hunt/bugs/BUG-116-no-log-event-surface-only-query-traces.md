# BUG-116: No log/event surface — only query traces; ingestion & breaker events hidden

- **Severity**: MINOR
- **Layer**: Frontend
- **Discovered**: 2026-07-11T20:20:00Z in Phase 6 (P6-S4)
- **Phase scenario**: P6-S4
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Navigate Chat / Collections / Settings / Observability.
2. Look for any raw log or event surface.
3. Observe: the full Observability page renders only System Health / Query Analytics / Metrics Trends / Query Traces / Collection Statistics — no log or event surface exists anywhere.

## Expected
Per playbook P6-S4 (Constitution IV): a log surface where a non-technical reader can understand recent operation flow.

## Actual
Runtime visibility is query-scoped traces only; no operation/event/error log surface exists. `/api/metrics` returns `circuit_breakers` + `active_ingestion_jobs`, but the UI never renders them; ingestion/provider/circuit-breaker events live only in container stdout.

## Artifacts
- Screenshot: screenshots/P6-S3-query-analytics-charts.png (gitignored)
- Log excerpt: null
- Trace: null

## Root-cause hypothesis
No log-viewer route/component exists; the observability page renders no event/breaker/active-job panels despite that data already being fetched.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: TBD
- **GitHub issue**: TBD
- **Rationale**: TBD

## Notes
Related: BUG-117 (same P6-S4 non-technical-readability mandate, different surface), BUG-114 (Metrics Trends readability gap, same panel family).

**CORROBORATION 2026-07-28 (P7-S1)**: extends this record's "runtime visibility is query-scoped traces only" finding with a structural limit in the one surface that does exist — `query_traces` is blind to every non-completing turn BY SCHEMA, not merely by omission. The single INSERT sits at step 8 of the 9-step request path (`chat.py:296-318`), and the 16-column schema carries no `status`, no `finished_at` and no `error` column, so an "aborted" turn is not expressible even in principle: there is no value that could represent it. Any turn that does not reach step 8 leaves no record of having existed.

**Scope note, deliberate**: this is filed as SCHEMA INEXPRESSIBILITY only. It is explicitly NOT filed as "0 `query_traces` rows for the P7-S1 killed turn" — that turn was SIGKILLed, so writing no row is the correct outcome and not a defect (same class as "the backend logged nothing on the way down", which was correctly excluded from this phase). No severity change; no new ID.

**CORROBORATION 2026-07-28 (P7-S2) — the affirmative half of this record's story**: the earlier P7-S1 note established that `query_traces` cannot EXPRESS a non-completing turn. P7-S2 supplies the complementary failure: a completed-but-degraded turn DOES write a row, and that row is actively misleading. With Ollama stopped, the turn completed in 21.5s with `done` and persisted `llm_model=qwen2.5:7b` and `provider_name=ollama` — a model and provider that never served the request. **Correction to an earlier draft of this note: the row is NOT "healthy-looking".** It does carry failure signals — `confidence_score=0`, empty `chunks_retrieved_json`, and `stage_timings_json` with `"intent_classification": {"duration_ms": 5428.2, "failed": true}`. The accurate and narrower finding is that the row ATTRIBUTES work to a model, provider and collection that were never involved: `collections_searched=["22923ab5-…"]` claims a collection was searched while the log for the same trace records `collections_searched: []` with zero tool calls, so the row contradicts the log. And with no error/status column, all four `ConnectError`s appear nowhere in it.

Taken together the two halves define the limit of this surface: it is silent about turns that fail, and confidently wrong about turns that degrade. `llm_model` in particular records what was REQUESTED, not what served — a distinction the schema cannot represent. Cross-ref BUG-126 (the user-facing false attribution from the same outage). No severity change; no new ID.
