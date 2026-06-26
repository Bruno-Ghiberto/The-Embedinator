# Implementation Plan: E2E Bug Hunt & Quality Baseline (Pre-v1.0.0)

**Branch**: `028-e2e-bug-hunt-quality-baseline` | **Date**: 2026-04-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/028-e2e-bug-hunt-quality-baseline/spec.md`
**Planning context**: `docs/PROMPTS/spec-28-E2E-v01/28-plan.md`

---

## Enforcement Banner (carries forward to `/speckit.implement`)

```text
╔═══════════════════════════════════════════════════════════════════════════════╗
║  MANDATORY — HYBRID EXECUTION (AGENT TEAMS LITE + LIVE HITL BLOCK)            ║
║                                                                                ║
║  Spec-28 runs in two execution modes, strictly sequenced:                      ║
║                                                                                ║
║    (A) AGENT TEAMS LITE — four mechanical waves coordinated by orchestrator   ║
║        via TeamCreate / TaskCreate / SendMessage. One teammate per tmux       ║
║        pane. Used for: Playwright stabilization (Wave 1), RAGAS harness       ║
║        scaffolding (Wave 2), RAGAS baseline run (Wave 3), wrap-up             ║
║        aggregation (Wave 4).                                                   ║
║                                                                                ║
║    (B) LIVE HITL BLOCK — a single 4-hour interactive session with a           ║
║        persistent 3-teammate team (Test Runner + Scribe + Log Watcher)        ║
║        coordinated by orchestrator SendMessage, with F/D/P gates paused       ║
║        in the orchestrator pane for user decision. Used for: exploratory      ║
║        charters (US2), fault injection (US3), and user-driven golden-pair    ║
║        authorship + review (US4 T033/T035).                                   ║
║                                                                                ║
║  WHY THE HYBRID: The spec contains both mechanical work that parallelizes     ║
║  cleanly (stabilization, harness code, batch runs, aggregation) and           ║
║  interactive work that REQUIRES synchronous user input on every Blocker and   ║
║  for golden-pair authorship. Pure Agent Teams Lite would batch Blockers       ║
║  instead of triaging live. Pure HITL would under-use parallelism for the      ║
║  phases where the user has nothing to decide.                                  ║
║                                                                                ║
║  PANE LAYOUT (orchestrator runs in pane 0; teammates auto-spawn in panes):    ║
║    Pane 0 — Orchestrator   (Claude Opus, reads 28-implement.md)               ║
║    Wave 1: Pane 1 — A1 Playwright Stabilizer (Sonnet)                         ║
║    Wave 2: Pane 1 — A2 RAGAS Harness Author  (Sonnet)                         ║
║    Live Block: Pane 1 — A3 Test Runner Live (Sonnet, persistent)              ║
║                Pane 2 — A4 Scribe Live       (Sonnet, persistent)             ║
║                Pane 3 — A5 Log Watcher Live  (Sonnet, persistent)             ║
║    Wave 3: Pane 1 — A6 RAGAS Runner          (Sonnet)                         ║
║    Wave 4: Pane 1 — A7 Wrap-up Scribe        (Sonnet)                         ║
║                                                                                ║
║  PREFLIGHT (the orchestrator runs this before work begins):                   ║
║    $ [ -n "$TMUX" ] || { echo "ERROR: must be inside tmux"; exit 1; }         ║
║    $ docker compose ps | grep -E 'qdrant|ollama|backend|frontend' \           ║
║        || { echo "ERROR: docker stack must be up"; exit 1; }                  ║
║    $ git rev-parse --abbrev-ref HEAD | grep -q "^028-e2e" \                   ║
║        || { echo "ERROR: must be on 028 feature branch"; exit 1; }            ║
║                                                                                ║
║  PROHIBITED:                                                                   ║
║    - Running any wave or the Live Block outside tmux                          ║
║    - Spawning teammates in the same pane (each teammate = separate pane)      ║
║    - Proceeding past a Live-Block Blocker without an F/D/P decision recorded  ║
║    - Silently deleting a failing test without a filed bug + written rationale ║
║    - Changing Makefile, embedinator.sh, embedinator.ps1 (SACRED per FR-026)   ║
║    - Mixing wave mode and Live-Block mode inside one TeamCreate (create a     ║
║      distinct team for each wave and one persistent team for the Live Block)  ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

