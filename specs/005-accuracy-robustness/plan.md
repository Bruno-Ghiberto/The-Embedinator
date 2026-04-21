# Implementation Plan: Accuracy, Precision & Robustness Enhancements

**Branch**: `005-accuracy-robustness` | **Date**: 2026-03-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-accuracy-robustness/spec.md`

## Summary

Implements five cross-cutting reliability mechanisms that eliminate the most common RAG failure modes. The work completes two Phase 2 stubs (verify_groundedness, validate_citations) introduced in spec-02, extends the existing circuit breaker pattern to qdrant_client.py, applies tier-based parameter lookup in rewrite_query, and adds a post-verification confidence adjustment via GAV's GroundednessResult. The confidence formula itself (spec-03 R8, 5-signal) and all schemas are already implemented and must not be modified.

## Technical Context

**Language/Version**: Python 3.14+
**Primary Dependencies**: LangGraph >= 1.0.10, LangChain >= 1.2.10, sentence-transformers >= 5.2.3, tenacity >= 9.0, Pydantic >= 2.12
**Storage**: SQLite WAL mode (existing `data/embedinator.db`); Qdrant (existing) — no new storage for this feature
**Testing**: pytest via `scripts/run-tests-external.sh` — NEVER run pytest inside Claude Code
**Target Platform**: Linux (Fedora), docker compose
**Project Type**: Web service (backend Python, FastAPI)
**Performance Goals**: GAV adds ≤1 LLM call per answer; citation validation <50ms per batch; circuit breaker rejection <1s
**Constraints**: No new services; no new core dependencies; no changes to confidence.py formula; backend/ingestion/embedder.py deferred to spec-06
**Scale/Scope**: 1–5 concurrent users; all subsystems operate within single FastAPI process

## Constitution Check

*GATE: Evaluated before Phase 0 research. All gates PASS.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Local-First Privacy | ✅ PASS | GAV uses existing local LLM; citation alignment reuses loaded cross-encoder; zero new outbound calls |
| II. Three-Layer Architecture | ✅ PASS | Only ConversationGraph Phase 2 stubs are implemented; 3-layer structure untouched |
| III. Retrieval Pipeline Integrity | ✅ PASS | Cross-encoder (ms-marco-MiniLM-L-6-v2) reused for citation alignment; no pipeline modifications |
| IV. Observability from Day One | ✅ PASS with note | GAV-adjusted `confidence_score` (int 0–100) is produced and emitted in the NDJSON metadata frame. Writing it to `query_traces` is deferred to spec-15 (observability spec) per explicit clarification Q5. Confidence MUST NOT come from LLM self-assessment: the base score originates from spec-03 retrieval signals; the GAV `confidence_adjustment` multiplier is derived from verdict counts (fraction of unsupported claims), not from the LLM's subjective confidence rating — the LLM classifies claims as supported/unsupported/contradicted, and the formula mechanically converts those counts to a multiplier. The base score's retrieval origin is preserved. |
| V. Secure by Design | ✅ PASS | No new credentials; groundedness results are ephemeral (Q2); no new endpoints exposed |
| VI. NDJSON Streaming Contract | ✅ PASS | Adjusted confidence_score feeds existing metadata frame; no protocol change required |
| VII. Simplicity by Default | ✅ PASS | Circuit breaker extends existing HybridSearcher pattern; TIER_PARAMS is a dict constant; no new services |

**Reliability Standards cross-check**: Constitution says "5 failures in 30s" but existing HybridSearcher (spec-03) implements consecutive-count without time window. This spec follows the established pattern (consecutive count) for consistency. The 30s cooldown is preserved. See ADR-001 (`adrs/adr-001-consecutive-count-circuit-breaker.md`) for formal justification.

## Project Structure

### Documentation (this feature)

```text
specs/005-accuracy-robustness/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── sse-events.md
│   └── embedder-validation.md  # FR-014/FR-015 contract (impl deferred to spec-06)
├── adrs/                # Approved Deviations & Deferrals
│   ├── adr-001-consecutive-count-circuit-breaker.md
│   └── adr-002-embedding-validation-deferred.md
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
  agent/
    nodes.py              # verify_groundedness (IMPLEMENT), validate_citations (IMPLEMENT), rewrite_query (EXTEND), inference service circuit breaker module-level state (FR-017 inference side)
    prompts.py            # VERIFY_PROMPT (NEW), FORMAT_RESPONSE_SYSTEM (UPDATE)
    schemas.py            # ClaimVerification, GroundednessResult, QueryAnalysis — ALREADY EXIST
    confidence.py         # compute_confidence() — ALREADY IMPLEMENTED (spec-03 R8); DO NOT MODIFY
    research_nodes.py     # collect_answer() — ALREADY IMPLEMENTED; reads unchanged
    conversation_graph.py # Graph wiring — ALREADY COMPLETE (stubs wired); no changes needed
  retrieval/
    reranker.py           # CrossEncoder — ALREADY EXISTS; reused by validate_citations
  storage/
    qdrant_client.py      # Add circuit breaker state machine (EXTEND from HybridSearcher pattern) — vector store side (FR-017)
  api/
    chat.py               # Catch CircuitOpenError + LLM failures; emit NDJSON error frame (FR-019)
  config.py               # All accuracy/robustness Settings fields ALREADY EXIST; no additions

