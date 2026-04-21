# Feature Specification: Performance Debug and Hardware Utilization Audit

**Feature Branch**: `026-performance-debug`
**Created**: 2026-04-13
**Status**: Draft
**Input**: User description: "Read /home/brunoghiberto/Documents/Projects/The-Embedinator/docs/PROMPTS/spec-26-performance-debug/26-specify.md"

## Clarifications

### Session 2026-04-13

- Q: FR-004 — Which thinking-model compatibility path does spec-26 adopt? → A: Path B — revert default LLM to a non-thinking model (`qwen2.5:7b`), publish a tested-and-recommended model list, and fail-fast at startup when an unsupported thinking model is selected.
- Q: P3 bug fix policy — how does spec-26 treat P3 bugs (BUG-021, BUG-022, BUG-023)? → A: Fix opportunistically. Cheap wins surfaced by the audit (one-line config changes, obvious defaults) are fixed in-spec; complex P3s are deferred with a documented rationale in the bug registry.
- Q: Latency success-criteria measurement surface — cold-start or warm-state? → A: Warm-state p50 gates SC-004 and SC-005. Cold-start (first-query-after-startup VRAM load penalty) is measured and reported separately in the benchmark output and the public performance document but does not block acceptance.

## Overview

Spec-26 is the **quality gate before public release**. The Embedinator works — specs 01 through 25 proved the architecture — but observed query latency is **26–158 seconds** against a spec-14 budget of 1.2 seconds, confidence scoring emits `0` on every response, thinking-model tokens break structured output parsers, and the circuit breaker opens under light concurrent load. These issues live scattered across session notes, engram memory, and prior bug lists; spec-26 consolidates them into one managed artifact, audits whether the system actually uses the hardware it targets, and closes the gap between "it runs" and "it runs well" before the public sees the project.

This is not a rewrite. It is an **honesty spec**: every open bug gets fixed or consciously deferred, every configuration knob gets justified against measured evidence, and every performance number in the public README gets defensible before it ships.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Performance Audit Produces Evidence (Priority: P1)

As a maintainer preparing the project for public open-source release, I run the audit tooling and receive concrete, reproducible measurements of CPU, GPU, RAM, disk, and framework-configuration health on the reference workstation. I can point at specific numbers in the audit report instead of speculating about bottlenecks.

**Why this priority**: Every downstream fix depends on knowing what is actually slow, what is actually idle, and which framework primitives are misconfigured. Without evidence, fixes are guesses.

**Independent Test**: Running the benchmark harness and audit scripts against the seeded corpus produces a hardware utilization report and a framework configuration report that cover every audit question with a measured answer.

**Acceptance Scenarios**:

1. **Given** the seeded corpus and a running stack, **When** the benchmark harness runs, **Then** it emits a dated JSON result with p50, p90, and p99 latencies per pipeline stage and overall.
2. **Given** the hardware audit report, **When** a reader inspects the CPU, GPU, RAM, and disk sections, **Then** every answer includes a concrete number, the measurement method, and a timestamp.
3. **Given** the framework audit report, **When** a reader inspects any finding, **Then** it cites the exact source location and links to the framework documentation that justifies the configuration choice.

---

### User Story 2 — Confidence Scoring Reflects Retrieval Quality (Priority: P1)

As a user asking a well-grounded factoid question, I see a confidence score on the response that reflects the actual quality of the retrieval — not a flat `0`.