---

## Summary

Spec-28 is the pre-v1.0.0 quality gate. It ships four deliverables in a single gated effort: (a) a stabilized scripted Playwright regression suite running on every PR with `continue-on-error: false`, (b) one four-hour charter-driven exploratory session that produces a structured bug inventory in `docs/E2E/YYYY-MM-DD-bug-hunt/`, (c) three-to-five fault-injection scenarios executed against the live container stack with pass/fail verdicts, and (d) a 20-pair RAGAS quality baseline on the committed Argentine gas regulatory corpus. The deliverable is the bug list + the quality numbers; the tests are the vehicle. Execution is a hybrid of **Agent Teams Lite** (four mechanical waves: stabilization → harness scaffolding → RAGAS run → wrap-up) and a single **Live HITL Block** (a persistent 3-teammate team running the 4-hour exploratory session, fault-injection scenarios, and user-driven golden-pair authorship, with F/D/P gates paused in the orchestrator pane for synchronous user decision on every Blocker).

---

## Technical Context

**Language/Version**:
- Python 3.14+ (backend, new `tests/quality/` directory)
- TypeScript 5.7 (frontend Playwright specs, unchanged runtime)
- Node.js LTS (frontend tooling, unchanged)

**Primary Dependencies** (existing, no new runtime dependencies for the product):
- Playwright v1.50 (frontend/tests/e2e/, existing)
- pytest >= 8.0 + pytest-asyncio >= 0.24 (tests/, existing)
- httpx >= 0.28 (test clients, existing)
- Docker Compose v2 (stack orchestration, existing)

**New evaluation-only dependency** (not shipped to users):
- `ragas` (latest stable at plan time — candidate, pin at implement time; contains to `tests/quality/` only)

**Storage**: SQLite WAL mode (`data/embedinator.db`, existing, read-only from the test's perspective) + Qdrant (existing, read-only from the test's perspective). No schema changes.

**Testing**:
- Playwright for scripted E2E (existing tool, stabilization + CI flip)
- pytest for the RAGAS quality harness (external runner policy from CLAUDE.md: `zsh scripts/run-tests-external.sh -n <name> tests/quality/...`)
- `docker kill` / `docker stop` / `docker network disconnect` for fault injection

**Target Platform**:
- Local Linux dev machine (session orchestration, 14 MB corpus, 4-hour exploratory)
- GitHub Actions Ubuntu runner for CI (Playwright only)
- Session tmux workflow: Linux + macOS primary (bash/zsh). Windows users MUST use WSL per Constitution VIII.

**Project Type**: Web application (existing `backend/` + `frontend/`) + new test-only additions. No production code additions unless a Phase 3 F-path fix lands on a Blocker.

**Performance Goals** (measurements, not product perf):
- Stabilized Playwright suite: under 5 minutes wall clock on the Chromium pass (target; plan flags if exceeded)
- RAGAS baseline run: under 30 minutes for 20 pairs against a warm stack
- Exploratory session cadence: average 1 logged finding per 5-8 minutes across the 4-hour block (calibration, not a gate)

**Constraints**:
- `Makefile` MUST remain unchanged (SACRED per FR-026, SC-010; verified by `git diff develop -- Makefile` returning empty at Phase 6 close)
- `embedinator.sh` and `embedinator.ps1` untouched (SACRED per spec-19)
- `backend/**` and `ingestion-worker/**` untouched unless a Phase 3 F-path fix demands it
- No change to the Shape X 9-check aggregate CI roster (spec-27 contract)
- Makefile, launchers, backend, ingestion-worker paths MUST be preserved byte-for-byte except where a Blocker fix forces backend edits (and those are auditable via git log)
- Corpus (`docs/Collection-Docs/`, 14 MB, 11 PDFs) MUST be committed — no LFS required (well under the 100 MB GitHub hard limit)

