# Bug Registry — Spec 26 Performance Debug

Every open bug from specs 21–25 addressed or consciously deferred during spec-26 execution.
Pre-spec-26 fixes committed to the `025-master-debug` branch before spec-26 started are
included for completeness.

## Severity Tiers

- **P1** — blocking public release
- **P2** — quality-of-life; degrades user perception
- **P3** — hardening; deferrable without blocking release

## Disposition Legend

| Code | Meaning |
|------|---------|
| `fixed-pre-spec-26 <sha>` | Fixed on the preceding branch before spec-26 started |
| `fixed-in-spec-26 <sha>` | Fixed by a commit in the spec-26 branch |
| `mitigated <sha>` | Root cause partially addressed; direct fix deferred with rationale |
| `deferred <follow-up>` | Deferred to a named follow-up spec with documented rationale |
| `false-positive <sha>` | Investigation showed no actual defect; audit artifact corrected |

---

## Registry

### Carryover Bugs from Specs 21–25

| Bug ID | Severity | Description | Disposition | Rationale / Commit |
|--------|----------|-------------|-------------|-------------------|
| BUG-007 | P1 | Session-continuity hang after idle timeout | `fixed-pre-spec-26 bfd178c` | Conversation graph stall resolved on `025-master-debug` before spec-26 began |
| BUG-008 | P1 | Research loop has no wall-clock timeout (runs indefinitely under slow LLM) | `fixed-pre-spec-26 7678e2e` | Wall-clock timeout guard added before spec-26 began |
| BUG-010 | P1 | Confidence score always emits 0 regardless of retrieval quality | `fixed-in-spec-26 4d1f421` | Root cause: `isinstance`-dict guard routed every call to `_legacy_confidence`, which returned 0 because `Citation.relevance_score` was `None`/`0`. Fix: pass `RetrievedChunk` objects directly + unify to int 0–100 scale. Restores Constitution IV compliance |
| BUG-015 | P1 | Concurrent chat crash under parallel requests | `fixed-pre-spec-26 2ceca94` | Race condition in conversation graph state resolved before spec-26 began |
| BUG-016 | P1 | Thinking-model `OutputParserException` breaks structured-output nodes | `mitigated d63736a` | FR-004 Path B: backend validates configured LLM against allowlist at startup; thinking models (`gemma4:*`, `qwen3-thinking`, `deepseek-r1:*`) rejected with a named-alternatives error. Direct parser fix (Path A) deferred — requires provider-level schema handling |
| BUG-017 | P2 | Citation deduplication insufficient — duplicate citations with different `passage_id` but identical text | `deferred spec-27` | `Send()` fan-out in research graph produces duplicates; fix requires reducer changes in `state.py`. Single-user impact is low; architectural change risks regression in concurrent paths |
| BUG-018 | P1 | Circuit breaker opens under light concurrent load (recoverable parser exceptions counted as failures) | `fixed-in-spec-26 75ef43c` | Three explicit `except` clauses added; `OutputParserException` (a recoverable parser retry) no longer increments the failure counter |
| BUG-019 | P2 | `trim_messages` uses `len()` as token counter (counts characters, not tokens) | `fixed-in-spec-26 627178e` | Replaced with tiktoken-based counter at both call sites (`research_nodes.py:139` + `nodes.py:722`); graceful character-count fallback when tiktoken unavailable |
| BUG-021 | P2 | Cross-encoder reranker runs on CPU despite available host GPU | `mitigated 5bae5e2` | **Prereq applied** (`5bae5e2`): backend container now has NVIDIA GPU reservation via `docker-compose.gpu-nvidia.yml` overlay. **Migration deferred to spec-27**: cross-encoder init coupling and ~90 MiB VRAM allocation require isolated testing; deferred to keep SC-004/SC-005 attribution clean |
| BUG-022 | P3 | Embedding model device placement not explicitly configured | `deferred spec-27` | Explicit GPU device for the embedding model requires Ollama container configuration changes outside spec-26 scope |
| BUG-023 | P3 | `embed_max_workers=4` under-utilizes the 20-thread reference CPU | `fixed-in-spec-26 8a1107e` | Raised to 12 per audit §CPU-002 (reference CPU has 20 threads; 12 workers is a conservative safe default for a mixed async workload) |

---

### Bugs Discovered During Spec-26

| ID | Severity | Description | Disposition | Rationale / Commit |
|----|----------|-------------|-------------|-------------------|
| DISK-001 | P1 | `checkpoints.db` grows unbounded — LangGraph checkpoint threads never pruned | `fixed-in-spec-26 c49d9b1` | Startup now prunes threads older than `checkpoint_max_threads` (default 100) to prevent disk exhaustion on long-running instances. Pre-release blocker for public deployment |
| BUG-020 | P2 | `stage_timings_json` population unverified — no regression test asserting the column is populated and consistent | `fixed-in-spec-26 A7-wave4` | FR-008 unit test (`tests/unit/test_stage_timings_validation.py`) added by A7 in Wave 4; asserts populated, stable-keyed, and stage sum within ±5% of overall latency |
| COLD-004 | — | A1 audit flagged `stage_timings_json` as NULL for all query traces | `false-positive 34f969e` | Direct DB query confirmed the column is populated for all 79 traced rows. Audit artifact corrected in `34f969e` |

---

## Summary by Disposition

| Disposition | Count | Bug IDs |
|-------------|-------|---------|
| fixed-pre-spec-26 | 3 | BUG-007, BUG-008, BUG-015 |
| fixed-in-spec-26 | 6 | BUG-010, BUG-018, BUG-019, BUG-020, BUG-023, DISK-001 |
| mitigated | 2 | BUG-016, BUG-021 |
| deferred | 3 | BUG-017, BUG-022, + BUG-021 migration |
| false-positive | 1 | COLD-004 |

---

## Follow-up Spec Candidates

Bugs consciously deferred from spec-26 and recommended for the next iteration:

- **BUG-017** — citation deduplication: reduce duplicate citation noise in multi-tool research
  responses; requires `state.py` reducer change
- **BUG-021** — cross-encoder GPU migration: unblocked since `5bae5e2`; ~90 MiB VRAM required
- **BUG-022** — embedding device placement: explicit GPU config for the embedding container
- **BUG-016 Path A** — thinking-model direct fix: only if community demand materializes and
  provider-level schema handling is available

Latency toward SC-004 (factoid ≤ 4,000 ms) and SC-005 (analytical ≤ 12,000 ms) requires
architectural changes documented in `docs/performance.md` §Spec-27 Candidates.
