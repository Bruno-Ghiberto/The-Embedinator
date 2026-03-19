# Feature Specification: Accuracy, Precision & Robustness Enhancements

**Feature Branch**: `005-accuracy-robustness`
**Created**: 2026-03-12
**Status**: Draft
**Input**: User description: "Read @Docs/PROMPTS/spec-05-accuracy/05-specify.md"

## Clarifications

### Session 2026-03-12

- Q: When the in-memory upsert buffer (cap 1,000) is full during a vector store outage, should the system drop excess items or pause the ingestion job? → A: Pause the ingestion job when buffer is full; resume automatically when buffer drains on recovery.
- Q: Should per-claim groundedness verdicts be persisted after the response is delivered, or are they ephemeral? → A: Ephemeral — verdicts exist only during the response pipeline; not stored after delivery.
- Q: When an operator disables groundedness verification, should users see any indication in the response that claims were not verified? → A: No indication — the response appears identical to users regardless of whether verification is enabled or disabled.
- Q: Should the circuit breaker operate as one circuit per service or one circuit per operation type within a service? → A: One circuit per service (e.g., one for inference service, one for vector store), shared across all operations against that service.
- Q: Should this spec define observability requirements for groundedness verification (e.g., claim verdict rate metrics), or defer to the observability spec? → A: Defer all observability instrumentation to the dedicated observability spec.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Grounded Answer Verification (Priority: P1)

As a user asking a factual question, I want the system to verify that its own answer is supported by the documents it retrieved, so I can trust that every claim in the response comes from real evidence -- not hallucination.

When the system is not confident in a claim, it explicitly marks it as `[unverified]` or removes it, rather than silently including unsupported information. If more than half the claims cannot be verified, the entire answer is flagged with a visible warning.

**Why this priority**: Answer groundedness is the core trust signal in a RAG system. False or unsupported claims are the most harmful form of system failure. P1 because it directly protects users from acting on hallucinated information.

**Independent Test**: Can be fully tested by submitting a query whose answer includes claims both supported and contradicted by retrieved documents, then verifying the response correctly annotates or removes the problematic claims.

**Acceptance Scenarios**:

1. **Given** the system has generated an answer and retrieved supporting context, **When** the answer contains a claim directly supported by a retrieved passage, **Then** that claim appears in the response without annotation.
2. **Given** an answer contains a claim with no support in any retrieved passage, **When** groundedness verification runs, **Then** the claim is annotated with `[unverified]` in the final response.
3. **Given** an answer contains a claim that contradicts a retrieved passage, **When** groundedness verification runs, **Then** the contradicted claim is removed and a brief explanation is appended.
4. **Given** more than 50% of claims in an answer are unsupported, **When** verification completes, **Then** the entire answer is visibly flagged with a warning to the user.
5. **Given** the verification service is temporarily unavailable, **When** the system encounters the failure, **Then** the answer is delivered without verification annotations rather than failing entirely, and the failure is logged.

---

### User Story 2 - Citation-Chunk Alignment Validation (Priority: P2)

As a user reviewing an answer with inline citations like `[1]`, `[2]`, I want every citation to actually point to a document passage that supports the surrounding claim, so I can trust that reviewing a citation will show genuinely relevant evidence.

When a citation does not support the claim it annotates, the system either remaps it to the most relevant passage or removes it -- preventing misleading or dangling references.

**Why this priority**: Incorrect citations create a false appearance of sourcing. P2 because it reinforces trust in the citation system once groundedness is secured.

**Independent Test**: Can be tested by crafting an answer where citation `[1]` is intentionally attached to a sentence it does not support, then verifying the system remaps it to a better chunk or strips it.

**Acceptance Scenarios**:

1. **Given** an answer has an inline citation and the referenced chunk genuinely supports the annotated claim, **When** citation validation runs, **Then** the citation is preserved unchanged.
2. **Given** an inline citation references a chunk whose content is unrelated to the claim, **When** citation validation runs, **Then** the citation is remapped to the highest-scoring relevant chunk, or stripped if no sufficiently relevant chunk exists.
3. **Given** citation validation fails due to a service error, **When** the error is caught, **Then** citations are passed through unvalidated rather than blocking the response.

---

### User Story 3 - Meaningful Confidence Indicator (Priority: P3)

As a user reading a response, I want to see a meaningful confidence indicator (high / moderate / low) that reflects the actual quality of the evidence the system found, so I can calibrate how much to rely on the answer.

The confidence score must be based on measurable retrieval signals -- not the language model's self-assessment -- because LLMs tend to rate themselves highly regardless of actual retrieval quality.

