# Feature Specification: MetaReasoningGraph

**Feature Branch**: `004-meta-reasoning`
**Created**: 2026-03-11
**Status**: Draft
**Input**: MetaReasoningGraph — Layer 3 of the three-layer agent architecture. Failure diagnosis and recovery when the ResearchGraph exhausts its budget without reaching confidence threshold.

## Clarifications

### Session 2026-03-11

- Q: Should the user see feedback during meta-reasoning, or is it invisible? → A: Lightweight status events — emit SSE stream events (e.g., "Trying alternative approaches...", "Evaluating retrieval quality...") so the user knows the system is working during the extra latency.
- Q: On the second meta-reasoning attempt, must the system try a different strategy or can it repeat? → A: Must try a different strategy — track previously attempted strategies and exclude them from selection on subsequent attempts.
- Q: Should strategy decision thresholds (mean relevance 0.2, score variance 0.15) be hardcoded or configurable? → A: Configurable via Settings with sensible defaults — thresholds are model-dependent and must be tunable per environment without code changes.
- Q: Should meta-reasoning emit structured log events and/or metrics counters for operator monitoring? → A: Structured log events per node — each node emits structlog JSON events (strategy selected, scores, attempt count) with session/trace ID, consistent with existing spec-02/03 logging patterns.
- Q: What happens if the ResearchGraph retry after recovery encounters an infrastructure error? → A: Route to report_uncertainty with the infrastructure error noted — retrying a different strategy won't help if the service is down; circuit breaker handles transient failures at the tool level.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automatic Recovery from Poor Retrieval (Priority: P1)

A user asks a question about a topic that exists in their uploaded documents, but the initial search uses the wrong collection or overly restrictive filters. Instead of receiving an unhelpful "I don't know" response, the system automatically diagnoses the retrieval failure, selects a recovery strategy, and retries with modified search parameters — ultimately returning a useful, evidence-based answer.

**Why this priority**: This is the core value proposition of the MetaReasoningGraph. Without it, the system degrades to a simple "try once, give up" RAG — losing the primary architectural differentiator.

**Independent Test**: Can be tested by creating a collection with relevant documents, asking a question that requires a collection switch or filter relaxation, and verifying the system recovers and returns a grounded answer within 2 meta-reasoning attempts.

**Acceptance Scenarios**:

1. **Given** retrieved chunks have low relevance scores (mean < 0.2) and few chunks (< 3), **When** the ResearchGraph exhausts its budget, **Then** the MetaReasoningGraph triggers WIDEN_SEARCH, retries with broader parameters, and returns an answer with confidence above the threshold.
2. **Given** retrieved chunks have low relevance scores (mean < 0.2) but many chunks (>= 3), **When** the ResearchGraph exhausts its budget, **Then** the MetaReasoningGraph triggers CHANGE_COLLECTION, switches to a different collection, and retries.
3. **Given** retrieved chunks have moderate relevance (mean >= 0.2) but high score variance (> 0.15), **When** the ResearchGraph exhausts its budget, **Then** the MetaReasoningGraph triggers RELAX_FILTERS, removes restrictive metadata constraints, and retries.

---

### User Story 2 - Honest Uncertainty Reporting (Priority: P1)

When the system genuinely cannot find relevant information — even after recovery attempts — the user receives a transparent explanation of what was searched, what was found (or not), and actionable suggestions for how to get a better answer (e.g., upload more documents, try different phrasing, select a different collection).

**Why this priority**: Equal to P1 because honest uncertainty is the safety net. Users must never receive fabricated or guessed answers. A well-crafted "I don't know" with actionable guidance is more valuable than a hallucinated answer.

**Independent Test**: Can be tested by asking a question about a topic that does not exist in any collection, verifying the system does not fabricate an answer, and confirming the uncertainty report includes specific details about what was searched and practical suggestions.

**Acceptance Scenarios**:

1. **Given** the MetaReasoningGraph has exhausted its maximum recovery attempts, **When** no strategy has improved confidence above the threshold, **Then** the system produces an honest uncertainty report that names the collections searched, summarizes what was found, and suggests user actions.
2. **Given** a user asks about a topic with no indexed documents, **When** the system reaches meta-reasoning, **Then** the uncertainty report does NOT contain fabricated facts, does NOT use "based on the available context" followed by a guess, and DOES suggest uploading relevant documents.

---

### User Story 3 - Alternative Query Formulation (Priority: P2)

Before attempting recovery strategies, the system automatically generates alternative phrasings of the user's question — using different terminology, simpler sub-components, or broader scope — to improve the chances of finding relevant documents on retry.

**Why this priority**: Alternative queries increase the surface area of retrieval. They are a prerequisite for effective WIDEN_SEARCH and CHANGE_COLLECTION strategies, but the system can still function with the original query alone.

**Independent Test**: Can be tested by providing a technical question with jargon, verifying that 3 alternative formulations are generated with meaningfully different terminology, and confirming they are used during retry.

**Acceptance Scenarios**:

