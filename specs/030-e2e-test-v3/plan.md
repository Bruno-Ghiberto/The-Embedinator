# Implementation Plan: E2E Test v3 — Single-Round Human-in-the-Loop Bug Hunt

**Branch**: `030-e2e-test-v3` | **Date**: 2026-05-15 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification at `specs/030-e2e-test-v3/spec.md`

---

```text
╔═══════════════════════════════════════════════════════════════════════════════╗
║  MANDATORY — TMUX 5-PANE AGENT TEAMS LITE SESSION                             ║
║                                                                                ║
║  This banner gates `/speckit.implement`, NOT `/speckit.plan` or                ║
║  `/speckit.tasks`. The planning + tasks phases are normal single-Claude       ║
║  sessions. The hunt itself MUST run inside a tmux 5-pane layout that the      ║
║  Pilot spawns BEFORE invoking `/speckit.implement` in pane 2.                 ║
║                                                                                ║
║  WHY AGENT TEAMS LITE (not Live HITL like spec-28): Spec-28's per-blocker     ║
║  F/D/P gate needed synchronous Pilot input on EVERY blocker. Spec-30's only   ║
║  synchronous interaction is the rare BLOCKER-PATCHED Y/N gate (FR-011).       ║
║  Pilot drives the browser sync; supporting sub-agents work async.             ║
║                                                                                ║
║  PANE LAYOUT (Pilot spawns before `/speckit.implement`):                      ║
║    Pane 1 — Pilot          (human, real browser + terminal, no Claude)        ║
║    Pane 2 — Lead           (this Claude session, Opus, /speckit.implement)    ║
║    Pane 3 — Log Analyst    (python-expert RO, Sonnet, always-on)              ║
║    Pane 4 — Frontend Insp. (frontend-architect RO, Sonnet, always-on)         ║
║    Pane 5 — Bug Registrar  (technical-writer WO, Haiku, always-on — SOLE)     ║
║                                                                                ║
║  Always-on teammates (panes 3–5) load when the Lead calls Agent(team_name).   ║
║  On-demand teammates spawn into transient panes when needed:                  ║
║    • Root-Cause Investigator (root-cause-analyst, Sonnet, RO) — §5.1          ║
║    • Inline Fixer            (architect agent,    Sonnet, WO) — BLOCKER-PATCH ║
║                                                                                ║
║  PREFLIGHT (Lead runs this before phase 1):                                   ║
║    $ [ -n "$TMUX" ] || { echo "ERROR: must be inside tmux"; exit 1; }         ║
║    $ tmux list-panes | wc -l | awk '$1>=5{ok=1}END{exit ok?0:1}' \            ║
║        || { echo "ERROR: need 5 tmux panes"; exit 1; }                        ║
║    $ docker compose ps | grep -E 'qdrant|ollama|backend|frontend' \           ║
║        || { echo "ERROR: docker stack must be up before Phase 1"; exit 1; }   ║
║    $ git rev-parse --abbrev-ref HEAD | grep -q "^030-e2e-test-v3$" \          ║
║        || { echo "ERROR: must be on 030-e2e-test-v3 branch"; exit 1; }        ║
║    $ test -f specs/030-e2e-test-v3/phase-playbook.md \                        ║
║        || { echo "ERROR: phase-playbook.md must exist"; exit 1; }             ║
║                                                                                ║
║  PROHIBITED:                                                                   ║
║    - Production code edits outside BLOCKER-PATCHED narrow exception (FR-010)  ║
║    - Autonomous BLOCKER-PATCHED fixes without Pilot Y/N (FR-011, SC-005)     ║
║    - Promoting any screenshot/log to `public-evidence/` without secret-scan   ║
║      verification AND session-log capture (FR-028, SC-012)                    ║
║    - Severity downgrade due to BLOCKER-PATCHED fix (FR-013)                  ║
║    - Closing hunt with unfiled CRITICALs or untriaged MAJORs (FR-014, FR-015) ║
║    - Starting spec-31 fix wave before this hunt's registry closes (A-004)    ║
║    - Editing Makefile (SACRED — spec-17 + spec-19 contracts)                 ║
║    - Editing embedinator.sh / embedinator.ps1 (SACRED — spec-19 contract)    ║
║    - Re-baselining chat answer correctness — out of scope (A-003)            ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

---

## Summary

A time-boxed, single-round end-to-end bug hunt over the running product surface for pre-v1.0.0 portfolio-quality validation. Pilot (human) drives a real Chromium browser sync through seven product-surface phases (cold start, ingestion, chat happy, chat edge, settings, observability, recovery); supporting sub-agents (Log Analyst, Frontend Inspector, Bug Registrar) work async on the data trail. The deliverable is a public, defensible bug registry — not code fixes (those belong to spec-31, the strictly-sequential fix wave). Eight phases (Phase 0 preflight + Phase 1–7 hunt + Phase 8 closure) over ≤12 working hours. Zero production code modifications outside a narrow Pilot-authorized BLOCKER-PATCHED exception. Secret hygiene enforced via tracked-vs-gitignored artifact split with Pilot-curated `public-evidence/` redaction.

## Technical Context

**Language/Version**: Python 3.14+ (backend, unchanged); TypeScript 5.7 (frontend, unchanged); Rust 1.93.1 (ingestion worker, NOT modified in this spec); Bash (Pilot session scripts)
**Primary Dependencies**: FastAPI >=0.135, LangGraph >=1.0.10, LangChain >=1.2.10, Pydantic v2 >=2.12, aiosqlite >=0.21, Qdrant Client >=1.17.0, sentence-transformers >=5.2.3, cryptography (Fernet) >=44.0, structlog >=24.0, tenacity >=9.0 (backend); Next.js 16, React 19, Tailwind 4, SWR 2 (frontend) — **all pre-existing, NO new application dependencies for spec-30**
**Storage**: SQLite WAL mode (`data/embedinator.db`, existing); Qdrant hybrid dense+BM25 (existing); LangGraph checkpoint DB (`data/checkpoints.db`, existing) — no schema changes
**Testing**: pytest (backend) and vitest/Playwright (frontend) — but spec-30 does NOT execute the test suites; it drives the running app via the Pilot in a real Chromium browser. Playwright is used in MANUAL mode (lead dispatches frontend-inspector with playwright MCP for one-off browser introspection, not for scripted assertions)
**Target Platform**: Linux (Fedora) Pilot workstation; Docker Compose v2 stack (qdrant, ollama, backend, frontend); cross-platform Pilot guidance optional (Constitution VIII inherited)
**Project Type**: Process spec — drives existing application surface, produces documentation deliverables (bug registry + summary + GitHub issues). Spec-30 makes ZERO production-code structure changes.
**Performance Goals**: Hunt itself: ≤12 working hours total budget (SC-001). Existing app performance budgets referenced via FR-029 binding to spec-14 (perf budgets) and spec-26 (latency p50/p95 targets); the hunt does not introduce new performance targets, it validates whether the documented ones hold in the running UI
**Constraints**: Single round (FR-002, no loops). Chromium-only (FR-018). No production code edits outside BLOCKER-PATCHED narrow exception (FR-010, SC-006). Zero secrets leaked in tracked artifacts (FR-028, SC-012). Strict sequencing — spec-31 cannot start until this hunt's registry closes (A-004)
**Scale/Scope**: 1 Pilot (Bruno Ghiberto) + 1 Lead Claude session (Opus, runs `/speckit.implement` via Agent Teams) + 3 always-on teammates (python-expert/Sonnet RO, frontend-architect/Sonnet RO, technical-writer/Haiku WO-sole-writer) + 2 on-demand teammates (root-cause-analyst/Sonnet RO, architect-agent/Sonnet WO plan-approval-gated). 8 phases. 7 product-surface user stories. 29 FRs. 12 SCs. Estimated 5–50 registered defects (lower bound: hunt finds the smoke; upper bound: 12h × ~3 defects/hour average). Single tracked session directory `docs/E2E/2026-05-NN-round-1-bug-hunt/`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

Evaluating each of the 8 Embedinator Constitution principles against this spec's design:

| Principle | Status | Notes |
|---|---|---|
| I. Local-First Privacy | ✅ Inherited | Hunt drives existing app; existing local-first defaults unchanged. Cloud-provider key tests (P5-S1) use placeholder `sk-test-PLACEHOLDER` strings, never real production keys |
| II. Three-Layer Agent Architecture (ADR-002) | ✅ Inherited | ConversationGraph → ResearchGraph → MetaReasoningGraph nesting unchanged. Hunt validates checkpoint resume behavior (P7-S1, P7-S5) but does not modify graph structure |
| III. Retrieval Pipeline Integrity (ADR-004, ADR-005) | ✅ Inherited | Parent/child chunking, hybrid dense+BM25, cross-encoder reranking all preserved. Hunt may surface bugs in retrieval UX surfacing (P3, P6) but does not modify the pipeline |
| IV. Observability from Day One (ADR-006) | ✅ Inherited + extended | Every chat in P3/P4/P5 will produce a `query_traces` row per existing contract. Hunt VALIDATES that the trace surface is user-readable (P6-S1, P6-S2) — additive enforcement of IV |
| V. Secure by Design (ADR-008) | ✅ Inherited + extended | Fernet-encrypted API key storage validated in P5-S1/S2/S5. Plaintext key audit (P5-S5) directly enforces Principle V's "API keys MUST NOT appear in logs or responses" rule. SC-012 elevates this to a hunt-level invariant |
| VI. NDJSON Streaming Contract (ADR-007) | ✅ Inherited | Chat streaming validated in P3 (token-by-token streaming, `chunk` event name per spec-24 fix). No protocol changes |
| VII. Simplicity by Default (ADR-001, ADR-003) | ✅ Aligned | Spec-30 introduces ZERO new application dependencies, ZERO new services, ZERO new abstractions. The hunt is a documentation-and-process spec |
| VIII. Cross-Platform Compatibility | ✅ Aligned | Hunt is Chromium-only (FR-018) but does not change the app's cross-platform stance. Pilot session runs on Linux but the methodology is platform-neutral (a future Pilot on macOS or Windows could re-execute the same playbook) |

**All gates PASS.** No principle violations. No Complexity Tracking entries required.

## Project Structure

### Documentation (this feature)

```text
specs/030-e2e-test-v3/
├── plan.md                              # This file (/speckit.plan command output)
├── spec.md                              # Feature specification (already exists)
├── research.md                          # Phase 0 output (5 open design questions resolved)
├── data-model.md                        # Phase 1 output (5 schemas)
├── quickstart.md                        # Phase 1 output (Pilot session ops guide)
├── phase-playbook.md                    # Phase 1 output (operational scenarios per phase)
├── contracts/                           # Phase 1 output (3 contract files)
│   ├── session-directory-contract.md    # File layout under docs/E2E/2026-05-NN-…
│   ├── blocker-patched-gate-contract.md # Lead prompt + Pilot Y/N protocol
│   └── bug-registry-schema.md           # JSON schema for spec-31 consumption
├── checklists/
│   └── requirements.md                  # Spec quality checklist (already exists, all pass)
└── tasks.md                             # Phase 2 output (/speckit.tasks command — NOT created here)
```

### Source Code (repository root)

Spec-30 makes **ZERO production-code structure changes**. The hunt drives the existing app:

```text
# EXISTING, UNCHANGED — referenced by hunt scenarios
backend/                  # Phase 1/2/3/4/6 scenarios validate this surface
├── agent/                # P3 + P4 chat streaming + research loop
├── retrieval/            # P3 + P6 retrieval trace surface
├── storage/              # P2 + P5 + P7 persistence behavior
├── api/                  # P1 health + P5 settings endpoints
└── main.py               # P1 cold start + P7 lifespan recovery