**Why this priority**: Confidence indicators inform downstream decisions. A misleading "high confidence" on weakly-evidenced answers is worse than showing none. P3 because it is a presentation layer built on top of P1/P2 infrastructure.

**Independent Test**: Can be tested by submitting queries with deliberately sparse, low-quality retrieval results and verifying the confidence indicator shows "low", versus rich retrieval producing "high".

**Acceptance Scenarios**:

1. **Given** retrieval returns many highly relevant, diverse passages, **When** the confidence score is computed, **Then** the indicator displayed shows "High confidence" (green).
2. **Given** retrieval returns few or weakly-relevant passages, **When** the confidence score is computed, **Then** the indicator shows "Low confidence" (red).
3. **Given** verification reveals several unsupported claims, **When** the confidence adjustment is applied, **Then** the displayed confidence score is lower than the raw retrieval-based score.
4. **Given** any response, **When** the confidence score is computed multiple times with identical retrieval results, **Then** the score is identical each time (deterministic).

---

### User Story 4 - Query-Adaptive Retrieval Depth (Priority: P4)

As a user asking a simple factoid question ("What version does the API support?"), I want a fast answer without unnecessary retrieval overhead. Conversely, when I ask a complex analytical question spanning multiple documents, I want the system to invest appropriate effort to find comprehensive evidence.

The system automatically classifies each query into a complexity tier and adjusts retrieval effort accordingly, without any input from the user.

**Why this priority**: Efficiency and answer quality trade-off. Over-retrieving for simple queries wastes latency; under-retrieving for complex ones degrades quality. P4 because it improves experience without being a correctness requirement.

**Independent Test**: Can be tested by submitting a simple factoid query and a multi-hop analytical query, then verifying the retrieval parameters differ measurably between the two.

**Acceptance Scenarios**:

1. **Given** a query classified as `factoid`, **When** retrieval begins, **Then** the system uses a shallow retrieval configuration (few chunks, low iteration limit, high confidence threshold).
2. **Given** a query classified as `analytical` or `multi_hop`, **When** retrieval begins, **Then** the system uses a deep retrieval configuration (more chunks, higher iteration limit, lower confidence threshold).
3. **Given** any query, **When** complexity classification runs, **Then** the classified tier is one of five defined levels: factoid, lookup, comparison, analytical, multi_hop.

---

### User Story 5 - Embedding Integrity Validation (Priority: P5)

As an operator ingesting documents, I want the system to reject corrupt or malformed embedding vectors before they are stored, so that the search index is never silently polluted with bad data that degrades retrieval quality.

Failed embeddings are logged with a reason and skipped -- but the rest of the batch continues, so a single corrupt vector does not block an entire ingestion job.

**Why this priority**: Silent corruption in a vector index degrades retrieval for all future queries without any obvious error. P5 because it is a data integrity concern at the ingestion boundary.

**Independent Test**: Can be tested by injecting a NaN-containing or zero vector into an ingestion batch and verifying the vector is rejected, logged, and the rest of the batch completes successfully.

**Acceptance Scenarios**:

1. **Given** an embedding vector contains NaN values, **When** validation runs, **Then** the vector is rejected, a log entry is created, and the batch continues.
2. **Given** an embedding vector is all zeros, **When** validation runs, **Then** it is rejected and logged.
3. **Given** an embedding vector has the wrong number of dimensions, **When** validation runs, **Then** it is rejected and logged.
4. **Given** an embedding vector has a near-zero magnitude, **When** validation runs, **Then** it is rejected and logged.
5. **Given** a batch contains 3 corrupt vectors and 97 valid ones, **When** the batch is processed, **Then** exactly 97 vectors are stored and 3 are logged as skipped.

---

### User Story 6 - Resilience Under External Service Failures (Priority: P6)

As a user chatting or an operator ingesting documents, I want the system to remain functional and return informative errors when the underlying inference or vector storage services are temporarily unavailable -- rather than hanging indefinitely or crashing silently.

The system uses automatic retries with backoff for transient failures and stops forwarding requests (circuit breaker) when a service is persistently down, preventing cascading timeouts.

**Why this priority**: Availability under partial failure is a fundamental reliability requirement. P6 because the baseline system functions with stubs in earlier specs; this hardens the production path.

**Independent Test**: Can be tested by simulating a service that fails 5 consecutive times, verifying the circuit opens, then recovering the service and verifying the circuit closes after a successful test request.

**Acceptance Scenarios**:

