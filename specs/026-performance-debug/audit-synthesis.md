# Audit Synthesis — Spec 26 Wave 1 Output

**Date**: 2026-04-14 | **Branch**: `026-performance-debug` | **Inputs**: `audit.md` (commit `2f17aad`) + `framework-audit.md` (commit `2c481bc`, citations re-sourced in `9bd4ee8`)

**Headline numbers (A1)**: warm-state factoid p50 ≈ **26,300 ms** vs SC-004 target 4,000 ms = **6.5× over budget**. GPU at 92–100% SM during generation — bottleneck is **token volume / round-trip count**, not hardware capacity. Per-stage telemetry (`stage_timings_json`) **IS POPULATED** for all 79 query_traces (verified by orchestrator post-Gate-1: `SELECT CASE WHEN stage_timings_json IS NULL THEN 'NULL' ELSE 'POPULATED' END, COUNT(*) FROM query_traces` → POPULATED|79). Sample row: `{"intent_classification":{"duration_ms":1088.7},"embedding":{"duration_ms":...},...}`. **A1's FINDING COLD-004 (telemetry NULL) is incorrect** — likely looked at a different column or stale data. Implication: A6 has REAL per-stage data and should query `query_traces.stage_timings_json` directly to empirically validate the architecture-derived ranking below before Iteration 1.

## Top-3 Latency Contributors (Ranked)

| Rank | Contributor | Estimated p50 (ms) | Source (audit §) | Fix Approach Sketch |
|------|-------------|--------------------|------------------|---------------------|
| 1 | `verify_groundedness` — full LLM round-trip per turn at `backend/agent/nodes.py:467-553`, `method="json_mode"` (silently inert for thinking models per BUG-016, still pays full latency) | 3,000–8,000 | A2 §F4.5 + A1 §GPU §Generation | Gate behind new `enable_groundedness_check: bool = False` in `backend/config.py`; short-circuit when False. Default OFF. ~5 LOC change, blast radius limited to a single node. |
| 2 | Orchestrator iteration explosion (10× LLM calls per query forced by BUG-010 closing the `"sufficient"` exit branch) | ~10,000 | A2 §F4.2 + A1 §ColdStart §FINDING COLD-001 | **A5's BUG-010 fix automatically resolves this — A6 does NOT touch.** A5 fixes the dict-vs-attribute mismatch at `nodes.py:423` ↔ `confidence.py:107`; orchestrator can then exit on iteration 1–2 via `"sufficient"`. |
| 3 | `validate_citations` cross-encoder `.rank()` worst case O(citations × chunks) at `backend/agent/nodes.py:569-665` | 2,000–5,000 | A2 §F4.6 | Batch all `claim × chunk` pairs into a single `.rank()` call (cross-encoder API supports this natively). A6 fallback for Iteration 2 if Top-1 fix doesn't close SC-004. |

## Top-1 Target for Wave 3 A6

**`verify_groundedness` at `backend/agent/nodes.py:467-553`.** The function is currently INERT for the active default model (`gemma4:e4b` thinking-model, BUG-016) — it returns `groundedness_result=None` silently — yet it still pays a full LLM round-trip (3–8 s) on every chat turn. Fix direction: introduce `enable_groundedness_check` settings flag (default False), short-circuit when False, document in `audit.md` Config Changes table. After A3's Wave 2 model revert to `qwen2.5:7b` and A6's Wave 3 gate fix, A6 re-benchmarks via FR-002 harness; if SC-004 still fails, Iteration 2 targets `validate_citations` batching (Rank 3).

## Reasoning Trace (Sequential Thinking — 7 thoughts)

1. Per-stage telemetry is broken (NULL `stage_timings_json`); architectural decomposition of LLM round-trips totals 17–27 s, matching A1's 26 s measurement.
2. Largest single contributor is BUG-010-induced orchestrator iterations (~10 s) but that's A5's fix; second-largest is `verify_groundedness` (~3–8 s) which is purely A6's.
3. A1 + A2 findings converge: GPU saturation at 92–100% SM ⇒ bottleneck is token volume ⇒ A2's "redundant verify_groundedness LLM call" hypothesis fits.
4. Smallest fix for verify_groundedness: settings flag default OFF + short-circuit. ~5 LOC, no blast radius beyond the single node.
5. Risk of fix moving bottleneck sideways: LOW for the fix itself; MEDIUM for SC-004 PASS — even with all three Top-3 fixes the math doesn't necessarily hit 4 s p50; iteration cap may need to escalate to user.
6. Final ranking placed verify_groundedness as Rank 1 (A6's target), BUG-010 iteration explosion as Rank 2 (A5's territory, deferred from A6's iteration count), validate_citations as Rank 3 (A6's Iteration-2 fallback).
7. Open issues for the orchestrator to surface: telemetry gap, iteration cap clarity, docker-compose.yml NEVER-TOUCH conflict with BUG-021 prerequisite, new checkpoints.db growth bug, confidence non-determinism explanation.

## Open Issues for Wave 2+

- ~~Telemetry blocker (FINDING COLD-004)~~ **CORRECTED 2026-04-14 by orchestrator**: `stage_timings_json` is **POPULATED for all 79 traces** (direct DB query). A1's audit was wrong on this point. A6 can read `query_traces.stage_timings_json` directly to empirically rank stages — no ad-hoc instrumentation needed. A7's FR-008/SC-007 test should already pass against current state. A8 documents the correction in `bug-registry-spec26.md` (mark COLD-004 as FALSE-POSITIVE).
- **BUG-021 prerequisite vs NEVER-TOUCH list**: A1 confirmed backend container has `torch.cuda.is_available()=False` because docker-compose.yml has no GPU deploy block for `backend`. plan.md §Files NEVER to touch lists docker-compose.yml. **Recommendation**: defer BUG-021 to follow-up spec; A6 SKIPS it in spec-26; A8 documents the prerequisite + deferral in `bug-registry-spec26.md`.
- **NEW BUG (not in spec-25 registry)**: `checkpoints.db` unbounded growth — 4.4 MB/query × 79 queries = 349 MB; ~44 GB at 10K queries. No TTL or cleanup. A8 must add to `bug-registry-spec26.md` as DISCOVERED-IN-SPEC-26 with severity P1; consider scope-creep into spec-26 only if a 5-LOC fix exists, otherwise defer.
- **Confidence non-determinism explanation** (informational, A5): A1 saw confidence = 0 mostly but occasionally 97–100. A2 §F4.9 explains: BUG-010 only kills the `aggregate_answers → compute_confidence` path; other writers (`verify_groundedness`, `fallback_response`, `collect_answer`) write valid values. When `_keep_last` reducer's most recent write is one of those, confidence appears valid. A5's fix MUST unify the scale (recommend int 0–100 at every write site) per A2 §F4.9.

## Iteration Cap Reminder (FR-005, clarified)

A6 has at most **2** contributor-fix iterations within this spec. Iteration 1 = `verify_groundedness` gate (Rank 1). If SC-004 still fails after re-benchmark: Iteration 2 = `validate_citations` batching (Rank 3). Rank 2 (BUG-010 iteration explosion) is deferred to A5's parallel work — does NOT count against A6's cap. If both A6 iterations fail to clear SC-004, mark SC-004 as **FAIL** in `validation-report.md` with "FR-005 iteration cap reached after Top-1 + Top-2" rationale; do NOT open Iteration 3.