tests/
  unit/
    test_accuracy_nodes.py        # NEW: GAV, citation threshold, tier params, circuit breaker
  integration/
    test_accuracy_integration.py  # NEW: end-to-end GAV + citation + adaptive depth flows

# NOTE: backend/ingestion/embedder.py DOES NOT EXIST — created by spec-06
```

**Structure Decision**: Single backend project (Option 1). No frontend changes in this spec. No new files except test files and VERIFY_PROMPT addition to prompts.py.

## Complexity Tracking

| Item | Justification | ADR |
|------|---------------|-----|
| Consecutive-count circuit breaker deviates from constitution §Reliability Standards "5 failures in 30s" | Established pattern from spec-03 C1 (HybridSearcher). Operationally equivalent at 1–5 user scale. 30s cooldown preserved. | [ADR-001](adrs/adr-001-consecutive-count-circuit-breaker.md) |
| FR-014/FR-015 (embedding validation) not implemented in this spec despite constitution MUST | `backend/ingestion/embedder.py` does not exist; deferred to spec-06 which creates the ingestion pipeline. Interface contract published in `contracts/embedder-validation.md`. | [ADR-002](adrs/adr-002-embedding-validation-deferred.md) |
| GAV `confidence_adjustment` multiplier derived from LLM verdict counts | Not LLM self-assessment: the LLM classifies claims; the formula converts count ratio to multiplier. Base score is retrieval-only (spec-03 R8). Justified in Constitution Check IV above. | — |

---

## Phase 0: Research Findings

*See [research.md](./research.md) for full findings.*

### Summary of Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Circuit breaker implementation | Custom state machine (extend HybridSearcher) | Tenacity lacks half-open probe semantics; consistency with spec-03 |
| GAV claim extraction | Full-answer batch evaluation via structured LLM output | One LLM call per answer; GroundednessResult already models per-claim verdicts |
| Citation text extraction | Regex split on `[N]` markers + sentence boundary | Simple, deterministic; no new dependency |
| TIER_PARAMS placement | Module-level constant in `nodes.py` | Co-located with rewrite_query; no indirection needed at this scale |
| Confidence adjustment | Multiplier applied inside `verify_groundedness` node | Keeps GAV self-contained; confidence_score in ConversationState is the user-facing value |

---

## Phase 1: Design & Contracts

*See [data-model.md](./data-model.md) and [contracts/](./contracts/) for full details.*

### Design Summary

**verify_groundedness node**:
1. Check `groundedness_check_enabled` (Settings) — if False, return `{"groundedness_result": None}` immediately
2. Build context string from `state["sub_answers"]` (passage texts)
3. Call LLM with `with_structured_output(GroundednessResult)`, low temperature
4. Annotate `state["final_response"]`: append `[unverified]` to unsupported claims; remove contradicted claims
5. Compute confidence adjustment: `int(mean(sub_answer.confidence_score) * result.confidence_adjustment)`, clamped 0-100
6. Return `{"groundedness_result": result, "confidence_score": adjusted, "final_response": annotated}`
7. On LLM failure: return `{"groundedness_result": None}` (graceful degradation, log warning)

**validate_citations node**:
1. For each citation `[N]` in `state["citations"]`: extract surrounding claim text
2. Score `(claim_text, chunk.text)` via `reranker.model.rank()` (batch call)
3. If score < `settings.citation_alignment_threshold` (0.3): remap to highest-scoring chunk, or strip if none clears threshold
4. Return `{"citations": corrected_citations}`
5. On reranker failure: return `{"citations": state["citations"]}` (pass-through, log warning)

**rewrite_query tier application**:
1. After LLM returns `QueryAnalysis`, look up `TIER_PARAMS[analysis.complexity_tier]`
2. Store tier params in return dict: `{"query_analysis": analysis, "retrieval_params": tier_params}`
3. ResearchGraph invocation reads `retrieval_params` from state to override defaults

**qdrant_client.py circuit breaker**:
- Add `_circuit_open: bool`, `_failure_count: int`, `_last_failure_time: float | None`, `_max_failures: int`, `_cooldown_secs: int`
- Implement `_check_circuit()`, `_record_success()`, `_record_failure()` following `HybridSearcher` pattern exactly
- Wrap all public methods (`create_collection`, `upsert`, `search`, `delete`, etc.) with circuit check
