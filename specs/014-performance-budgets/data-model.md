# Data Model: Performance Budgets and Pipeline Instrumentation

**Phase**: 1 — Design & Contracts
**Date**: 2026-03-18
**Branch**: `014-performance-budgets`

---

## Modified Entity: Query Trace

The `query_traces` SQLite table gains one new column. All other columns are unchanged.

### Schema Change

```sql
ALTER TABLE query_traces ADD COLUMN stage_timings_json TEXT;
```

**Migration**: Idempotent — wrapped in `try/except OperationalError` to handle re-runs.

### Full query_traces schema (post-spec-14)

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | TEXT | NOT NULL | UUID, primary key |
| `session_id` | TEXT | NOT NULL | Foreign key → sessions |
| `query` | TEXT | NOT NULL | Truncated to 10,000 chars (spec-13) |
| `collections_searched` | TEXT | NOT NULL | JSON array of collection IDs |
| `chunks_retrieved_json` | TEXT | NULL | JSON array of retrieved chunk objects |
| `confidence_score` | INTEGER | NOT NULL | 0–100 scale |
| `latency_ms` | INTEGER | NOT NULL | Total wall-clock latency |
| `llm_model` | TEXT | NULL | Model name used for generation |
| `embed_model` | TEXT | NULL | Model name used for embedding |
| `sub_questions_json` | TEXT | NULL | JSON array of decomposed sub-questions |
| `reasoning_steps_json` | TEXT | NULL | JSON array of agent reasoning narrative |
| `strategy_switches_json` | TEXT | NULL | JSON array of meta-reasoning strategy switches |
| `meta_reasoning_triggered` | INTEGER | NOT NULL | Boolean (0/1) |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp |
| `provider_name` | TEXT | NULL | Active LLM provider name (spec-10) |
| `stage_timings_json` | TEXT | NULL | **NEW** — Per-stage timing breakdown (spec-14) |

---

## New Value Object: Stage Timings

`stage_timings_json` stores a JSON object mapping stage names to timing entries.

### JSON Schema

```json
{
  "intent_classification": { "duration_ms": 180.4 },
  "embedding":             { "duration_ms": 45.1 },
  "retrieval":             { "duration_ms": 28.3 },
  "ranking":               { "duration_ms": 142.6 },
  "answer_generation":     { "duration_ms": 487.2 },
  "grounded_verification": { "duration_ms": 390.5 },
  "meta_reasoning":        { "duration_ms": 1240.0 }
}
```

### Stage Timing Entry Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `duration_ms` | float | always | Duration in milliseconds, rounded to 1 decimal place (`round(..., 1)`) |
| `failed` | boolean | only on error | Present and `true` only when the stage raised an exception; absent on success |

### Stage Names (canonical)

| Stage Name | Always Present | Node | Condition |
|------------|---------------|------|-----------|
| `intent_classification` | ✅ yes | `classify_intent()` | Every query |
| `embedding` | ✅ yes | query embedding call site | Every query |
| `retrieval` | ✅ yes | `HybridSearcher.search()` call | Every query |
| `ranking` | ✅ yes | cross-encoder reranker call | Every query |
| `answer_generation` | ✅ yes | LLM generation call | Every query |
| `grounded_verification` | ❌ conditional | `verify_groundedness()` | Only when Phase 2 GAV executes |
| `meta_reasoning` | ❌ conditional | MetaReasoningGraph invocation | Only when triggered by low confidence |

### Invariants

1. An absent key means "did not run" — do NOT insert `{"duration_ms": 0}` for skipped stages.
2. If a stage errors: `{"duration_ms": X.X, "failed": true}` — subsequent stages are absent.
3. The sum of `duration_ms` values is generally less than `latency_ms` (I/O and overhead not attributed to a specific stage are not included).
4. NULL `stage_timings_json` (legacy traces) → API returns `{}` (empty dict), not `null`.

---

## Modified State: ConversationState

The `ConversationState` TypedDict gains one new field to accumulate timing data as the pipeline executes.

### New Field

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `stage_timings` | `dict` | `{}` | Accumulated per-stage timing entries; grows as each node records its duration |

### State Lifecycle

```
start → {} (empty dict, initial state)
  → classify_intent node executes → {"intent_classification": {"duration_ms": 180.4}}
  → embedding → {"intent_classification": ..., "embedding": {"duration_ms": 45.1}}
  → retrieval → {..., "retrieval": {"duration_ms": 28.3}}
  → ranking   → {..., "ranking": {"duration_ms": 142.6}}
  → answer_generation → {..., "answer_generation": {"duration_ms": 487.2}}
  → [grounded_verification, if triggered] → {..., "grounded_verification": {"duration_ms": 390.5}}
  → [meta_reasoning, if triggered] → {..., "meta_reasoning": {"duration_ms": 1240.0}}
  → chat.py extracts final stage_timings → serialize → store in query_traces
```

---

## API Response Extension

The `GET /api/traces/{id}` response gains one new field. No new endpoint is introduced.

### New Response Field

| Field | Type | Source |
|-------|------|--------|
| `stage_timings` | `dict` | Parsed from `stage_timings_json` column; defaults to `{}` if NULL |

### Response Shape (post-spec-14)

```json
{
  "id": "...",
  "session_id": "...",
  "query": "...",
  "collections_searched": [...],
  "confidence_score": 72,
  "latency_ms": 1580,
  "llm_model": "llama3.1:8b",
  "meta_reasoning_triggered": false,
  "created_at": "2026-03-18T12:00:00Z",
  "sub_questions": [...],
  "chunks_retrieved": [...],
  "reasoning_steps": [...],
  "strategy_switches": [...],
  "stage_timings": {
    "intent_classification": {"duration_ms": 180.4},
    "embedding": {"duration_ms": 45.1},
    "retrieval": {"duration_ms": 28.3},
    "ranking": {"duration_ms": 142.6},
    "answer_generation": {"duration_ms": 487.2}
  }
}
```