frontend/                 # Phase 1/3/5/6 UI surface
├── src/                  # Pilot drives this via real Chromium
└── tests/e2e/            # NOT used by spec-30 (Playwright manual-driving only)

ingestion-worker/         # P2 ingestion worker — NOT modified

# NEW deliverable directory (created by Phase 0 of the hunt)
docs/E2E/2026-05-NN-round-1-bug-hunt/
├── bugs/                            # TRACKED — one .md per BUG-XXX
├── session-log.md                   # TRACKED — chronological timeline
├── triage.md                        # TRACKED — Phase 8 severity rollup
├── SUMMARY.md                       # TRACKED — Phase 8 closing summary
├── bugs-registry.json               # TRACKED — machine-readable, spec-31 input
├── public-evidence/                 # TRACKED — Pilot-curated redacted artifacts
├── .gitignore                       # TRACKED — declares subdirs below as ignored
├── logs/                            # GITIGNORED — raw log excerpts
├── screenshots/                     # GITIGNORED — raw screenshots
└── traces/                          # GITIGNORED — raw browser traces
```

**Structure Decision**: This is a process/documentation spec. The "code structure" is the layout of the new dated session directory under `docs/E2E/`, governed by the contract in `contracts/session-directory-contract.md`. No `src/`, `tests/`, or production-source paths are introduced.

## Phase Breakdown

All seven hunt phases run in order. Phase 0 (preflight) precedes Phase 1; Phase 8 (closure) follows Phase 7. Time-box per phase is FLEXIBLE within the 12-hour total budget (FR-001).

### Phase 0 — Preflight & Playbook Verification (≤30 min)

**US**: setup for all. **FRs**: FR-022, FR-027, FR-028. **SCs**: SC-006.
**Owner**: Lead (pane 2).
**Work**:
1. Run the enforcement-banner preflight script (tmux check, pane count, docker stack, branch, playbook exists).
2. Create the dated session directory with canonical structure (see `contracts/session-directory-contract.md`).
3. Start `session-log.md` with a "Session opened" timestamped entry; capture develop HEAD SHA + spec/plan/playbook SHAs.
4. Confirm the next free BUG ID (BUG-024 onwards).

**Gate**: Preflight green; session dir exists with correct structure; session-log has opening entry; next BUG ID acknowledged.

### Phase 1 — Cold Start Hunt (US1, ~1h)

**FRs**: FR-001, FR-003, FR-004, FR-005, FR-006, FR-007, FR-008. **SCs**: SC-001, SC-002, SC-004, SC-010.
**Owner**: Pilot drives stack; Log Analyst tails startup logs; Frontend Inspector captures first-paint; Bug Registrar records.
**Scenarios** (4): P1-S1 clean cold start, P1-S2 first-paint dashboard, P1-S3 degraded health signal, P1-S4 restart cycle. Full scenario detail in `phase-playbook.md`.
**Exit**: Dashboard loaded, all health green, OR findings registered.

### Phase 2 — Ingestion Hunt (US2, ~2h)

**FRs**: FR-003 through FR-009. **SCs**: SC-002, SC-004, SC-010.
**Owner**: Pilot drives uploads; Log Analyst on worker logs; Frontend Inspector on progress UI; Bug Registrar records.
**Scenarios** (6): P2-S1 single PDF, P2-S2 each file type, P2-S3 malformed PDF, P2-S4 oversized upload, P2-S5 duplicate upload, P2-S6 mid-upload kill.
**Exit**: ≥1 doc fully queryable + adversarial cases exercised.

### Phase 3 — Chat Happy Path Hunt (US3, ~2h)

**FRs**: FR-003 through FR-009, FR-020. **SCs**: SC-002, SC-004, SC-010.
**Owner**: Pilot drives chat; Frontend Inspector on streaming+citation UX; Log Analyst on trace data; Bug Registrar records.
**Question set (FR-020 hybrid)**: 5 reused from spec-28 RAGAS golden (Q-001/005/014/018/007) + 3–4 new UI-behavior probes.
**Scenarios** (6): P3-S1 factoid streaming, P3-S2 citation interaction, P3-S3 long-answer scroll, P3-S4 multi-turn follow-up, P3-S5 Spanish accents, P3-S6 mid-stream navigation.
**Exit**: All 5 reused + 3 new probes exercised; findings registered.

### Phase 4 — Chat Edge Case Hunt (US4, ~1.5h)

**FRs**: FR-003 through FR-009, FR-021. **SCs**: SC-002, SC-004, SC-010.
**Owner**: Pilot drives; Log Analyst correlates decline/timeout logs; Bug Registrar records.
**Scenarios** (6): P4-S1 out-of-scope, P4-S2 ambiguous, P4-S3 Spanish-English mix, P4-S4 direct prompt injection, P4-S5 in-chunk prompt injection (skippable with Pilot consent), P4-S6 induced tool timeout.
**Exit**: All 5 FR-021 categories exercised; findings registered.

### Phase 5 — Settings & Providers Hunt (US5, ~1.5h)

**FRs**: FR-003 through FR-009. **SCs**: SC-002, SC-004, SC-010, **SC-012**.
**Owner**: Pilot drives; Frontend Inspector on Settings UI; Log Analyst greps logs for key/secret strings; Bug Registrar records.
**Scenarios** (5): P5-S1 add fake API key, P5-S2 restart with stored key, P5-S3 active model swap, P5-S4 embedding model swap, P5-S5 plaintext key audit (SC-012 enforcement).
**Exit**: Key-storage scenarios exercised; SC-012 zero-leak check passes for this phase.

### Phase 6 — Observability Hunt (US6, ~1h)

**FRs**: FR-003 through FR-009. **SCs**: SC-002, SC-004, SC-010.
**Owner**: Pilot drives traces/charts; Frontend Inspector on observability UI; Log Analyst verifies trace coherence; Bug Registrar records.
**Scenarios** (4): P6-S1 trace navigation, P6-S2 error navigability, P6-S3 performance chart, P6-S4 log surface readability.
**Exit**: All observability surfaces exercised.

### Phase 7 — Recovery & State Hunt (US7, ~1.5h)

**FRs**: FR-003 through FR-009. **SCs**: SC-002, SC-004, SC-010.
**Owner**: Pilot drives kill scenarios; Log Analyst on restart logs; Frontend Inspector on UI state; Bug Registrar records.
**Scenarios** (5): P7-S1 backend kill mid-stream, P7-S2 Ollama unavailable, P7-S3 Qdrant unavailable mid-ingestion, P7-S4 full restart with persistent data, P7-S5 checkpoint resume validation.
**Exit**: All recovery scenarios exercised.

### Phase 8 — Closure & Registry Freeze (≤1h)

**FRs**: FR-014, FR-015, FR-016, FR-017, FR-022, FR-023, FR-024, FR-025, FR-026, FR-027, FR-028. **SCs**: SC-002, SC-003, SC-005, SC-006, SC-007, SC-008, SC-011, SC-012.
**Owner**: Lead (pane 2).
**Work**:
1. Triage every MAJOR-or-higher finding: v1.0-fix or v1.1-defer; create public GitHub issue via `gh issue create`; record URL in `triage.md` and `bugs-registry.json`.
2. Evidence curation (FR-027 + FR-028): Pilot reviews each artifact, verifies no secrets/PII, redacts via imagemagick, copies to `public-evidence/`, lead writes verification entry.
3. Severity treemap via `mcp-chart` (fallback: markdown table if MCP unavailable — see research.md).
4. Write `SUMMARY.md`: severity counts, triage roll-up, BLOCKER-PATCHED log, notable findings, link to `bugs-registry.json`. SC-007 peer-review test.
5. Validate `bugs-registry.json` against schema (see `contracts/bug-registry-schema.md`).
6. Add README link to `SUMMARY.md`.
7. SC-006 check: `git diff develop -- backend/ frontend/ ingestion-worker/` empty (or matches BLOCKER-PATCHED commits).
8. SC-012 check: `rg -i 'sk-(test|live|proj)\|api[_-]?key\s*=' docs/E2E/.../` returns zero hits in tracked files.

**Gate**: SUMMARY committed, README link committed, registry schema-valid, every MAJOR+ has triage decision with issue URL, every BLOCKER-PATCHED has Y/N session-log capture, SC-006 + SC-012 pass.

## Tmux Pane Roster (verbatim from spec)

| Pane | Role | Agent | Model | Reads | Writes | Primary MCPs |
|------|------|-------|-------|-------|--------|--------------|
| 1 | Pilot | — (human) | — | spec, playbook, app UI | session-log relay, BLOCKER-PATCHED Y/N | chrome-devtools (manual), playwright (manual), shell |
| 2 | Lead | — (this Claude session, via Agent Teams) | **Opus** | spec, plan, playbook, Pilot relay | triage decisions, BLOCKER-PATCHED gate, phase transitions, SUMMARY, triage.md | sequential-thinking, engram, serena, gitnexus (impact) |
| 3 | Log Analyst | python-expert (RO) | Sonnet | docker logs, structlog JSON, backend source | log excerpts (paths only) | rust-mcp-filesystem (tail_file, regex), docker, serena |
| 4 | Frontend Inspector | frontend-architect (RO) | Sonnet | running frontend, DevTools state, frontend source | screenshot annotations | browser-tools, chrome-devtools, playwright, serena |
| 5 | Bug Registrar | technical-writer (write-only on registry) | **Haiku** | lead dispatch, Pilot observations | bugs/BUG-NNN.md, session-log entries, bugs-registry.json (final), severity treemap | rust-mcp-filesystem (write_file), mcp-chart |

**On-demand**: Root-Cause Investigator (root-cause-analyst, Sonnet, RO); Inline Fixer (python-expert / backend-architect / frontend-architect, Sonnet, write access scoped to BLOCKER-PATCHED only).

## FR-029 Budget Binding Table

The phase-playbook is the canonical source for these bindings; the table is reproduced here for plan-level traceability.

| Spec reference | Scenario | Source binding |
|----------------|----------|----------------|
| "documented startup budget" (US1 AC1) | P1-S1 | spec-14 §perf-budgets (Constitution: UI cold load <2s, /health <50ms); playbook §1.S1 fills service-level (default 90s total / 30s per service) |
| "documented status states" (US2 AC1) | P2-S1, S2 | playbook §2 canonical: `pending → parsing → chunking → indexing → ready` + `failed` terminal |
| "documented timeout" (US2 AC2) | P2-S3 | Ingestion worker per-file timeout (verify constant in `backend/ingestion/worker.py` at hunt time); expected error-surface ≤10s. Per research.md R5 — no single canonical timeout anchor exists in spec-26 |
| "documented latency budget" (US3 AC1) | P3-S1, S2, S5 | spec-26 measured baseline (warm factoid p50 ≈ 19.5s, analytical p50 ≈ 16.0s after PR #20). Constitution: first-token <500ms target / <800ms Phase 1 actual |
| "documented UX" (US3 AC3) | P3-S3 | spec-22 frontend-pro auto-scroll policy; playbook §3.S3 captures concrete behavior |
| "documented timeout" (US7 AC2) | P7-S1, S2 | `backend/config.py::Settings.max_loop_seconds = 300` (research-loop wall-clock; spec-26 BUG-008 fix); circuit-breaker cooldown 30s (Constitution §Reliability). Per research.md R5 |
| "documented ingestion budget" (derived) | P2-S1, S2 | playbook §2.S1 (default: ≤60s for ≤5MB PDF, scaled per MB above) |
| "documented startup readiness" (derived) | P1-S1 | playbook §1.S1 |
| Citation interaction UX (US3 AC2) | P3-S2 | playbook §3.S2 (tooltip ≤200ms, click navigation ≤1s) |

## Files the Plan Expects to Modify

**NEW** (created during hunt):
- `docs/E2E/2026-05-NN-round-1-bug-hunt/` entire dated session directory (per `contracts/session-directory-contract.md`).
- `specs/030-e2e-test-v3/research.md`, `data-model.md`, `quickstart.md`, `phase-playbook.md`, `contracts/*.md` (this plan phase emits these).

**MODIFIED**:
- `README.md` — one-line link to `docs/E2E/2026-05-NN-round-1-bug-hunt/SUMMARY.md` after Phase 8.
- Public GitHub issues — created via `gh issue create` for every MAJOR-or-higher finding during Phase 8.

**MAY BE MODIFIED (BLOCKER-PATCHED only)**:
- Any one file affected by an authorized inline patch — only after Pilot Y/N. Each such commit referenced in the bug's BLOCKER-PATCHED note.

**NEVER TOUCH**:
- `Makefile` (SACRED — spec-17 + spec-19; SC-010 invariant).
- `embedinator.sh`, `embedinator.ps1` (SACRED — spec-19 launcher contract).
- `backend/**`, `frontend/**`, `ingestion-worker/**` outside BLOCKER-PATCHED exception.
- Any file owned by an in-flight Dependabot PR (`gh pr list --label dependencies` before any inline edit).
- The corpus (`data/Collection-Docs/` — gitignored, relocated from `docs/` in repo-order cleanup; out of spec-30 scope per A-002).

## SC Evaluation Matrix

| SC | What proves it | Where the evidence lives |
|----|----------------|--------------------------|
| SC-001 (12-hour time-box) | session-log "Session opened/closed" timestamps differ ≤12h | session-log.md |
| SC-002 (100% CRITICAL records) | Every CRITICAL in registry has all required fields | bugs-registry.json + JSON schema validation |
| SC-003 (100% MAJOR+ triaged with issue) | Every MAJOR+ has triage.github_issue_url non-null | bugs-registry.json |
| SC-004 (100% bug records have required attrs) | JSON schema validation passes | bugs-registry.json |
| SC-005 (100% BLOCKER-PATCHED have Pilot Y/N) | Every blocker_patched.applied=true has pilot_authorization_timestamp non-null AND session-log cross-ref | bugs-registry.json + session-log.md |
| SC-006 (0 production code edits outside BLOCKER-PATCHED) | `git diff develop -- backend/ frontend/ ingestion-worker/` empty or matches BLOCKER-PATCHED commits | git diff at Phase 8 |
| SC-007 (SUMMARY non-technical readable) | Peer-review pass without codebase access; attestation in session-log | SUMMARY.md + reviewer attestation |
| SC-008 (registry schema-valid) | `jsonschema validate` exits 0 | CI/Phase 8 closure step |
| SC-009 (≥80% repeatability) | Deferred — measurable only with a 2nd hunt round; documented as forward-looking | N/A this round |
| SC-010 (all 7 phases entered+exited) | session-log has phase-transition entries for all 7 | session-log.md |
| SC-011 (registry+SUMMARY → go/no-go) | Pilot writes `LAUNCH-DECISION.md` referencing both | LAUNCH-DECISION.md alongside SUMMARY.md |
| SC-012 (0 secrets in public artifacts) | `rg -i 'sk-(test|live|proj)\|api[_-]?key\s*=' docs/E2E/2026-05-NN-...` returns zero hits in tracked files | grep at Phase 8 |

## Dependency Graph

```
Phase 0 (preflight + playbook check)
   └── Phase 1 (cold start)
          └── Phase 2 (ingestion)
                 └── Phase 3 (chat happy)
                        ├── Phase 4 (chat edge)
                        ├── Phase 5 (settings)
                        ├── Phase 6 (observability)
                        └── Phase 7 (recovery)
                               └── Phase 8 (closure + registry freeze)
                                      └── spec-31 (fix wave — STRICTLY after spec-30 closes)
```

Phases 4–7 fan out from Phase 3 — sequential in execution order, but each is independent of the others; Phase 3's exit signal (≥1 doc queryable + happy-path validated) is the entry condition for all. Phase 8 cannot start until Phase 7 exits.

## Complexity Tracking

> No constitution violations. No complexity tracking entries required.

## Post-Design Constitution Re-check

After Phase 1 (data-model.md, contracts/, quickstart.md, phase-playbook.md) materialized:

| Principle | Status post-design |
|---|---|
| I. Local-First Privacy | ✅ Reaffirmed — placeholder keys only in P5 scenarios |
| II. Three-Layer Agent Architecture | ✅ Reaffirmed — graph structure unchanged |
| III. Retrieval Pipeline Integrity | ✅ Reaffirmed — pipeline unchanged |
| IV. Observability from Day One | ✅ Reaffirmed — trace surface validated, not modified |
| V. Secure by Design | ✅ Reaffirmed — SC-012 zero-leak target operationalized |
| VI. NDJSON Streaming Contract | ✅ Reaffirmed — `chunk` event name validated |
| VII. Simplicity by Default | ✅ Reaffirmed — zero new app deps, zero new services |
| VIII. Cross-Platform Compatibility | ✅ Reaffirmed — Chromium-only is a hunt scope choice, not a platform restriction |

All gates remain green. Plan is ready for `/speckit.tasks`.
