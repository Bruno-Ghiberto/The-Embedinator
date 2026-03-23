# Quickstart: Performance Budgets and Pipeline Instrumentation

**Date**: 2026-03-18
**Branch**: `014-performance-budgets`

---

## What This Spec Implements

Spec-14 adds per-stage timing instrumentation to every chat query. After this spec is
deployed, every query trace in the database includes a `stage_timings` breakdown showing
how long each pipeline stage took.

---

## Verifying the Implementation

### 1. Run a query and inspect its trace

After deployment, run any chat query through the UI or API, then fetch the trace:

```bash
# Get the trace ID from the chat response metadata frame
curl http://localhost:8000/api/traces/<trace-id>
```

The response should include:
```json
{
  "stage_timings": {
    "intent_classification": {"duration_ms": 185.2},
    "embedding": {"duration_ms": 47.1},
    "retrieval": {"duration_ms": 31.4},
    "ranking": {"duration_ms": 145.8},
    "answer_generation": {"duration_ms": 492.3}
  }
}
```

### 2. Verify legacy traces still work

Traces created before spec-14 deployment return `"stage_timings": {}` — not an error:

```bash
curl http://localhost:8000/api/traces/<pre-spec-14-trace-id>
# → {"stage_timings": {}, ... all other fields present}
```

### 3. Run the benchmark test suite

```bash
zsh scripts/run-tests-external.sh -n spec14-bench tests/integration/test_performance.py
cat Docs/Tests/spec14-bench.summary
```

Expected output: SC-006 (concurrent queries) and SC-007 (stage timings present) pass.
SC-001 through SC-005 and SC-008 are skipped in CI (require reference hardware or live inference).

---

## Performance Budgets Reference

| Stage | Budget | Notes |
|-------|--------|-------|
| Intent classification | 200 ms | Ollama 7B model |
| Query embedding | 50 ms | nomic-embed-text |
| Hybrid retrieval | 30 ms | Qdrant dense + BM25 |
| Cross-encoder ranking | 150 ms | CPU, top-20 candidates |
| Answer generation (first token) | 500 ms | Streaming; budget is to first token |
| Grounded verification | 400 ms | Conditional (Phase 2) |
| **Total simple query (first token)** | **~1.2 s** | Phase 2 with GAV |
| **Total complex query (first token)** | **~3–5 s** | Includes ResearchGraph loops |

---

## Agent Teams Execution

This spec uses 3 waves. Read `Docs/PROMPTS/spec-14-performance/14-plan.md` for the full
orchestration protocol before spawning any agents.

**Wave 1** (A1, quality-engineer, opus): Pre-flight audit — confirm pre-FR state of all 5 target files.
**Wave 2** (A2 + A3, python-expert, sonnet, parallel): Implementation — state/nodes + storage/API layer.
**Wave 3** (A4, quality-engineer, sonnet): Benchmarks + final validation.

Do not spawn Wave 2 until `Docs/Tests/spec14-a1-audit.md` exists and shows PASS.
