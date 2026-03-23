# Guided Hybrid E2E Loop (Human-in-the-Loop)

This guidethrough is the required entrypoint for live frontend E2E validation during the `guided-hybrid-e2e-loop` change.

## Startup Gate (Mandatory)

Do not start live E2E yet.

Before any live E2E action:
1. User reads this file end-to-end.
2. User explicitly acknowledges readiness in the session (for example: `ACK guided-hybrid-e2e-loop`).
3. Assistant records the acknowledgment in the checkpoint ledger.

If acknowledgment is missing, the run is blocked.

## Purpose

- Run live E2E in a controlled loop where human verification and machine evidence are both mandatory.
- Stop quickly on major runtime/functionality issues to avoid noisy or misleading audit results.
- Resume from explicit checkpoints after each fix cycle, with updated guide + logs.

## Rules of Engagement

- User is the UI truth source; assistant is the flow coordinator and evidence/triage lead.
- Every checkpoint must capture both automation evidence and human observation.
- A major issue triggers immediate stop: no ad hoc continuing.
- Fixes must follow safe analysis before edits (`gitnexus_impact` before symbol edits).
- Design/responsive/a11y/SEO/performance checks are deferred until runtime correctness is stable.
- After each fix cycle, update this guide's ledgers before resuming.

## Roles and Responsibilities

## User Actions

- Confirm this guide was read and acknowledged.
- Execute visible UI actions in the browser when requested.
- Validate intent-level behavior (copy, state transitions, trustworthiness, UX clarity).
- Report perceived breakage, confusion, or mismatch from expected outcome.
- Confirm post-fix behavior after hot reload before checkpoint resume.

## Assistant Actions

- Prepare run sequence, checkpoints, and expected outcomes.
- Collect and correlate evidence from MCP/browser/runtime tooling.
- Enforce stop conditions, issue classification, and fix/resume protocol.
- Run GitNexus safety analysis before code edits, then targeted retests.
- Keep ledgers current after each checkpoint and each fix cycle.

## Prerequisites and Runtime Preparation

Do not execute automatically from this guide. Use these as the required prep checklist.

1. Infrastructure and services
   - `make dev-infra`
   - `make dev-backend`
   - `make dev-frontend`
2. Baseline smoke preflight
   - `python3 scripts/smoke_test.py --base-url http://localhost:8000 --frontend-url http://localhost:3000 --skip-chat`
3. Runtime access
   - Frontend URL reachable: `http://localhost:3000`
   - Backend health reachable: `http://localhost:8000/api/health`
4. MCP/tooling readiness
   - Next.js runtime tools available for runtime/route errors
   - Playwright or Chrome DevTools available for deterministic replay + browser signals
   - GitNexus index fresh enough for impact checks (refresh if stale)

If any prerequisite fails, do not proceed to live checkpoints.

## MCP and Tool Matrix

| Tool | When to Use | What to Capture |
|---|---|---|
| `bash` | Service checks, command-driven preflight, targeted script retests | Command output summary, timestamps, pass/fail |
| `MCP_DOCKER_nextjs_runtime` | Route/runtime diagnostics, build/runtime server signals | Runtime error snapshots, route diagnostics, tool output refs |
| `playwright_browser_*` or `MCP_DOCKER_browser_eval` | Deterministic user-flow replay, route transitions, screenshots | Repro steps, screenshots/snapshots, console/network indicators |
| `chrome-devtools_*` | Deep browser signals (console, network, perf traces) | Console error IDs, failing requests, trace references |
| `browser-tools_*` | Quick audits (a11y, performance, SEO, best practices) after stability gate | Audit score outputs and key issues |
| `gitnexus_impact` | Before any symbol/function/class edit | Blast radius, direct callers (d=1), risk level |
| `gitnexus_detect_changes` | After fix implementation, before commit/review | Changed symbols/processes, risk summary |

Use the strongest available evidence source. Manual recollection alone is not sufficient for blocker triage.