**Scale/Scope**:
- 20 golden Q&A pairs (Spanish-language, grounded in NAG corpus sections)
- 16 known-failing Playwright tests to stabilize (root causes categorized in Phase 1)
- 3–5 fault-injection scenarios (catalog of 5 defined; 3 mandatory)
- Single 4-hour exploratory session (single calendar day, per spec Assumptions)
- 6 user stories / 29 FRs / 11 SCs / 3 Clarifications locked

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Applies to spec-28? | Verdict |
|---|-----------|---------------------|---------|
| I | Local-First Privacy | RAGAS harness calls the local backend only; no outbound calls | PASS |
| II | Three-Layer Agent Architecture | Spec-28 does not modify `ConversationGraph / ResearchGraph / MetaReasoningGraph`. F-path fixes (if any) MUST preserve the three-layer structure | PASS (conditional on F-path discipline) |
| III | Retrieval Pipeline Integrity | RAGAS measures the pipeline; does not alter parent/child chunking, hybrid search, or reranking. A Phase 3 F-fix MAY NOT remove any pipeline component | PASS (conditional on F-path discipline) |
| IV | Observability from Day One | Spec-28 explicitly surfaces observability gaps as bugs (per spec edge case: "Bug found in observability itself"). Constitution is reinforced, not weakened | PASS |
| V | Secure by Design | Bug markdowns and session logs MUST NOT contain secrets (API keys, tokens). Fault-injection commands touch container orchestration, not credentials. Plan mandates secret-scrubbing review at Phase 6 close | PASS |
| VI | NDJSON Streaming Contract | Chat.spec.ts stabilization updates assertions to the current `chunk` event name (spec-24 contract). Schema is validated, not changed | PASS |
| VII | Simplicity by Default | `ragas` is evaluation-only, confined to `tests/quality/`, never ships to users or runs in production. No 5th Docker service. No new RDBMS. No new production abstraction | PASS with justified addition (see Complexity Tracking) |
| VIII | Cross-Platform Compatibility | Playwright suite runs on the existing CI runner matrix (Linux). Tmux session workflow is Linux/macOS; Windows users use WSL per the principle's own pragmatic rule. RAGAS is Python-only, Docker-containerized via existing stack. No platform-specific file ops or shell calls added to product code | PASS |

**Additional project-scope gates**:

- **Testing coverage**: Backend ≥80% (existing pytest-cov enforcement). `tests/quality/` is excluded from coverage counts because it is evaluation, not unit/integration — plan mandates a `.coveragerc` or `pyproject.toml` exclusion for this directory.
- **Test policy**: All Python tests run via external runner (`zsh scripts/run-tests-external.sh`) per CLAUDE.md; plan respects this.
- **CI contract**: Shape X 9-check roster stays 9 checks; only `continue-on-error: false` flip on the existing `frontend-e2e` entry.

**Verdict**: PASS. No constitution violations require justification. One dependency addition (`ragas`) is logged in Complexity Tracking below with rationale.

---

## Project Structure

### Documentation (this feature)

