# Feature Specification: Observability Layer

**Feature Branch**: `015-observability`
**Created**: 2026-03-18
**Status**: Draft
**Input**: User description: "Observability layer providing full-stack visibility into RAG pipeline through structured logging, trace ID propagation, metrics collection, and observability dashboard enhancements"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - End-to-End Request Tracing (Priority: P1)

As a system operator investigating a slow or failed query, I want every log entry produced during a single user request to be automatically tagged with the same trace ID so that I can filter all logs for one request and reconstruct the full execution path without manually correlating timestamps.

**Why this priority**: Without automatic trace propagation, operators cannot diagnose production issues -- this is the foundational observability capability that all other stories depend on.

**Independent Test**: Can be fully tested by sending a chat query, capturing the `X-Trace-ID` response header, then searching logs for that trace ID. Every log entry from middleware, agent nodes, storage, and retrieval layers must include the matching `trace_id` field.

**Acceptance Scenarios**:

1. **Given** a user sends a chat query, **When** the system processes it through rewrite, research, compression, and generation stages, **Then** every log entry emitted during that request contains a `trace_id` field matching the `X-Trace-ID` response header.
2. **Given** two users send concurrent chat queries, **When** both requests are processed simultaneously, **Then** each request's log entries contain only their own trace ID with no cross-contamination between requests.
3. **Given** a chat query is processed, **When** the session ID is available, **Then** all log entries for that request also include a `session_id` field for cross-request correlation within a conversation.

---

### User Story 2 - Time-Series Metrics Dashboard (Priority: P2)

As a system operator monitoring system health over time, I want to view time-bucketed trend data for query latency, confidence scores, and meta-reasoning rates so that I can identify performance regressions and usage patterns before they become critical issues.

**Why this priority**: While aggregate statistics exist, they provide no temporal context. Time-series data is essential for trend analysis, capacity planning, and detecting gradual degradation.

**Independent Test**: Can be tested by running several chat queries over a period, then requesting metrics with different time windows (1h, 24h, 7d) and verifying that the response contains properly bucketed data with latency percentiles, confidence averages, and meta-reasoning counts.

**Acceptance Scenarios**:

1. **Given** at least 10 chat queries have been processed in the last 24 hours, **When** I request metrics for a 24-hour window, **Then** the system returns time-bucketed data showing query count, average latency, 95th percentile latency, average confidence, and meta-reasoning trigger count per bucket.
2. **Given** I request metrics with different time windows (1h, 24h, 7d), **When** the data is returned, **Then** each window uses appropriate bucket granularity (e.g., 5-minute buckets for 1h, hourly buckets for 24h, daily buckets for 7d).
3. **Given** I request metrics, **When** the system has circuit breakers for external services, **Then** the response includes the current state and failure count for each circuit breaker.

---

### User Story 3 - Per-Component Log Level Control (Priority: P3)

As a developer debugging a specific subsystem, I want to increase the log verbosity of a single component (e.g., the reranker or search module) without flooding the entire log stream so that I can get detailed diagnostic information while keeping other components at their normal log level.

**Why this priority**: Currently only a global log level exists, which means debugging one component requires accepting verbose logs from all components. This creates noise that makes debugging harder rather than easier.

**Independent Test**: Can be tested by setting a per-component log level override for a specific module to DEBUG while keeping the global level at INFO, sending a query, and verifying that only that component produces debug-level log entries.

**Acceptance Scenarios**:

1. **Given** the global log level is set to INFO, **When** I override a specific component's log level to DEBUG, **Then** only that component emits debug-level log entries while all other components remain at INFO.
2. **Given** no per-component overrides are configured, **When** the system starts, **Then** all components use the global log level as their default.
3. **Given** a per-component override is set via environment variable, **When** the system starts, **Then** the override takes effect without requiring code changes or redeployment.

---

### User Story 4 - Stage Timings Visualization (Priority: P3)

As a user viewing a specific query trace in the observability dashboard, I want to see a visual breakdown of how long each pipeline stage took (rewrite, research, compression, generation) so that I can immediately identify which stage is the bottleneck without parsing raw timing data.

**Why this priority**: The per-stage timing data already exists in storage from a previous spec, but there is no visual representation. Adding a chart turns raw data into actionable insight.

**Independent Test**: Can be tested by processing a chat query, navigating to the trace detail view on the observability page, and verifying that a stage timing chart renders showing time spent in each stage.

**Acceptance Scenarios**:

1. **Given** a query trace includes stage timing data, **When** I view the trace detail on the observability page, **Then** a chart displays showing the duration of each pipeline stage.
2. **Given** a query trace does not include stage timing data (legacy traces), **When** I view the trace detail, **Then** the stage timings chart section is hidden gracefully rather than showing an empty or broken chart.

---

### User Story 5 - Consistent Log Event Naming (Priority: P4)

As a log analysis tool consumer, I want all log events to follow a consistent naming convention with category prefixes so that I can build reliable alerting rules, dashboards, and filters without manually discovering every event name.

**Why this priority**: Log consistency is important for operational maturity but does not block any other observability feature. It can be done incrementally.

