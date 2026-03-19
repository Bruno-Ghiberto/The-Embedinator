# Research: MetaReasoningGraph

**Branch**: `004-meta-reasoning` | **Date**: 2026-03-11 | **Plan**: [plan.md](plan.md)

## Summary

No NEEDS CLARIFICATION items remained after the `/speckit.clarify` session (5 clarifications resolved). This research phase documents the 8 key decisions made during specification and planning, including alternatives evaluated.

## Decisions

### R1: Quality Evaluation Method — Cross-Encoder via Reranker

**Decision**: Use the project's `Reranker` class (`backend/retrieval/reranker.py`) for retrieval quality evaluation. Call `reranker.rerank(query, chunks, top_k=len(chunks))` to score ALL chunks.

**Rationale**: The `Reranker` wraps `sentence_transformers.CrossEncoder` and uses `model.rank()` internally. It provides quantitative, reproducible scores independent of LLM self-assessment (FR-003). Reusing the existing class avoids duplicating cross-encoder logic. Scoring all chunks (not default top-5) is essential for computing accurate mean relevance and variance signals.

**Alternatives considered**:
- Raw `CrossEncoder.predict()` — bypasses project abstraction, loses circuit breaker integration
- LLM self-assessment — rejected per FR-003; subjective, non-reproducible

### R2: Score Variance Signal — statistics.stdev

**Decision**: Use `statistics.stdev(chunk_relevance_scores)` as the variance signal for the RELAX_FILTERS strategy decision, with configurable threshold `settings.meta_variance_threshold` (default 0.15).

**Rationale**: The original architecture blueprint referenced `answer_coherence` as a decision signal, but it was never defined, computed, or configured anywhere. `stdev` of cross-encoder scores is a concrete, measurable signal derived from existing chunk scores — high variance indicates a mix of relevant and irrelevant chunks, suggesting over-restrictive metadata filters.

**Alternatives considered**:
- `answer_coherence` — undefined in any state schema or node; would require LLM self-assessment (violates FR-003)
- Score range (max - min) — less statistically meaningful than stdev for small sample sizes

### R3: Strategy Deduplication — attempted_strategies Set

**Decision**: Track previously attempted strategies in `attempted_strategies: set[str]` field on `MetaReasoningState`. On subsequent attempts, exclude already-tried strategies and fall back to the next best alternative from a priority order (FR-015).

**Rationale**: Without dedup, the second meta-reasoning attempt could repeat the same failed strategy, wasting the retry budget. The set-based approach is O(1) lookup and naturally extends to any number of strategies.

**Alternatives considered**:
- List-based tracking — O(n) lookup, no functional advantage
- Single `last_strategy` field — insufficient for >2 strategies or >2 attempts

### R4: Configurable Thresholds — Settings Fields

**Decision**: Add `meta_relevance_threshold: float = 0.2` and `meta_variance_threshold: float = 0.15` to `backend/config.py` `Settings` class.

**Rationale**: Thresholds are model-dependent (different cross-encoder models produce different score distributions). Environment variables allow tuning without code changes (FR-004 clarification). Defaults chosen based on cross-encoder/ms-marco-MiniLM-L-6-v2 typical output ranges.

**Alternatives considered**:
- Hardcoded constants — inflexible, violates clarification decision
- Per-collection thresholds — over-engineering for current scope

### R5: SSE Status Events — NDJSON Extension

**Decision**: Emit `{"type": "meta_reasoning", "data": {"status": "...", "attempt": N}}` events via the existing NDJSON streaming protocol during meta-reasoning nodes (FR-014).

**Rationale**: Users experience up to 20s additional latency during meta-reasoning. Lightweight status events ("Trying alternative approaches...", "Evaluating retrieval quality...") keep the user informed without protocol changes. Extends the existing `type` vocabulary used by spec-02/03 events.

**Alternatives considered**:
- Silent processing (no events) — poor UX during latency spike
- WebSocket push — unnecessary protocol change; NDJSON already established

### R6: Node Interface Contract — Config DI Pattern

**Decision**: All nodes follow `async def name(state: MetaReasoningState, config: RunnableConfig = None) -> dict` with dependencies resolved from `config["configurable"]`.

**Rationale**: Established convention from spec-03. `config: RunnableConfig = None` (not `RunnableConfig | None`) due to LangGraph quirk. Return partial `dict` (not full TypedDict) for state updates. Dependencies (LLM, Reranker) injected via configurable dict, not keyword args.

**Alternatives considered**:
- Keyword arg DI (`*, llm: BaseChatModel`) — inconsistent with spec-03 convention, doesn't work with LangGraph's node invocation

### R7: Graph Structure — Subgraph in ResearchGraph

**Decision**: MetaReasoningGraph is compiled as a standalone `StateGraph` and invoked from a `meta_reasoning` node in ResearchGraph. The `should_continue_loop` edge's `"exhausted"` route is updated from `fallback_response` to `meta_reasoning`.

**Rationale**: Subgraph composition keeps the MetaReasoningGraph testable in isolation while allowing clean integration. State mapping between ResearchState and MetaReasoningState happens at the node boundary. When `meta_reasoning_max_attempts == 0`, routing falls back to `fallback_response` (FR-011).

**Alternatives considered**:
- Inline nodes in ResearchGraph — clutters the research graph, harder to test in isolation
- Separate endpoint — violates single-entry-point architecture

### R8: Retry Failure Handling — Direct to Uncertainty

**Decision**: If the ResearchGraph retry after applying `modified_state` encounters an infrastructure error (Qdrant down, LLM timeout), route directly to `report_uncertainty` with the error noted (FR-017).

**Rationale**: Infrastructure errors (service unavailability, connection failures) are not recoverable by changing search strategies. Additional retry attempts would waste time and resources. The circuit breaker at the tool level handles transient failures; persistent failures should surface as honest uncertainty.

**Alternatives considered**:
- Retry with different strategy — wrong recovery for infrastructure failures
- Silent retry with backoff — already handled by tenacity at the tool call level