```text
specs/028-e2e-bug-hunt-quality-baseline/
├── plan.md                           # This file (/speckit.plan output)
├── spec.md                           # Authoritative spec (238 lines, locked)
├── research.md                       # Phase 0 output (/speckit.plan)
├── data-model.md                     # Phase 1 output (/speckit.plan)
├── quickstart.md                     # Phase 1 output (/speckit.plan)
├── contracts/
│   ├── session-directory-contract.md # Doc-trail file-layout contract
│   └── fdp-gate-contract.md          # Orchestrator prompt shape + recording format
├── checklists/
│   └── requirements.md               # Requirements quality checklist (existing)
└── tasks.md                          # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/                              # UNTOUCHED in plan phase
├── agent/                            # ConversationGraph, ResearchGraph, MetaReasoningGraph
├── retrieval/                        # HybridSearcher, CrossEncoder reranker
├── storage/                          # SQLite + Qdrant adapters
└── api/chat.py                       # NDJSON streaming endpoint

frontend/
├── src/                              # UNTOUCHED
└── tests/e2e/                        # MODIFIED — Phase 1 stabilization
    ├── chat.spec.ts                  # 4 failing: chunk event + streaming assertions
    ├── collections.spec.ts           # 4 failing: selector drift
    ├── documents.spec.ts             # 3 failing: size-limit / extension / progress
    ├── responsive.spec.ts            # unchanged (appears passing)
    ├── settings.spec.ts              # 4 failing: save toast / persistence
    └── workflow.spec.ts              # 1 failing: strict-mode violation

tests/
├── unit/                             # existing — untouched
├── integration/                      # existing — untouched
├── e2e/                              # existing — untouched
└── quality/                          # NEW — RAGAS harness, evaluation-only
    ├── conftest.py                   # golden_dataset, backend_client, ragas_metrics fixtures
    └── test_ragas_baseline.py        # single test that writes quality-metrics.md

docs/
├── Collection-Docs/                  # COMMITTED in Phase 0 (11 NAG PDFs, 14 MB)
└── E2E/
    └── YYYY-MM-DD-bug-hunt/          # NEW, dated at session start
        ├── session-log.md            # Scribe-owned, live updates
        ├── bugs-found.md             # aggregated at Phase 6
        ├── bugs-raw/
        │   └── BUG-XXX-short-slug.md # one file per bug, all 7 fields mandatory
        ├── scenarios-executed.json   # Test Runner-owned, structured entries
        ├── quality-metrics.md        # RAGAS harness-owned, numeric + hypotheses
        ├── golden-qa.yaml            # 20 pairs, hybrid-authored per FR-019
        ├── traces/                   # Playwright trace.zip bundles per failing/bug replay
        ├── screenshots/              # one per bug with visual evidence
        └── SUMMARY.md                # Orchestrator-owned, Phase 6 close, linked from README

.github/workflows/                    # MODIFIED — Phase 1
├── _ci-core.yml                      # OR ci.yml — flip continue-on-error: false on frontend-e2e
└── (other workflows)                 # fix actions/upload-artifact path for playwright-report

README.md                             # MODIFIED — Phase 6, one-line link to SUMMARY.md
pyproject.toml                        # MODIFIED — add ragas to test-only extras (if present)
                                      # OR requirements*.txt — add ragas
```

**Structure Decision**: The project already uses Option 2 (web application with `backend/` + `frontend/`). Spec-28 adds a new `tests/quality/` peer to existing `tests/unit/`, `tests/integration/`, `tests/e2e/` for RAGAS evaluation, and a new `docs/E2E/YYYY-MM-DD-bug-hunt/` tree for session documentation. No new top-level directories. No changes to `backend/` or `frontend/src/`.

---

## Phase 0: Research

All research tasks resolve to concrete decisions in [research.md](./research.md). Summary of unknowns resolved:

1. **RAGAS API surface** — which metrics, how to pass citation-bearing responses, how to cope with Spanish-language inputs. → research.md §1.
2. **Playwright strict-mode selectors** — the `getByText` strict-mode failure pattern and the migration to `getByRole` / `{exact: true}`. → research.md §2.
3. **`actions/upload-artifact@v7.0.1` path resolution** — the 2026-04-22 "No files were found" void on the `playwright-report/` upload step. → research.md §3.
4. **Tmux 4-pane setup with per-pane Claude models** — how the user spawns the layout and binds each pane's Claude to the intended model + MCP allowlist. → research.md §4.
5. **Fault-injection Docker commands and observed behaviors** — validated against the existing stack's container names and the spec-22 circuit breaker semantics. → research.md §5.

No [NEEDS CLARIFICATION] markers remain. All 3 from the spec (FR-012, FR-019, FR-029) were resolved in the 2026-04-23 clarify session and are locked in spec.md.

---

## Phase 1: Design & Contracts

### Data model

Four schemas, all documented in [data-model.md](./data-model.md):

