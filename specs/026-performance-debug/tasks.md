---
description: "Task list for spec-26 Performance Debug and Hardware Utilization Audit"
---

# Tasks: Performance Debug and Hardware Utilization Audit

**Input**: Design documents from `/specs/026-performance-debug/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `quickstart.md` — all present.
**Tests**: Generated where FRs explicitly require them (FR-003 unit, FR-006 integration, FR-007 unit, FR-008 unit, FR-004 startup-refusal); no speculative tests.
**Organization**: Tasks are grouped by user story. US-1 (audit) is the MVP and blocks every other user story per FR-001 commit-order gate.

## Format: `[TaskID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no blocking dependencies on incomplete work)
- **[Story]**: User story label (`[US1]` … `[US7]`) for user-story phases; setup and foundational phases carry no story label
- Every task lists the concrete file path(s) it touches
- Tasks map to the 8 agent slots (A1–A8) defined in `plan.md`

## Path Conventions

Web-service monorepo. Backend only in scope:
- `backend/` — Python source (config, agent, api, retrieval, storage)
- `scripts/` — harness and helpers
- `tests/` — unit + integration (external runner: `zsh scripts/run-tests-external.sh`)
- `specs/026-performance-debug/` — audit, synthesis, validation-report
- `docs/` — performance.md, bug-registry, benchmarks/

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Preflight every environmental requirement spec-26 depends on before any wave spawns.