## Checkpoint Flow (Operational Loop)

Apply this exact sequence for each checkpoint:

1. Run
   - Execute scripted/assisted actions for the checkpoint scope.
2. Inspect
   - Gather runtime/browser evidence and user-visible behavior confirmation.
3. Stop (if triggered)
   - Stop immediately on blocker conditions (see classification below).
4. Analyze
   - Correlate evidence across runtime/browser/logs; identify likely fault surface.
5. Fix
   - Plan safe edit scope and implement focused fix.
6. Update Guide
   - Update issue ledger + checkpoint ledger before retest.
7. Retest
   - Retest affected route plus one adjacent flow.
8. Resume
   - Resume only from the recorded checkpoint state.

No checkpoint advances without completed evidence + human confirmation.

## Blocking vs Design/Performance Classification

## Blocking Issues (Stop Immediately)

- Crashes, hard runtime errors, broken navigation, dead primary actions.
- Data corruption risk, failed critical API paths, stuck/failed chat streaming.
- Inconsistent evidence where state correctness is unclear.

Status: `blocked` or `needs-fix`.
Action: stop -> analyze -> fix -> update ledgers -> targeted retest -> resume.

## Design/Performance/Quality Issues (Deferred Until Stable)

- Visual polish, spacing/typography details, minor content/copy issues.
- Responsiveness tuning, accessibility scoring, SEO, performance tuning.

Status: `deferred-nonfunctional` unless correctness baseline is stable.
Action: queue for audit stage after functional/runtime blockers clear.

## Checkpoint Ledger (Update During Execution)

Use one row per checkpoint transition.

| Timestamp | Checkpoint ID | Route | Action | Expected | Automated Evidence | User Observation | Status | Issue Link | Resume Target |
|---|---|---|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  | pass / blocked / needs-fix / retest-pass |  |  |
| 2026-03-22T16:16Z | CHK-STARTUP-001 | backend startup (`:8001`) | start hot-reload backend with local `.env` | backend starts without settings validation crash; health/model endpoints respond | `/tmp/embed-backend-8001.log` shows successful startup and `qdrant` on port `6335`; `python3 scripts/smoke_test.py --base-url http://localhost:8001 --frontend-url http://localhost:3001 --skip-chat` => `10/13` | frontend remains renderable on `http://localhost:3001`; backend blocker moved from startup crash to ingestion-only failure | retest-pass | GH-E2E-001, GH-E2E-002 | CHK-NAV-001 |
| 2026-03-22T16:34Z | CHK-INGEST-001 | ingestion path (`:8001`) | stop/fix/retest ingestion compatibility blockers | smoke check 10 passes and frontend proxy aligns to healthy backend | `ollama pull nomic-embed-text`; `python3 scripts/smoke_test.py --base-url http://localhost:8001 --frontend-url http://localhost:3001 --skip-chat` => `11/13` (2 skipped); `http://localhost:3001/api/health` => `200 healthy`; browser `/chat` API calls to `3001/api/*` return `200` | runtime now stable enough to start first real manual checkpoint loop; one unrelated hydration warning still visible and tracked for later | retest-pass | GH-E2E-002, GH-E2E-003 | CHK-NAV-001 |

## Running Issue Ledger (Template)

Add one entry per issue and keep state current through closure.

