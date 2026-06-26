---

description: "Task list for spec-28: E2E Bug Hunt & Quality Baseline (Pre-v1.0.0)"
---

# Tasks: E2E Bug Hunt & Quality Baseline (Pre-v1.0.0)

**Input**: Design documents from `/specs/028-e2e-bug-hunt-quality-baseline/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md
**Branch**: `028-e2e-bug-hunt-quality-baseline` (cut from `develop@691bbad`)

**Tests**: NOT requested as TDD. The RAGAS harness is itself an evaluation test (Phase 6), and Playwright specs are the regression tests being stabilized — both live inside user-story phases, not as pre-written failing tests.

**Organization**: Tasks are grouped by user story. User Story 6 (F/D/P gate protocol) is woven into US2 and US3 (where the gate triggers); its validation lives in Phase 7 (wrap-up).

**Session nature**: This spec runs as a live 4-hour human-in-the-loop tmux session. Tasks are written to be executed in sequence within that session by the 4-pane roster (Orchestrator / Test Runner / Scribe / Log Watcher). Ownership of each task is marked inline with the pane abbreviation (**O** / **TR** / **S** / **LW**).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no cross-dependencies)
- **[Story]**: `[US1]`–`[US6]` maps to user stories in `spec.md`
- **[Pane]**: `[O]` Orchestrator, `[TR]` Test Runner, `[S]` Scribe, `[LW]` Log Watcher
- File paths are absolute-from-repo-root

## Path Conventions

- **Web app** with `backend/` + `frontend/` (existing)
- **New**: `tests/quality/` (RAGAS), `docs/E2E/YYYY-MM-DD-bug-hunt/` (session)
- **SACRED (never touched)**: `Makefile`, `embedinator.sh`, `embedinator.ps1`, `backend/**` (except Phase 3 F-path fixes), `ingestion-worker/**`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Repo-level scaffolding for the evaluation harness and session directory.

- [ ] T001 [O] Verify prerequisites via `.specify/scripts/bash/check-prerequisites.sh --json` — confirm branch `028-e2e-bug-hunt-quality-baseline`, FEATURE_DIR resolves, all design docs present
- [ ] T002 [P] [TR] Add `ragas` Python dependency under test-only extras in `pyproject.toml` (new group `[project.optional-dependencies.quality]` or equivalent) — do NOT add to the default install set
- [ ] T003 [P] [TR] Add `tests/quality/` to the coverage omit list in `pyproject.toml` `[tool.coverage.run]` so the 80% backend coverage threshold remains honest after the evaluation harness lands
- [ ] T004 [P] [TR] Create `tests/quality/` directory with empty `__init__.py` and placeholder `conftest.py` (fixtures added in Phase 6)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Preflight validation, corpus commit, and gate tooling needed before ANY user story phase runs.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T005 [O] Run the Phase 0 preflight checklist from `quickstart.md` — verify `$TMUX` env var is set, `docker compose ps` shows qdrant+ollama+backend+frontend all `Up`, `git rev-parse --abbrev-ref HEAD` returns `028-e2e-bug-hunt-quality-baseline`
- [ ] T006 [O] Commit `docs/Collection-Docs/` (11 NAG PDFs, 14 MB total, currently untracked) to the feature branch — single commit with message `chore(corpus): commit Argentine gas regulatory corpus for spec-28 fixtures` (FR-028, SC-008)
- [ ] T007 [O] Create dated session directory tree at `docs/E2E/$(date -u +%F)-bug-hunt/` with subdirectories `bugs-raw/`, `traces/`, `screenshots/`, `logs/` per `contracts/session-directory-contract.md`
- [ ] T008 [O] Seed the corpus into Qdrant + SQLite via the standard ingestion flow (use the frontend upload UI or the backend ingestion API); verify a warm primer query (`curl -X POST http://localhost:8000/api/chat -d '{"message": "NAG-200 diámetro mínimo"}'`) returns relevant results in under 30 seconds (FR-028)
- [ ] T009 [P] [TR] Create `scripts/validate-bug-records.sh` — shell script that walks `docs/E2E/*/bugs-raw/*.md`, asserts each file has all 7 mandatory fields (severity, layer, discovered, steps to reproduce, expected, actual, root-cause hypothesis) plus F/D/P decision for `Severity: Blocker` — exits non-zero on violation (used by SC-002, SC-004, SC-005)
- [ ] T010 [S] Initialize `session-log.md` in the dated session directory with the Phase 0 entry: timestamp, preflight results, corpus commit SHA, primer query latency — per the template in `contracts/session-directory-contract.md`

**Checkpoint**: Foundation ready — the corpus is committed, the session directory exists, the validation script is in place, and the stack is warm. User story phases can begin.

---

## Phase 3: User Story 1 — Scripted E2E regression suite (Priority: P1) 🎯 MVP

**Goal**: Stabilize the 16 known-failing Playwright tests so the scripted E2E suite runs green in CI on every PR, with `continue-on-error: false` enforcing the gate.

**Independent Test**: Push the feature branch to GitHub and observe the `frontend-e2e` job turn green on the Shape X 9-check aggregate roster; a trivial PR that breaks a core flow (e.g., removes a button click handler) MUST fail the suite and block merge.

### Implementation for User Story 1

- [ ] T011 [US1] [TR] Run the existing Playwright suite (`cd frontend && npm run e2e -- --reporter=line`) and categorize the 16 failures by root cause — write the categorization to `session-log.md` under a new `## Phase 1: Stabilization` header. Expected categories per `research.md` §2: strict-mode selector drift, chat streaming assertion mismatch, upload-artifact path void, settings/collections/documents selector drift
- [ ] T012 [P] [US1] [TR] Fix `frontend/tests/e2e/chat.spec.ts` — migrate the 4 streaming assertions to use the current `chunk` NDJSON event name (spec-24 contract); preserve the original test intent, update the locator strategy where the card-title strict-mode issue applies
- [ ] T013 [P] [US1] [TR] Fix `frontend/tests/e2e/workflow.spec.ts` line 19 strict-mode violation — migrate `getByText("e2e-workflow-*")` to `getByRole("heading", {name: /.../ , exact: true})` per `research.md` §2 migration guide
- [ ] T014 [P] [US1] [TR] Fix `frontend/tests/e2e/collections.spec.ts` — 4 failures driven by the same selector-drift pattern (`getByText` matching `sr-only` accessibility spans added in spec-22); migrate to role-based selectors
- [ ] T015 [P] [US1] [TR] Fix `frontend/tests/e2e/documents.spec.ts` — 3 failures on size-limit / extension / upload-progress assertions; validate against the current UI, migrate selectors
- [ ] T016 [P] [US1] [TR] Fix `frontend/tests/e2e/settings.spec.ts` — 4 failures on save-toast / persistence / key-PUT / key-DELETE; migrate selectors and assertions
- [ ] T017 [US1] [TR] Fix the `actions/upload-artifact@v7.0.1` path void in `.github/workflows/_ci-core.yml` (or whichever workflow runs `frontend-e2e`) — read `frontend/playwright.config.ts` reporter config, align with the job's working directory, update the upload step's `path:` key, and set `if: always()` so traces upload on failure per `research.md` §3
- [ ] T018 [US1] [TR] Run the full Playwright suite locally; verify all 16 previously-failing tests now pass AND no previously-passing test regresses. Record result in `session-log.md`. If a test cannot be stabilized, file a bug in `bugs-raw/` and mark it `quarantined` with an inline comment linking to the bug (SC-011)
- [ ] T019 [US1] [TR] Flip `continue-on-error: false` on the `frontend-e2e` job in `.github/workflows/_ci-core.yml` (single-line edit after all 16 tests are green — NOT before); commit with message `ci(e2e): make frontend-e2e failures gate merges (spec-28 US1)`
- [ ] T020 [US1] [O] Push the feature branch, open a draft PR, and observe the Shape X 9-check roster on the PR. `frontend-e2e` MUST turn green. If green, record CI run URL in `session-log.md` as SC-001 evidence; if red, file a bug and return to the stabilization loop (no Phase 2-onward work until green)

**Checkpoint**: MVP complete. The scripted suite is now a regression gate. If time remains before the 4-hour exploratory budget begins, OPTIONAL Phase-2-of-plan flow expansion may be attempted (see `plan.md` Phase 2); otherwise skip to Phase 4.

---

## Phase 4: User Story 2 — Charter-driven exploratory session (Priority: P1)

**Goal**: Execute one 4-hour charter-driven exploratory session against the seeded local stack, logging every finding live with all 7 mandatory fields and triggering the F/D/P gate on every Blocker (US6 woven in).

**Independent Test**: After the session closes, `scripts/validate-bug-records.sh docs/E2E/$(date -u +%F)-bug-hunt/bugs-raw/` exits zero (every bug has all 7 fields); reading `session-log.md` end-to-end shows every Blocker has a matching `## HH:MM UTC — F/D/P gate: BUG-XXX` entry.

### Implementation for User Story 2

- [ ] T021 [US2] [O] Define the 4-hour exploratory charter list — write 4–6 charters to `session-log.md` under `## Phase 3: Exploratory charters`. Example charters: "probe citation rendering on cross-referenced NAG articles", "stress Spanish accent/punctuation handling in chat input", "navigate between pages mid-stream", "force collection-switching during streaming", "stress session continuity across follow-up turns"
- [ ] T022 [US2] [O] Start the session clock (log the start timestamp in `session-log.md`) and confirm all 4 panes are alive; announce the first charter to Panes 2/3/4 via the shared file
- [ ] T023 [US2] [TR, S, LW] Execute each charter in sequence. Test Runner drives the app + Playwright/chrome-devtools; Scribe logs findings live to `session-log.md` and `bugs-raw/BUG-XXX-*.md` (Scribe OWNS those files per session-directory-contract.md); Log Watcher tails `docker compose logs -f` and surfaces structlog anomalies to Scribe via session-log.md. Budget: ~45 minutes per charter, 4–6 charters total
- [ ] T024 [US2] [US6] [O] At every Blocker-severity bug filed by Scribe, open the F/D/P gate per `contracts/fdp-gate-contract.md` — emit the prompt verbatim in Pane 1, wait for user response, record decision in the bug markdown AND in `session-log.md` under a `## HH:MM UTC — F/D/P gate: BUG-XXX` header. For P decisions, convene the 15-minute investigation and re-prompt F/D on timeout (FR-023, FR-024, SC-005)
- [ ] T025 [US2] [O] At the 4-hour mark, close intake (Scribe stops logging new findings from new charters). Spend remaining time ensuring every open Blocker has a decision, every bug has 7 fields, and any in-flight P decision resolves to F or D
- [ ] T026 [US2] [TR] Run `scripts/validate-bug-records.sh docs/E2E/$(date -u +%F)-bug-hunt/bugs-raw/` — exit code 0 required. If non-zero, fix the bug records inline and re-run until green (SC-002, SC-004)

**Checkpoint**: Exploratory deliverable complete. Bug inventory + F/D/P decisions are in place. Stack state may have changed from in-session F-path fixes — verify `docker compose ps` still healthy before Phase 5.

---

## Phase 5: User Story 3 — Targeted fault injection (Priority: P1)

**Goal**: Execute between 3 and 5 fault-injection scenarios against the normal local stack with a preflight checklist, recording each outcome to `scenarios-executed.json` and session-log.md.

**Independent Test**: `jq '.entries | map(select(.type == "fault-injection")) | length' scenarios-executed.json` returns ≥ 3; every such entry has `pass_fail` and `remediation` populated.

### Implementation for User Story 3

- [ ] T027 [US3] [O] Run the Phase 4 preflight checklist from `quickstart.md` — all 5 items checked. Verify container names via `docker compose ps --format json | jq -r '.[] | .Name'` match the catalog (`embedinator-ollama-1`, `-qdrant-1`, `-backend-1`, `-frontend-1`) per `research.md` §5
- [ ] T028 [US3] [TR] [LW] [S] Execute FI-01 (Ollama killed mid-stream): TR starts a chat stream in the UI; mid-stream, runs `docker kill embedinator-ollama-1`. LW tails backend logs. S records observed user-facing outcome + pass/fail + remediation in `session-log.md` and appends an entry to `scenarios-executed.json`. TR restarts the container (`docker compose start ollama`) before proceeding
- [ ] T029 [US3] [TR] [LW] [S] Execute FI-02 (Qdrant down at query time): same pane orchestration. `docker stop embedinator-qdrant-1`; submit a query; observe. Expected: clear "retrieval unavailable" UI state, no silent empty result. Restart via `docker compose start qdrant`
- [ ] T030 [US3] [TR] [LW] [S] Execute FI-03 (Backend crash mid-stream): `docker kill embedinator-backend-1` during an active stream. Expected: stream terminates cleanly, UI surfaces disconnect, reconnect works after `docker compose start backend`
- [ ] T031 [US3] [TR] [LW] [S] If FI-01/02/03 completed in under 45 minutes AND the user wants to extend: execute FI-04 (Docker network partition via `docker network disconnect embedinator_default embedinator-ollama-1` then reconnect) and/or FI-05 (LLM context-length exceeded via oversized input prompt). Opportunistic only per `plan.md`; skippable
- [ ] T032 [US3] [TR] Validate `scenarios-executed.json` with `jq`: exit code 0 on a valid parse, `.entries | length >= 3`, each fault-injection entry has non-null `pass_fail` and `remediation`. For any Blocker surfaced by fault injection, the F/D/P gate triggers (T024 protocol applies), noting that in-session F-path fixes during fault injection are discouraged per `contracts/fdp-gate-contract.md`

**Checkpoint**: Fault-injection deliverable complete. Stack should be fully restored (all containers `Up`). If not, restart the full stack via `docker compose restart` before Phase 6.

---

## Phase 6: User Story 4 — RAGAS quality baseline (Priority: P1)

**Goal**: Curate a 20-pair Spanish-language golden Q&A dataset (hybrid authorship per FR-019), run RAGAS scoring for four metrics across five question categories, publish `quality-metrics.md` with H1–H4 hypothesis evaluations.

**Independent Test**: `quality-metrics.md` exists at `docs/E2E/$(date -u +%F)-bug-hunt/quality-metrics.md`, contains the per-category table + overall row, and has explicit CONFIRMED/REFUTED verdicts for each of H1–H4.

### Implementation for User Story 4

- [ ] T033 [US4] [O] User hand-authors the 3 highest-bias Q&A pairs (1 ambiguous, 2 out-of-scope) per FR-019 locked clarification — write directly into `docs/E2E/*/golden-qa.yaml` with `authored_by: user`. The ambiguous pair tests disambiguation behavior; the two out-of-scope pairs test graceful decline (H4). Schema per `data-model.md` §1
- [ ] T034 [P] [US4] [TR] Scaffold 17 candidate Q&A pairs from the NAG corpus — 10 factoid, 4 analytical, 3 follow-up. For each pair, cite `source_doc` + `source_section`. Use grep/manual extraction OR LLM-assisted draft (plan open question #2 — document the choice in `quality-metrics.md` Reproduction section). Mark `authored_by: scaffold-reviewed`
- [ ] T035 [US4] [O] User reviews the 17 scaffolded pairs in Pane 1, edits or accepts each. Only after user approval do pairs land in the final `golden-qa.yaml`. Final file MUST have exactly 20 pairs with the category distribution locked by FR-014 (10/4/3/2/1)
- [ ] T036 [P] [US4] [TR] Implement `tests/quality/conftest.py` — pytest fixtures for `golden_dataset` (loads `golden-qa.yaml`), `backend_client` (httpx AsyncClient against `localhost:8000`), `ragas_metrics` (four metrics from `ragas.metrics`: context_precision, context_recall, answer_relevancy, faithfulness), `session_id` (current date). See the sketch in `plan.md` §"RAGAS Harness Design"
- [ ] T037 [P] [US4] [TR] Implement `tests/quality/test_ragas_baseline.py` — single async test that: (a) issues each question in golden_dataset against backend_client, (b) collects answer + retrieved contexts + citations, (c) calls `ragas.evaluate()` with the metric list, (d) writes per-category + overall scores to `quality-metrics.md` per `data-model.md` §4 schema. Judge LLM choice via `RAGAS_JUDGE` env var (default `local`); pass `--judge=<value>` through if set
- [ ] T038 [US4] [TR] Run the RAGAS baseline via the external runner: `zsh scripts/run-tests-external.sh -n spec28-ragas tests/quality/test_ragas_baseline.py`. Poll `cat Docs/Tests/spec28-ragas.status` until `PASSED` or `FAILED`. A `FAILED` status indicates a harness bug (file write failure) — fix and re-run
- [ ] T039 [US4] [TR] Open the generated `quality-metrics.md`, add the "Hypotheses" section — explicitly mark H1 (Spanish-on-English-embedder degradation), H2 (PDF table extraction edges), H3 (citation cross-reference grounding), H4 (out-of-scope graceful decline) as CONFIRMED or REFUTED with one-line evidence each (FR-018, SC-009)
- [ ] T040 [US4] [TR] Validate `quality-metrics.md`: all 5 category rows present with row counts (10/4/3/2/1), overall row present, 4 hypotheses each stamped. Use `grep -E "H[1-4] —" quality-metrics.md | grep -E "(CONFIRMED|REFUTED)" | wc -l` — returns 4 (SC-003, SC-009)

**Checkpoint**: RAGAS deliverable complete. Numbers published. Baseline is informational (not a ship gate per spec Assumptions + FR-018).

---

## Phase 7: User Story 5 + User Story 6 — Structured bug log & gate validation (Priority: P2)

**Goal**: Aggregate the session's artifacts into the canonical bug list and `SUMMARY.md`, link from the top-level README, and batch-promote Blocker-severity bugs to GitHub issues. Validate US6 acceptance: every Blocker has a recorded F/D/P decision and a matching session-log.md gate entry.

**Independent Test**: `SUMMARY.md` exists, is linked from `README.md`, contains the severity treemap; `grep -E "F/D/P decision: (F|D|P→F|P→D)" bugs-raw/BUG-*-*.md | wc -l` equals the Blocker count; every Blocker is either a GitHub issue or has an explicit defer rationale in the bug file (FR-025, SC-005, SC-006).

### Implementation for User Story 5 + US6 wrap-up

- [ ] T041 [US5] [S] Aggregate `bugs-raw/*.md` into a single `bugs-found.md` in the session directory — one table row per bug with columns: BUG-ID, Title, Severity, Layer, F/D/P decision, Discovery channel, Link. Sort by Severity descending then BUG-ID ascending
- [ ] T042 [US5] [O] Render the severity treemap via `mcp-chart` (generate_treemap_chart) using the bug data — embed the resulting PNG/SVG into `SUMMARY.md`. If `mcp-chart` fails, fall back to a Markdown severity table and file a Cosmetic bug against the chart MCP (FR-021)
- [ ] T043 [US5] [O] Write `SUMMARY.md` per `contracts/session-directory-contract.md` schema — severity counts, F-vs-D breakdown, Blocker promotion list, quality baseline summary, fault-injection verdicts, links to all artifacts. One-shot write by Orchestrator (pane 1 owns this file)
- [ ] T044 [US5] [O] Add a one-line link to `SUMMARY.md` at the top-level `README.md` (under a "Recent work" or "Quality" heading). Path form: `docs/E2E/<YYYY-MM-DD>-bug-hunt/SUMMARY.md` relative to repo root (FR-021, SC-006)
- [ ] T045 [US5] [O] Batch-promote Blocker-severity bugs with `D` (defer) decisions to GitHub issues via `gh issue create --title "<bug title>" --body "$(cat <bug file>)" --label "bug,severity:blocker,from:spec-28" --milestone v1.1`. Blockers with `F` decisions are recorded as "Fixed in-session (commit <sha>)" in SUMMARY.md — no new issue. Labels + milestone per plan open question #3 default (FR-025)
- [ ] T046 [US6] [O] Validate SC-005 — for every `BUG-*.md` with `Severity: Blocker`, assert (a) `F/D/P decision:` field is populated with F/D/P→F/P→D format, (b) a matching `## HH:MM UTC — F/D/P gate: <BUG-ID>` entry exists in `session-log.md`. Use the validation snippet from `contracts/fdp-gate-contract.md` §Validation

**Checkpoint**: All deliverables published and linked. Session directory is self-contained and reviewer-navigable.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final validation + PR readiness.

- [ ] T047 [O] Verify SACRED files unchanged — `git diff develop -- Makefile embedinator.sh embedinator.ps1` MUST be empty. If not empty, identify the offending commit and revert the SACRED-file change (SC-010)
- [ ] T048 [P] [O] Optional — run sonarqube scan in diff-only mode against the 028 branch's diff vs develop (plan open question #4 default). If sonar surfaces critical findings, file as bugs; otherwise log "clean" in session-log.md
- [ ] T049 [P] [TR] Run the full SC evaluation matrix from `plan.md` §"SC Evaluation Matrix" — one command per SC. Record pass/fail for each in `SUMMARY.md` under a new `## Success Criteria` section. All 11 SCs SHOULD pass; any failure requires either a remediation task or an explicit acknowledgment
- [ ] T050 [O] Final PR preparation — stage all session artifacts (`docs/E2E/<dir>/`, `docs/Collection-Docs/`, `tests/quality/`, frontend test edits, CI workflow edit, README edit, pyproject.toml edits), commit as one or more logical commits (separate: stabilization, corpus, RAGAS harness, session artifacts), push, open PR with title `spec-28: E2E bug hunt & quality baseline` and body linking to `SUMMARY.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — starts immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **Phase 3 (US1)**: Depends on Foundational. Playwright stabilization can start immediately after the session directory exists and corpus is committed
- **Phase 4 (US2 + US6)**: Depends on Phase 3 completion. Exploratory session assumes a stable suite as a baseline reference
- **Phase 5 (US3)**: Depends on Phase 4 completion. Shares stack state; must run after exploratory to avoid corrupting charter findings with destructive faults
- **Phase 6 (US4)**: Depends on Phase 5 completion. Shares stack state; RAGAS needs the stack warm and unperturbed
- **Phase 7 (US5 + US6)**: Depends on Phases 4, 5, 6 all complete — consumes artifacts from each
- **Phase 8 (Polish)**: Depends on Phase 7

**Strict-sequential chain**: Phases 4 → 5 → 6 cannot overlap because they share corpus + stack state.
**Parallelizable within-phase**: Setup tasks T002/T003/T004, most of US1 Phase 3 (T012–T016 different files), US4 Phase 6 T036/T037 (different files).

### User Story Dependencies

- **US1 (P1)**: Independent — can start first after Foundational. MVP.
- **US2 (P1) + US6 (P2)**: Depends on US1 (stabilized suite as reference). US6 is woven into US2 execution, validated in Phase 7.
- **US3 (P1)**: Depends on US2 (shares stack state, but US2 exploratory informs which fault scenarios matter).
- **US4 (P1)**: Depends on US3 (stack state must be restored after fault injection before RAGAS runs).
- **US5 (P2)**: Depends on US2, US3, US4 — aggregates their outputs.

### Within Each User Story

- Setup tasks first (if any story-specific setup exists)
- Independent file edits marked `[P]` can run in parallel (different .spec.ts files, different Python modules)
- Validation tasks last — gate the story's checkpoint

### Parallel Opportunities

- Phase 1: T002, T003, T004 all touch different files
- Phase 3: T012 (chat.spec.ts), T013 (workflow.spec.ts), T014 (collections.spec.ts), T015 (documents.spec.ts), T016 (settings.spec.ts) are independent files
- Phase 6: T034 (scaffold pairs, YAML edits) parallel with T036 (conftest.py) and T037 (test file)
- Phase 8: T048 (sonarqube), T049 (SC matrix) independent

### Cross-pane parallelism within the session

- During Phase 4 exploration: TR drives the app, S logs findings, LW watches logs — all three panes active simultaneously. O blocks on F/D/P gate only.
- During Phase 5 fault injection: same three-pane rhythm.
- Phase 7 wrap-up is O-dominant with S assisting.

---

## Parallel Example: User Story 1 (Playwright stabilization)

```bash
# All 5 spec.ts files are independent — launch fixes in parallel (different files, no cross-dependencies).
# In the Test Runner pane:
Task T012: "Fix chat.spec.ts streaming assertions"
Task T013: "Fix workflow.spec.ts strict-mode violation"
Task T014: "Fix collections.spec.ts selector drift"
Task T015: "Fix documents.spec.ts size/extension/progress assertions"
Task T016: "Fix settings.spec.ts save-toast/persistence"

# T017 (CI upload path) is also parallelizable with the above — it's in .github/workflows/
# T018 (full suite run) is serial — depends on T012–T017 all complete
# T019 (continue-on-error flip) is serial — depends on T018 passing
# T020 (CI dry-run green) is serial — depends on T019 pushed
```

## Parallel Example: User Story 4 (RAGAS harness scaffolding)

```bash
# While user authors the 3 hand-authored pairs in Pane 1 (T033):
# In the Test Runner pane, run in parallel:
Task T034: "Scaffold 17 candidate pairs from NAG corpus"
Task T036: "Implement tests/quality/conftest.py fixtures"
Task T037: "Implement tests/quality/test_ragas_baseline.py"

# T035 (user review of scaffolded pairs) blocks on both T033 and T034.
# T038 (run RAGAS) blocks on T035, T036, T037 all complete.
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup)
2. Complete Phase 2 (Foundational) — corpus committed, session dir ready, validation script in place
3. Complete Phase 3 (US1) — 16 tests green, CI gating on
4. **STOP and VALIDATE**: A trivial regression PR on `develop` must fail the `frontend-e2e` job
5. Even if the session stops here, US1 alone is a shippable improvement — the regression gate is live

### Incremental Delivery

1. Phase 1 + 2 → Foundation
2. Phase 3 (US1) → Regression gate live → Deploy/demo
3. Phase 4 (US2 + US6) → Exploratory bug inventory → Deliverable: `bugs-raw/` populated
4. Phase 5 (US3) → Fault-injection verdicts → Deliverable: `scenarios-executed.json`
5. Phase 6 (US4) → Quality baseline → Deliverable: `quality-metrics.md` with numbers
6. Phase 7 (US5 + US6) → Final `SUMMARY.md` → Deliverable: single-link-from-README portfolio artifact
7. Phase 8 → PR ready

### Solo-Developer Strategy (this project)

- The 4-hour block covers Phases 3–6 in a single focused session
- Phases 1, 2, 7, 8 bookend the session (Phase 1+2 pre-session setup; Phase 7+8 same-day wrap-up)
- No parallel-team strategy applies — the tmux 4-pane model is the parallelism here (different roles, same person driving)

---

## Notes

- `[P]` tasks = different files, no cross-task dependencies
- `[Story]` label maps task → user story for traceability
- `[Pane]` label assigns execution responsibility inside the tmux session
- Tests are NOT pre-written failing tests — the "tests" in this spec are the RAGAS evaluation harness (Phase 6) and the Playwright suite being stabilized (Phase 3); both live in their user-story phases
- Commit after each phase's checkpoint (one commit per phase is the default rhythm)
- Session-log.md is append-only during the session; it is the canonical cross-pane communication channel
- Every Blocker triggers the F/D/P gate — no exceptions. Silent triage is a process violation (see `contracts/fdp-gate-contract.md` Forbidden variants)
- Avoid: SACRED-file edits (Makefile, launchers), backend/** edits unless forced by an F-path decision on a Blocker