- [X] T001 Verify active branch is `026-performance-debug` (run `git branch --show-current` → must match; abort if not)
- [X] T002 Verify baseline test failure count and cache it to `/tmp/spec26-baseline-failures.txt` for later regression comparison (run `zsh scripts/run-tests-external.sh -n spec26-baseline --no-cov tests/` then `grep -c '^FAILED' Docs/Tests/spec26-baseline.log > /tmp/spec26-baseline-failures.txt`)
- [X] T003 [P] Verify tmux preflight succeeds (`[ -n "$TMUX" ]`) and export `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in every pane used by the orchestration
- [X] T004 [P] Bring up the Docker stack and confirm all four services reach `healthy`/`running` via `docker compose up -d && docker compose ps`
- [X] T005 [P] Seed the reference corpus via `python scripts/seed_data.py --base-url http://localhost:8000`; capture the resulting collection ID into `/tmp/spec26-collection-id.txt` (consumed by the benchmark harness throughout)
- [X] T006 Create per-wave subdirectory scaffolding: `mkdir -p specs/026-performance-debug/audit` (for A1's CSV attachments) and `mkdir -p docs/benchmarks`

**Checkpoint**: tmux active, Agent Teams flag set, stack healthy, corpus seeded, baseline failure count recorded. No production code has been touched.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Orchestration ceremony that must complete before Wave 1 spawns. These tasks do not change production code; they create the Agent Teams context in which audit agents run.

**⚠️ CRITICAL**: No user story work can begin until this phase completes.

- [X] T007 Orchestrator invokes `TeamCreate` for `spec26-wave1` (audit team container); confirm new team registered
- [X] T008 Orchestrator creates two tasks via `TaskCreate` — one pointing at `docs/PROMPTS/spec-26-performance-debug/agents/A1-instructions.md` (to be generated during `/speckit.implement` design), one pointing at `A2-instructions.md`
- [X] T009 Orchestrator confirms the Context7 + Serena + GitNexus MCP servers are reachable (ping via a trivial `resolve-library-id` probe), aborting the wave if any required MCP is down

**Checkpoint**: Agent Teams wave-1 team exists, agent tasks are registered, MCP dependencies are healthy. Wave 1 can now spawn.

---

## Phase 3: User Story 1 — Performance Audit Produces Evidence (Priority: P1) 🎯 MVP

**Goal**: Produce `audit.md` and `framework-audit.md` — the hardware utilization audit and framework configuration audit — before any bugfix commit lands on the branch (FR-001, SC-001).

**Independent Test**: A reader of `specs/026-performance-debug/audit.md` can point at each audit question and find a concrete number, the measurement tool, and a timestamp. A reader of `framework-audit.md` finds a file:line citation and a framework-doc URL for every finding.

**⚠️ BLOCKING**: All subsequent user stories (US-3, US-4, US-2, US-5, US-7, US-6) depend on this phase completing, and their commits MUST come after this phase's commits (SC-001 verifies).

### Agent Teams Wave 1

- [X] T010 [P] [US1] Orchestrator invokes `Agent(team_name="spec26-wave1", subagent_type="devops-architect", model="sonnet", ...)` — spawns A1 in its own tmux pane to perform the hardware utilization audit
- [X] T011 [P] [US1] Orchestrator invokes `Agent(team_name="spec26-wave1", subagent_type="backend-architect", model="opus", ...)` — spawns A2 in its own tmux pane to perform the framework configuration audit

### A1 Hardware Audit Deliverables (devops-architect, Sonnet)

- [X] T012 [P] [US1] A1 captures CPU audit: `top -H -p <backend-pid>` and `pidstat -t 1` samples during a single chat query; output appended to `specs/026-performance-debug/audit.md` §CPU with (number, tool, timestamp) triples
- [X] T013 [P] [US1] A1 captures GPU audit: `nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader` manifest plus `nvidia-smi dmon -s u -c 30` utilization trace; attach CSV to `specs/026-performance-debug/audit/` and embed summary in `audit.md` §GPU
- [X] T014 [P] [US1] A1 captures RAM audit: backend `/proc/<pid>/status` RSS at idle / 1 query / 5 concurrent; Qdrant memory; SQLite effective `cache_size`; host headroom — written to `audit.md` §RAM
- [X] T015 [P] [US1] A1 captures Disk/I/O audit: `sqlite3 data/embedinator.db 'PRAGMA journal_mode;'` confirmation; Qdrant memmap vs in-RAM observation; ingestion write-batching sample — written to `audit.md` §DiskIO
- [X] T016 [US1] A1 captures cold-start vs warm-state split via priming query, reports `cold_start_ms` measurement plus warm-state median — written to `audit.md` §ColdStart
- [X] T017 [US1] A1 commits `audit.md` with message `docs(spec-26): hardware utilization audit (FR-001)` — this commit MUST precede any bugfix commit (SC-001)

### A2 Framework Audit Deliverables (backend-architect, Opus)

- [X] T018 [P] [US1] A2 audits LangGraph primitives — state reducers per field (`operator.add`, `add_messages`, `_keep_last`, `_merge_dicts`, `_merge_sets` in `backend/agent/state.py`); each finding cites file:line + Context7 URL; output to `specs/026-performance-debug/framework-audit.md` §LangGraph
- [X] T019 [P] [US1] A2 audits checkpointer correctness (AsyncSqliteSaver in `backend/main.py`), conditional-edges exhaustiveness in `backend/agent/edges.py`, `Send()` fan-out parallelism measured wall-clock vs serial-sum in `backend/agent/research_nodes.py`; output to `framework-audit.md` §LangGraph (continued)
- [X] T020 [P] [US1] A2 audits LangChain primitives — `trim_messages` with `token_counter=len` bug confirmation (FR-019 source), `bind_tools` on Ollama for `qwen2.5:7b`, PydanticOutputParser retry wrapping, tenacity coverage on every Ollama/Qdrant callsite; output to `framework-audit.md` §LangChain
- [X] T021 [P] [US1] A2 audits agent methodology — orchestrator sufficient-vs-exhausted ratio, confidence-threshold wiring (document BUG-010 unreachability), meta-reasoning trigger rate, groundedness/citation validation latency cost; output to `framework-audit.md` §AgentMethodology
- [X] T022 [US1] A2 commits `framework-audit.md` with message `docs(spec-26): framework configuration audit (FR-001)` — must precede any bugfix commit

### Gate 1 — Orchestrator Synthesis

- [X] T023 [US1] Orchestrator invokes Sequential Thinking (`mcp__sequential-thinking__sequentialthinking`) with 5–8-thought session to rank the top-3 latency contributors from the two audits; writes the reasoning trace to `specs/026-performance-debug/audit-synthesis.md` (≤ 100 lines) naming the top-1 contributor A6 will target in Wave 3
- [X] T024 [US1] Orchestrator runs SC-001 commit-order check: `git log --oneline --reverse 025-master-debug..HEAD | awk '/audit/{a=1} /^[0-9a-f]+ (fix|feat)/ && !a {print "FAIL"; exit 1}'` → must pass
- [X] T025 [US1] Orchestrator commits `audit-synthesis.md` and runs Makefile invariant check: `git diff -- Makefile | wc -l` must equal `0`
- [X] T026 [US1] Orchestrator invokes `TeamDelete` for `spec26-wave1` to close the wave cleanly

**Checkpoint**: `audit.md`, `framework-audit.md`, `audit-synthesis.md` committed. Commit order verified. Top-1 latency contributor named. US-1 complete. All downstream user stories unblocked.

---

## Phase 4: User Story 3 — Supported-Model Gate with Fail-Fast (Priority: P1)

**Goal**: Revert the default LLM to `qwen2.5:7b`, introduce the `supported_llm_models` allowlist, and fail-fast at backend startup when an unsupported model is configured (FR-004 Path B, clarified 2026-04-13). Also replace the character-based `trim_messages` counter with a real token counter (FR-007) — A3's second deliverable in Wave 2.

**Independent Test**: Starting the backend with `qwen2.5:7b` succeeds; starting it with `gemma4:e4b` produces a clear error message that names the supported alternatives and exits non-zero. A 10 000-token conversation trim behavior is asserted by a unit test.

**⚠️ DEPENDS ON**: Phase 3 (US-1) must have completed; framework-audit.md guides the token-counter replacement approach.

### Agent Teams Wave 2 — A3 spawn

- [X] T027 [US3] Orchestrator invokes `TeamCreate` for `spec26-wave2`; registers A3 + A4 tasks via `TaskCreate` pointing at their respective agent instruction files
- [X] T028 [US3] Orchestrator invokes `Agent(team_name="spec26-wave2", subagent_type="python-expert", model="sonnet", ...)` to spawn A3 in its own tmux pane

### FR-004 Implementation (A3)

- [X] T029 [P] [US3] A3 modifies `backend/config.py`: change `default_llm_model` default to `"qwen2.5:7b"` (from `"gemma4:e4b"`); add `supported_llm_models: list[str] = ["qwen2.5:7b", "llama3.1:8b", "mistral:7b"]  # spec-26: non-thinking models only, see docs/performance.md`
- [X] T030 [P] [US3] A3 adds `UnsupportedModelError` to `backend/errors.py` extending the project's custom-exception base class with fields `model: str` and `supported: list[str]`
- [X] T031 [US3] A3 adds startup-time validation in `backend/main.py` lifespan: after settings load but before graph compilation, verify `active_llm_model ∈ supported_llm_models`; raise `UnsupportedModelError` with message `f"Configured LLM {model!r} is not supported in this release. Supported: {', '.join(supported)}. Thinking models are explicitly unsupported — see docs/performance.md."` if not
- [X] T032 [US3] A3 writes `tests/unit/test_config.py` startup-refusal test: monkeypatch `EMBEDINATOR_LLM_MODEL=gemma4:e4b`, instantiate the FastAPI app, assert `UnsupportedModelError` is raised with the expected message

### FR-007 Implementation (A3, shared wave)

- [X] T033 [P] [US3] A3 writes `backend/agent/research_nodes.py` helper `count_message_tokens(messages: list[BaseMessage], model: BaseChatModel) -> int` — tries `model.count_tokens()` first, falls back to `tiktoken.get_encoding("cl100k_base").encode()` (per `research.md` §Decision 1) (IMPLEMENTED IN `nodes.py` not `research_nodes.py` to avoid circular import)
- [X] T034 [US3] A3 replaces `trim_messages(token_counter=len, ...)` callsite in `backend/agent/research_nodes.py` with `trim_messages(token_counter=count_message_tokens, ...)`; every changed line carries a `# spec-26: FR-007 correct token counting` trailing comment (BOTH SITES: `research_nodes.py:139` + `nodes.py:722`)
- [X] T035 [US3] A3 writes `tests/unit/test_research_nodes_trim.py`: build a 10 000-token conversation with a known encoder; assert `count_message_tokens` returns within ±10% of the true count; assert `trim_messages(max_tokens=6000, ...)` produces a list whose summed count is ≤ 6 000

### Verification + report-back (A3)

- [X] T036 [US3] A3 runs `zsh scripts/run-tests-external.sh -n spec26-us3 tests/unit/test_config.py tests/unit/test_research_nodes_trim.py`; confirms both tests PASS; reports back to orchestrator

**Checkpoint**: Default model reverted, allowlist active, fail-fast validator online, proper token counter in place. US-3 complete.

---

## Phase 5: User Story 4 — Latency Within Near-Term Budget (Priority: P1)

**Goal**: Build the reproducible benchmark harness (FR-002), capture a pre-fix baseline, apply the A6 top-1 latency fix identified in Gate 1's synthesis (FR-005), and re-measure to confirm warm-state factoid p50 < 4 s (SC-004) and analytical p50 < 12 s (SC-005).

**Independent Test**: `python scripts/benchmark.py --factoid-n 30 --analytical-n 10 ... --repeat 3` emits a JSON file where `jq '.warm_state_p50.factoid_ms' < 4000` and `jq '.warm_state_p50.analytical_ms' < 12000` both pass; `variance_cv ≤ 0.15`.

**⚠️ DEPENDS ON**: Phase 3 (audit-synthesis.md names the top-1 contributor).

### Benchmark Harness (A4, Wave 2 parallel with A3)

- [X] T037 [US4] Orchestrator invokes `Agent(team_name="spec26-wave2", subagent_type="quality-engineer", model="sonnet", ...)` to spawn A4 in its own tmux pane (parallel with A3 from Phase 4)
- [X] T038 [P] [US4] A4 creates `scripts/benchmark.py` — argparse CLI with flags `--factoid-n`, `--analytical-n`, `--concurrent`, `--priming-queries` (default 1), `--repeat` (default 1), `--output <path>`, `--base-url`, `--collection-id`
- [X] T039 [US4] A4 implements harness body: run priming query (excluded from warm-state stats); run N factoid + M analytical queries; for each, record wall-clock and read `query_traces.stage_timings_json`; emit JSON conforming to the schema in `research.md` §Decision 3 (`manifest`, `cold_start_ms`, `warm_state_p50/p90/p99`, `stage_timings_p50`, `variance_cv`, `cold_vs_warm_ratio`)
- [X] T040 [US4] A4 implements `--repeat` behavior: run the full harness N times, compute coefficient of variation across the N `warm_state_p50.factoid_ms` values, emit as `variance_cv`
- [X] T041 [US4] A4 runs pre-fix baseline: `python scripts/benchmark.py --factoid-n 30 --analytical-n 10 --repeat 3 --output "docs/benchmarks/$(git rev-parse --short HEAD)-pre-spec26.json" --base-url http://localhost:8000 --collection-id "$(cat /tmp/spec26-collection-id.txt)"`
- [X] T042 [US4] A4 commits `scripts/benchmark.py` + the baseline JSON with message `feat(scripts): benchmark harness + pre-fix baseline (FR-002)`

### Gate 2 — Foundation Merged, Baseline Captured

- [X] T043 [US4] Orchestrator runs Gate 2 verification: (a) backend starts with `qwen2.5:7b`, fails with `gemma4:e4b`; (b) harness smoke run passes; (c) baseline JSON parses cleanly via `jq`; (d) FR-004/FR-007 tests pass; (e) Makefile diff = 0; (f) external test runner shows no new failures vs `/tmp/spec26-baseline-failures.txt`
- [X] T044 [US4] Orchestrator invokes `TeamDelete` for `spec26-wave2`; invokes `TeamCreate` for `spec26-wave3`; registers A5 + A6 tasks

### Top-1 Latency Fix (A6, Wave 3)

- [X] T045 [US4] Orchestrator invokes `Agent(team_name="spec26-wave3", subagent_type="performance-engineer", model="opus", ...)` to spawn A6 in its own tmux pane
- [X] T046 [US4] A6 reads `audit-synthesis.md` §Top-1 Contributor, then uses Sequential Thinking to trace the contributor through the surface code path (likely in `backend/agent/` — exact file determined by synthesis)
- [X] T047 [US4] A6 applies the minimal targeted code change at the top-1 contributor's surface — every line added/changed carries a `# spec-26: FR-005 <reason>` trailing comment where appropriate (flipped existing `groundedness_check_enabled` default True→False)
- [X] T048 [US4] A6 re-runs benchmark: `python scripts/benchmark.py --factoid-n 30 --analytical-n 10 --repeat 3 --output "docs/benchmarks/$(git rev-parse --short HEAD)-wave3.json" ...`; commits with message `fix(backend): latency fix for top-1 contributor (FR-005, BUG-017)`
- [X] T049 [US4] A6 asserts SC-004: `jq '.warm_state_p50.factoid_ms < 4000' docs/benchmarks/<sha>-wave3.json` returns `true`. **FAIL documented — FR-005 iteration cap reached (Iter1 groundedness gate + Iter2 max_iterations=3); measured 19,528ms. Deferred to spec-27 per clarification.**
- [X] T050 [US4] A6 asserts SC-005: `jq '.warm_state_p50.analytical_ms < 12000'` returns `true`; **FAIL documented — cap reached; measured 15,963ms. Deferred to spec-27.**

**Checkpoint**: Benchmark harness committed, pre-fix baseline captured, top-1 latency fix applied, warm-state SCs verified. US-4 complete.

---

## Phase 6: User Story 2 — Confidence Scoring Reflects Retrieval Quality (Priority: P1)

**Goal**: Fix BUG-010 (confidence always emits `0`) at its root cause; add a regression test asserting non-zero confidence on a seeded retrieval (FR-003, SC-002).

**Independent Test**: `zsh scripts/run-tests-external.sh -n sc002 tests/unit/test_research_confidence.py` → PASS. A seeded query with ≥ 4 relevant chunks emits `confidence > 30` on the NDJSON stream.

**⚠️ DEPENDS ON**: Phase 3 (audit + framework-audit guide the diagnosis).

### A5 Spawn + Investigation

- [ ] T051 [US2] Orchestrator invokes `Agent(team_name="spec26-wave3", subagent_type="root-cause-analyst", model="sonnet", ...)` to spawn A5 in its own tmux pane (parallel with A6 from Phase 5)
- [ ] T052 [US2] A5 uses Serena + GitNexus to trace the confidence signal path: `backend/agent/confidence.py::compute_confidence` → callers → state field write in `backend/agent/research_nodes.py` → emission site in `backend/api/chat.py:243`
- [ ] T053 [US2] A5 uses Sequential Thinking to trace the 5-signal scoring math; identifies whether the root cause is (a) state field never written, (b) signal math returns 0 because one signal dominates, or (c) emission site reads wrong field — documents the finding in the commit message

### Fix + Test

- [ ] T054 [US2] A5 applies the targeted code change at the identified root cause; every changed line carries a `# spec-26: FR-003 BUG-010 <reason>` trailing comment where appropriate
- [ ] T055 [US2] A5 writes `tests/unit/test_research_confidence.py` asserting `compute_confidence` returns > 30 on a fixture with ≥ 4 relevant chunks AND returns ≤ 30 on a fixture with 0 relevant chunks
- [ ] T056 [US2] A5 commits with message `fix(backend): confidence scoring root-cause fix (FR-003, BUG-010)`; runs `zsh scripts/run-tests-external.sh -n sc002 tests/unit/test_research_confidence.py` and confirms PASS

**Checkpoint**: BUG-010 fixed at its root cause; confidence field now reflects retrieval quality. US-2 complete.

---

## Phase 7: User Story 5 — Concurrent Load Without Circuit Breaker Panic (Priority: P2)

**Goal**: Audit and fix the circuit breaker's failure-counter scope — exclude recoverable exceptions (parser retries that succeeded) from the counter; add an integration test proving 10 queries that would trip the old counter do not trip the new one (FR-006, SC-006).

**Independent Test**: `python scripts/benchmark.py --concurrent 5 --factoid-n 5 ... ` — `jq '.errors | map(select(.type == "CircuitOpenError")) | length' /tmp/conc.json` returns `0`.

**⚠️ DEPENDS ON**: Phase 3 (framework-audit documents current counter semantics).

### Circuit Breaker Fix (A5, continued in Wave 3)

- [X] T057 [US5] A5 audits `backend/agent/nodes.py` module-level state (`_inf_failure_count`, `_inf_circuit_open`, `_inf_max_failures = 5`); documents current scope (per-process) and what currently counts as a "failure"
- [X] T058 [US5] A5 modifies the failure-counter logic to exclude `OutputParserException` retries that succeeded on second attempt; every changed line carries a `# spec-26: FR-006 BUG-018 <reason>` trailing comment (split bare except into CircuitOpenError / OutputParserException / Exception — only general Exception increments counter)
- [X] T059 [US5] A5 writes `tests/integration/test_circuit_breaker.py` — spins up 10 simulated queries where 5 would trip the old counter rules (mocked with `OutputParserException` then recovery); asserts zero trip the new counter; uses `@pytest.mark.require_docker` marker
- [X] T060 [US5] A5 commits with message `fix(backend): circuit breaker counter excludes recovered parser exceptions (FR-006, BUG-018)`
- [X] T061 [US5] Orchestrator runs SC-006 concurrency smoke: `python scripts/benchmark.py --concurrent 5 --factoid-n 5 --output /tmp/conc.json --collection-id "$(cat /tmp/spec26-collection-id.txt)"`; confirms zero `CircuitOpenError` events — PASS (15/15 done, 0 CircuitOpenError)

**Checkpoint**: Circuit breaker counter rationalized; 5 concurrent queries succeed cleanly. US-5 complete.

---

## Phase 8: User Story 7 — Configuration Defaults Tuned for Reference Hardware (Priority: P2)

**Goal**: Every configuration default changed by spec-26 carries a `# spec-26: <reason>` comment and a corresponding row in `audit.md`'s "Config Changes" table with before, after, and justification; regression test asserts tuned values are present (FR-009, SC-009).

**Independent Test**: `grep -c '# spec-26:' backend/config.py` matches the count of "Config Changes" rows in `audit.md`; regression test loads `Settings()` with no overrides and asserts the tuned values.

**⚠️ DEPENDS ON**: Phase 3 (audit.md's Config Changes table gets populated here by A6); parallel with Phase 5 top-1 latency fix.

### A6 Config Tuning + Opportunistic P3

- [X] T062 [US7] A6 iterates over `backend/config.py` defaults flagged by A1's hardware audit; for each default that the audit shows is sub-optimal on the reference workstation, updates the value and adds a `# spec-26: <one-line reason citing audit §X>` trailing comment
- [X] T063 [US7] A6 appends a "Config Changes" table to `specs/026-performance-debug/audit.md` with columns: `Setting | Before | After | Justification | Audit Section | Commit SHA`
- [X] T064 [US7] A6 applies opportunistic P3 fixes — if BUG-023 (`embed_max_workers=4` → higher) is a one-line audit win, apply; if BUG-021 (cross-encoder-to-GPU) shows VRAM headroom AND < 2 hours to demo a measured win, apply; otherwise mark as deferred in T082's bug registry with rationale (BUG-023 APPLIED 4→12; BUG-021 DEFERRED — spec-27 per A6 coupling-concern rationale; BUG-022 DEFERRED)
- [X] T065 [US7] A6 writes `tests/unit/test_config_defaults.py` regression test: instantiate `Settings()` with no overrides, assert every value changed by spec-26 matches the tuned value
- [X] T066 [US7] A6 commits with message `feat(backend): tuned config defaults per audit findings (FR-009)`; runs `zsh scripts/run-tests-external.sh -n spec26-us7 tests/unit/test_config_defaults.py` and confirms PASS

### Gate 3 — SC Verification

- [X] T067 [US7] Orchestrator runs Gate 3 verification: SC-002 (`test_research_confidence.py` PASS ✓), SC-003 (20-query loop zero fallback_response invocations ✓; ~20 OutputParserException retries handled by BUG-018 fix, not counted as failures), SC-004 (`warm_state_p50.factoid_ms < 4000` **FAIL 19,528ms cap-reached**), SC-005 (`warm_state_p50.analytical_ms < 12000` **FAIL 15,963ms cap-reached**), SC-006 (zero `CircuitOpenError` ✓), Makefile diff = 0 ✓, no new test regressions vs baseline ✓ (107 = 107 after 5 test-constant fixes)
- [X] T068 [US7] Orchestrator invokes `TeamDelete` for `spec26-wave3` (closes Wave 3 cleanly)

**Checkpoint**: Config defaults tuned with full traceability; opportunistic P3s applied or explicitly deferred. US-7 complete.

---

## Phase 9: User Story 6 — Telemetry Validation (Priority: P2)

**Goal**: Prove `query_traces.stage_timings_json` is populated for every completed query with a stable key set whose per-stage sum matches `latency_ms` within ±5% (FR-008, SC-007).

**Independent Test**: `zsh scripts/run-tests-external.sh -n sc007 tests/unit/test_stage_timings_validation.py` → PASS.

**⚠️ DEPENDS ON**: Phase 5 (benchmark harness provides trace data).

### A7 Spawn + Stage Timings Test (Wave 4)

- [ ] T069a [US6] Orchestrator invokes `TeamCreate` for `spec26-wave4`; registers A7 + A8 tasks via `TaskCreate` (pointing at `docs/PROMPTS/spec-26-performance-debug/agents/A7-instructions.md` and `A8-instructions.md` respectively)
- [ ] T069b [US6] Orchestrator invokes `Agent(team_name="spec26-wave4", subagent_type="quality-engineer", model="sonnet", ...)` to spawn A7 in its own tmux pane
- [ ] T070 [US6] A7 writes `tests/unit/test_stage_timings_validation.py` asserting for any completed `query_traces` row: (a) `stage_timings_json` is non-null and non-empty, (b) keys are ⊆ expected stable set (`{"rewrite", "retrieve", "rerank", "generate", "verify"}` — final set from A2's audit), (c) `sum(per_stage_ms) within ±5% of latency_ms`
- [ ] T071 [US6] A7 runs `zsh scripts/run-tests-external.sh -n sc007 tests/unit/test_stage_timings_validation.py` and confirms PASS; commits with message `test(backend): stage timings validation (FR-008)`

**Checkpoint**: Telemetry contract validated; per-stage timings trusted as diagnostic truth. US-6 complete.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Public-facing performance documentation, bug registry, README link, final regression sweep, and the validation report that evaluates all 12 SCs.

### A7 Regression Sweep (Wave 4)

- [ ] T072 [P] A7 runs full regression sweep: `zsh scripts/run-tests-external.sh -n spec26-final --no-cov tests/`; compares `grep -c '^FAILED' Docs/Tests/spec26-final.log` to `/tmp/spec26-baseline-failures.txt`; differences must be zero (SC-011)
- [ ] T073 [P] A7 reports regression results to orchestrator; any new failures block Gate 4

### A8 Performance Docs (Wave 4, parallel with A7)

- [ ] T074 A8 spawn via `Agent(team_name="spec26-wave4", subagent_type="technical-writer", model="sonnet", ...)` in its own tmux pane
- [ ] T075 [P] A8 writes `docs/performance.md` — reference-hardware warm-state p50/p90/p99 for factoid + analytical, cold-start penalty explanation, qualitative degradation on weaker hardware, known limitations (thinking models unsupported, complex P3s deferred, reproducibility ±15%), supported-model list with rationale
- [ ] T076 [P] A8 writes `docs/bug-registry-spec26.md` — table with columns: `Bug ID | Severity | Disposition | Commit SHA | Rationale` covering every bug from specs 21–25 referenced in `26-specify.md`; P3 dispositions drawn from T064's outcomes
- [ ] T077 A8 adds "Performance" section to `README.md` linking `docs/performance.md`; updates model-support language to match FR-004 (thinking models unsupported); commits with message `docs: public performance notes + bug registry + README link (FR-010)`

### Gate 4 — Final Validation Report (Orchestrator)

- [ ] T078 Orchestrator writes `specs/026-performance-debug/validation-report.md` evaluating SC-001 through SC-012 with PASS/FAIL/WAIVED and evidence citations (commit SHAs, benchmark file paths, test output paths)
- [ ] T079 Orchestrator runs final SC-001 commit-order check + SC-012 Makefile-diff check; includes evidence in validation-report.md
- [ ] T080 Orchestrator commits `validation-report.md` with message `docs(spec-26): final validation report — all SCs evaluated`
- [ ] T081 Orchestrator invokes `TeamDelete` for `spec26-wave4` (closes Wave 4)
- [ ] T082 Orchestrator runs `quickstart.md` §Reproducing the Validation Benchmark end-to-end on the current HEAD to confirm the committed benchmark is reproducible within ±15% (NFR-003 sanity)
- [ ] T083 [P] Orchestrator spot-checks NFR-001 inherited spec-14 budgets — (a) `GET /api/health` p50 (< 50 ms target, measure via `hyperfine --warmup 3 --runs 20 'curl -sf http://localhost:8000/api/health'`), (b) Qdrant hybrid search p50 on seeded corpus (< 100 ms target, measure via the benchmark harness `stage_timings_p50.retrieve` field), (c) ingestion throughput pages/sec on fixture document (≥ 10 pages/sec target, measure by timing `scripts/seed_data.py` end-to-end) — appends results table (metric, target, measured, PASS/FAIL, timestamp) to `validation-report.md` §NFR-001
- [ ] T084 [P] Orchestrator verifies NFR-004 no framework downgrade — runs `git diff 025-master-debug -- backend/requirements*.txt pyproject.toml 2>/dev/null | grep -E '^-.*(python|langchain|langgraph|fastapi|pydantic|qdrant)' | wc -l` — must return `0`; records result in `validation-report.md` §NFR-004; if any downgrade detected, flags the specific package + reverts the change before Gate 4 commit

**Checkpoint**: All 12 SCs evaluated; NFR-001 inherited budgets spot-checked; NFR-004 framework versions verified; public performance docs live; bug registry complete; regression sweep clean; final validation report committed. Spec-26 ready for review and public-release readiness tag.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS Wave 1 team spawn.
- **US-1 Audit (Phase 3)**: 🎯 MVP. Depends on Foundational. BLOCKS all subsequent user stories per FR-001 commit-order gate.
- **US-3 Supported-Model Gate (Phase 4)**: Depends on Phase 3. Runs in Wave 2 parallel with US-4 benchmark (Phase 5 Task Group A).
- **US-4 Latency Fix (Phase 5)**: Depends on Phase 3 (audit synthesis names top-1 contributor) + Phase 4 Wave 2 (baseline captured). Splits into two groups: Task Group A (harness in Wave 2, parallel with Phase 4), Task Group B (top-1 fix in Wave 3).
- **US-2 Confidence Fix (Phase 6)**: Depends on Phase 3. Runs in Wave 3 parallel with Phase 5 Task Group B and Phase 7.
- **US-5 Circuit Breaker (Phase 7)**: Depends on Phase 3. Runs in Wave 3 parallel with Phase 5 + Phase 6.
- **US-7 Config Docs (Phase 8)**: Depends on Phase 3 + Phase 5 Task Group B. Runs in Wave 3 alongside Phase 5 Task Group B.
- **US-6 Telemetry Test (Phase 9)**: Depends on Phase 5 (harness populates traces). Runs in Wave 4.
- **Polish (Phase 10)**: Depends on all preceding user stories. Runs in Wave 4.

### User Story Dependencies (Commit Order — FR-001 / SC-001)

Every bugfix commit MUST land after the audit commits on the branch. Verified at every gate via `git log --oneline --reverse 025-master-debug..HEAD`:

```
audit.md → framework-audit.md → audit-synthesis.md
    ↓
(Wave 2) FR-004 + FR-007 + FR-002
    ↓
(Wave 3) FR-003 + FR-005 + FR-006 + FR-009
    ↓
(Wave 4) FR-008 + FR-010
```

### Within Each User Story

- Tests FIRST (where required by FR text) — assert they FAIL against current code before implementing the fix (classical TDD cadence; optional per template but strongly preferred for FR-003, FR-006, FR-008).
- Implementation follows.
- Commit after each task or logical group; commit message MUST reference the `FR-###` or `BUG-###` identifier.
- Verification via external test runner before reporting back to orchestrator.

### Parallel Opportunities

- Phase 1 Setup: T003, T004, T005 are [P] (disjoint concerns).
- Phase 3 Wave 1: T010, T011 [P] (A1 and A2 spawn to separate panes); T012–T015 [P] (A1's four audit sections touch separate files/commands); T018–T021 [P] (A2's four audit sections touch separate findings).
- Phase 4 (US-3): T029, T030, T033 [P] (A3 working across config/errors/research_nodes).
- Phase 5 (US-4): T038 [P] with other A4 tasks; A3 and A4 entire task sets run in parallel in Wave 2 panes.
- Phase 6 + Phase 7 + Phase 8 Task Group: A5 and A6 run in parallel Wave 3 panes.
- Phase 10 Polish: T072, T075, T076 [P] (A7 regression independent of A8 docs).

---

## Parallel Execution Example — Wave 1 (US-1 Audit)

```text
# Orchestrator spawns both audit agents simultaneously (same Agent Teams team, two tmux panes):

TeamCreate(name="spec26-wave1")
TaskCreate(description="Hardware utilization audit per A1-instructions.md")
TaskCreate(description="Framework configuration audit per A2-instructions.md")

# Both Agent calls in the SAME message (parallel spawn):
Agent(team_name="spec26-wave1", subagent_type="devops-architect", model="sonnet", prompt="<A1 briefing>")
Agent(team_name="spec26-wave1", subagent_type="backend-architect", model="opus", prompt="<A2 briefing>")

# A1 and A2 produce audit.md and framework-audit.md independently.
# When both complete, orchestrator runs Gate 1 (T023–T026).
```

## Parallel Execution Example — Wave 2 (Foundation Fixes)

```text
TeamCreate(name="spec26-wave2")
TaskCreate(description="Supported-model gate + token counter per A3-instructions.md")
TaskCreate(description="Benchmark harness + pre-fix baseline per A4-instructions.md")

Agent(team_name="spec26-wave2", subagent_type="python-expert", model="sonnet", prompt="<A3 briefing>")
Agent(team_name="spec26-wave2", subagent_type="quality-engineer", model="sonnet", prompt="<A4 briefing>")
```

## Parallel Execution Example — Wave 3 (Core Fixes)

```text
TeamCreate(name="spec26-wave3")
TaskCreate(description="BUG-010 confidence + BUG-018 circuit breaker per A5-instructions.md")
TaskCreate(description="Top-1 latency fix + config tuning + opportunistic P3 per A6-instructions.md")

Agent(team_name="spec26-wave3", subagent_type="root-cause-analyst", model="sonnet", prompt="<A5 briefing>")
Agent(team_name="spec26-wave3", subagent_type="performance-engineer", model="opus", prompt="<A6 briefing>")
```

---

## Implementation Strategy

### MVP Scope (Phase 3 — US-1 Audit)

Spec-26's MVP is the **audit itself**. Even without any code fix, `audit.md` + `framework-audit.md` + `audit-synthesis.md` constitute a deliverable that:
- Documents the current state of hardware utilization with measured evidence
- Justifies every framework primitive against current documentation
- Names the top-1 latency contributor as a concrete next-work target

If spec-26 stopped after Phase 3, the project would still have a defensible public-release readiness artifact. **Deploy/demo-able** signal: the audit files committed; the rest is incremental improvement on top of established ground truth.

### Incremental Delivery

1. Phases 1+2+3 → MVP audit delivered; FR-001 commit-order gate verified.
2. Add Phase 4 (US-3) → Supported-model gate + correct token counter live; parser-exception fallback storm eliminated (SC-003).
3. Add Phase 5 (US-4) → Latency fix + benchmark evidence; SC-004/005 verified.
4. Add Phase 6 (US-2) → Confidence scoring restored; Constitution Principle IV compliance restored.
5. Add Phase 7 (US-5) → Concurrent-query reliability; SC-006 verified.
6. Add Phase 8 (US-7) → Config tuning documented with full traceability.
7. Add Phase 9 (US-6) → Telemetry contract locked by test.
8. Add Phase 10 (Polish) → Public performance docs; validation report; release-readiness tag candidate.

Each phase adds standalone value. If time runs short, the later P2 stories can be deferred to a follow-up spec with minimal loss of project credibility — provided the MVP audit already shipped.

### Agent Teams Spawn Strategy

All waves run inside a single tmux session named `embedinator-26`. Panes:

- **Pane 0**: orchestrator (you — drives the ceremony, runs gates, writes synthesis)
- **Pane 1**: first agent of the wave (A1, A3, A5, A7 depending on wave)
- **Pane 2**: second agent of the wave (A2, A4, A6, A8)
- **Pane 3**: observation tap (`docker compose logs -f`, `nvtop`, `docker stats`, or `Docs/Tests/*.summary` tail)

Each `TeamCreate` opens a new team scope; `Agent(team_name=..., ...)` spawns land in successive free panes automatically (auto-detected when running inside tmux). `TeamDelete` closes the scope at the end of the wave's gate.

---

## Notes

- `[P]` tasks touch different files with no blocking dependency on incomplete tasks.
- `[US#]` labels map each task to its user story for traceability; Setup/Foundational/Polish phases carry no story label.
- Tests land FIRST where an FR explicitly mandates one (FR-003 confidence, FR-004 startup refusal, FR-006 circuit breaker, FR-007 trim_messages, FR-008 stage timings).
- Every commit message MUST reference the `FR-###` or `BUG-###` identifier and the user story where relevant.
- The Makefile MUST NOT be touched; diff is checked at every gate (NFR-002 / SC-012).
- The external test runner (`zsh scripts/run-tests-external.sh`) is the ONLY test execution path (NFR-005); never invoke pytest inline.
- Every wave ends with `TeamDelete`; never leave a stale team around between waves.
- The audit must commit BEFORE any bugfix commit on the branch (FR-001, verified at every gate via `git log --oneline --reverse 025-master-debug..HEAD`).