1. **Given** a sub-question that uses specialized terminology, **When** the MetaReasoningGraph generates alternatives, **Then** exactly 3 alternative query formulations are produced, each using a different rephrasing strategy (synonym replacement, sub-component breakdown, scope broadening).
2. **Given** 3 alternative queries are generated, **When** the WIDEN_SEARCH or CHANGE_COLLECTION strategy is selected, **Then** the retry uses the alternative queries as part of the modified search parameters.

---

### User Story 4 - Cross-Encoder Quality Evaluation (Priority: P2)

The system uses quantitative cross-encoder scoring — not LLM self-assessment — to diagnose retrieval quality. This provides reproducible, measurable signals that drive strategy selection without relying on the LLM's subjective confidence.

**Why this priority**: Cross-encoder evaluation is the diagnostic backbone. It produces the mean relevance score and per-chunk scores that determine which recovery strategy to select. Without it, strategy selection would be random or LLM-guessed.

**Independent Test**: Can be tested by providing a set of chunks with known relevance to a query, verifying the cross-encoder produces accurate scores, and confirming the mean and per-chunk scores correctly classify the failure mode.

**Acceptance Scenarios**:

1. **Given** a sub-question and a set of retrieved chunks, **When** retrieval quality is evaluated, **Then** every chunk receives a cross-encoder relevance score, the mean relevance score is computed, and per-chunk scores are recorded in state.
2. **Given** chunks with uniformly low scores (mean < 0.2, 2 chunks), **When** the strategy decision runs, **Then** WIDEN_SEARCH is selected (not CHANGE_COLLECTION or RELAX_FILTERS).

---

### User Story 5 - Recursion Protection (Priority: P2)

The meta-reasoning loop is bounded by a configurable maximum attempt count. The system never enters infinite recursion between the ResearchGraph and MetaReasoningGraph, even if every recovery strategy fails to improve confidence.

**Why this priority**: Safety guardrail. Without it, a pathological query could cause the system to loop indefinitely between research and meta-reasoning, consuming resources and blocking the user.

**Independent Test**: Can be tested by providing a query that cannot be answered (empty collection), verifying that the system attempts recovery at most the configured maximum number of times, and then produces an uncertainty report.

**Acceptance Scenarios**:

1. **Given** the maximum attempts is configured to 2, **When** the first recovery attempt fails to reach the confidence threshold, **Then** the system retries exactly once more before forcing uncertainty reporting.
2. **Given** meta_attempt_count equals the configured maximum, **When** the strategy decision runs, **Then** report_uncertainty is forced regardless of evaluation scores.

---

### User Story 6 - Seamless Integration with ResearchGraph (Priority: P3)

The MetaReasoningGraph integrates as a subgraph within the ResearchGraph, replacing the current direct-to-fallback routing. When triggered, it receives the current research context, and when recovery succeeds, the ResearchGraph seamlessly re-enters its orchestrator loop with modified parameters.

**Why this priority**: Integration is the wiring that makes everything work together. It depends on all other stories being implemented first but is essential for end-to-end functionality.

**Independent Test**: Can be tested by running a full end-to-end query that triggers meta-reasoning, verifying the graph compiles without errors, the routing from `should_continue_loop` correctly reaches meta-reasoning, and the modified state flows back into the ResearchGraph loop.

**Acceptance Scenarios**:

1. **Given** the MetaReasoningGraph is compiled as a subgraph, **When** `should_continue_loop` returns "exhausted", **Then** the meta_reasoning node is invoked (not fallback_response).
2. **Given** a recovery strategy produces a modified_state, **When** the MetaReasoningGraph completes, **Then** the ResearchGraph re-enters the orchestrator loop with the updated parameters applied.
3. **Given** report_uncertainty is reached, **When** the MetaReasoningGraph completes, **Then** its answer and uncertainty_reason are propagated back through the ResearchGraph to the ConversationGraph.

---

### Edge Cases

