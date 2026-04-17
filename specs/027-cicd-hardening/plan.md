# Implementation Plan: CI/CT/CD Pipeline Hardening

**Branch**: `027-cicd-hardening` | **Date**: 2026-04-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification at `/home/brunoghiberto/Documents/Projects/The-Embedinator/specs/027-cicd-hardening/spec.md`
**Context prompt**: [docs/PROMPTS/spec-27-cicd-hardening/27-plan.md](../../docs/PROMPTS/spec-27-cicd-hardening/27-plan.md)

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
║    3. Agent(team_name="spec27-waveN", subagent_type="...", model="...")       ║
║       — ONE Agent call PER teammate. Each spawn opens its own tmux pane.      ║
║    4. SendMessage (for follow-ups, NEVER a new Agent call with same name)     ║
║    5. TeamDelete  (only after the wave's gate check passes)                   ║
║                                                                                ║
║  PROHIBITED:                                                                   ║
║    - Spawning agents via plain `Agent(subagent_type=...)` without team_name   ║
║    - Running multiple agents in the same pane                                 ║
║    - Launching a wave without tmux (the session MUST be inside tmux)          ║
║    - Skipping the gate check between waves                                    ║
║    - Merging to `main` during any wave (spec-27 lives on `027-cicd-hardening` ║
║      until Gate 4 passes, then a single PR → `develop` → `main`)              ║
║                                                                                ║
║  PREFLIGHT (the orchestrator runs THIS before Wave 1):                        ║
║    $ [ -n "$TMUX" ] || { echo "ERROR: must be inside tmux"; exit 1; }         ║
║    $ env | grep CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 \                      ║
║        || { echo "ERROR: export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1"; }    ║
║    $ gh auth status || { echo "ERROR: gh must be authenticated"; exit 1; }    ║
║                                                                                ║
║  If any preflight fails, STOP and instruct the user.                          ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

---

## Summary

Transform the repository's CI/CT/CD pipeline from advisory into enforceable. Today six GitHub Actions workflows run but nothing BLOCKS a broken artifact from publishing: `docker-publish.yml`, `release.yml`, and `release-cli.yml` fire on push/tag with no CI dependency; `ci.yml` disables the declared `--cov-fail-under=80` via `--no-cov`; `-m "not require_docker"` excludes every Qdrant-dependent test; the Rust ingestion-worker has zero CI; Actions are pinned to mutable tags; there is no Python type checking, Docker smoke test, image signing, SBOM, or vulnerability scanning.

Spec-27 does NOT rewrite the pipeline. It adds enforceable gates via a reusable `_ci-core.yml` workflow that every publish flow calls, flips the repo to PUBLIC to unlock branch protection, extends coverage to Python/Rust/Go/Frontend, and hardens supply chain (cosign keyless signing, syft SBOMs, trivy scans, extended CodeQL). 9 agents across 4 waves + 4 gates. Zero production code changes.

## Technical Context

**Language/Version**: N/A (spec-27 touches CI/CD only; production runtimes unchanged: Python 3.14.x, TypeScript 5.7, Rust 1.93.1, Go 1.25.x).
**Primary Dependencies (CI-only, NEW)**: `mypy` + `pydantic.mypy` plugin; `pip-audit`; `cargo-audit`; `govulncheck`; `trivy` action; `cosign` (keyless OIDC); `syft` / `anchore/sbom-action`; `action-semantic-pull-request` (commit-lint on PR title); `codecov/codecov-action` (coverage upload); `goreleaser check` (already present, now wired to CI). All are CI-only; none ship in production containers.
**Storage**: N/A (no new persistence; gates inspect repo state via `git`, `gh api`, and workflow YAML).
**Testing**: Existing `pytest` (backend), `vitest` (frontend unit), `playwright` (frontend E2E), `cargo test` (ingestion-worker). Test suite is UNCHANGED — spec-27 ENFORCES thresholds; it does not expand tests (Out-of-Scope).
**Target Platform**: GitHub Actions `ubuntu-latest` runners (public-repo tier, effectively unlimited minutes post-Gate-1). Rust CI scoped to `ubuntu-latest` only per Out-of-Scope.
**Project Type**: Infrastructure hardening spec (not a library, CLI, or web service in the conventional sense). Maps to the "web application" layout in the canonical template only in that it affects backend/frontend/ingestion-worker CI, not their source.
**Performance Goals**: NFR-001 — typical PR wall-clock time under 10 minutes from push to all-checks-green.
**Constraints**: Makefile SACRED (inherited from spec-19 NFR-007); production code trees (`backend/**/*.py`, `frontend/src/**`, `frontend/app/**`, `ingestion-worker/src/**`) UNTOUCHED; PR #2 CI-CLI fixes (commits `d8f6034`, `1b6b234`) PRESERVED; `cli/.golangci.yml` tech-debt deferrals PRESERVED (tracked via FR-020 issue, not resolved here).
**Scale/Scope**: Solo-dev project with planned open-source contributors post-Gate-1. 9 agent slots × 4 waves. 20 FRs, 7 NFRs, 12 SCs, 20 ACs.

## Clarifications Locked

These five decisions were resolved via `/speckit.clarify` on 2026-04-16. They are FIXED inputs to the plan.

| Q | Decision | Downstream wave impact |
|---|----------|------------------------|
| Q1 | **Repo → PUBLIC** (FR-019) | Gate 1 runs `gh repo edit --visibility public` after a secrets audit; configures `gh api` branch protection. Unlocks every "required for merge" framing. |
| Q2 | **Reusable workflow composition** (FR-001) | Wave 1 A1 creates `_ci-core.yml` and refactors `ci.yml` + 3 publish workflows to call it. No `workflow_run` pattern. |
| Q3 | **Every PR, no path filter** (FR-003) | Wave 2 A3 adds Qdrant service-container integration job that runs on every PR. No `paths:` filter. |
| Q4 | **`mypy` + Pydantic plugin, baseline strictness** (FR-005) | Wave 2 A3 configures `pyproject.toml` / `mypy.ini` with `plugins = ["pydantic.mypy"]`, `--no-implicit-optional`, `--warn-unused-ignores`. NO `--strict`. |
| Q5 | **PR title only, block non-conforming** (FR-016) | Wave 3 A7 adds `action-semantic-pull-request` (or `commitlint`) on PR title; blocks merge. No per-commit enforcement. |

## Constitution Check

*GATE: All principles evaluated against spec-27's design. Re-check identical conclusions after Phase 1.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| **I. Local-First Privacy** | PASS | Spec-27 adds no mandatory outbound calls to the production system. cosign/trivy/Codecov run in CI only, not at `docker compose up` time. No authentication or login introduced. |
| **II. Three-Layer Agent Architecture** | PASS (unchanged) | Agent code is not touched. `backend/agent/**` is in the NEVER-TOUCH list. |
| **III. Retrieval Pipeline Integrity** | PASS (unchanged) | Retrieval code is not touched. Parent/child chunking, hybrid search, and cross-encoder reranking remain exactly as spec-26 shipped. |
| **IV. Observability from Day One** | PASS (ENHANCED) | FR-014 adds `timeout-minutes` to every job (process observability); FR-018 adds coverage-delta PR comments (CI observability). Trace recording in backend unchanged. |
| **V. Secure by Design** | PASS (ENHANCED) | FR-008 SHA-pins every third-party Action (supply-chain integrity); FR-009 adds vulnerability scanning (pip-audit, cargo-audit, govulncheck, trivy); FR-010 adds image signing + SBOMs; FR-011 extends CodeQL to Go. Gate 1's pre-flip audit explicitly scans for leaked secrets before visibility flip. |
| **VI. NDJSON Streaming Contract** | PASS (unchanged) | API boundary code is not touched. |
| **VII. Simplicity by Default** | PASS | New tools (`mypy`, `pip-audit`, `cargo-audit`, `govulncheck`, `trivy`, `cosign`, `syft`, `commitlint`, `codecov-action`) are CI-only — they do NOT add runtime dependencies to the 4-service docker-compose deployment. YAGNI preserved: every new tool discharges a specific FR. No speculative tooling. |
| **VIII. Cross-Platform Compatibility** | PASS | Workflows run on `ubuntu-latest`. No platform-specific assumptions reach user-facing deployment. Rust CI scoped to Linux per Out-of-Scope. No bash-only escape hatches in production code. |

**Development Standards alignment**:

- **Backend coverage ≥ 80%**: FR-002 ENFORCES this (currently bypassed). PASS.
- **Frontend coverage ≥ 70%**: FR-002 (frontend) adopts this as baseline. PASS.
- **Conventional commits**: FR-016 ENFORCES this on PR titles. PASS.
- **Circuit breaker + reliability**: Unchanged (lives in production code). PASS.
- **Performance budgets**: Unchanged (runtime not affected). NFR-001's CI wall-clock budget is a new CI-side budget, consistent in spirit with existing performance culture. PASS.

**Result**: **All 8 principles + Development Standards PASS.** No Complexity Tracking violations. No new ADR required beyond the branch-protection ADR that spec-27 itself produces (A9 in Wave 4).

## Project Structure

### Documentation (this feature)

```text
specs/027-cicd-hardening/
├── plan.md                   # This file (/speckit.plan output)
├── spec.md                   # Authoritative contract (5 user stories, 20 FRs, 7 NFRs, 12 SCs, 5 clarifications locked)
├── checklists/
│   └── requirements.md       # Spec quality checklist (from /speckit.specify)
├── research.md               # Phase 0 output (this run)
├── quickstart.md             # Phase 1 output (this run)
├── validation-report.md      # Wave 4 A8 draft, Gate 4 orchestrator final
└── tasks.md                  # Phase 2 output (NEXT: /speckit.tasks)
```

Intentionally omitted (justified in Phase 1 below):

- `data-model.md` — spec-27 introduces no persisted entities.
- `contracts/` — spec-27 introduces no new API surfaces; the only "contract" (reusable workflow inputs/outputs + required status-check names) is documented in the Workflow Contracts section below.

### Source / Config Paths Affected

```text
.github/
├── workflows/
│   ├── _ci-core.yml          # NEW (A1) — reusable workflow
│   ├── ci.yml                # REFACTOR (A1) — calls _ci-core.yml
│   ├── ci-cli.yml            # EDIT (A4, A7) — + govulncheck, + goreleaser check
│   ├── ci-rust.yml           # NEW (A4) — cargo fmt/clippy/test/audit
│   ├── docker-publish.yml    # REFACTOR (A1, A6) — gated on CI; + trivy + cosign + SBOM
│   ├── release.yml           # REFACTOR (A1) — gated on CI
│   ├── release-cli.yml       # REFACTOR (A1, A6) — gated on CI; SBOMs for goreleaser
│   ├── security.yml          # EDIT (A6) — CodeQL matrix extended to Go
│   └── pr-title.yml          # NEW (A7) — commit-lint on PR title
├── CODEOWNERS                # NEW (A2) — `* @Bruno-Ghiberto`
└── dependabot.yml            # UNCHANGED (already good per spec)
pyproject.toml (or mypy.ini)  # EDIT (A3) — mypy + Pydantic plugin config
pytest.ini                    # UNCHANGED (cov threshold already declared; A3 removes --no-cov from CI invocation)
ruff.toml                     # UNCHANGED (format config already present; A3 adds `ruff format --check` step in _ci-core.yml)
requirements.txt              # EDIT (A3) — add mypy, pydantic[mypy], pip-audit as dev deps
frontend/
├── vitest.config.ts          # EDIT (A5) — coverage threshold 70%
└── playwright.config.ts      # VERIFY (A5) — adjust baseURL only if needed
cli/
├── .goreleaser.yml           # EDIT (A6) — checksums + SBOMs
└── .golangci.yml             # UNCHANGED (PR #2 deferrals preserved; FR-020 files a tracking issue)
docs/
├── cicd.md                   # NEW (A9) — ≤300 lines, 30-min comprehension
└── adr/
    └── 0001-branch-protection.md  # NEW (A9) — ADR for Q1 decision
README.md                     # EDIT (A9) — CI/CD section linking to docs/cicd.md
```

### NEVER Touch

- `Makefile` (SACRED — NFR-007 adaptation from spec-19)
- `embedinator.sh`, `embedinator.ps1` (launcher scripts — SACRED from spec-19)
- `backend/**/*.py` (production backend source)
- `frontend/src/**`, `frontend/app/**`, `frontend/components/**` (production frontend source)
- `ingestion-worker/src/**`, `ingestion-worker/Cargo.toml` source (except CI-relevant dev-deps if absolutely necessary)
- `docker-compose.yml` (infra stable; any change raises gate risk)
- `tests/**` (test suite UNCHANGED per Out-of-Scope — red-CI demos use short-lived branches, never committed to `027-cicd-hardening`)
- `specs/0[01][0-9]-*/` except the `027-cicd-hardening/` directory (prior specs are immutable)
- `.env`, `.env.example`, `.env.*` (secret hygiene)

**Structure Decision**: Infrastructure hardening spec — no conventional library/web/mobile layout applies. The affected surface is `.github/`, `docs/`, root-level build config (`pyproject.toml`, `requirements.txt`), frontend test config (`frontend/vitest.config.ts`, `frontend/playwright.config.ts`), and CLI goreleaser config. Production source trees are intentionally excluded (gate-enforced scope check).

## Phase 0: Outline & Research (→ `research.md`)

All five clarification targets are already resolved. Phase 0 captures the remaining documentation lookups needed to justify tool choices and eliminate residual "NEEDS CLARIFICATION" from the Technical Context.

Unknowns resolved in `research.md`:

1. `workflow_call` semantics — inputs/outputs shape, secrets passing, permissions inheritance.
2. cosign keyless OIDC flow — `id-token: write` permission requirement and verification UX.
3. `pydantic.mypy` plugin activation — config block shape and exclusion patterns.
4. `trivy` action vs CLI install — justified choice.
5. `commitlint` vs `action-semantic-pull-request` — picked winner.
6. Coverage-reporting provider default — Codecov on public repo, tokenless.
7. Frontend coverage threshold — 70% baseline confirmed against current suite.
8. SHA-pinning workflow — the `gh api .../commits/<tag>` pattern A2 will use.

Output: [research.md](./research.md).

## Phase 1: Design & Contracts (→ `quickstart.md`, agent-context)

**Prerequisite**: `research.md` complete.

### Data Model

**N/A — spec-27 introduces no persisted entities.** The spec names four conceptual entities (Pipeline Gate, Artifact, Policy Document, Debt Item) but none require a schema. Pipeline Gates are GitHub Actions jobs (state lives in GitHub's runner logs + checks API); Artifacts are container images / releases (state lives in ghcr.io and GitHub Releases); Policy Documents are markdown files (state lives in git); Debt Items are GitHub Issues (state lives in the issue tracker). No `data-model.md` file.

### Workflow Contracts (replaces `contracts/`)

**Reusable workflow interface** (`_ci-core.yml`):

```yaml
# on: workflow_call
inputs:
  commit_sha:
    type: string
    required: false
    description: "Commit SHA to run CI against. Defaults to caller's ref."
outputs:
  backend_cov_pct:
    description: "Backend test coverage percentage (integer)."
  frontend_cov_pct:
    description: "Frontend test coverage percentage (integer)."
  all_passed:
    description: "Boolean aggregate — true only if every required job passed."
permissions:
  contents: read
  checks: write
  pull-requests: write
  id-token: write   # REQUIRED for cosign keyless signing in callers
```

**Required status-check roster** (configured on `main` and `develop` via `gh api repos/:owner/:repo/branches/:branch/protection`):

| Check name | Source workflow | Conditional |
|------------|-----------------|-------------|
| `CI / backend-lint` | `_ci-core.yml` | Always required |
| `CI / backend-test` | `_ci-core.yml` | Always required |
| `CI / backend-format-check` | `_ci-core.yml` | Always required |
| `CI / backend-type-check` | `_ci-core.yml` | Always required |
| `CI / backend-integration` | `_ci-core.yml` | Always required (Q3) |
| `CI / backend-pip-audit` | `_ci-core.yml` | Always required |
| `CI / frontend-lint` | `_ci-core.yml` | Always required |
| `CI / frontend-test` | `_ci-core.yml` | Always required |
| `CI / frontend-coverage` | `_ci-core.yml` | Always required |
| `CI / frontend-e2e` | `_ci-core.yml` | Path-conditional on `frontend/**` |
| `CI / docker-build-smoke` | `_ci-core.yml` | Always required |
| `CI / pre-commit-parity` | `_ci-core.yml` | Always required |
| `CI Rust / fmt` | `ci-rust.yml` | Path-conditional on `ingestion-worker/**` |
| `CI Rust / clippy` | `ci-rust.yml` | Path-conditional on `ingestion-worker/**` |
| `CI Rust / test` | `ci-rust.yml` | Path-conditional on `ingestion-worker/**` |
| `CI Rust / audit` | `ci-rust.yml` | Path-conditional on `ingestion-worker/**` |
| `CI CLI / govulncheck` | `ci-cli.yml` | Path-conditional on `cli/**` |
| `PR Title / semantic` | `pr-title.yml` | Always required |

Gate 1's initial `gh api` call uses placeholder names; Gate 2 finalizes them after A3/A4/A5 emit the actual job names. Conditional checks are expected to report `skipped` (GitHub treats `skipped` as `success` for required-check purposes when the triggering path isn't in the PR diff).

### Quickstart

See [quickstart.md](./quickstart.md) for reproduction commands.

### Agent Context Update

Run `.specify/scripts/bash/update-agent-context.sh claude` to refresh `CLAUDE.md` with the spec-27 Active Technologies line. Executed as part of this run.

## Wave-by-Wave Plan

### Wave 1 — Foundation + Visibility (BLOCKING)

**Goal**: Build the reusable `_ci-core.yml` workflow; apply cross-cutting hardening; flip the repo to PUBLIC; configure branch protection.

**Slots (2 parallel panes)**:

| Slot | Agent type | Model | Primary FRs | Deliverables |
|------|------------|-------|-------------|--------------|
| A1 | devops-architect | Sonnet | FR-001 | `_ci-core.yml` (new); refactor `ci.yml`, `docker-publish.yml`, `release.yml`, `release-cli.yml` to call it |
| A2 | security-engineer | **Opus** | FR-008, FR-014, FR-015 | SHA-pin all external Actions across every workflow; add `timeout-minutes:` to every job; create `.github/CODEOWNERS`; pin runtime versions to full semver |

**User stories served**: US1 (P1 — block broken artifacts).
**SCs moved**: SC-003 (immutable pinning), SC-004 (runtime SoT), partial SC-001 (gating scaffold; red-CI demos land in Wave 4).
**ACs enabled**: AC-001, AC-002, AC-009, AC-014, AC-015.

**Exit criteria (Gate 1, orchestrator Opus)**:

1. `_ci-core.yml` parses; publish workflows reference it with `if: needs.ci.outputs.all_passed == 'true'`.
2. `! grep -rE 'uses: [a-zA-Z0-9._/-]+@v[0-9]+\b' .github/workflows/` returns zero lines.
3. `grep -rL 'timeout-minutes:' .github/workflows/` returns zero files.
4. `.github/CODEOWNERS` exists with `* @Bruno-Ghiberto`.
5. **Pre-flip audit** (REQUIRED before visibility flip):
   - `gh api repos/:owner/:repo --jq .private` returns `true` (confirm start state).
   - No `.env*` tracked by git: `git ls-files | grep -E '^\.env'` returns empty.
   - Inline-secret grep across `backend/`, `frontend/`, `.github/` returns zero matches (pattern in Gate Check Protocol below).
   - User explicitly confirms "OK to flip PUBLIC" — orchestrator prompts.
6. **Flip**: `gh repo edit --visibility public --accept-visibility-change-consequences`.
7. **Branch protection** configured on `main` and `develop` via `gh api PUT` with placeholder required-check list; refined at Gate 2.
8. `git diff -- Makefile | wc -l` equals 0.

**Blocks**: any pre-flip audit finding (tracked `.env`, inline secrets, private prompt file in git history) aborts Gate 1. Operator resolves (e.g. `git filter-repo`) before retry.

### Wave 2 — Language-Specific Gates

**Goal**: Wire enforceable gates per language surface.

**Slots (3 parallel panes)**:

| Slot | Agent type | Model | Primary FRs | Deliverables |
|------|------------|-------|-------------|--------------|
| A3 | python-expert | Sonnet | FR-002 (backend), FR-003, FR-005, FR-006, FR-009 (Python) | Remove `--no-cov`; add mypy + Pydantic plugin; add `ruff format --check`; add Qdrant service-container integration job; add pip-audit step |
| A4 | devops-architect | Sonnet | FR-004, FR-009 (Rust, Go) | `ci-rust.yml` (new) with cargo fmt/clippy/test/audit; govulncheck step in `ci-cli.yml` |
| A5 | frontend-architect | Sonnet | FR-002 (frontend), FR-012 | Frontend coverage threshold enforced in `_ci-core.yml`; Playwright E2E job path-conditional on `frontend/**` |

**User stories served**: US2 (P2 — quality gates).
**SCs moved**: SC-009 (coverage threshold enforced), SC-010 (integration every PR), SC-011 (Rust CI covers ingestion-worker).
**ACs enabled**: AC-003, AC-004, AC-005, AC-006, AC-007, AC-013.

**Exit criteria (Gate 2)**:

1. A3/A4/A5 committed. `_ci-core.yml` now contains backend-test (`--cov-fail-under=80`), backend-format-check, backend-type-check, backend-integration (Qdrant `services:` block), backend-pip-audit, frontend-coverage, frontend-e2e jobs.
2. `ci-rust.yml` exists and triggers on `ingestion-worker/**` PRs.
3. `ci-cli.yml` has a `govulncheck` step; PR #2 fixes (`d8f6034`, `1b6b234`) preserved.
4. Smoke-PR dry-run: push `027-smoke-gate2`, open a draft PR, confirm all new jobs execute on the smoke SHA (expect green — no deliberate regression yet).
5. `git diff -- Makefile` equals 0.
6. No new test regressions vs `026-performance-debug` HEAD baseline (via external test runner).
7. Branch protection `required_status_checks.contexts` updated with the real job names emitted by A3/A4/A5.

### Wave 3 — Supply Chain + Polish

**Goal**: Add runtime-smoke, signing, SBOMs, extended CodeQL, pre-commit parity, commit-lint, goreleaser check, Codecov, and file the deferred-debt issue.

**Slots (2 parallel panes)**:

| Slot | Agent type | Model | Primary FRs | Deliverables |
|------|------------|-------|-------------|--------------|
| A6 | security-engineer | **Opus** | FR-007, FR-009 (trivy), FR-010, FR-011 | Docker smoke test (curl `/api/health` post-up); trivy scan on images; cosign keyless signing; syft SBOM; CodeQL matrix extended to Go |
| A7 | devops-architect | Sonnet | FR-013, FR-016, FR-017, FR-018, FR-020 | Pre-commit parity CI job; PR-title commit-lint; `goreleaser check` on `cli/.goreleaser.yml` PRs; Codecov upload; GitHub issue for 33 deferred Go lint items |

**User stories served**: US3 (P3 — supply chain), US4 (P4 — polish), US5 (P5 — reporting/debt).
**SCs moved**: SC-012 (signed + SBOM images), SC-002 (self-documenting workflows via A7's pre-commit + comment headers), partial SC-005/SC-006 (finalized in Wave 4).
**ACs enabled**: AC-008, AC-010, AC-011, AC-012, AC-016, AC-017, AC-020.

**Exit criteria (Gate 3, orchestrator Opus)**:

1. A6 + A7 committed.
2. Smoke-PR: docker-build runs full smoke (up/health/down) and passes.
3. Tag `v0.3.0-spec27-smoke` on the branch, confirm trivy scans; cosign signs; SBOM attaches.
4. `cosign verify ghcr.io/<owner>/embedinator-backend:<tag>` succeeds (keyless OIDC).
5. `security.yml` CodeQL matrix includes Go (visible in `gh run view --log`).
6. Pre-commit parity job passes on the smoke PR.
7. `pr-title.yml` fires; a non-conventional title fails it.
8. goreleaser check runs when `cli/.goreleaser.yml` is in the PR diff.
9. Codecov comment lands on the smoke PR.
10. `gh issue list --label tech-debt` shows the newly filed issue for the 33 Go lint items.
11. `git diff -- Makefile` equals 0.
12. No new test regressions vs baseline.

**Blocks**: cosign verification failure usually = missing `id-token: write` permission. Fix at workflow level and re-dispatch A6 via `SendMessage`.

### Wave 4 — Validation + Docs

**Goal**: Execute red-CI demonstrations for every AC; measure wall-clock; write `docs/cicd.md`, ADR-0001, and update README; finalize `validation-report.md`.

**Slots (2 parallel panes)**:

| Slot | Agent type | Model | Primary FRs | Deliverables |
|------|------------|-------|-------------|--------------|
| A8 | quality-engineer | Sonnet | All 20 ACs, NFR-001 | Short-lived demo branches for red-CI reproductions (coverage drop, unformatted code, mypy error, broken QdrantStorage, known-CVE dep, clippy warning, non-conventional PR title); wall-clock measurement; draft `validation-report.md` |
| A9 | technical-writer | Sonnet | SC-005, SC-008, FR-019 ADR | `docs/cicd.md` (≤300 lines, 30-min comprehension target); `docs/adr/0001-branch-protection.md`; README section linking to `docs/cicd.md` |

**User stories served**: Validation across all P1–P5.
**SCs moved**: SC-001 (publish-gate demos), SC-005 (newcomer comprehension doc), SC-006 (required-check roster in README), SC-007 (wall-clock measured), SC-008 (ADR committed).
**ACs enabled**: AC-018, AC-019, plus final evidence for AC-001, AC-003, AC-004, AC-005, AC-006, AC-007, AC-010, AC-016.

**Exit criteria (Gate 4, orchestrator)**:

1. All 20 ACs and all 12 SCs evaluated in `validation-report.md` (PASS / FAIL / WAIVED + evidence artifact reference).
2. `gh repo view --json visibility --jq '.visibility'` returns `"public"`.
3. `gh api repos/:owner/:repo/branches/main/protection` returns a populated config matching the Workflow Contracts roster.
4. `docs/cicd.md`, `docs/adr/0001-branch-protection.md`, and the README link all exist.
5. `git diff -- Makefile` equals 0.
6. No new test regressions vs `026-performance-debug` baseline.
7. Short-lived demo branches are NOT present in the branch's history (they were deleted after each red-CI demonstration; evidence lives in `validation-report.md` URL references, not in commits).

**If PASS**: open PR `027-cicd-hardening` → `develop`; after review + merge, tag next version (`v0.3.1` if `v0.3.0` already consumed, else `v0.3.0`; check `git tag` first).
**If FAIL**: write WAIVED rationale or dispatch `SendMessage` back to the offending slot.

## Agent Roster

| Slot | Agent type | File | Wave | Model | Deliverable summary |
|------|------------|------|------|-------|---------------------|
| A1 | devops-architect | `~/.claude/agents/devops-architect.md` | 1 | Sonnet | `_ci-core.yml` + publish refactor |
| A2 | security-engineer | `~/.claude/agents/security-engineer.md` | 1 | **Opus** | SHA pinning + timeouts + CODEOWNERS + runtime pins |
| A3 | python-expert | `~/.claude/agents/python-expert.md` | 2 | Sonnet | Python gates (cov, mypy, fmt, integration, pip-audit) |
| A4 | devops-architect | `~/.claude/agents/devops-architect.md` | 2 | Sonnet | Rust + Go CI (ci-rust.yml + govulncheck) |
| A5 | frontend-architect | `~/.claude/agents/frontend-architect.md` | 2 | Sonnet | Frontend cov + Playwright E2E |
| A6 | security-engineer | `~/.claude/agents/security-engineer.md` | 3 | **Opus** | Smoke test + trivy + cosign + SBOM + CodeQL Go |
| A7 | devops-architect | `~/.claude/agents/devops-architect.md` | 3 | Sonnet | Pre-commit + commit-lint + goreleaser + Codecov + debt issue |
| A8 | quality-engineer | `~/.claude/agents/quality-engineer.md` | 4 | Sonnet | Red-CI demos + wall-clock + validation-report.md draft |
| A9 | technical-writer | `~/.claude/agents/technical-writer.md` | 4 | Sonnet | `docs/cicd.md` + ADR-0001 + README link |

**Model tier rationale**: Opus is reserved for slots requiring cross-cutting mental model (A2 holds every workflow in mind simultaneously for the SHA-pin + timeout + runtime-pin sweep) or architectural judgment (A6 threat-models signing/SBOM/scanning decisions). All other slots execute mechanical refactors, file additions, or documentation — Sonnet is sufficient and faster.

## MCP Tool Strategy

| Tool | Orchestrator | A1 | A2 | A3 | A4 | A5 | A6 | A7 | A8 | A9 |
|------|--------------|----|----|----|----|----|----|----|----|----|
| Docker MCP | ✓ (gates 2+) | — | — | ✓ | ✓ (rehearsal) | ✓ (rehearsal) | ✓ | — | ✓ | — |
| Sequential Thinking | ✓ (gate 1 pre-flip, gate 3 threat model) | — | ✓ | — | — | — | ✓ | — | ✓ | — |
| Context7 | — | opt | — | ✓ | — | — | opt (fallback) | — | — | — |
| Serena | — | ✓ | ✓ | ✓ | — | ✓ | — | ✓ | — | — |
| GitNexus | — | ✓ | — | — | — | — | — | — | — | — |
| Playwright MCP | — | — | — | — | — | ✓ (rehearsal) | — | — | opt (T164b) | — |
| mcp-chart | — | — | — | — | — | — | — | — | — | ✓ (flow diagram) |
| WebFetch | — | opt | opt | — | — | — | opt | — | — | — |
| Bash | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `gh` CLI | ✓ (gate 1 flip + branch protection; gate 3+ verify; gate 4 PR) | — | — | — | — | — | — | ✓ (gh issue create) | ✓ (gh run view / pr create) | — |
| shadcn-ui MCP | — | — | — | — | — | opt | — | — | — | — |

Legend: ✓ = allowed, — = not needed / prohibited, opt = optional.

**Explicitly excluded**:
- **SonarQube MCP** — spec-27 uses Codecov (FR-018) for coverage-delta PR comments. SonarQube's broader static-analysis surface is deferred to a future spec.
- **browser-tools / chrome-devtools / next-devtools-mcp / langchain-docs / gemini-api-docs / claude_ai_***  — not applicable to CI/CD hardening scope (no Next.js runtime, LLM, or productivity-suite surface touched).

**Orchestrator-only tools**: `gh repo edit --visibility public` and `gh api ... branches/*/protection` are ONLY invoked by the orchestrator at Gate 1. No agent touches repo settings directly.

## Gate Check Protocol (shared across all gates)

```bash
# --- Makefile SACRED (inherited from spec-19) ---
git diff -- Makefile | wc -l | grep -q '^0$' \
  && echo "PASS: Makefile" \
  || { echo "FAIL: Makefile"; exit 1; }

# --- Scope: spec-27 touched ONLY CI/CD files ---
git diff --name-only 026-performance-debug..HEAD \
  | grep -vE '^(\.github/|docs/|specs/027|pyproject\.toml|pytest\.ini|ruff\.toml|mypy\.ini|frontend/(vitest|playwright)\.config\.ts|requirements\.txt|cli/\.goreleaser\.yml|cli/\.golangci\.yml|README\.md)' \
  && { echo "FAIL: spec-27 touched unexpected file(s)"; exit 1; } \
  || echo "PASS: scope"

# --- No test regressions vs branch baseline (external runner only) ---
zsh scripts/run-tests-external.sh -n spec27-gate<N> --no-cov tests/
cat Docs/Tests/spec27-gate<N>.status    # PASSED or same failure count as baseline
cat Docs/Tests/spec27-gate<N>.summary

# --- Workflow YAML validity ---
for f in .github/workflows/*.yml; do
  yq eval '.' "$f" > /dev/null || { echo "FAIL: invalid YAML $f"; exit 1; }
done
echo "PASS: YAML"

# --- SHA-pin sanity (gates 1+) ---
! grep -rE 'uses: [a-zA-Z0-9._/-]+@v[0-9]+\b' .github/workflows/ \
  && echo "PASS: SHA-pinning" \
  || { echo "FAIL: unpinned actions"; exit 1; }

# --- Timeout coverage (gates 1+) ---
[ -z "$(grep -rLE 'timeout-minutes:' .github/workflows/)" ] \
  && echo "PASS: timeouts" \
  || { echo "FAIL: job(s) missing timeout-minutes"; exit 1; }

# --- Pre-flip secrets audit (Gate 1 only; fails closed) ---
grep -rE '(password|secret|token|api[_-]?key)\s*=\s*["\x27][^"\x27]+["\x27]' \
  --include='*.py' --include='*.ts' --include='*.tsx' --include='*.js' --include='*.yml' \
  backend/ frontend/ .github/ \
  && { echo "FAIL: inline secret candidate found"; exit 1; } \
  || echo "PASS: no inline secret candidates"

# --- Visibility + branch protection (post-Gate-1) ---
gh repo view --json visibility --jq '.visibility'   # expect "PUBLIC"
gh api "repos/$(gh repo view --json nameWithOwner --jq .nameWithOwner)/branches/main/protection" \
  | jq '.required_status_checks.contexts'
```

## Build Verification Protocol (gate demos)

```bash
# --- Smoke PR (gates 2+) ---
git checkout -b 027-smoke-gate<N>
echo "# smoke" >> README.md
git commit -am "chore: smoke gate<N>"
git push -u origin 027-smoke-gate<N>
gh pr create --title "chore: smoke gate<N>" --body "Smoke test for spec-27 gate<N>" --draft
gh pr checks --watch
# cleanup:
gh pr close --delete-branch

# --- cosign verify (gate 3+) ---
REPO="$(gh repo view --json nameWithOwner --jq '.nameWithOwner' | tr '[:upper:]' '[:lower:]')"
cosign verify "ghcr.io/${REPO}-backend:<tag>" \
  --certificate-identity-regexp=".*" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com"

# --- Red-CI demo skeleton (gate 4, run per AC) ---
git checkout -b 027-red-<ac-name>
# <introduce deliberate regression>
git commit -am "demo: <ac-name> red path"
git push -u origin 027-red-<ac-name>
gh pr create --title "demo: AC-<NNN>" --body "Demonstrates red-CI path" --draft
gh pr checks --watch  # expect FAIL at the expected step
# Record evidence URL in validation-report.md, then:
gh pr close --delete-branch
```

## SC Evaluation Matrix

| SC | Evidence artifact | Verification command |
|----|-------------------|----------------------|
| SC-001 Zero unguarded publications | A8 red-CI demos on `main` merge + broken tag push | `gh run view <red-CI-run-id>` shows publish job short-circuited |
| SC-002 Every workflow self-documents | Top-of-file comment block on every workflow | `for f in .github/workflows/*.yml; do head -20 "$f" \| grep -q '^#'; done` |
| SC-003 Immutable action pinning | SHA-pin grep returns 0 lines | `! grep -rE 'uses: [a-zA-Z0-9._/-]+@v[0-9]+\b' .github/workflows/` |
| SC-004 Runtime version SoT | Consolidated version pins | `grep -hE 'go-version\|node-version\|python-version\|rust-toolchain' .github/workflows/*.yml \| sort -u` |
| SC-005 30-min comprehension | `docs/cicd.md` newcomer walkthrough | A9 deliverable + optional acceptance test |
| SC-006 Required-check roster | README + `gh api` | `gh api repos/:owner/:repo/branches/main/protection \| jq .required_status_checks.contexts` |
| SC-007 PR wall-clock | A8 measurement table | `validation-report.md` §"SC-007" |
| SC-008 Branch-protection ADR | `docs/adr/0001-branch-protection.md` | file existence + content review |
| SC-009 Coverage threshold enforced | Red-CI demo: drop coverage → fail | A8 `027-red-coverage` transcript |
| SC-010 Integration tests per PR | Red-CI demo: break QdrantStorage → fail | A8 `027-red-qdrant` transcript |
| SC-011 Rust CI covers ingestion-worker | Red-CI demo: clippy warning → fail | A8 `027-red-rust-clippy` transcript |
| SC-012 Signed + SBOM images | `cosign verify` + `cosign download sbom` | Gate 3 verification transcript |

## Dependency Graph

```text
                 Wave 1 — Foundation + Visibility (BLOCKING)
                ┌──────────────────┬───────────────────────┐
                │ A1: _ci-core.yml │ A2: SHA-pin + timeout │
                │ + publish gates  │ + CODEOWNERS + runtime│
                │ (devops, Sonnet) │ (security, Opus)      │
                └──────────────────┴───────────────────────┘
                                 │
                    ┌─── GATE 1 (orchestrator, Opus) ───┐
                    │ Pre-flip audit (secrets scan)     │
                    │ → gh repo edit --visibility public│
                    │ → gh api branch protection config │
                    │ → ADR stub (finalized in Wave 4)  │
                    └───────────────────────────────────┘
                                 │
                 Wave 2 — Language-Specific Gates
                ┌────────────────┬─────────────────┬───────────────┐
                │ A3: Python     │ A4: Rust + Go   │ A5: Frontend  │
                │ cov + mypy +   │ ci-rust.yml +   │ cov + Playwr. │
                │ fmt + integr + │ govulncheck     │ E2E           │
                │ pip-audit      │                 │               │
                │ (python-expert)│ (devops, Sonnet)│ (frontend-arch)│
                └────────────────┴─────────────────┴───────────────┘
                                 │
                    ┌─── GATE 2 (orchestrator) ───┐
                    │ Smoke PR: all new jobs run  │
                    │ gh api branch protection    │
                    │ updated with real check     │
                    │ names from Wave 2 outputs   │
                    └─────────────────────────────┘
                                 │
                 Wave 3 — Supply Chain + Polish
                ┌──────────────────┬───────────────────────┐
                │ A6: Docker smoke │ A7: pre-commit +      │
                │ + trivy + cosign │ commit-lint + gorel + │
                │ + SBOM + CodeQL  │ Codecov + gh issue    │
                │ Go               │                       │
                │ (security, Opus) │ (devops, Sonnet)      │
                └──────────────────┴───────────────────────┘
                                 │
                    ┌─── GATE 3 (orchestrator, Opus) ───┐
                    │ cosign verify on tagged smoke     │
                    │ trivy scans; CodeQL Go; pre-commit│
                    │ parity; commit-lint blocks bad    │
                    │ titles; Codecov comment lands     │
                    └───────────────────────────────────┘
                                 │
                 Wave 4 — Validation + Docs
                ┌──────────────────┬───────────────────────┐
                │ A8: Red-CI demos │ A9: docs/cicd.md +    │
                │ + wall-clock +   │ ADR-0001 + README     │
                │ validation-      │ link                  │
                │ report.md        │                       │
                │ (quality, Sonnet)│ (writer, Sonnet)      │
                └──────────────────┴───────────────────────┘
                                 │
                    ┌─── GATE 4 (orchestrator) ───┐
                    │ 20 ACs + 12 SCs evaluated   │
                    │ with evidence; PR 027→dev   │
                    │ opened                      │
                    └─────────────────────────────┘
```

## Constraints Inherited From Spec

| Constraint | Source | Encoded As |
|-----------|--------|-----------|
| Makefile SACRED | NFR-007 (adapted from spec-19) | Every gate's `git diff -- Makefile \| wc -l` check |
| Production code untouched | Out-of-Scope: "Zero production code changes" | Gate scope-check grep; file blocklist |
| No `@latest` anywhere | NFR-002 (deterministic builds) | Gate 1 SHA-pin check; A2 runtime-pin sweep |
| PR wall-clock < 10 min typical | NFR-001 | A8 measurement; matrix/caching guidance |
| Secret hygiene | NFR-006 | A7 Codecov token decision; Gate 1 pre-flip audit |
| Public/private workflow parity | NFR-007 | No workflow depends on `private` state after Gate 1 |
| Clarifications locked (Q1–Q5) | `/speckit.clarify` 2026-04-16 | Dedicated section in this plan; enforced in wave assignments |
| PR #2 CI-CLI fixes preserved | Spec "Already Implemented" | A4 prompt forbids reverting commits `d8f6034`, `1b6b234` |
| Test suite UNCHANGED (no expansion) | Out-of-Scope | A8 demos use short-lived branches; never committed to `027-cicd-hardening` |

## Files the Plan Expects to Modify

| Path | Agent(s) | Purpose |
|------|----------|---------|
| `.github/workflows/_ci-core.yml` | A1 create; A3, A5, A6, A7 edit | Reusable workflow; all CI jobs live here |
| `.github/workflows/ci.yml` | A1 | Thin dispatcher → calls `_ci-core.yml` |
| `.github/workflows/docker-publish.yml` | A1, A6 | Gated on CI; adds trivy + cosign + SBOM |
| `.github/workflows/release.yml` | A1 | Gated on CI |
| `.github/workflows/release-cli.yml` | A1, A6 | Gated on CI; SBOMs via goreleaser |
| `.github/workflows/ci-rust.yml` | A4 | New — cargo fmt/clippy/test/audit |
| `.github/workflows/ci-cli.yml` | A4, A7 | Adds govulncheck + goreleaser check; PR #2 fixes preserved |
| `.github/workflows/security.yml` | A6 | CodeQL matrix extended to Go |
| `.github/workflows/pr-title.yml` | A7 | New — commit-lint on PR title |
| `.github/CODEOWNERS` | A2 | New — `* @Bruno-Ghiberto` |
| `pyproject.toml` (or `mypy.ini`) | A3 | mypy config with Pydantic plugin |
| `requirements.txt` | A3 | Add `mypy`, `pydantic[mypy]`, `pip-audit` dev deps |
| `frontend/vitest.config.ts` | A5 | Coverage threshold (70% baseline) |
| `frontend/playwright.config.ts` | A5 | Verify / adjust baseURL for CI |
| `cli/.goreleaser.yml` | A6 | Add checksums + SBOMs |
| `docs/cicd.md` | A9 | New — newcomer CI/CD walkthrough (≤ 300 lines) |
| `docs/adr/0001-branch-protection.md` | A9 | New — ADR for Q1 decision |
| `README.md` | A9 | Add CI/CD section + link to `docs/cicd.md` |
| `specs/027-cicd-hardening/validation-report.md` | A8 draft, orchestrator final | Gate 4 evaluation of 20 ACs + 12 SCs |

## Files NEVER To Touch

- `Makefile` (SACRED)
- `embedinator.sh`, `embedinator.ps1` (SACRED)
- `backend/**/*.py`
- `frontend/src/**`, `frontend/app/**`, `frontend/components/**`
- `ingestion-worker/src/**`
- `docker-compose.yml`
- `tests/**` (red-CI demos use short-lived branches that are never committed)
- `specs/0[01][0-9]-*/` except `027-cicd-hardening/`
- `.env`, `.env.example`, `.env.*`

## Complexity Tracking

> **Empty — no Constitution Check violations requiring justification.**

Every principle passed. New CI-only tooling (mypy, pip-audit, cargo-audit, govulncheck, trivy, cosign, syft, commitlint, codecov-action) does not add runtime dependencies to the 4-service Docker deployment and is justified by specific FRs.

## Post-Design Re-check

After Phase 1 completion (research.md + quickstart.md + agent-context update), all Constitution Check conclusions remain identical. Principle V (Secure by Design) is strengthened — not weakened — by SHA pinning, vulnerability scanning, image signing, and SBOMs. Principle VII (Simplicity) is preserved because every new tool is CI-only and ties to a discrete FR.

---

**Status**: Phase 0 + Phase 1 complete. Ready for `/speckit.tasks`.

**Next commands**:

1. `/speckit.tasks` — produces `tasks.md` with numbered work items mapped to A1–A9 slots and gates.
2. `/speckit.analyze` — cross-checks spec ↔ plan ↔ tasks coherence.
3. User-initiated design of `27-implement.md` context prompt + 9 per-agent instruction files under `docs/PROMPTS/spec-27-cicd-hardening/agents/`.
4. `/speckit.implement` (inside tmux) — orchestrator spawns Wave 1 via Agent Teams Lite; flips visibility at Gate 1; etc.
