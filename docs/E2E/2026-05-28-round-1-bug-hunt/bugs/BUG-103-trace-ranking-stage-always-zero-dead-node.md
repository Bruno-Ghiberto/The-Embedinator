# BUG-103: Trace 'ranking' stage always 0ms — measures dead node, real rerank untimed

- **Severity**: MAJOR
- **Layer**: Backend
- **Discovered**: 2026-07-11T19:16:29Z in Phase 6 (P6-S1)
- **Phase scenario**: P6-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Open any Trace Detail — the `ranking` bar reads 0.
2. Query the DB: `SELECT stage_timings_json` — `ranking.duration_ms = 0.0` in all 6 sampled traces.

## Expected
The `ranking` stage reflects retrieval reranking (cross-encoder) duration.

## Actual
`ranking.duration_ms` is always `0.0` (6/6 traces). The key is written by `validate_citations` — a post-generation citation-QA node that early-returns 100% of the time because its `reranker` param is never bound; the real `cross_encoder_rerank` tool has no dedicated timing key (folded into `research_tools_ms`).

## Artifacts
- Screenshot: screenshots/P6-S1-trace-detail-stage-timings.png (gitignored)
- Log excerpt: null
- Trace: traces/P6-S1-stage-timings-analysis.md (gitignored)

## Root-cause hypothesis
`validate_citations` (`backend/agent/nodes.py:633-724`) is registered bare at `backend/agent/conversation_graph.py:65` — no partial/closure binds its keyword-only `reranker` param → `reranker=None` → early return at `nodes.py:651-657` → ~0ms every call. The real rerank runs as a research tool (`research_nodes.py:380`) with no dedicated `stage_timings` key of its own.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.1-defer
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/163
- **Rationale**: The 0.0ms value is accurate for the no-op node it actually measures; this is the mislabelled-instrumentation symptom whose functional half — citation QA never running — is owned and fixed by BUG-107.

## Notes
Related: BUG-107 (same root cause — `validate_citations` is a 100% no-op because the reranker is unbound; this record is the timing symptom, BUG-107 is the functional-loss finding), BUG-102 (same chart, adjacent instrumentation gap).