- What happens when the retrieved_chunks list is empty (0 chunks) at meta-reasoning entry? Strategy must handle zero-division for mean/score_variance calculations.
- What happens when all chunk_relevance_scores are identical (score_variance = 0.0)? Falls through the strategy decision logic: if mean < threshold, routes to WIDEN_SEARCH or CHANGE_COLLECTION based on chunk count; if mean >= threshold and variance <= threshold, routes to report_uncertainty since no filtering optimization can help.
- What happens when the LLM call for alternative query generation fails? Must degrade gracefully — proceed with original sub_question only.
- What happens when the Reranker/cross-encoder is unavailable (circuit breaker open)? Must skip evaluation and route directly to report_uncertainty.
- What happens when the first recovery attempt produces worse results than the original? The second attempt should still be allowed (meta_attempt_count tracks attempts, not quality).
- What happens when `meta_reasoning_max_attempts` is set to 0? Should skip meta-reasoning entirely and behave as current fallback_response.
- What happens when the ResearchGraph retry (after modified_state) encounters an infrastructure error (Qdrant down, LLM timeout)? Route directly to report_uncertainty with the error noted — retrying another strategy won't help if the underlying service is unavailable.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST generate exactly 3 alternative query formulations when meta-reasoning is triggered, using synonym replacement, sub-component breakdown, and scope broadening strategies.
- **FR-002**: System MUST evaluate retrieval quality using cross-encoder scoring for ALL retrieved chunks (not just top-k), producing a mean relevance score and per-chunk relevance scores.
- **FR-003**: System MUST NOT use LLM self-assessment for quality evaluation — only quantitative cross-encoder scores.
- **FR-004**: System MUST select one of three recovery strategies (WIDEN_SEARCH, CHANGE_COLLECTION, RELAX_FILTERS) based on mean cross-encoder score, chunk count, and score variance, following the defined decision logic. The decision thresholds (mean relevance default: 0.2, score variance default: 0.15) MUST be configurable via application settings and tunable per environment without code changes.
- **FR-005**: System MUST produce concrete state modifications for each strategy that the ResearchGraph can apply on retry (e.g., broadened collections, relaxed filters, increased retrieval limits).
- **FR-006**: System MUST enforce a configurable maximum number of meta-reasoning attempts (default: 2), forcing uncertainty reporting when the limit is reached.
- **FR-007**: System MUST generate an honest uncertainty report when no strategy succeeds, including: collections searched, what was found/missing, why results were insufficient, and actionable suggestions for the user.
- **FR-008**: System MUST NOT fabricate answers or present guesses as evidence in the uncertainty report.
- **FR-009**: System MUST integrate with the ResearchGraph by replacing the current "exhausted" → fallback_response routing with "exhausted" → meta_reasoning.
- **FR-010**: System MUST propagate recovery results (modified_state) back to the ResearchGraph for retry, or propagate uncertainty results back through the ResearchGraph to the ConversationGraph.
- **FR-011**: System MUST handle the case where meta_reasoning_max_attempts is 0 by skipping meta-reasoning and falling back directly (preserving current behavior).
- **FR-012**: System MUST handle cross-encoder unavailability gracefully by returning zero scores (`mean_relevance_score=0.0`, `chunk_relevance_scores=[]`) and allowing the strategy decision to proceed normally. This lets the system attempt a recovery strategy (e.g., WIDEN_SEARCH with raw retrieval scores) rather than immediately giving up.
- **FR-013**: System MUST handle empty chunk lists (0 chunks) at meta-reasoning entry without errors (guard against zero-division in mean/std_dev).
- **FR-014**: System MUST emit lightweight SSE status events during meta-reasoning so the user sees progress (e.g., "Trying alternative approaches...", "Evaluating retrieval quality...", "Retrying with broadened search..."). Events use the existing NDJSON streaming protocol.
- **FR-015**: System MUST track previously attempted strategies and exclude them from selection on subsequent meta-reasoning attempts. If the evaluation signals point to an already-attempted strategy, the system MUST select the next best alternative or force uncertainty reporting if no untried strategies remain.
- **FR-016**: Each meta-reasoning node MUST emit structured log events with session and trace IDs, including: strategy selected, mean relevance score, chunk count, score variance, attempt count, and recovery outcome. Log format MUST be consistent with existing structlog JSON patterns used in specs 02-03.
- **FR-017**: If the ResearchGraph retry after applying modified_state encounters an infrastructure error (service unavailability, connection failure), the system MUST route directly to report_uncertainty with the error noted, rather than attempting additional recovery strategies.

### Key Entities

- **MetaReasoningState**: The working state for the meta-reasoning phase. Contains the sub-question, retrieved chunks, alternative queries, evaluation scores, attempt counter, previously attempted strategies (for deduplication), selected strategy, modified state for retry, and optional final answer with uncertainty reason.
- **Recovery Strategy**: One of three diagnostic classifications (WIDEN_SEARCH, CHANGE_COLLECTION, RELAX_FILTERS) that maps a specific failure mode to a concrete set of state modifications for retry.
- **Modified State**: A set of ResearchState field overrides produced by the strategy decision, applied when re-entering the ResearchGraph (e.g., broadened collection selection, increased retrieval limits, removed filters).
- **Uncertainty Report**: A structured response produced when all recovery attempts fail, containing what was searched, what was found, why it was insufficient, and user-actionable suggestions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users receive a relevant, evidence-based answer at least 30% more often for queries that previously triggered "I don't know" responses (compared to direct fallback without meta-reasoning).
- **SC-002**: The uncertainty report, when triggered, provides actionable guidance in 100% of cases — no generic "I don't know" without context.
- **SC-003**: Recovery strategies correctly classify the failure mode at least 85% of the time (WIDEN_SEARCH for coverage gaps, CHANGE_COLLECTION for routing errors, RELAX_FILTERS for over-restrictive filtering).
- **SC-004**: The meta-reasoning phase completes within 10 seconds per attempt at p95 under standard load (including cross-encoder scoring and LLM calls), keeping total additional latency under 20 seconds for a full 2-attempt cycle. Validated by manual benchmarking post-implementation.
- **SC-005**: The system never enters infinite recursion — meta-reasoning attempts are strictly bounded by the configured maximum, verifiable in 100% of test cases.
- **SC-006**: Zero fabricated facts in uncertainty reports, verified by manual review of a sample of 50 uncertainty responses.