1. **Golden Q&A pair** (`golden-qa.yaml`) — id, category, question_es, reference_answer_es, source_doc, source_section, notes, authored_by
2. **Bug markdown** (`bugs-raw/BUG-XXX-short-slug.md`) — 7 mandatory fields per FR-022
3. **Scenarios executed log** (`scenarios-executed.json`) — entries with type, id, name, timestamps, command, observed_outcome, pass_fail, remediation, bugs_filed
4. **Quality metrics** (`quality-metrics.md`) — per-category table + overall + hypothesis evaluation

### Contracts

Two contract files under `specs/028-.../contracts/`:

1. **[session-directory-contract.md](./contracts/session-directory-contract.md)** — the authoritative file layout under `docs/E2E/YYYY-MM-DD-bug-hunt/`; pane ownership of each file; cross-pane communication rules.
2. **[fdp-gate-contract.md](./contracts/fdp-gate-contract.md)** — exact orchestrator prompt shape for F/D/P gates; recording format; P-resolution rule.

### Quickstart

[quickstart.md](./quickstart.md) covers: (a) spawning the tmux 4-pane layout with model+MCP bindings, (b) running the stabilized Playwright suite locally, (c) re-running the RAGAS baseline, (d) reproducing a specific bug from `bugs-raw/` cold, (e) the preflight checklist before fault injection.

### Agent context update

