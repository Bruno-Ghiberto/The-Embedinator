# Feature Specification: Performance Budgets and Pipeline Instrumentation

**Feature Branch**: `014-performance-budgets`
**Created**: 2026-03-18
**Status**: Draft
**Input**: User description: "Read @Docs/PROMPTS/spec-14-performance/14-specify.md"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Query Response Time Verification (Priority: P1)

As a developer deploying The Embedinator, I want the system to stay within
its defined response time budgets for all pipeline stages, so that users
experience consistently fast answers without unexpected delays.

**Why this priority**: Response time is the most user-visible quality metric.
If queries are slow, users lose trust in the system regardless of answer
accuracy. Configuration defaults must be tuned to keep each stage within
budget before other performance work is meaningful.

**Independent Test**: Send a set of factoid queries against a pre-loaded
collection and measure time to first response token. Delivers value as a
standalone benchmark confirming the system meets its latency targets.

**Acceptance Scenarios**:

1. **Given** a collection with at least 500 indexed chunks, **When** a
   simple factoid query is submitted, **Then** the first response token
   appears within 1.5 seconds of submission.
2. **Given** a collection with at least 500 indexed chunks, **When** a
   complex analytical query requiring multiple sub-questions is submitted,
   **Then** the first response token appears within 6 seconds of submission.
3. **Given** any chat query, **When** the answer is fully generated,
   **Then** the complete response is delivered within 3 seconds for simple
   queries and within 10 seconds for complex queries.

---

### User Story 2 — Per-Stage Timing Visibility (Priority: P2)

As a power user investigating a slow query, I want to see a breakdown of
how long each stage of the query pipeline took, so that I can identify
which component is the bottleneck without guessing.

**Why this priority**: Total latency alone is insufficient for diagnosis.
When a query takes longer than expected, users need to know whether the
delay is in retrieval, ranking, or generation. This per-stage data does
not currently exist and is the primary new work of this spec.

**Independent Test**: Run a query and inspect its saved trace record to
confirm it contains named timing entries for each pipeline stage. Delivers
standalone value as soon as trace records include per-stage data.

**Acceptance Scenarios**:

1. **Given** a completed query, **When** the user views its trace record,
   **Then** the record shows the time spent in each major processing stage
   (at minimum: intent classification, retrieval, ranking, answer generation,
   and verification when executed).
2. **Given** a query where one stage is unexpectedly slow, **When** the
   user examines the trace, **Then** the slow stage is clearly identifiable
   by its recorded duration relative to others.
3. **Given** a trace record with per-stage data, **When** the total latency
   field is also present, **Then** the sum of stage durations is consistent
   with the total latency (accounting for minor overhead).

---

### User Story 3 — Document Ingestion Throughput Verification (Priority: P2)

As a developer loading a large document collection, I want ingestion to
complete within predictable time bounds, so that I can plan indexing time
for collections of known size.

**Why this priority**: Users with large document sets need confidence that
ingestion is not a bottleneck. Defined, verifiable throughput targets give
a planning basis and expose regressions if ingestion slows unexpectedly.

**Independent Test**: Time the ingestion of a 10-page PDF and a 200-page
PDF against the defined targets. Delivers standalone value as a confirmed
throughput benchmark.

**Acceptance Scenarios**:

1. **Given** a 10-page PDF submitted for ingestion, **When** ingestion
   completes, **Then** all document chunks are searchable within 3 seconds.
2. **Given** a 200-page PDF submitted for ingestion, **When** ingestion
   completes, **Then** all document chunks are searchable within 15 seconds.
3. **Given** a 50 KB Markdown file submitted for ingestion, **When**
   ingestion completes, **Then** all chunks are searchable within 5 seconds.

---

### User Story 4 — Concurrent Query Handling (Priority: P3)

As a user running queries from multiple browser tabs, I want the system to
handle simultaneous queries without errors, so that I can work across several
conversations at once without interference.

**Why this priority**: The system targets 1–5 concurrent users. Verifying
this boundary ensures the system does not crash or degrade under expected
real-world use. This is primarily a verification story; the architecture
already provides isolation by design.

**Independent Test**: Send 3 simultaneous queries from independent sessions
and confirm all return valid answers. Delivers value as a concurrency
smoke test.

**Acceptance Scenarios**:

