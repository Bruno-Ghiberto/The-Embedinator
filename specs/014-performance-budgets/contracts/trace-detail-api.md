# Contract: GET /api/traces/{id} — Stage Timings Extension

**Endpoint**: `GET /api/traces/{id}`
**Change type**: Additive extension (backwards-compatible)
**Spec**: FR-008 / SC-007
**Date**: 2026-03-18

---

## Change Summary

This spec adds `stage_timings` to the response body of the existing trace detail endpoint.
No new endpoint is created. All existing response fields are unchanged.

---

## Response Schema (extended)

```
GET /api/traces/{id}
→ 200 OK
→ Content-Type: application/json

{
  // --- Existing fields (unchanged) ---
  "id":                       string (UUID),
  "session_id":               string (UUID),
  "query":                    string,
  "collections_searched":     string[],
  "confidence_score":         integer (0–100),
  "latency_ms":               integer (milliseconds),
  "llm_model":                string | null,
  "meta_reasoning_triggered": boolean,
  "created_at":               string (ISO 8601),
  "sub_questions":            object[],
  "chunks_retrieved":         object[],
  "reasoning_steps":          object[],
  "strategy_switches":        object[],

  // --- NEW field (spec-14) ---
  "stage_timings": {
    "<stage_name>": {
      "duration_ms": number,    // float, rounded to 1 decimal; always present
      "failed"?:     boolean    // only present and true if the stage errored
    }
  }
}
```

---

## stage_timings Field Contract

### Possible stage_name values

| Name | Category | Presence |
|------|----------|----------|
| `intent_classification` | always-present | Every trace produced after spec-14 |
| `embedding` | always-present | Every trace produced after spec-14 |
| `retrieval` | always-present | Every trace produced after spec-14 |
| `ranking` | always-present | Every trace produced after spec-14 |
| `answer_generation` | always-present | Every trace produced after spec-14 |
| `grounded_verification` | conditional | Only when Phase 2 GAV node executed |
| `meta_reasoning` | conditional | Only when MetaReasoningGraph was triggered |

### Semantics

- **Key absent** → stage did not execute (not an error; e.g., conditional stage skipped)
- **Key present, no `failed` field** → stage completed successfully
- **Key present, `"failed": true`** → stage raised an exception; `duration_ms` records elapsed time up to the point of failure
- **`stage_timings: {}`** (empty object) → trace was produced before spec-14 was deployed (legacy trace); display as "pre-instrumentation" in UI

### Relationship to latency_ms

The sum of `duration_ms` values across all stage entries will be less than or equal to
`latency_ms`. The difference accounts for:
- FastAPI routing and session load time
- LangGraph orchestration overhead
- Time between stages (state serialization, edge evaluation)
- Any pipeline stages that are not individually instrumented

---

## Error Responses (unchanged)

```
404 Not Found  — trace ID does not exist
500 Internal Server Error — unexpected database error
```

---

## Backwards Compatibility

This change is additive. Existing API consumers that do not read `stage_timings` are unaffected.
The field is always present in the response (never omitted); it defaults to `{}` for legacy traces.