**Independent Test**: Can be tested by exercising all major code paths (chat, ingestion, search, provider operations) and verifying that every log event name starts with one of the defined category prefixes and that error events include the error class name.

**Acceptance Scenarios**:

1. **Given** the system is processing various operations, **When** log entries are emitted, **Then** each event name begins with one of the defined category prefixes: `http_`, `agent_`, `retrieval_`, `storage_`, `ingestion_`, `provider_`, `circuit_`.
2. **Given** an error occurs during processing, **When** the error is logged, **Then** the log entry includes an `error` field containing the exception class name.

---

### Edge Cases

- What happens when the metrics endpoint is queried with no query traces in the database? The system should return empty buckets with zero counts rather than an error.
- Background ingestion tasks generate their own trace IDs at task start (covered by FR-014).
- What happens when a per-component log level environment variable contains an invalid value? The system should fall back to the global log level and log a warning.
- How does the system handle very large time windows (e.g., 30 days) in metrics queries? The system should cap the maximum window and return an appropriate message.
- What happens when stage timing data is malformed or contains unexpected keys? The chart should render available data and gracefully skip malformed entries.

## Clarifications

### Session 2026-03-18

- Q: Should FR-011 log event renaming apply to ALL existing log events across the codebase (full rename), or only to new/modified events in this spec? → A: Full rename -- ALL existing log events across the entire codebase must be renamed to follow the prefix convention. No legacy unprefixed event names should remain.
- Q: Should trace ID propagation for background ingestion pipeline tasks be included in this spec's scope? → A: In-scope -- background ingestion tasks must generate and bind a trace ID at task start, included in all ingestion log entries.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST automatically bind the trace ID generated by middleware to structured logging context so that all downstream log entries include the trace ID without explicit parameter passing.
- **FR-002**: System MUST bind the session ID to structured logging context when processing chat requests so that all log entries within a chat request include the session identifier.
- **FR-003**: System MUST clear logging context after each request completes to prevent trace ID and session ID leakage between concurrent requests.
- **FR-004**: System MUST support per-component log level overrides configurable via environment variables, with the global log level as the fallback default.
- **FR-005**: System MUST provide a metrics endpoint that returns time-bucketed trend data for query latency (including percentiles), confidence scores, meta-reasoning rates, and error counts.
- **FR-006**: System MUST support configurable time windows (1h, 24h, 7d) for the metrics endpoint, with appropriate bucket granularity for each window.
- **FR-007**: System MUST include current circuit breaker state (open/closed) and failure count for each monitored service in the metrics response.
- **FR-008**: System MUST include active ingestion job count in the metrics response.
- **FR-009**: System MUST render per-stage timing data as a visual chart in the trace detail view on the observability page when stage timing data is present.
- **FR-010**: System MUST gracefully hide the stage timings chart when a trace does not contain stage timing data.
- **FR-011**: System MUST rename ALL existing log events across the entire codebase to follow consistent event name prefixes, categorized by subsystem (`http_`, `agent_`, `retrieval_`, `storage_`, `ingestion_`, `provider_`, `circuit_`). This is a full codebase-wide rename, not limited to new code.
- **FR-012**: System MUST include the exception class name in an `error` field for all error-level log entries.
- **FR-013**: All backend log output MUST be valid JSON Lines format parseable by standard JSON tools.
- **FR-014**: Background ingestion tasks MUST generate a trace ID at task start and bind it to structured logging context so that all log entries emitted during ingestion processing include a correlatable trace ID.

### Key Entities

- **Query Trace**: A record of a single user query with timing, confidence, and diagnostic data. Stored per-query with 15 fields including trace ID, latency, confidence, stage timings, and meta-reasoning flags.
- **Metrics Bucket**: A time-bounded aggregation of query trace data containing counts, averages, and percentiles for a specific time interval.
- **Circuit Breaker State**: The current open/closed state and failure count for a monitored external service. Three independent circuit breakers exist: vector database, inference, and search.
- **Log Level Override**: A per-component configuration that sets a specific log verbosity level for a single module, overriding the global default.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of log entries produced during an HTTP request or background ingestion task contain a matching `trace_id` field, verified by log inspection across at least 3 different subsystems (agent, storage, retrieval) for HTTP requests and across ingestion modules for background tasks.
- **SC-002**: Zero trace ID leakage between concurrent requests -- verified by sending 5 concurrent requests and confirming each request's logs contain only its own trace ID.
- **SC-003**: Metrics endpoint returns time-bucketed data within 500ms for a 24-hour window with up to 10,000 stored traces.
- **SC-004**: Per-component log level overrides take effect without requiring application restart or code changes -- verified by setting an environment variable and confirming changed verbosity.
- **SC-005**: Stage timings chart renders correctly for traces with timing data and is hidden for traces without -- verified on at least 3 traces of each type.
- **SC-006**: ALL log event names across the entire codebase follow the defined prefix convention -- verified by exercising all major code paths (chat, ingestion, search, provider operations) and confirming every emitted log entry's event name starts with one of the 7 defined prefixes. No legacy unprefixed event names remain.
- **SC-007**: The system handles edge cases gracefully: empty trace database returns empty buckets (not errors), malformed stage timing data is skipped (not crashes), invalid log level overrides fall back to global default with a warning.
