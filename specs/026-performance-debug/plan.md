# Implementation Plan: Performance Debug and Hardware Utilization Audit

**Branch**: `026-performance-debug` | **Date**: 2026-04-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/026-performance-debug/spec.md`
**Planning Prompt**: [`docs/PROMPTS/spec-26-performance-debug/26-plan.md`](../../docs/PROMPTS/spec-26-performance-debug/26-plan.md)

---

```text
╔═══════════════════════════════════════════════════════════════════════════════╗
║  MANDATORY — AGENT TEAMS + TMUX MULTI-PANE EXECUTION                          ║
║                                                                                ║
║  This spec WILL be executed via Agent Teams Lite running in tmux.             ║
║  Every wave agent gets its OWN tmux pane. NO exceptions.                      ║
║                                                                                ║
║  The orchestrator MUST use the following spawn sequence for each wave:        ║
║                                                                                ║
║    1. TeamCreate  (creates the team container)                                ║
║    2. TaskCreate  (one task per agent with the instruction-file path)         ║
║    3. Agent(team_name="spec26-waveN", subagent_type="...", model="...")       ║
║       — ONE Agent call PER teammate. Each spawn opens its own tmux pane.      ║
║    4. SendMessage (for follow-ups, NEVER a new Agent call with same name)     ║
║    5. TeamDelete  (only after the wave's gate check passes)                   ║
║                                                                                ║
║  PROHIBITED:                                                                   ║
║    - Spawning agents via plain `Agent(subagent_type=...)` without team_name   ║
║    - Running multiple agents in the same pane                                 ║
║    - Launching a wave without tmux (the session MUST be inside tmux)          ║
║    - Skipping the gate check between waves                                    ║
║                                                                                ║
║  PREFLIGHT (the orchestrator runs THIS before Wave 1):                        ║
║    $ [ -n "$TMUX" ] || { echo "ERROR: must be inside tmux"; exit 1; }         ║
║    $ env | grep CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 \                      ║
║        || { echo "ERROR: export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1"; }    ║
║                                                                                ║
║  If either preflight fails, STOP and instruct the user.                       ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

---

## Summary

Spec-26 is the quality-gate-before-public-release spec. The Embedinator works but measured first-token latency is 26–158 seconds against a 1.2-second spec-14 budget, confidence always emits `0`, and the circuit breaker trips under light load. Spec-26 delivers four things in strict order: (1) a hardware utilization audit and a framework configuration audit that produce measured evidence before any code change, (2) audit-independent foundation fixes — reverting the default LLM to `qwen2.5:7b` with a fail-fast supported-model allowlist, a proper token counter, and a reproducible benchmark harness that separates cold-start from warm-state, (3) audit-driven core fixes — BUG-010 confidence root cause, BUG-018 circuit-breaker failure-counter semantics, FR-005 top-1 latency contributor — plus configuration tuning and opportunistic P3 fixes, and (4) validation, regression sweep, and public-facing performance documentation. The implementation runs as 8 agent slots across 4 waves in tmux multi-pane via Agent Teams Lite, with a hard commit-order gate (FR-001) enforcing that audit reports land before any bugfix commit.

## Technical Context

**Language/Version**: Python 3.14+ (backend); TypeScript 5.7 (frontend — not modified in this spec); Rust 1.93.1 (ingestion worker — not modified)
**Primary Dependencies**: LangGraph >= 1.0.10, LangChain >= 1.2.10, FastAPI >= 0.135, Pydantic v2 >= 2.12, aiosqlite >= 0.21, Qdrant Client >= 1.17.0, sentence-transformers >= 5.2.3, structlog >= 24.0, tenacity >= 9.0, httpx >= 0.28, cryptography >= 44.0 (all pre-existing)
**Candidate New Dependencies** (Phase 0 research resolves these): `tiktoken` for FR-007 proper token counting (fallback when provider lacks `count_tokens`); `nvidia-ml-py` or `pynvml` for A1's programmatic GPU utilization audit (alternative: `nvidia-smi` subprocess). Both flagged as candidates; pinning decision in `research.md`.
**Storage**: SQLite WAL mode (`data/embedinator.db`, existing); Qdrant hybrid dense+BM25 (existing, unchanged schema). LangGraph checkpoint DB (`data/checkpoints.db`, existing). No schema changes in this spec.
**Testing**: pytest >= 8.0 + pytest-asyncio + pytest-cov via the external test runner script (`zsh scripts/run-tests-external.sh`); in-memory SQLite for unit tests; real Qdrant on `localhost:6333` for integration tests marked `@pytest.mark.require_docker`. Never invoke pytest inline per NFR-005.
**Target Platform**: Linux (Fedora 43 reference workstation — Intel i7-12700K, 64 GB DDR5, RTX 4070 Ti 12 GB VRAM, NVMe SSD); macOS and Windows 11+ supported via Docker Compose per Constitution Principle VIII.
**Project Type**: web-service (backend + frontend monorepo; spec-26 is backend-only — frontend is NOT touched).
**Performance Goals**: Warm-state factoid p50 first-token < 4 seconds (SC-004); warm-state analytical p50 < 12 seconds (SC-005); 5 concurrent factoid queries without `CircuitOpenError` (SC-006); ±15% benchmark run-to-run variance (NFR-003); populated stage timings whose sum is within ±5% of overall latency (SC-007). See Complexity Tracking for gap vs Constitution's < 800 ms Phase 1 first-token budget.
**Constraints**: No Makefile modifications (NFR-002, SC-012); no test regressions vs `025-master-debug` baseline (NFR-005, SC-011); audit commits MUST precede bugfix commits (FR-001, SC-001); thinking models explicitly unsupported this release (FR-004 Path B, clarified 2026-04-13); no Python/LangGraph/LangChain downgrades (NFR-004); benchmark harness MUST use a priming query to separate cold-start from warm-state statistics.
**Scale/Scope**: Single-user 1–5 concurrent queries (Constitution Principle VII); reference-hardware-only SC verification; 10 FRs, 5 NFRs, 12 SCs; 7 user stories; estimated 40–60 implementation tasks across 8 agent slots.

## Constitution Check

*Evaluated against Constitution v1.1.0 (2026-03-18). All principles pass; one Performance Budget deviation documented in Complexity Tracking.*

| Principle | Status | Evaluation |
|-----------|--------|------------|
| I. Local-First Privacy | ✅ PASS | FR-004 reverts default LLM to the local `qwen2.5:7b`; no new cloud calls; no authentication introduced. |
| II. Three-Layer Agent Architecture | ✅ PASS | Spec-26 tunes `ConversationGraph`, `ResearchGraph`, `MetaReasoningGraph` but does not replace or flatten any layer; meta-reasoning max-attempts constraint preserved. |
| III. Retrieval Pipeline Integrity | ✅ PASS | Parent/child chunking, breadcrumbs, hybrid dense+BM25, cross-encoder reranking all retained. Opportunistic P3 BUG-021 may relocate the reranker to GPU (same model, same function) but does not remove any pipeline component; BUG-023 tunes `embed_max_workers` only. |
| IV. Observability from Day One | ✅ REINFORCES | BUG-010 (confidence always 0) is a direct violation of Principle IV's rule "The confidence score (0–100 integer) MUST be displayed to the user in the chat UI alongside every answer"; FR-003 fixes this. FR-008 validates that `stage_timings_json` is populated for every query. Trace recording stays non-optional. |
| V. Secure by Design | ✅ PASS | No changes to Fernet encryption, rate limiting, CORS, trace ID injection, SQL parameterization, or file upload validation. FR-004's startup validator is purely additive — it tightens which models can be configured. |
| VI. NDJSON Streaming Contract | ✅ PASS | No changes to the `chunk` / `metadata` / `error` frame schemas, media type, or first-token target. The 500ms constitutional first-token target exceeds spec-26's near-term SC-004 of < 4s — see Complexity Tracking for the acknowledged gap. |
| VII. Simplicity by Default | ✅ PASS | FR-004 REMOVES thinking-model-handling complexity (no `<think>`-token stripping code path adopted — Path B rejected Path A); no new services added; P3 policy is "opportunistic, defer the rest"; no new abstractions. |
| VIII. Cross-Platform Compatibility | ✅ PASS | Benchmark harness written in Python + optional `bash` verification snippets; Python uses `pathlib.Path`; all reference measurements captured on Linux but FR-010 performance doc explicitly notes Docker as the canonical deployment abstraction. `nvidia-smi` / `nvidia-ml-py` tooling is Linux-only by nature — A1's audit explicitly runs on the reference workstation; Windows/macOS users retain the Docker-compose degradation path documented in `docs/performance.md`. |

**Pre-design gate**: PASS with one Complexity Tracking entry (performance budget deviation disclosed, not resolved).
**Post-design gate**: to be re-evaluated after Phase 1 artifacts; expected PASS.

## Project Structure

### Documentation (this feature)

```text
specs/026-performance-debug/
├── plan.md                      # This file (/speckit.plan output)
├── spec.md                      # Feature specification (locked by /speckit.clarify 2026-04-13)
├── research.md                  # Phase 0: candidate dep choices, framework doc lookups
├── quickstart.md                # Phase 1: how to run harness, read audit, validate config
├── audit.md                     # Wave 1 deliverable (A1 — hardware)
├── framework-audit.md           # Wave 1 deliverable (A2 — LangGraph/LangChain primitives)
├── audit-synthesis.md           # Gate 1 orchestrator synthesis (top-3 latency contributors)
├── validation-report.md         # Gate 4 — all 12 SCs evaluated
├── checklists/
│   └── requirements.md          # Quality checklist (spec-level)
└── tasks.md                     # Phase 2 (/speckit.tasks — NOT created here)
```

No `data-model.md` (no new entities; existing spec-07 schema unchanged). No `contracts/` directory (no new API surfaces; FR-004's startup validator is a runtime configuration contract documented in plan.md below, not a formal interface file).

### Source Code (repository root, existing web-service layout)

```text
backend/
├── agent/
│   ├── conversation_graph.py    # Layer 1 — not modified in spec-26
│   ├── research_graph.py        # Layer 2 — not modified in spec-26
│   ├── research_nodes.py        # A3 modifies: trim_messages token counter (FR-007); A5 may modify: confidence callsite
│   ├── nodes.py                 # A5 modifies: circuit breaker failure-counter scope (FR-006)
│   ├── confidence.py            # A5 modifies: BUG-010 root cause (FR-003)
│   ├── state.py                 # audited by A2; likely unmodified
│   └── edges.py                 # audited by A2; likely unmodified
├── api/
│   └── chat.py                  # A5 may modify only if confidence emission site IS the bug
├── config.py                    # A3 modifies: default LLM + supported_llm_models; A6 modifies: tuned defaults with # spec-26: comments
├── main.py                      # A3 modifies: startup-time supported-model validator
├── providers/                   # audited by A2; likely unmodified
├── retrieval/                   # audited by A2; BUG-021 cross-encoder-to-GPU handled by A6 only if opportunistic
└── storage/
    └── sqlite_db.py             # A4 may add get_recent_traces() helper; schema unchanged

scripts/
└── benchmark.py                 # A4 creates (new) — FR-002 harness

tests/
├── unit/
│   ├── test_research_confidence.py          # A5 writes — BUG-010 regression (FR-003)
│   ├── test_research_nodes_trim.py          # A3 writes — trim_messages regression (FR-007)
│   ├── test_stage_timings_validation.py     # A7 writes — FR-008
│   └── test_config.py                       # A3 extends — startup-refusal test
└── integration/
    └── test_circuit_breaker.py              # A5 writes — FR-006 integration

docs/
├── benchmarks/
│   ├── <sha>-pre-spec26.json    # A4 commits — pre-fix baseline
│   └── <sha>-wave3.json         # A6 commits — post-fix result
├── performance.md               # A8 writes — FR-010
└── bug-registry-spec26.md       # A8 writes — per-bug disposition
```

**Files NEVER to touch (enforced at every gate)**: `Makefile`, `embedinator.sh`, `embedinator.ps1`, `frontend/**`, `ingestion-worker/**`, `docker-compose.yml`, `specs/0{01..25}/**` (prior spec artifacts).

**Structure Decision**: Web-service monorepo, backend-only scope. Reuses existing directory layout — no new top-level directories. `specs/026-performance-debug/` gains four audit/synthesis/validation artifacts unique to this spec.

---

## Why This Spec is Inverted (Audit Before Fix)

Most specs follow design → build → test → polish. Spec-26 is inverted:

1. **The audit MUST come before any code change.** FR-001 is a hard commit-ordering gate (SC-001 verifies). Every code commit comes after the two audit reports. Wave 1 → Gate 1 enforces this structurally — Wave 2 cannot start until the orchestrator merges Gate 1.
2. **The audit's findings determine the implementation.** FR-005 ("fix the biggest latency contributor") is parameterized by whatever Wave 1 surfaces. This plan commits to the *process* of synthesizing the audit and dispatching Wave 3 at the top-1 contributor — it does NOT pre-decide which code gets edited.
3. **Many FRs are diagnostic-then-fix.** FR-003 (confidence), FR-005 (latency), FR-006 (circuit breaker) begin with "identify the root cause" and only then "apply the fix". `tasks.md` will reflect this two-step shape.
4. **Success is measured against an external benchmark.** The benchmark harness (FR-002) is the ONLY authoritative SC verifier. Every gate that asserts a latency number does so via `python scripts/benchmark.py` against the seeded corpus on the reference workstation.

---

## Agent Roster

The project ships 20 subagents at `~/.claude/agents/`. Spec-26 draws on 6 of them across 8 slots (one agent type may run in more than one slot — different tmux pane, different task).

| Slot | Agent type | Wave | Model | Primary FRs | Deliverable |
|------|------------|------|-------|-------------|-------------|
| A1 | devops-architect | 1 | Sonnet | FR-001 (hardware half) | `audit.md` |
| A2 | backend-architect | 1 | **Opus** | FR-001 (framework half) | `framework-audit.md` |
| A3 | python-expert | 2 | Sonnet | FR-004, FR-007 | Supported-model gate + proper token counter + startup validator |
| A4 | quality-engineer | 2 | Sonnet | FR-002 | `scripts/benchmark.py` + pre-fix baseline JSON |
| A5 | root-cause-analyst | 3 | Sonnet | FR-003, FR-006 | BUG-010 + BUG-018 fixes with tests |
| A6 | performance-engineer | 3 | **Opus** | FR-005, FR-009 | Top-1 latency fix + tuned defaults + opportunistic P3 |
| A7 | quality-engineer | 4 | Sonnet | FR-008, NFR-005 | Stage-timings test + regression sweep |
| A8 | technical-writer | 4 | Sonnet | FR-010 | `docs/performance.md` + bug registry + README link |

**Model tier rationale**:
- **Opus**: A2 (framework audit — requires holding the whole LangGraph/LangChain graph mental model simultaneously and justifying each primitive against framework docs); A6 (latency fix — requires architectural judgment to pick the top-1 contributor and avoid moving the bottleneck sideways).
- **Sonnet** (everyone else): structural, measurement, implementation, documentation — well-bounded task shapes.

---

## Phase-by-Phase Breakdown

### Wave 1 — Audit (BLOCKING — FR-001, SC-001)

**Goal**: Produce `audit.md` and `framework-audit.md` before any bugfix commit.

**User stories**: US-1 (Performance Audit Produces Evidence).
**FRs discharged**: FR-001.
**SCs advanced**: SC-001.
**Dependencies**: none (first wave).
**Exit criteria**: both audit files committed; synthesis written; Makefile diff 0; no test runs required (no code changed).

#### A1 — Hardware Utilization Audit (devops-architect, Sonnet)

Reads: `spec.md` US-1 + Edge Cases, `docs/PROMPTS/spec-26-performance-debug/26-specify.md` §Hardware Baseline + §Hardware Utilization Audit.
Writes: `specs/026-performance-debug/audit.md` ≥ 400 lines with these mandatory sections:

1. CPU — which processes consume cycles during one chat query (`top -H`, `pidstat -t 1`); uvicorn worker model; Qdrant thread pool sizing for 20 host threads.
2. GPU — VRAM + utilization under chat query (`nvidia-smi dmon -s u -c 30`, `nvtop`); `qwen2.5:7b` 100% GPU check; `nomic-embed-text` GPU-or-CPU verification; cross-encoder device placement headroom.
3. RAM — backend RSS at idle / 1 query / 5 concurrent (`/proc/<pid>/status`); Qdrant memory; SQLite `cache_size` effective vs configured; host headroom.
4. Disk/I/O — SQLite WAL confirmed via `PRAGMA journal_mode`; ingestion write batching; Qdrant memmap vs in-RAM.
5. Cold-start vs warm-state — first-query VRAM load cost, separated via priming query.
6. Config-changes table — empty in Wave 1; A6 appends in Wave 3.

Every answer has (number, measurement tool, timestamp). Three independent samples per metric with variance noted (NFR-003 posture).

MCP tools: Docker MCP (`docker compose exec`, `docker stats`), Bash (`nvidia-smi`, `nvtop`, `top`, `pidstat`, `sqlite3 PRAGMA`), `mcp-chart` optional for GPU utilization line chart, Sequential Thinking optional for GPU-sharing trade-off discussion.

#### A2 — Framework Configuration Audit (backend-architect, Opus)

Reads: `spec.md` US-1, `26-specify.md` §Framework Configuration Audit, `backend/agent/state.py`, `backend/agent/research_graph.py`, `backend/agent/research_nodes.py`, `backend/agent/nodes.py`, `backend/agent/conversation_graph.py`, `backend/main.py`.
Writes: `specs/026-performance-debug/framework-audit.md` ≥ 300 lines with file:line citations and Context7-fetched doc URLs:

1. LangGraph primitives — state reducers correctness per field; checkpointer `thread_id` wiring + DB growth; conditional edges exhaustiveness; `Send()` fan-out measured parallelism; `recursion_limit` tightness; `interrupt()` resume-path liveness.
2. LangChain primitives — `trim_messages` current counter bug confirmation; `bind_tools` support by `qwen2.5:7b`; PydanticOutputParser retry wrapping + `.with_structured_output()` adoption; tenacity coverage on every Ollama + Qdrant call path.
3. Agent methodology — orchestrator stop-signal quality (sufficient vs exhausted ratio); confidence-threshold wiring (document BUG-010 unreachability + expected post-fix distribution); tool-exhaustion F4 behavior; meta-reasoning trigger rate + efficacy; groundedness + citation validation latency cost.

MCP tools: Serena, GitNexus (pre-edit impact), Context7 (doc lookups), Sequential Thinking (reducer-correctness).

#### Gate 1 — Audit Review and Synthesis (orchestrator, Opus)

Preconditions: both audits committed; `git log --oneline` shows audit commits before any bugfix commit.

Actions:
1. Read both audits end-to-end.
2. Use Sequential Thinking to rank top-3 latency contributors by magnitude.
3. Write `specs/026-performance-debug/audit-synthesis.md` (≤ 100 lines) naming the top-1 that A6 will target in Wave 3 FR-005.
4. Commit the synthesis. Verify Makefile diff = 0.

Blocks: if either audit is missing mandatory sections, reject via `SendMessage` rather than advancing.

---

### Wave 2 — Foundation Fixes (post-audit, parallel)

**Goal**: Land audit-independent fixes that any implementation plan would require regardless of audit findings.

**User stories**: US-3 (Thinking-Model Compatibility), US-6 (Telemetry Validation — partial).
**FRs discharged**: FR-002 (benchmark), FR-004 (supported-model gate), FR-007 (token counter).
**SCs advanced**: SC-003 (parser fallbacks), SC-008 (token counter test).
**Dependencies**: Gate 1 passed (audit reports merged, synthesis committed).
**Exit criteria**: Gate 2 shell block passes (see below).

#### A3 — Supported-Model Gate + Token Counter (python-expert, Sonnet)

Reads: `spec.md` US-3 + Clarifications (Path B locked) + FR-004 + FR-007, `framework-audit.md` (for token-counter finding), `backend/config.py`, `backend/providers/*`, `backend/main.py` lifespan, `backend/agent/research_nodes.py` trim_messages callsite.

Writes:
- `backend/config.py`: `default_llm_model: str = "qwen2.5:7b"` (reverted from `"gemma4:e4b"`); add `supported_llm_models: list[str]` default (initial draft: `["qwen2.5:7b", "llama3.1:8b", "mistral:7b"]` — final list negotiated with A8 for `docs/performance.md`); `# spec-26: <reason>` trailing comments on every changed default.
- `backend/main.py` lifespan (or provider-wiring hook): validate `active_llm_model ∈ supported_llm_models`; fail-fast with a structured error message that names the supported alternatives if validation fails. Error code and message are part of the runtime configuration contract — see §Configuration Contract Changes below.
- `backend/agent/research_nodes.py`: replace `trim_messages(token_counter=len, ...)` with a provider-aware counter (LangChain 1.2+ `model.count_tokens()` if available; `tiktoken` fallback otherwise — see `research.md` §Decision 1).
- Tests: `tests/unit/test_config.py` startup-refusal test (configure `gemma4:e4b`, assert backend refuses with expected error); `tests/unit/test_research_nodes_trim.py` unit test on a 10,000-token conversation asserting correct trim behavior.

MCP tools: Serena (symbol navigation for `Settings`, `providers`, `research_nodes`), Context7 (LangChain `count_tokens` API and `trim_messages` signature history), GitNexus (pre-edit impact for `trim_messages` callers).

#### A4 — Benchmark Harness + Pre-Fix Baseline (quality-engineer, Sonnet)

Reads: `spec.md` US-4 + US-6 + FR-002 + NFR-003, `scripts/seed_data.py`, `backend/storage/sqlite_db.py` `query_traces` schema.

Writes:
- `scripts/benchmark.py` — argparse CLI with flags `--factoid-n 30`, `--analytical-n 10`, `--concurrent 1`, `--priming-queries 1`, `--output <path>`, `--base-url http://localhost:8000`, `--collection-id <id>`.
- Harness behavior: run priming query first (not counted in warm-state statistics); run N factoid + M analytical in sequence (or parallel if `--concurrent > 1`); for each, record wall-clock + `query_traces.stage_timings_json`; emit JSON with `warm_state_p50/p90/p99` per stage and overall, `cold_start_ms`, `cold_vs_warm_ratio`, `variance_cv` (across 3 repeat runs of the whole harness for NFR-003), and a `manifest` block (commit SHA, corpus fingerprint, model identifiers, timestamp).
- End of wave: run harness once → commit `docs/benchmarks/<sha>-pre-spec26.json` as pre-fix baseline.

MCP tools: Bash, Docker MCP (stack management, `docker stats` sampling during benchmark).

#### Gate 2 — Foundation Merged, Baseline Captured (orchestrator)

Checks:
1. `qwen2.5:7b` configured as default; starting backend with `gemma4:e4b` fails fast with supported-alternatives error.
2. `python scripts/benchmark.py --factoid-n 5 --analytical-n 2 --output /tmp/bench-smoke.json` runs cleanly end-to-end (harness smoke, not SC gate).
3. `docs/benchmarks/<sha>-pre-spec26.json` committed and parseable via `jq`.
4. `zsh scripts/run-tests-external.sh -n spec26-wave2 tests/unit/test_config.py tests/unit/test_research_nodes_trim.py` → PASS.
5. Makefile diff = 0.
6. Full test runner shows no NEW failures vs `025-master-debug` baseline.

Blocks: implausible baseline numbers (p50 < 500 ms suggests harness mis-measurement; p50 > 300 s suggests stack broken rather than slow) → reject via `SendMessage` to A4.

---

### Wave 3 — Core Fixes (audit-driven, partial parallel)

**Goal**: Fix every remaining P1 + P2 bug with audit-backed decisions.

**User stories**: US-2 (Confidence), US-4 (Latency), US-5 (Concurrent load), US-7 (Config tuning).
**FRs discharged**: FR-003 (BUG-010), FR-005 (BUG-017 top-1 contributor), FR-006 (BUG-018), FR-009 (config tuning).
**SCs advanced**: SC-002, SC-004, SC-005, SC-006, SC-009.
**Dependencies**: Gate 2 passed (baseline committed, foundation fixes landed).
**Exit criteria**: Gate 3 shell block (below) confirms warm-state latency + concurrency + confidence.

#### A5 — Confidence Fix + Circuit Breaker Review (root-cause-analyst, Sonnet)

Reads: `spec.md` US-2 + US-5 + FR-003 + FR-006, `framework-audit.md` agent-methodology §confidence-threshold, `audit-synthesis.md`, `backend/agent/confidence.py`, `backend/agent/research_nodes.py` compute_confidence callsite, `backend/api/chat.py:243` (confidence emission), `backend/agent/nodes.py` module-level `_inf_*` state.

Writes:
- BUG-010 fix: identify actual root cause (likely candidates per prior forensic: `confidence_score` field never written to state, 5-signal math always returns 0 because one signal dominates, emission site reads wrong field). Add `tests/unit/test_research_confidence.py` asserting `compute_confidence` returns > 30 on a seeded retrieval with ≥ 4 relevant chunks.
- BUG-018 fix: audit `_inf_failure_count`, `_inf_circuit_open`, `_inf_max_failures = 5`. Exclude recoverable exceptions (parser retries that succeed) from the counter. Decide per-node vs per-process scoping. Add `tests/integration/test_circuit_breaker.py` — 10 queries that would trip under old counter rules but zero trip under new rules.

MCP tools: Serena, GitNexus (confidence caller graph, `_inf_*` accessors), Sequential Thinking (5-signal scoring math trace).

#### A6 — Top-1 Latency Fix + Config Tuning + P3 Opportunistic (performance-engineer, Opus)

Reads: `audit.md`, `framework-audit.md`, `audit-synthesis.md` (orchestrator-named top-1 contributor), `spec.md` US-4 + US-7 + FR-005 + FR-009 + Clarification 2 (P3 opportunistic), `backend/config.py`.

Writes:
- FR-005: apply minimal targeted code change at the top-1 contributor's surface. Acceptable outcomes: (a) p50 factoid drops under 4 s, (b) contributor is fundamental — documented + shift to #2, (c) bottleneck moves sideways — address within this spec if remaining budget permits.
- FR-009: tune `backend/config.py` defaults per audit. Every changed default gets `# spec-26: <reason>` trailing comment. Append to `audit.md` §Config Changes table (before / after / justification).
- P3 opportunistic: if audit shows BUG-023 (`embed_max_workers=4` → higher) is a one-line win, apply. If BUG-021 (cross-encoder-to-GPU) shows VRAM headroom AND < 2 hours to demonstrate a measured win, apply; else add `deferred` entry to `docs/bug-registry-spec26.md` with rationale + follow-up spec pointer.
- Re-run benchmark at end of wave → `docs/benchmarks/<sha>-wave3.json`. Compare to baseline.

MCP tools: Bash, Docker MCP (restart backend after config changes), Sequential Thinking (top-1 contributor reasoning trace), `mcp-chart` optional (before/after bar chart).

#### Gate 3 — SC Verification (orchestrator)

Checks:
1. Re-run `python scripts/benchmark.py --factoid-n 30 --analytical-n 10 --output docs/benchmarks/$(git rev-parse --short HEAD)-gate3.json`.
2. SC-004: `jq '.warm_state_p50.factoid_ms' <file> < 4000` → PASS.
3. SC-005: `jq '.warm_state_p50.analytical_ms' <file> < 12000` → PASS.
4. SC-006: `python scripts/benchmark.py --concurrent 5 --factoid-n 5 --output /tmp/conc.json` → no `CircuitOpenError`, all `done` events.
5. SC-002: `zsh scripts/run-tests-external.sh -n sc002 tests/unit/test_research_confidence.py` → PASS.
6. SC-003: 20-query loop on `qwen2.5:7b` shows zero parser-exception fallback log entries; backend started with `gemma4:e4b` fails fast.
7. Makefile diff = 0.
8. No new test regressions vs baseline.

Blocks: if SC-004 or SC-005 fails, do NOT proceed to Wave 4. Either re-run Wave 3 via `SendMessage` to A6 targeting the next contributor, or escalate to user with benchmark numbers + audit synthesis.

**Iteration cap (FR-005, clarified)**: A6 may attempt at most **2 contributor-fix iterations** within this wave. If the first iteration moves the bottleneck sideways and the second iteration also fails to clear SC-004, the third-and-beyond contributors are deferred to a follow-up spec. A6 records the deferral with rationale in `docs/bug-registry-spec26.md`, and the orchestrator evaluates SC-004/005 as FAIL in Gate 4's validation report with the cap-reached explanation. Cap exists to prevent scope creep; a sideways bottleneck after two fixes is a signal for architectural re-review, not continued iteration in-spec.

---

### Wave 4 — Validation + Docs (post-fixes, parallel)

**Goal**: Lock regression protection; publish honest public-facing performance documentation.

**User stories**: US-1 (final evidence), US-6 (telemetry validation test).
**FRs discharged**: FR-008 (stage timings test), FR-010 (docs/performance.md).
**SCs advanced**: SC-007, SC-010, SC-011, SC-012.
**Dependencies**: Gate 3 passed.
**Exit criteria**: Gate 4 `validation-report.md` evaluates all 12 SCs with PASS/FAIL/WAIVED + evidence citations.

#### A7 — Telemetry Test + Regression Sweep (quality-engineer, Sonnet)

Reads: `spec.md` US-6 + FR-008 + NFR-005 + SC-007 + SC-011, `backend/storage/sqlite_db.py` `query_traces` shape.
Writes: `tests/unit/test_stage_timings_validation.py` asserting for any completed query row: stage-timings non-null, keys ⊆ expected stable set, sum(per-stage) within ±5% of `latency_ms`. Runs full regression sweep via external test runner; compares to `025-master-debug` baseline; zero new failures allowed.

MCP tools: Bash.

#### A8 — Performance Docs + Bug Registry + README Link (technical-writer, Sonnet)

Reads: `spec.md`, both audit files, `audit-synthesis.md`, all `docs/benchmarks/*.json`, git log on branch.
Writes:
- `docs/performance.md` — reference-hardware warm p50/p90/p99 factoid + analytical numbers, cold-start penalty, qualitative degradation on weaker hardware, known limitations (thinking models unsupported, complex P3s deferred, reproducibility ±15%).
- `docs/bug-registry-spec26.md` — table with each bug: ID, severity, disposition (`fixed-in-spec` with commit SHA, or `deferred` with rationale + follow-up spec pointer).
- `README.md` — add Performance section linking `docs/performance.md`; update model-support language to match FR-004.

MCP tools: Read-only.

#### Gate 4 — Final Validation Report (orchestrator)

Writes: `specs/026-performance-debug/validation-report.md` evaluating all 12 SCs with evidence citations; commit-pin the post-fix benchmark result; Makefile diff = 0; commit-order check (SC-001); full test runner comparison to baseline (SC-011).

If PASS: prompt user for public-release readiness review (tag candidate, e.g., `v0.3.0-rc1`).
If FAIL: record WAIVED rationale or return to relevant wave via `SendMessage`.

---

## Dependency Graph

```
                Wave 1 — Audit (BLOCKING, FR-001)
               ┌───────────────────┬────────────────────────┐
               │ A1 Hardware       │ A2 Framework Config    │
               │ Audit             │ Audit                  │
               │ (devops, Sonnet)  │ (backend-arch, Opus)   │
               └───────────────────┴────────────────────────┘
                                │
                   ┌── GATE 1 (orchestrator) ──┐
                   │ Synthesize top-3 latency   │
                   │ contributors → name top-1  │
                   │ SC-001 commit-order check  │
                   └───────────────────────────┘
                                │
                Wave 2 — Foundation (audit-independent)
               ┌───────────────────┬────────────────────────┐
               │ A3 Supported-     │ A4 Benchmark Harness   │
               │ Model Gate +      │ + Baseline Capture     │
               │ Token Counter     │ (quality, Sonnet)      │
               │ (python, Sonnet)  │                        │
               └───────────────────┴────────────────────────┘
                                │
                   ┌── GATE 2 (orchestrator) ──┐
                   │ qwen2.5:7b default; smoke  │
                   │ harness; baseline JSON     │
                   │ SC-003 parser fallbacks    │
                   └───────────────────────────┘
                                │
                Wave 3 — Core Fixes (audit-driven)
               ┌───────────────────┬────────────────────────┐
               │ A5 BUG-010 + 018  │ A6 Top-1 Latency +     │
               │ root-cause fixes  │ Config + P3 opp        │
               │ (root-cause, S)   │ (perf-eng, Opus)       │
               └───────────────────┴────────────────────────┘
                                │
                   ┌── GATE 3 (orchestrator) ──┐
                   │ SC-002 confidence > 30     │
                   │ SC-004 factoid < 4s warm   │
                   │ SC-005 analytical < 12s    │
                   │ SC-006 5 concurrent OK     │
                   └───────────────────────────┘
                                │
                Wave 4 — Validation + Docs
               ┌───────────────────┬────────────────────────┐
               │ A7 Stage-Timings  │ A8 docs/performance +  │
               │ test + regression │ bug registry + README  │
               │ (quality, Sonnet) │ (writer, Sonnet)       │
               └───────────────────┴────────────────────────┘
                                │
                   ┌── GATE 4 (orchestrator) ──┐
                   │ validation-report.md all   │
                   │ 12 SCs with evidence       │
                   │ SC-007/008/010/011/012     │
                   └───────────────────────────┘
```

---

## Gate Check Protocol (shared by every gate)

```bash
# Makefile is SACRED
git diff -- Makefile | wc -l | grep -q '^0$' && echo "PASS: Makefile" \
  || { echo "FAIL: Makefile"; exit 1; }

# No test regressions vs branch-start baseline
zsh scripts/run-tests-external.sh -n gate-<N> --no-cov tests/
cat Docs/Tests/gate-<N>.status      # must equal baseline count of failures or fewer
cat Docs/Tests/gate-<N>.summary     # ~20-line summary, token-efficient

# Docker stack health (Waves 2+ when harness runs)
docker compose ps | awk 'NR>1 && $5 !~ /healthy|running/ {print "FAIL:",$0; exit 1}' \
  && echo "PASS: stack"

# Commit-order invariant (Gates 2+, verifies SC-001)
git log --oneline --reverse 025-master-debug..HEAD | \
  awk '/audit/{a=1} /^[0-9a-f]+ (fix|feat)/ && !a {print "FAIL: bugfix before audit:",$0; exit 1}'
```

---

## MCP Tool Assignment Matrix

| Tool | Orchestrator | A1 | A2 | A3 | A4 | A5 | A6 | A7 | A8 |
|------|-------------|----|----|----|----|----|----|----|----|
| Docker MCP | ✓ (all gates) | ✓ | — | — | ✓ | — | ✓ | — | — |
| Sequential Thinking | ✓ (gates 1, 3) | opt | ✓ | — | — | ✓ | ✓ | — | — |
| Context7 | — | — | ✓ (primitives) | ✓ (count_tokens) | — | — | — | — | — |
| Serena | — | — | ✓ | ✓ | — | ✓ | — | — | — |
| GitNexus | — | — | ✓ (pre-edit impact) | ✓ (trim_messages callers) | — | ✓ (confidence callers) | — | — | — |
| mcp-chart | — | opt | — | — | — | — | opt | — | — |
| Bash | ✓ | ✓ | — | ✓ | ✓ | — | ✓ | ✓ | — |

Sequential Thinking stays with orchestrator + the two architectural slots (A2 framework audit, A6 latency judgment, A5 confidence math trace). Agents do not use it casually — inflates latency for narrow tasks.

---

## Configuration Contract Changes (in lieu of formal `contracts/`)

FR-004 introduces a runtime configuration contract change; documented here because spec-26 adds no new API surfaces.

**Before (spec-25)**:
- `default_llm_model` was `"gemma4:e4b"` with no startup-time validation.
- Any model name the user configured was attempted at first query; parser exceptions surfaced at chat time.

**After (spec-26)**:
- `default_llm_model = "qwen2.5:7b"`.
- `supported_llm_models: list[str]` settings field lists the tested-and-recommended models.
- At backend startup (lifespan): `active_llm_model` is validated against `supported_llm_models`. If the configured model is absent, the backend fails to start with a structured error:
  - Error code: `UNSUPPORTED_MODEL` (or similar, final choice by A3)
  - Error message: `f"Model {model!r} is not in the supported list. Supported models: {supported_llm_models}"`
  - Exit code: non-zero; lifespan raises so Docker marks the container unhealthy.

**Caller impact**:
- Docker Compose health probe surfaces the failure (backend never becomes healthy).
- Launcher scripts (`embedinator.sh`, `embedinator.ps1`) propagate the error to the user. Launchers are NOT modified by spec-26; the error message is designed to be self-explanatory.
- Frontend observability page shows backend unreachable (BackendStatusProvider retry loop) — this is the intended UX for a configuration error.

**Deprecation note**: Thinking models (`gemma4:e4b`, `qwen3-thinking`, `deepseek-r1`) are explicitly unsupported in this release. Users who need thinking-model support must wait for a future spec that chooses Path A (token stripping) or later.

---

## Files the Plan Expects to Modify

| Path | Agent | Purpose |
|------|-------|---------|
| `backend/config.py` | A3, A6 | Default LLM revert; `supported_llm_models` allowlist; tuned defaults with `# spec-26:` comments |
| `backend/main.py` | A3 | Startup-time supported-model validation |
| `backend/agent/research_nodes.py` | A3, A5 | `trim_messages` counter swap; confidence callsite (if bug is there) |
| `backend/agent/confidence.py` | A5 | BUG-010 root-cause fix |
| `backend/agent/nodes.py` | A5 | Circuit breaker failure-counter scope (FR-006) |
| `backend/api/chat.py` | A5 (conditional) | Confidence emission site — only if emission is the bug |
| `backend/storage/sqlite_db.py` | A4 (conditional) | `get_recent_traces()` helper if harness needs it |
| `scripts/benchmark.py` | A4 | NEW — FR-002 harness |
| `tests/unit/test_research_confidence.py` | A5 | FR-003 regression test |
| `tests/unit/test_research_nodes_trim.py` | A3 | FR-007 regression test |
| `tests/unit/test_stage_timings_validation.py` | A7 | FR-008 regression test |
| `tests/unit/test_config.py` | A3 | Startup-refusal test |
| `tests/integration/test_circuit_breaker.py` | A5 | FR-006 integration test |
| `specs/026-performance-debug/audit.md` | A1, A6 (append) | Wave 1 writes; A6 appends config-changes table |
| `specs/026-performance-debug/framework-audit.md` | A2 | Wave 1 |
| `specs/026-performance-debug/audit-synthesis.md` | orchestrator | Gate 1 |
| `specs/026-performance-debug/validation-report.md` | orchestrator | Gate 4 |
| `docs/benchmarks/<sha>-pre-spec26.json` | A4 | Pre-fix baseline |
| `docs/benchmarks/<sha>-wave3.json` | A6 | Post-fix benchmark |
| `docs/performance.md` | A8 | Public performance doc |
| `docs/bug-registry-spec26.md` | A8 | Per-bug disposition |
| `README.md` | A8 | Performance-section link + model-support update |

### Files NEVER to Touch

`Makefile`, `embedinator.sh`, `embedinator.ps1`, `frontend/**`, `ingestion-worker/**`, `docker-compose.yml`, `specs/0{01..25}/**`.

---

## Build Verification Protocol

```bash
# --- Stack management (every wave that needs running services) ---
docker compose up -d
docker compose ps

# --- Health ---
curl -sf http://localhost:8000/api/health    | python -m json.tool
curl -sf http://localhost:8000/api/health/live | python -m json.tool

# --- Benchmark smoke (Gate 2) ---
python scripts/benchmark.py \
  --factoid-n 5 --analytical-n 2 \
  --output /tmp/bench-smoke.json \
  --base-url http://localhost:8000 \
  --collection-id <seeded-collection>

# --- Benchmark full (Gate 3, SC-004/005 gate) ---
python scripts/benchmark.py \
  --factoid-n 30 --analytical-n 10 \
  --output "docs/benchmarks/$(git rev-parse --short HEAD)-gate3.json" \
  --base-url http://localhost:8000 \
  --collection-id <seeded-collection>

# --- Concurrency smoke (Gate 3, SC-006 gate) ---
python scripts/benchmark.py \
  --concurrent 5 --factoid-n 5 \
  --output /tmp/conc.json \
  --base-url http://localhost:8000 \
  --collection-id <seeded-collection>

# --- Test runner (NEVER inline pytest) ---
zsh scripts/run-tests-external.sh -n spec26-<phase> --no-cov tests/
cat Docs/Tests/spec26-<phase>.status       # PASSED / FAILED / ERROR
cat Docs/Tests/spec26-<phase>.summary      # ~20 lines, token-efficient

# --- Makefile invariant (every gate) ---
git diff -- Makefile | wc -l               # MUST be 0

# --- Commit-order invariant (SC-001) ---
git log --oneline --reverse 025-master-debug..HEAD | head
```

---

## SC Evaluation Matrix

| SC | Evidence artifact | Verification command |
|----|-------------------|---------------------|
| SC-001 | Commit order on `026-performance-debug` | `git log --oneline --reverse 025-master-debug..HEAD \| head` |
| SC-002 | `tests/unit/test_research_confidence.py` | `zsh scripts/run-tests-external.sh -n sc002 tests/unit/test_research_confidence.py` |
| SC-003 | Backend startup log + 20-query sample log | `for i in {1..20}; do curl -sf .../chat; done 2>&1 \| grep -c 'fallback'` → 0; `EMBEDINATOR_LLM_MODEL=gemma4:e4b docker compose up backend` → fails fast |
| SC-004 | `docs/benchmarks/<sha>-gate3.json` | `jq '.warm_state_p50.factoid_ms' <file>` → < 4000 |
| SC-005 | same file | `jq '.warm_state_p50.analytical_ms' <file>` → < 12000 |
| SC-006 | `/tmp/conc.json` (concurrent run) | `jq '.errors \| map(select(.type==\"CircuitOpenError\")) \| length' /tmp/conc.json` → 0 |
| SC-007 | `tests/unit/test_stage_timings_validation.py` | `zsh scripts/run-tests-external.sh -n sc007 tests/unit/test_stage_timings_validation.py` |
| SC-008 | `tests/unit/test_research_nodes_trim.py` | `zsh scripts/run-tests-external.sh -n sc008 tests/unit/test_research_nodes_trim.py` |
| SC-009 | `grep -c '# spec-26:' backend/config.py` + `audit.md` §Config Changes | `grep '# spec-26:' backend/config.py \| wc -l` matches audit table row count |
| SC-010 | `docs/performance.md` + `README.md` link | file existence + `grep -c 'performance.md' README.md` ≥ 1 |
| SC-011 | Full regression via external runner vs baseline | `diff <baseline-failures> <spec26-final-failures>` → empty |
| SC-012 | Makefile byte diff | `git diff --stat -- Makefile \| wc -c` → 0 |

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| SC-004 target (warm-state factoid p50 < 4 s) is **above** Constitution's first-token budget (< 500 ms target / < 800 ms Phase 1 actual) | Current measured p50 is 26 s; reaching 800 ms in one spec is not achievable. Spec-26 targets 3× spec-14's 1.2 s as a realistic near-term milestone that a 10×–25× improvement can deliver. Further optimization toward the Constitution's budget is scheduled for a post-26 follow-up spec. | Matching Constitution's 800 ms in spec-26 rejected because: audit has not run, bottleneck is unknown, and committing to 800 ms blindly risks architectural rewrites that violate the spec's "no redesign" rule (Out of Scope §2). A staged approach keeps the Constitution's budget live as a long-term commitment without promising it in a single spec. |

Note: this is the ONLY Complexity Tracking entry. All other Constitution principles pass cleanly.

---

## Post-Plan Next Steps

1. **`/speckit.tasks`** — generate `tasks.md` with numbered tasks (T001+), each tagged with its agent slot (A1–A8) and gate. Dependency-ordered; parallel-safe tasks marked.
2. **`/speckit.analyze`** — cross-artifact consistency check (spec.md ↔ plan.md ↔ tasks.md).
3. **Design `/speckit.implement` context prompt** — the user will ask for this next. It will:
   - Inherit the enforcement banner above.
   - Generate 8 per-agent instruction files at `docs/PROMPTS/spec-26-performance-debug/agents/A{1..8}-instructions.md` (each ≤ 200 lines, following the spec-21 template).
   - Specify the tmux session/window/pane naming convention.
4. **`/speckit.implement`** — run inside tmux; orchestrator executes the 4 waves with gate checks.

---

## Appendix A — tmux Setup Reference

```bash
# Start a new session with 2×2 pane layout
tmux new-session -d -s embedinator-26
tmux split-window -h -t embedinator-26
tmux split-window -v -t embedinator-26
tmux select-pane -t embedinator-26:0.0
tmux split-window -v -t embedinator-26
tmux select-layout -t embedinator-26 tiled
tmux attach-session -t embedinator-26

# Required environment variable in every pane
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

**Layout per wave**:
- **Wave 1**: pane 0 orchestrator, pane 1 A1, pane 2 A2, pane 3 `docker compose logs -f` tail.
- **Wave 2**: pane 0 orchestrator, pane 1 A3, pane 2 A4, pane 3 test/log tail.
- **Wave 3**: pane 0 orchestrator, pane 1 A5, pane 2 A6, pane 3 `nvtop` + `docker stats`.
- **Wave 4**: pane 0 orchestrator, pane 1 A7, pane 2 A8, pane 3 test output.

## Appendix B — Agent Instruction File Template

Each `docs/PROMPTS/spec-26-performance-debug/agents/A{N}-instructions.md` (to be generated in the `/speckit.implement` design step) follows the spec-21 canonical form (see `docs/PROMPTS/spec-21-debug/agents/A1-instructions.md`):

- **Role** (agent type + wave + model)
- **Mission** (one paragraph)
- **Read First** (ordered list)
- **MCP Tools Available** (whitelist)
- **Tasks** (bulleted, mapped to T-IDs in `tasks.md`)
- **Files to Modify** (table)
- **Files NEVER to Touch** (explicit blocklist — inherited from §Files NEVER to Touch above)
- **Key Gotchas** (numbered)
- **Verification** (shell block)
- **Report Back** (what to return to orchestrator)

Each file ≤ 200 lines. Longer means scope is too broad — split the slot.