1. **Given** 3 simultaneous chat queries from different sessions, **When**
   all are submitted concurrently, **Then** all 3 return valid, complete
   answers without errors or timeouts.
2. **Given** 3 concurrent queries in flight, **When** one query takes
   longer than expected, **Then** the other queries are not blocked and
   complete independently.
3. **Given** an ongoing document ingestion, **When** a concurrent chat
   query is submitted, **Then** the chat query completes without error
   and ingestion continues unaffected.

---

### Edge Cases

- What happens when a query is submitted while the inference model is at
  maximum concurrency? The system must return a graceful response rather
  than an error.
- What happens when a document exceeds the throughput budget on
  minimum-spec hardware? Ingestion must still complete eventually; only
  the benchmark target time may be exceeded on non-reference hardware.
- What happens when per-stage timing data is missing for a legacy trace
  record written before this spec was implemented? The trace must remain
  readable; a null or absent `stage_timings_json` field is treated as
  "pre-instrumentation" and displayed accordingly — not as zeros.
- What happens when a conditional stage (grounded verification,
  meta-reasoning) does not execute? Its key is omitted from
  `stage_timings_json` entirely — an absent key means "did not run".
- What happens when memory usage approaches the defined budget under
  concurrent load? Queries must still complete; budgets are guidelines,
  not hard runtime limits.
- What happens when a pipeline stage errors mid-execution? Its entry in
  `stage_timings_json` MUST record the duration up to the error and include
  a `"failed": true` marker. Subsequent stages that did not execute are omitted.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST operate within defined time budgets for each
  stage of the chat query pipeline. Compliance is demonstrated through
  benchmarking, not runtime enforcement.

- **FR-002**: Document ingestion MUST complete within defined time bounds:
  a 10-page PDF in under 3 seconds, a 200-page PDF in under 15 seconds,
  and a 50 KB Markdown file in under 5 seconds.

- **FR-003**: Each service MUST operate within defined memory guidelines
  during normal use. Exceeding a guideline produces an observable warning
  (a `structlog` WARNING-level log event emitted at application startup,
  estimating memory based on known model sizes and configuration); it does
  not cause a hard failure and requires no new runtime dependency.

- **FR-004**: The system MUST handle 3–5 simultaneous chat queries from
  independent sessions without errors, data corruption, or one query
  blocking another.

- **FR-005**: Every chat query that produces a trace record MUST include a
  per-stage timing breakdown in `stage_timings_json` covering at minimum:
  intent classification, embedding, retrieval, ranking, and answer generation
  (always present). Conditional stages (grounded verification, meta-reasoning)
  MUST be omitted when they do not execute. If a stage errors, its entry MUST
  include the duration up to the point of failure plus a `"failed": true`
  marker — partial timing data is more useful than no data. This data MUST
  be stored in a new dedicated `stage_timings_json` column, separate from
  `reasoning_steps_json` and `latency_ms`.

- **FR-006**: The system MUST sustain a minimum response streaming rate of
  50 output events per second during answer generation.

- **FR-008**: The `stage_timings_json` field MUST be included in the
  response payload of the existing trace detail endpoint, making per-stage
  data accessible without direct database access.

- **FR-007**: The system MUST sustain a minimum of 1,000 storage write
  operations per second during document ingestion without data loss or
  corruption.

### Key Entities

- **Query trace**: A persistent record of a single query's execution,
  extended by this spec to include a structured per-stage timing breakdown
  stored in a new dedicated `stage_timings_json` column in the trace record.
  This column is separate from the existing `reasoning_steps_json` (which
  stores agent reasoning narrative) and `latency_ms` (total duration).

- **Pipeline stage**: A named processing step in the query handling flow
  (e.g., "intent classification", "retrieval", "ranking"). Each stage has
  a defined time budget and a measured actual duration recorded per query.

- **Performance budget**: A defined time or memory threshold for a
  component or service, used as a benchmarking target and monitoring
  reference rather than a hard runtime limit.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Simple factoid queries return their first visible response
  token within 1.5 seconds of submission on the reference hardware
  (25% margin over the 1.2-second Phase 2 budget).

- **SC-002**: Complex analytical queries return their first visible response
  token within 6 seconds of submission on the reference hardware.