| Issue ID | Detected At | Severity | Class | Checkpoint | Symptoms | Evidence Links | Root Cause Hypothesis | Fix Plan | Retest Scope | State |
|---|---|---|---|---|---|---|---|---|---|---|
| GH-E2E-001 |  | blocker / medium / low | runtime / functional / design / perf / a11y / seo |  |  |  |  |  | affected route + adjacent flow | open / fixed-awaiting-retest / closed / deferred |
| GH-E2E-001 | 2026-03-22T16:14Z | blocker | runtime | CHK-STARTUP-001 | backend hot reload crashed at boot with `extra_forbidden` for `.env` keys `EMBEDINATOR_PORT_QDRANT*` | `/tmp/embed-backend-8001.log` (pre-fix startup trace), `backend/config.py` | settings model rejected infra port keys and did not map `EMBEDINATOR_PORT_QDRANT` to `qdrant_port` | allow extra env keys and map `qdrant_port` alias to `EMBEDINATOR_PORT_QDRANT`; restart backend on `:8001` | rerun `/api/health`, `/api/models/llm`, smoke checks 1+6 | closed |
| GH-E2E-002 | 2026-03-22T16:16Z | blocker | runtime | CHK-STARTUP-001 | smoke check 10 fails with `Ingestion job failed` while health/models are green | smoke output (`10/13`), direct probe to `http://localhost:11434/api/embed` and `/api/embeddings` returning model-not-found `404` | embed model drift in local Ollama (`nomic-embed-text` missing), not endpoint incompatibility | pull missing model and keep endpoint fallback compatibility in backend embed calls | rerun check 10 plus adjacent collections/chat path after fix | closed |
| GH-E2E-003 | 2026-03-22T16:33Z | blocker | runtime | CHK-INGEST-001 | ingestion still failed after model pull with `UNIQUE constraint failed: parent_chunks.id` during repeat smoke cycles | `/tmp/embed-backend-8001.log` latest trace, `backend/ingestion/chunker.py`, `backend/ingestion/pipeline.py` | deterministic chunk IDs were global (`source_file:page:chunk_index`) causing cross-collection collisions in SQLite `parent_chunks` | namespace deterministic IDs by `collection_id` during ingest split/build path | rerun check 10 and verify no parent chunk collision on repeated smoke | closed |

### Issue Notes Template

```
Issue ID:
Checkpoint:
Repro Steps:
Observed:
Expected:
Evidence:
Decision (stop/fix/defer):
Fix Summary:
Retest Result:
Resume From:
```

## Evidence and Logging Expectations

For each checkpoint or issue, record:
- Timestamp and active route.
- Exact action/repro step.
- Tool outputs or artifact references (console req IDs, screenshots, runtime excerpts).
- User observation (visible behavior, trust signal, UX clarity).
- Decision and next state (`pass`, `blocked`, `needs-fix`, `retest-pass`, `deferred-nonfunctional`).

Minimum evidence for a blocker:
1. One runtime or browser artifact,
2. One user-observed symptom note,
3. One explicit stop/fix/defer decision.

## Re-entry and Resume Instructions (After Every Fix Cycle)

After a fix is applied:
1. Confirm hot reload or manual refresh reached the intended route.
2. Re-run targeted retest for affected checkpoint.
3. Re-run one adjacent-flow check for regression guard.
4. Update checkpoint ledger and issue ledger with retest outcome.
5. If retest passes, mark `retest-pass` and resume from `Resume Target`.
6. If retest fails, remain paused and continue fix loop (no forward progression).

Never resume from memory. Always resume from the last written ledger state.

## Guided Checkpoint Set (Acceptance Sweep)

Mark each as `pass`, `skip-with-reason`, or `fail-with-issue-link`.

1. Startup readiness gate (services, smoke preflight, guide acknowledgment)
2. Basic navigation (`/chat`, `/collections`, `/settings`, `/observability`)
3. Ingestion/setup flow (if relevant to current change scope)
4. Chat flow (send, stream, completion state)
5. Citations/history/config UX verification
6. Post-fix regression retest (affected route + adjacent flow)
7. Non-functional audits (responsive, a11y, SEO, performance) after stability gate

## Stability Gate for Non-Functional Audits

Only enter non-functional audits when all are true:
- No open blocker in issue ledger.
- Latest critical path checkpoints are `pass` or `retest-pass`.
- Runtime/console signals are stable enough to trust audit outputs.

If any condition breaks, return to blocker loop and pause audits.

## Execution Guardrail

This guide is documentation and control protocol only.

Do not start live E2E execution until the user explicitly confirms this file was read and acknowledged.