1. **Given** an external service call fails transiently, **When** the error is detected, **Then** the system retries up to 3 times with exponential backoff before treating the call as failed.
2. **Given** a service has failed 5 consecutive times, **When** the next call is attempted, **Then** the circuit opens and the call is rejected immediately without waiting for a timeout.
3. **Given** a circuit is open, **When** 30 seconds have elapsed, **Then** the circuit enters a half-open state and allows one test request through.
4. **Given** a test request in half-open state succeeds, **When** the result is recorded, **Then** the circuit closes and normal operation resumes.
5. **Given** a test request in half-open state fails, **When** the result is recorded, **Then** the circuit returns to open state.
6. **Given** the inference service is down during a chat request, **When** the error is returned to the user, **Then** the user receives an informative message indicating the service is unavailable, not a generic crash.
7. *(Deferred to spec-06 — ingestion pipeline not yet created)* **Given** the vector store is unreachable during an ingestion job, **When** the failure is detected, **Then** upserts are buffered in memory (up to 1,000 items) and flushed when the connection recovers.
8. *(Deferred to spec-06 — ingestion pipeline not yet created)* **Given** the in-memory upsert buffer has reached its 1,000-item capacity and the vector store is still unreachable, **When** a new upsert attempt arrives, **Then** the ingestion job is paused (not aborted) and resumes automatically once the buffer drains on recovery.

---

### Edge Cases

- What happens when groundedness verification produces zero verifiable claims (e.g., the answer is purely structural: "Here are the results...")?
- What happens when the complexity classifier falls back to a default tier due to an unexpected query format?
- How does the circuit breaker handle concurrent requests that all arrive during the half-open test window?
- What happens when embedding validation rejects every vector in a batch (100% failure rate)?
- What happens when the confidence adjustment from groundedness verification would drive the displayed score below the minimum?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST evaluate each factual claim in a generated answer as SUPPORTED, UNSUPPORTED, or CONTRADICTED against the retrieved context before returning the response.
- **FR-002**: System MUST annotate UNSUPPORTED claims with `[unverified]` in the final response.
- **FR-003**: System MUST remove CONTRADICTED claims and append a brief explanation of the contradiction.
- **FR-004**: System MUST flag the entire answer with a warning when more than 50% of claims are UNSUPPORTED.
- **FR-005**: System MUST deliver the answer unmodified (without verification annotations) when the groundedness verification call fails, and log the failure.
- **FR-006**: System MUST validate every inline citation by scoring the relevance of the cited chunk against the surrounding claim.
- **FR-007**: System MUST remap citations scoring below the alignment threshold to the highest-scoring relevant chunk, or remove them if no sufficiently relevant chunk exists.
- **FR-008**: System MUST pass citations through unvalidated when citation validation fails, rather than blocking the response.
- **FR-009**: System MUST classify every incoming query into one of five complexity tiers: factoid, lookup, comparison, analytical, multi_hop.
- **FR-010**: System MUST apply tier-specific retrieval parameters (retrieval depth, iteration limit, tool call limit, confidence threshold) based on the classified tier.
- **FR-011**: System MUST compute the confidence score from measurable retrieval signals (rerank scores, chunk counts, score variance, collection coverage), never from language model self-assessment.
- **FR-012**: System MUST apply a post-verification confidence adjustment based on the groundedness result, reducing the score proportionally when claims are unsupported.
- **FR-013**: System MUST display a confidence indicator with three levels: High (score ≥0.7), Moderate (0.4–0.69), Low (<0.4). The displayed confidence value is the post-verification adjusted score as computed in FR-012.
- **FR-014**: System MUST validate every embedding vector before storage against four checks: correct dimension count, no NaN values, non-zero vector, and magnitude above threshold. *(Implementation deferred to spec-06 — `backend/ingestion/embedder.py` not yet created; interface contract defined in `contracts/embedder-validation.md`; see ADR-002.)*
- **FR-015**: System MUST skip invalid embedding vectors and log each failure with the reason, without aborting the rest of the batch. *(Implementation deferred to spec-06; see ADR-002.)*
- **FR-016**: System MUST retry failed external service calls up to 3 times with exponential backoff plus jitter.
- **FR-017**: System MUST maintain one circuit breaker per external service (one for the inference service, one for the vector store), shared across all operation types targeting that service. The circuit MUST open after 5 consecutive failures to that service, rejecting all further calls to it immediately for a 30-second cooldown period.
- **FR-018**: System MUST allow one test request after the cooldown period expires (half-open state); on success, close the circuit; on failure, reopen it.
- **FR-019**: System MUST return informative, user-readable error messages when the inference service or vector store is unavailable, instead of hanging or returning generic errors.
- **FR-020**: System MUST buffer up to 1,000 pending vector upserts in memory when the vector store is unreachable during ingestion; when the buffer reaches capacity, the system MUST pause the ingestion job rather than dropping items, and MUST resume and flush the buffer automatically once the connection recovers. *(Implementation deferred to spec-06 — ingestion pipeline not yet created; see Out of Scope.)*
- **FR-021**: Groundedness verification MUST be configurable: when disabled by the operator, the system skips verification and returns the raw answer. The response format and user experience MUST be identical whether verification is enabled or disabled — no disclaimer or indicator is shown to users.