**Why this priority**: A confidence value of `0` on every answer makes the UI feature meaningless and is visible to anyone running the app. It also breaks downstream logic (the research loop's continuation check depends on confidence crossing a threshold, which is unreachable while the score is always `0`).

**Independent Test**: Run a regression set of queries with known-relevant chunks available; observe confidence scores distributed above the low-confidence threshold. Run a second set with no relevant chunks; observe scores calibrated low.

**Acceptance Scenarios**:

1. **Given** a query that retrieves four or more chunks rated as relevant, **When** the response completes, **Then** the emitted confidence score is greater than 30 on the 0–100 scale.
2. **Given** a query that retrieves no relevant chunks, **When** the response completes, **Then** the emitted confidence score is 30 or below.
3. **Given** a regression seed run three times, **When** scores are compared, **Then** the confidence distribution is stable across runs.

---

### User Story 3 — Supported-Model Gate with Fail-Fast (Priority: P1)

As a user selecting an LLM from the model picker, the system either runs a model on the supported list cleanly (no parser exceptions) or refuses to start with a clear error message that names the supported alternatives. The default LLM is a proven non-thinking model; thinking models are explicitly unsupported in this release and rejected at startup.

**Why this priority**: Silent failures with circuit breakers tripping is the worst of both worlds. An explicit supported-model list with fail-fast validation eliminates the entire class of thinking-token parsing failures and makes the system's model-compatibility contract auditable.

**Independent Test**: With the default (non-thinking) model, run 20 consecutive queries and observe zero parser-exception fallback events. With an unsupported thinking model configured, observe startup refusal with a message that names the supported alternatives.

**Acceptance Scenarios**:

1. **Given** the default LLM is active (non-thinking, from the supported list), **When** 20 consecutive queries run, **Then** no parser-exception fallbacks are recorded in the logs.
2. **Given** a model not on the supported list is configured, **When** the backend starts, **Then** startup fails with a clear error message that names the tested-and-recommended alternatives.
3. **Given** the public documentation, **When** a reader checks the model-support section, **Then** they find the explicit tested-and-recommended list and a statement that thinking models are unsupported in the current release.

---

### User Story 4 — Latency Within Near-Term Budget (Priority: P1)

As a user running a typical factoid query on the reference workstation, first-token latency arrives within **4 seconds** — the realistic near-term target, defined as three times the aspirational spec-14 Phase 2 budget of 1.2 seconds.

**Why this priority**: Public-release perception. A 4-second first-token latency feels acceptable for a local-first system; 26 seconds feels broken.

**Independent Test**: Benchmark harness on the seeded corpus produces a p50 first-token latency for factoid queries below the 4-second target, and below 12 seconds for analytical queries (three times the analytical budget).

**Acceptance Scenarios**:

1. **Given** the seeded corpus, reference hardware, and a warmed backend (at least one priming query has run), **When** the benchmark harness runs 30 factoid queries, **Then** warm-state p50 first-token latency is under 4 seconds.
2. **Given** the same corpus and warmed backend, **When** the harness runs 10 analytical queries, **Then** warm-state p50 first-token latency is under 12 seconds.
3. **Given** any benchmark run, **When** a reader inspects the result file, **Then** cold-start latency (first query after cold backend) is reported alongside warm-state p50/p90/p99 but does not gate acceptance.
4. **Given** the validation commit, **When** a reader inspects the benchmarks directory, **Then** they find a result file alongside the commit that achieved it.

---

### User Story 5 — Concurrent Load Without Circuit Breaker Panic (Priority: P2)

As a developer exercising the system, I submit 5 concurrent queries and all of them complete successfully without the circuit breaker opening or a `CircuitOpenError` being surfaced to the client.

**Why this priority**: Spec-14 asserts support for 3–5 concurrent queries. The current breaker trips at five failures within two minutes under modest load, which violates that contract. P2 because it affects quality of life rather than the core single-user experience.

**Independent Test**: Fire 5 parallel factoid queries from a load script and verify every one returns a `done` event with no circuit-open error raised.

**Acceptance Scenarios**:

1. **Given** 5 parallel factoid queries, **When** all finish, **Then** every response includes a `done` event and no `CircuitOpenError` is emitted.
2. **Given** the production code, **When** a reader inspects what the circuit breaker counts as a "failure", **Then** the logic is documented and recoverable exceptions (parser retries that succeeded) are excluded from the failure counter.

---

### User Story 6 — Telemetry Validation (Priority: P2)

As an operator investigating a slow query, the per-stage timings captured for that query are populated, use a stable set of keys, and sum to within ±5% of the overall latency value — so I can trust the observability layer when I diagnose problems.

**Why this priority**: Spec-14 built the per-stage timing instrumentation but never validated that every query actually populates it with consistent keys. P2 because missing telemetry does not break user queries but does block accurate diagnosis.

**Independent Test**: Run a batch of 100 queries via the benchmark harness and inspect their trace rows for non-empty, stable-keyed timings that sum to the recorded overall latency.

**Acceptance Scenarios**:

1. **Given** any completed query, **When** its trace row is read, **Then** the stage-timings field is non-null and non-empty.
2. **Given** 100 traces from queries of the same shape, **When** the key sets are compared, **Then** they are identical across all 100 rows.
3. **Given** any trace row, **When** per-stage times are summed, **Then** the sum is within ±5% of the recorded overall latency.

---

### User Story 7 — Configuration Defaults Tuned for Reference Hardware (Priority: P2)

As a new user running the project on comparable hardware (16 GB+ RAM, mid-range consumer GPU), the default configuration values produce reasonable out-of-the-box performance, and every non-obvious default carries a comment that cites the audit finding that justified it.

**Why this priority**: The project is about to be open-sourced. New users will inherit the defaults and judge the system by them. P2 because the defaults need audit data first; it is not blocking on its own.

**Independent Test**: Inspect the configuration file for changed defaults; every change has a traceable justification in the audit report and a before-versus-after entry.

**Acceptance Scenarios**:

1. **Given** the configuration module, **When** a reader scans comment lines on default values, **Then** every value changed by spec-26 carries a `# spec-26: <reason>` comment.
2. **Given** the audit report, **When** a reader checks the config-changes section, **Then** a table lists every changed value with before, after, and justification.
3. **Given** the test suite, **When** a regression test loads default settings without overrides, **Then** it asserts the tuned values are present.

---

### Edge Cases

- **Cold-start penalty**: First query after backend startup can include 15–30 seconds of model weight loading into VRAM. Benchmark harness separates cold-start from warm-state via a priming query; warm-state statistics gate SC-004/005, cold-start is reported separately in the output and public performance doc.
- **Orchestrator exhaustion**: Research loop exits via `exhausted` rather than `sufficient` when the orchestrator cannot signal completion. If always `exhausted`, either the orchestrator prompt is broken or the confidence threshold is unreachable (related to User Story 2).
- **Zero tool calls on iteration 1**: Loop completes with empty chunks when the LLM emits no tool calls initially. The audit must decide whether this should raise, retry with a corrected prompt, or short-circuit to collect-answer.
- **Resume-after-interrupt dead code**: The clarification flow uses interrupts; audit must confirm the resume path is exercised in production or document it as dead.
- **Checkpoint database growth**: Long-running sessions can inflate the checkpoint store. Audit must measure growth rate and recommend retention.
- **VRAM headroom during rerank**: If cross-encoder moves to GPU, verify free VRAM after model weights load to avoid out-of-memory under concurrent load.
- **Run-to-run benchmark variance**: Three independent benchmark runs on identical configuration must produce p50 values within ±15% of each other; larger variance indicates unreliable measurement.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001 — Audit Gate Before Code Changes**: The system MUST produce a hardware utilization audit report and a framework configuration audit report before any code change that targets a performance bug is committed. The audit reports MUST be committed before any bugfix commit, verifiable by commit order on the feature branch.

- **FR-002 — Benchmark Harness**: The system MUST provide a reproducible benchmark harness that seeds a deterministic corpus, runs a configurable number of factoid and analytical queries, records per-stage timings from the telemetry layer, and emits a JSON result file containing warm-state p50, p90, and p99 latencies per stage and overall, plus a separately-labelled cold-start latency for the first query after a cold backend. The harness MUST use a priming query (not counted in warm-state statistics) to separate the two regimes, and MUST be idempotent and re-runnable.

- **FR-003 — Confidence Scoring Root-Cause Fix**: The system MUST identify the root cause of the confidence score always being 0, apply a code fix, and add an automated regression test that asserts a non-zero confidence value for a retrieval that contains relevant chunks.

- **FR-004 — Supported-Model Gate with Fail-Fast**: The system MUST (a) revert the default LLM to a proven non-thinking model (`qwen2.5:7b`), (b) define and publish a tested-and-recommended supported-model list, and (c) validate the configured LLM against that list at backend startup. If the configured model is not on the list, startup MUST fail with a clear error message that names the supported alternatives. Thinking models are explicitly unsupported in this release.

- **FR-005 — Latency Investigation and Fix**: The system MUST identify the single biggest contributor to first-token latency via per-stage timings, apply a fix that either brings p50 factoid latency under 4 seconds, or — if the bottleneck reveals a fundamental architectural limit — documents the limit and targets the next-largest contributor within this spec. Maximum of 2 contributor-fix iterations within this spec; a third contributor (if the first two move the bottleneck sideways without clearing SC-004) MUST be deferred to a follow-up spec with a documented rationale in the bug registry, and SC-004/005 evaluated as FAIL with explicit explanation.

- **FR-006 — Circuit Breaker Review**: The system MUST audit what counts as a "failure" in the breaker's counter, exclude recoverable exceptions that retry successfully from the counter, and add an integration test that confirms 10 queries where 5 would have tripped the breaker under old rules do not trip it under the corrected rules.

- **FR-007 — Proper Token Counting in Message Trimming**: The system MUST replace the current character-based token counter in message trimming with a provider-aware or library-based true token counter, and add a unit test that asserts correct trim behavior on a 10,000-token conversation.

- **FR-008 — Stage Timings Validation**: The system MUST provide a unit test asserting that for any completed query trace row, the stage-timings field is populated, keys come from an expected stable set, and per-stage times sum to within ±5% of the overall latency.

- **FR-009 — Configuration Tuning Documentation**: The system MUST accompany every configuration default changed by this spec with: (a) a trailing source comment citing the audit finding, (b) a row in the audit report's config-changes table with before, after, and justification, and (c) a reference to the commit that applied the change.

- **FR-010 — Public-Release Performance Notes**: The system MUST publish a performance documentation page that honestly describes measured performance on the reference hardware, expected degradation on weaker hardware, and any known limitations. The document MUST be linked from the project README before public release.

### Non-Functional Requirements

- **NFR-001 — No Regression Against Prior Budgets**: Any metric that already meets its spec-14 budget before spec-26 begins MUST continue to meet it after spec-26 completes. Measured improvement, never regression. Budgets verified in scope: first-token latency (gated by SC-004/005), Qdrant hybrid search p50 (< 100 ms target), `GET /api/health` p50 (< 50 ms target), and ingestion throughput (≥ 10 pages/sec target). Each carries a spot-check entry in the validation report; any budget reported as regressed blocks Gate 4.

- **NFR-002 — Makefile Preserved**: The Makefile MUST remain unchanged from the branch-start baseline. The benchmark harness is invoked directly as a script; Makefile integration is deferred.

- **NFR-003 — Reproducible Benchmarks**: Three independent benchmark runs on the same seeded corpus, same model versions, and same configuration MUST produce p50 latency values within ±15% of one another. Run-to-run variance MUST be documented in the audit report.

- **NFR-004 — Modern Framework Versions Preserved**: No downgrade of Python, LangGraph, or LangChain to work around framework-configuration issues. If a framework API has changed, migration to the new API is the required path.

- **NFR-005 — Test Runner Policy Preserved**: All test execution MUST use the project's external test runner script. Baseline pre-existing test failures MUST remain unchanged (no regressions introduced by spec-26).

### Key Entities

- **Bug Registry**: Authoritative list of open issues consolidated from specs 21 through 25, each with a severity tier (P1 blocking, P2 quality-of-life, P3 deferrable), a symptom, a surface area, a required outcome, and — for P3s — a resolution disposition (`fixed-in-spec` for cheap wins or `deferred` with a rationale and follow-up pointer).

- **Hardware Utilization Audit**: Report capturing measured CPU, GPU, RAM, and disk usage under representative load; answers the question "is the backend actually using the hardware it targets?" for every relevant subsystem.

- **Framework Configuration Audit**: Report capturing every agent-framework primitive in use — state reducers, checkpointers, conditional edges, parallel fan-out, recursion limits, token counters, structured output parsers, retry policies — with a finding and a documentation citation for each.

- **Benchmark Result**: Dated JSON record of a benchmark run, containing the commit identifier, corpus fingerprint, model identifiers, per-stage p50/p90/p99 latencies, and overall latency.

- **Query Trace**: Per-query telemetry row with a stable-keyed stage-timings field; the unit of observability that the audit, harness, and validation all read from.

- **Configuration Knob**: A tunable default in the backend configuration module; after spec-26, every knob changed by this spec carries a source comment and a row in the audit's config-changes table.

- **Audit Synthesis**: Orchestrator-authored ranking of the top-3 latency contributors, derived from the Hardware Utilization Audit and Framework Configuration Audit via a Sequential Thinking reasoning session at Gate 1. Names the top-1 contributor that FR-005's fix targets in the subsequent wave.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The audit reports land before any bugfix commit on the feature branch; verified by commit ordering.
- **SC-002**: A well-grounded factoid query with four or more relevant chunks produces a confidence score greater than 30 on the 0–100 scale; a unit test locks in the non-zero result.
- **SC-003**: With the default supported model active, 20 consecutive queries complete without a parser-exception fallback; configuring an unsupported model triggers a fail-fast at backend startup with a clear error naming the supported alternatives.
- **SC-004**: Warm-state factoid p50 first-token latency on the reference workstation is under 4 seconds, measured by the benchmark harness on the seeded corpus after a priming query.
- **SC-005**: Warm-state analytical p50 first-token latency on the reference workstation is under 12 seconds, measured after a priming query.
- **SC-006**: Five concurrent factoid queries all complete with a `done` event and no `CircuitOpenError` is surfaced.
- **SC-007**: Every completed query in a benchmark run carries populated, stable-keyed stage timings whose sum is within ±5% of the overall latency.
- **SC-008**: The message-trimming subsystem uses a true token counter; the corresponding unit test passes.
- **SC-009**: Every configuration default changed by this spec carries a `# spec-26: <reason>` comment and a row in the audit report's config-changes table.
- **SC-010**: A public-facing performance document exists, is linked from the README, and its measured numbers match the validation benchmark run.
- **SC-011**: No new test regressions appear compared to the branch-start baseline (baseline is the currently-passing test set on the immediately prior branch HEAD).
- **SC-012**: The Makefile differs by zero bytes from the branch-start baseline.

## Scope

### In Scope

- Consolidating every open bug from spec-21 through spec-25 into one managed registry. P1 and P2 bugs MUST be fixed in-spec. P3 bugs are fixed opportunistically: cheap wins surfaced by the audit (one-line config defaults, obvious device-placement settings) land in-spec; complex P3s are deferred with a documented rationale and a pointer to the follow-up spec.
- Hardware utilization audit across CPU, GPU, RAM, and disk subsystems
- Framework configuration audit across agent orchestration and retrieval primitives
- Configuration default tuning with audit-backed justifications
- Supported-model gate with fail-fast at startup; default reverted to a proven non-thinking model
- Confidence scoring root-cause fix
- Circuit breaker failure-counter review and tuning
- Reproducible benchmark harness and commit-pinned benchmark result
- Telemetry validation — proving the spec-14 per-stage timings are populated and consistent
- Public-facing performance documentation

### Out of Scope

- End-to-end browser testing — scheduled for the immediately following spec-27
- Redesigning the 3-layer agent architecture — spec-26 tunes and audits the existing design; it does not replace it
- Migrating off the current LLM runtime, vector database, or orchestrator framework — any such migration is a separate future spec
- Adding new models to the test matrix beyond those currently installed — future spec
- Frontend performance optimization — frontend is not the bottleneck on current measurements
- Distributed deployment, horizontal scaling, GPU multiplexing
- Security hardening beyond what the audit surfaces incidentally — spec-13's domain
- Makefile modifications — preserved as a hard rule (NFR-002)

## Dependencies

- **Spec-14 (Performance Budgets)** — defines target latency budgets and the per-stage timings schema used by FR-002, FR-008, and SC-004/005/007
- **Spec-15 (Observability)** — structured logging and trace identifier propagation consumed by the audit and benchmark tooling
- **Spec-07 (Storage Architecture)** — the query traces table that carries per-stage timings
- **Spec-02 (Conversation Graph)** — conversation state and top-level graph that benchmark and audit measure
- **Spec-03 (Research Graph)** — research loop, orchestrator, and should-continue logic that User Story 2 and FR-005 touch
- **Spec-10 (Provider Architecture)** — active-provider resolution consumed by FR-004's model-compatibility path
- **Spec-25 (Master Debug)** — forensic analysis that seeded the bug inventory consolidated in this spec

## Assumptions

- The reference workstation (Intel i7-12700K, 64 GB DDR5, RTX 4070 Ti 12 GB VRAM, NVMe SSD, Fedora Linux 43) is the target hardware for all measurements and tuning; weaker hardware is expected to degrade gracefully.
- The current LLM runtime and vector database stack is retained; no swap to alternative runtimes is in scope.
- The spec-14 per-stage timings instrumentation exists and is correctly wired, pending FR-008 validation.
- The benchmark corpus seeded by existing project tooling is representative of typical user content.
- Fixes land as small, reviewable commits with the bug identifier in the commit message.
- The project's external test runner is operational; pre-existing baseline test failures are tolerated but not extended.
- "Thinking model" means any LLM that emits internal-reasoning tokens delimited by markup before its user-visible answer.