Between `<!-- SPECKIT START -->` and `<!-- SPECKIT END -->` markers in `CLAUDE.md`, the plan reference is pointed to `specs/028-e2e-bug-hunt-quality-baseline/plan.md`. Update is applied at Phase 1 close (part of this command's output).

---

## Phases at a Glance (full breakdown in 28-plan.md §"Phase Breakdown")

| Phase | US | FRs | SCs | Owner pane | Exit gate |
|-------|-----|-----|-----|-----------|-----------|
| 0 — Preflight + corpus commit | all | FR-028 | SC-008 | Orchestrator | Corpus committed; stack warm; primer query <30s |
| 1 — Playwright stabilization | US1 | FR-001/002/004 | SC-011 | Test Runner | All 16 failures resolved; CI dry-run green |
| 2 — Optional flow expansion | US1 | FR-001 | SC-001 | Test Runner | Green or skip |
| 3 — Exploratory 4h | US2/US6 | FR-006–009, 023–025 | SC-002/004/005 | Orchestrator + all panes | 4h clock; every Blocker has F/D/P |
| 4 — Fault injection | US3 | FR-010–012 | SC-007 | Test Runner + Log Watcher | ≥3 entries in scenarios-executed.json |
| 5 — RAGAS baseline | US4 | FR-013–018 | SC-003/009 | Test Runner | quality-metrics.md with per-category + H1–H4 |
| 6 — Wrap-up | US5 | FR-020–022, 025 | SC-006/008/010 | Orchestrator | SUMMARY.md linked; Makefile diff empty |

### Tmux pane roster

| Pane | Role | Model | Reads | Writes | Primary MCPs |
|------|------|-------|-------|--------|--------------|
| 1 | Orchestrator | Opus | `28-implement.md`, `spec.md`, `plan.md` | F/D/P decisions, phase transitions, `SUMMARY.md` | sequential-thinking, engram, serena, gitnexus |
| 2 | Test Runner | Sonnet | `frontend/tests/e2e/**`, `tests/quality/**`, orchestrator instructions | Playwright traces, pytest output, fault verdicts, `scenarios-executed.json` | playwright, chrome-devtools, docker, Bash |
| 3 | Scribe | Sonnet | orchestrator instructions, bug discoveries from panes 2/4 | `session-log.md`, `bugs-raw/*.md`, `bugs-found.md` | rust-mcp-filesystem, gitnexus, serena |
| 4 | Log Watcher | Sonnet | `docker compose logs -f`, structlog JSON | regex-extracted incidents, back-channel to Scribe | docker, rust-mcp-filesystem, browser-tools |

Ad-hoc, not pane-bound: sonarqube (end-of-session, optional), mcp-chart (severity treemap for SUMMARY.md), context7 (library docs lookup on unfamiliar stack traces).

**Cross-pane communication**: (a) user relays, or (b) shared file (`session-log.md` canonical). No pane writes another pane's files.

---

## Files the plan expects to modify

### NEW (created in this spec)

- `docs/E2E/YYYY-MM-DD-bug-hunt/` (entire tree, dated at session start)
- `docs/Collection-Docs/` (committed in Phase 0 from currently-untracked state)
- `tests/quality/`, `tests/quality/conftest.py`, `tests/quality/test_ragas_baseline.py`
- `specs/028-e2e-bug-hunt-quality-baseline/` supporting artifacts (this plan + research + data-model + contracts + quickstart)

### MODIFIED

- `frontend/tests/e2e/*.spec.ts` (the 6 existing files — Phase 1 stabilization edits)
- `.github/workflows/_ci-core.yml` OR `.github/workflows/ci.yml` — Phase 1 sub-fix: flip `continue-on-error: false` on the `frontend-e2e` job AND repair the `actions/upload-artifact@v7.0.1` path to the Playwright reporter output
- `README.md` (one-line link to `SUMMARY.md`, Phase 6)
- `pyproject.toml` OR the equivalent Python deps file — add `ragas` under a test-only extras group (NOT the default install)
- `.coveragerc` OR `pyproject.toml` `[tool.coverage.run]` — exclude `tests/quality/` from line-coverage accounting
- `CLAUDE.md` SPECKIT markers (part of this plan phase)

### NEVER TOUCH

- `Makefile` (SACRED per FR-026, SC-010, and prior specs)
- `embedinator.sh`, `embedinator.ps1` (launchers — SACRED per spec-19)
- `backend/**` unless a Phase 3 F-path Blocker genuinely requires it (auditable via `git log backend/`)
- `ingestion-worker/**` (out of scope)
- Any file owned by an in-flight Dependabot PR (`gh pr list --label dependencies` before editing)

---

## Build verification protocol

Per CLAUDE.md testing policy: no pytest runs inside Claude Code. Verification uses:

1. **Playwright CI dry-run**: push the feature branch after Phase 1 stabilization and observe the `frontend-e2e` job turn green on the Shape X 9-check roster. Trace artifact downloadable from the CI run.
2. **External test runner for RAGAS**: `zsh scripts/run-tests-external.sh -n spec28-ragas tests/quality/test_ragas_baseline.py` → status + summary + log under `Docs/Tests/spec28-ragas.{status,summary,log}`.
3. **Docker stack health**: before any phase other than 0, verify `docker compose ps` shows `qdrant`, `ollama`, `backend`, `frontend` all `Up`.
4. **Preflight checklist**: defined in [quickstart.md](./quickstart.md); must pass before Phase 4 fault injection.
5. **SACRED file diff check**: before committing each phase, `git diff develop -- Makefile embedinator.sh embedinator.ps1` MUST be empty.

---

## SC Evaluation Matrix

| SC | Command / Artifact that produces the evidence |
|----|-----------------------------------------------|
| SC-001 | Latest CI run on `develop` HEAD shows `frontend-e2e` green; Playwright trace artifact downloadable from the run. |
| SC-002 | `ls docs/E2E/YYYY-MM-DD-bug-hunt/bugs-raw/ \| wc -l` > 0 AND `scripts/validate-bug-records.sh` (new, written by Scribe during Phase 3) reports zero files missing any of the 7 mandatory fields. |
| SC-003 | `cat docs/E2E/.../quality-metrics.md` — numeric table covering all 5 categories + overall. |
| SC-004 | Same validation script as SC-002: every bug record has severity + layer + repro + root-cause populated. |
| SC-005 | `grep -E "F/D/P decision:" bugs-raw/*.md \| grep Blocker` — every Blocker has a decision; no `pending`. |
| SC-006 | `grep -q "docs/E2E/.*/SUMMARY.md" README.md` AND `grep -q "treemap" SUMMARY.md`. |
| SC-007 | `jq '.entries \| map(select(.type == "fault-injection")) \| length' scenarios-executed.json` ≥ 3, and every entry has `pass_fail` + `remediation`. |
| SC-008 | `git log --oneline -- docs/Collection-Docs/` shows a commit; `golden-qa.yaml` has pairs tagged for all 5 categories. |
| SC-009 | `grep -E "H[1-4] —" quality-metrics.md \| grep -E "(CONFIRMED\|REFUTED)"` returns 4 hits. |
| SC-010 | `git diff develop -- Makefile` is empty. |
| SC-011 | No `test.skip` or `quarantined` markers in `frontend/tests/e2e/**` without a corresponding entry in `bugs-raw/`. |

---

## Dependency Graph

```text
                              ┌─────────────────────────┐
                              │ Phase 0: Preflight +    │
                              │         Corpus commit   │
                              └───────────┬─────────────┘
                                          │
                              ┌───────────┴─────────────┐
                              │ Phase 1: Stabilize 16   │
                              │         + CI flip       │
                              └───────────┬─────────────┘
                                          │
                              ┌───────────┴─────────────┐
                              │ Phase 2: (optional)     │
                              │         Flow expansion  │
                              └───────────┬─────────────┘
                                          │
                              ┌───────────┴─────────────┐
                              │ Phase 3: Exploratory    │
                              │         (4h, F/D/P)     │
                              └───────────┬─────────────┘
                                          │
                              ┌───────────┴─────────────┐
                              │ Phase 4: Fault injection│
                              │         (≥3 scenarios)  │
                              └───────────┬─────────────┘
                                          │
                              ┌───────────┴─────────────┐
                              │ Phase 5: RAGAS baseline │
                              │         (20-pair)       │
                              └───────────┬─────────────┘
                                          │
                              ┌───────────┴─────────────┐
                              │ Phase 6: Wrap-up +      │
                              │         SUMMARY + PR    │
                              └─────────────────────────┘
```

Phases 1–2 may overlap. Phases 3–5 are strictly sequential (shared corpus + stack state). Phase 6 consumes all prior artifacts.

---

## Complexity Tracking

| Addition | Why needed | Simpler alternative rejected because |
|----------|-----------|-------------------------------------|
| `ragas` Python dependency (test-only extras) | FR-016 requires numeric retrieval precision / answer relevance / citation faithfulness / context recall. Hand-rolled sentence-transformer similarity would reimplement measurement patterns that `ragas` has already validated. | Hand-rolled metrics were considered in spec Assumptions; rejected because they introduce more custom code than a pinned library dependency, and the library is evaluation-only (never runs in production; never in the user-facing Docker image). |
| `tests/quality/` new test directory | Separate from `tests/unit/`, `tests/integration/`, `tests/e2e/` because RAGAS requires a live backend + real corpus + LLM calls. Mixing it into `integration/` would skew the 80% coverage target and make the pre-existing baseline ambiguous. | Placing it under `integration/` rejected because it is qualitative evaluation, not correctness testing — different cadence, different failure semantics. |
| `docs/E2E/YYYY-MM-DD-bug-hunt/` dated directory | FR-020 mandates a structured trail with 7 sub-artifacts. A single flat file would not support machine-readable `scenarios-executed.json` alongside human prose `session-log.md` with per-bug reproduction artifacts. | Flat-file alternative rejected because the bug artifacts (trace.zip, screenshots) cannot live in a single markdown. |

No constitution violations. All added complexity is confined to evaluation tooling and session documentation.

---

## Re-evaluated Constitution Check (post-design)

All 8 principles re-checked against the Phase 1 design: no changes to verdicts. The addition of `tests/quality/` + `ragas` is the only Complexity Tracking entry, and it does not violate Principle VII (Simplicity by Default) because it is evaluation-only, confined to the test tree, and not shipped to users.

**Gate: PASS.** Ready for `/speckit.tasks`.

---

## Post-plan actions

- `CLAUDE.md` SPECKIT marker updated to reference this plan file.
- Feature pointer persisted at `.specify/feature.json` → `specs/028-e2e-bug-hunt-quality-baseline`.
- Clarifications section in spec.md remains authoritative for FR-012/019/029.

Next pipeline step: `/speckit.tasks` consuming `28-tasks.md` (to be written).