- **SC-003**: A 10-page PDF is fully indexed and searchable within 3 seconds
  of submission on the reference hardware.

- **SC-004**: A 200-page PDF is fully indexed and searchable within 15 seconds
  of submission on the reference hardware.

- **SC-005**: The system backend consumes less than 600 MB of memory at idle,
  including all loaded models except the inference engine.

- **SC-006**: Three simultaneous chat queries from independent sessions all
  return complete, valid answers without any errors or timeouts within
  30 seconds.

- **SC-007**: Every query trace record contains a per-stage timing breakdown
  with at least 5 always-present named stages (intent classification,
  embedding, retrieval, ranking, answer generation). Conditional stages
  (grounded verification, meta-reasoning) appear only when executed.
  The breakdown is accessible via the existing trace detail API endpoint
  and verifiable by fetching any trace record produced after this spec
  is implemented.

- **SC-008**: Response token streaming sustains at least 50 output events
  per second during answer generation, measurable by recording event
  arrival timestamps during a live streaming response.

---

## Scope

### In Scope

- Ensuring configuration defaults keep each pipeline stage within its
  defined time budget.
- Adding per-stage timing instrumentation to the query processing flow
  and storing the results as structured data within each trace record.
- Verifying ingestion throughput for standard document sizes against
  defined targets.
- Verifying concurrent query handling for up to 5 simultaneous sessions.
- Verifying memory usage at idle and under query load.
- Defining reproducible benchmark procedures for all success criteria.

### Out of Scope

- Runtime enforcement of per-stage time limits (hard timeouts per stage).
- Horizontal scaling, load balancing, or multi-node deployment.
- GPU-accelerated ranking (ranking runs on CPU by design).
- External caching layers.
- Frontend bundle size optimization.
- Profiling tooling integration beyond standard timing primitives.

---

## Assumptions

- The reference hardware (Intel i7-12700K, 64 GB DDR5, NVIDIA RTX 4070 Ti,
  NVMe SSD, Windows 11 Pro / macOS 13+ / Linux) is the benchmark baseline.
  Performance on minimum-spec hardware (8 GB RAM, 4-core CPU, no GPU) may
  exceed these time budgets.
- The current implementation is Phase 2 (Grounded Verification active);
  Phase 1 latency numbers are historical reference only.
- Concurrent query capacity is limited by the inference engine's sequential
  processing model, not the application layer.
- Per-stage timing data for trace records created before this spec is
  implemented will be absent; this is expected and acceptable.
- The Rust ingestion worker is already implemented; ingestion throughput
  targets apply to the existing implementation.
- Ingestion targets apply to text-based documents; scanned or image-only
  PDFs are not in scope.

---

## Dependencies

- **Spec 02** (Conversation Graph): query pipeline stages are defined by
  the agent graph; instrumentation points must be added to those nodes.
- **Spec 03** (Research Graph): analytical-tier timing covers sub-question
  research loops; instrumentation must cover Research Graph nodes.
- **Spec 04** (Meta-Reasoning): per-stage timing includes the meta-reasoning
  phase when triggered; instrumentation must cover that graph.
- **Spec 06** (Ingestion Pipeline): ingestion throughput targets apply to
  the Rust worker and Python embedding pipeline already implemented.
- **Spec 07** (Storage): the query traces table already stores total latency;
  this spec adds per-stage data to that same record structure.
- **Spec 08** (API Reference): the chat endpoint is the timing entry point;
  total wall-clock measurement starts at request receipt.
- **Spec 15** (Observability): latency alerting and breakdown charts depend
  on the per-stage data introduced by this spec.

---

## Clarifications

### Session 2026-03-18

- Q: Where should per-stage timing data be stored in the trace record? → A: New dedicated `stage_timings_json` column in `query_traces`, separate from `reasoning_steps_json` and `latency_ms`.
- Q: When a conditional stage does not execute, how should it appear in the timing breakdown? → A: Omit the stage entirely — absent key means "did not run".
- Q: When a pipeline stage errors mid-execution, what should `stage_timings_json` contain? → A: Record duration up to the error with a `"failed": true` flag on that stage entry.
- Q: How must `stage_timings_json` be accessible to satisfy SC-007? → A: Exposed in the existing `GET /api/traces/{id}` response payload — no new endpoint required.