### Key Entities

- **ClaimVerification**: Represents the verdict for a single factual claim -- includes the original claim text, verdict (supported / unsupported / contradicted), which document chunk supports or contradicts it, and a brief explanation. Ephemeral: exists only during the response pipeline.
- **GroundednessResult**: The overall output of the verification step -- contains a list of ClaimVerification entries, a boolean indicating whether the majority of claims are grounded, and a confidence adjustment multiplier applied to the final score. Ephemeral: not persisted after the response is delivered.
- **ComplexityTier**: An enumerated classification (factoid, lookup, comparison, analytical, multi_hop) assigned to each query based on its inherent retrieval complexity; determines the retrieval depth configuration used.
- **CircuitBreakerState**: The state of each external service connection at any point in time: closed (normal operation), open (failing fast), or half-open (testing recovery). One instance exists per service (inference service and vector store); all operation types share the same circuit state for a given service.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of answers with verifiable factual claims pass through groundedness verification; no unsupported claims appear in responses without annotation when verification is enabled.
- **SC-002**: 100% of inline citations either score above the alignment threshold or are remapped or removed; no misaligned citations appear in delivered responses.
- **SC-003**: The confidence indicator matches the correct level (High / Moderate / Low) for all responses based on the defined score ranges, with zero misclassifications.
- **SC-004**: Factoid queries use a retrieval configuration measurably shallower than multi-hop queries (at minimum: fewer chunks and a lower iteration limit), as verified through logged retrieval parameters.
- **SC-005**: 0% of embedding vectors with NaN values, all-zero content, wrong dimensions, or near-zero magnitude reach the vector store; all such vectors are logged with the failure reason.
- **SC-006**: The system automatically recovers from transient service failures within the retry window (3 attempts) without user intervention.
- **SC-007**: Once a circuit opens (after 5 consecutive failures), no further requests are forwarded to the failed service until the cooldown period elapses and the test request succeeds.
- **SC-008**: When a circuit is open, users receive a readable error response within 1 second, not a network-timeout hang.
- **SC-009**: Groundedness verification adds at most one additional inference call per answer, regardless of the number of claims.
- **SC-010**: Citation validation adds no perceptible latency to the overall response time (completes in under 50ms per answer).

## Assumptions

- The relevance scoring model used for citation alignment is the same model already used for retrieval reranking -- no new model dependency is introduced.
- The 5-signal confidence formula (rerank scores, chunk counts, score variance, collection coverage) is already implemented from the ResearchGraph spec; this feature adds a post-verification adjustment layer on top of the existing score.
- Query complexity classification is already part of the query rewriting step, which already outputs a `complexity_tier` field; this feature defines the behavior when that tier is applied to select retrieval parameters.
- The circuit breaker pattern for the vector search client is already partially implemented; this feature standardizes and extends it to cover the ingestion pipeline.
- The embedding validation logic is defined here as an interface contract but will be physically implemented inside the ingestion pipeline component (a separate feature spec that depends on this one).
- Buffering vector upserts in memory during store outages is capped at 1,000 items to prevent unbounded memory growth; when the buffer is full, the ingestion job pauses rather than dropping items, and resumes automatically on recovery.
- The alignment threshold for citation validation (default 0.3) is operator-configurable.

## Out of Scope

- Persistent storage of per-claim groundedness verdicts or full `GroundednessResult` objects after response delivery (audit trails and analytics on groundedness are deferred to the observability spec).
- Observability instrumentation for groundedness verification (metrics, dashboards, alerting on verdict rates, skip rates) — deferred entirely to the dedicated observability spec.
- UI for operators to review historical groundedness results per query.
- **FR-014 / FR-015 — Embedding vector validation implementation**: `backend/ingestion/embedder.py` does not yet exist. The interface contract is defined in `contracts/embedder-validation.md`; physical implementation is deferred to spec-06. See ADR-002.
- **FR-020 — Upsert buffer / ingestion job pause-and-resume**: The ingestion pipeline (`backend/ingestion/`) is out of scope for this spec. This requirement is deferred to spec-06 which creates the ingestion pipeline. US6 acceptance scenarios 7 and 8 are annotated as deferred accordingly.
