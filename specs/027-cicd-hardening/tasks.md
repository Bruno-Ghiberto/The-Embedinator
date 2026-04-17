---
description: "Task list for Spec 27 — CI/CT/CD Pipeline Hardening"
---

# Tasks: CI/CT/CD Pipeline Hardening

**Input**: Design documents from `/specs/027-cicd-hardening/`
**Prerequisites**: plan.md, spec.md, research.md, quickstart.md (all present)

**Tests**: This spec validates via **red-CI demonstrations** (intentional regressions on short-lived branches) rather than unit tests — the "test" of a CI gate is that a broken input makes it fail. Red-CI demos are explicit tasks in each user story phase. No new unit/integration tests are added to the codebase (per Out-of-Scope).

**Organization**: Tasks are grouped by user story (US1–US5). Each phase maps to one or more waves + agent slots from `plan.md`. Story labels mirror the spec's P1–P5 priority tiers.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1…US5)
- Include exact file paths or `gh` commands in descriptions
- Tasks are tagged inline with their wave/agent slot (Wave 1 A1, Gate 1, etc.)

## Path Conventions

All paths are absolute-from-repo-root, matching the repo layout from `plan.md` § "Source / Config Paths Affected". Spec-27 touches `.github/`, `docs/`, `pyproject.toml`, `requirements.txt`, `frontend/vitest.config.ts`, `frontend/playwright.config.ts`, `cli/.goreleaser.yml`, `README.md`, and `specs/027-cicd-hardening/`. Production source trees are in the NEVER-TOUCH list.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Environment preflight and baseline capture before any wave work.

- [ ] T001 Verify tmux session active and Agent Teams feature flag exported: `[ -n "$TMUX" ] && [ "$CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS" = "1" ]`
- [ ] T002 [P] Verify `gh` CLI authenticated: `gh auth status`
- [ ] T003 [P] Confirm branch is `027-cicd-hardening` and working tree clean: `git branch --show-current && git status -s`
- [ ] T004 [P] Capture test baseline for regression comparison at each gate: `zsh scripts/run-tests-external.sh -n spec27-baseline --no-cov tests/` then record `Docs/Tests/spec27-baseline.status` + failure count
- [ ] T005 [P] Read context docs: specs/027-cicd-hardening/spec.md (authoritative), plan.md (wave structure), research.md (tool decisions), quickstart.md (reproduction recipes)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Wave 1 + Gate 1 — build the reusable CI workflow that every publish flow calls, harden cross-cutting supply-chain hygiene, flip the repo to PUBLIC, and configure branch protection. Everything downstream depends on this phase.

**⚠️ CRITICAL**: No user story work can begin until Gate 1 passes and the repo is PUBLIC.

### Wave 1 A1 — Reusable Workflow + Publish Refactor (devops-architect, Sonnet)

- [ ] T010 Create `.github/workflows/_ci-core.yml` — `on: workflow_call` with inputs (`commit_sha` optional), outputs (`backend_cov_pct`, `frontend_cov_pct`, `all_passed`), and explicit `permissions:` block (contents:read, checks:write, pull-requests:write, id-token:write). Top-of-file comment block documenting purpose/triggers/blockers per NFR-005.
- [ ] T011 Refactor `.github/workflows/ci.yml` — becomes thin dispatcher on `pull_request` and `push: main` that calls `uses: ./.github/workflows/_ci-core.yml`. Preserve existing job-fan-out visibility in the Checks UI.
- [ ] T012 Refactor `.github/workflows/docker-publish.yml` — trigger on `push: main` AND `tags: [v*]`; FIRST job `ci: uses: ./.github/workflows/_ci-core.yml`; publish job adds `needs: ci` + `if: needs.ci.outputs.all_passed == 'true'`.
- [ ] T013 Refactor `.github/workflows/release.yml` — same pattern as T012; `_ci-core.yml` runs before `gh release create`.
- [ ] T014 Refactor `.github/workflows/release-cli.yml` — gate goreleaser on `_ci-core.yml` (CLI-scoped subset); **PRESERVE** PR #2 fixes (Go 1.25, `shell:bash` on Windows, golangci-lint-from-source) — do NOT revert commits `d8f6034` or `1b6b234`.

### Wave 1 A2 — Cross-Cutting Hardening (security-engineer, Opus)

- [ ] T020 [P] Resolve 40-char SHA for every external action across `.github/workflows/*.yml` via `gh api repos/<owner>/<action>/commits/<tag> --jq .sha`; build an action→SHA lookup table
- [ ] T021 Apply SHA-pin sweep: replace every `uses: <owner>/<action>@vX.Y.Z` with `uses: <owner>/<action>@<40-char-sha> # vX.Y.Z` across all workflow files in a single commit
- [ ] T022 [P] Add `timeout-minutes:` to every job in every workflow file — default 15, docker-build 25, Playwright 20, CodeQL 30; separate commit for bisectability
- [ ] T023 [P] Pin runtime versions to full semver in every workflow: `python-version: "3.14.1"`, `node-version: "22.12.0"` (or current), `go-version: "1.25.3"` (or current — confirm via `gh run view --log`); consolidate duplicates across files; separate commit
- [ ] T024 [P] Pin `golangci-lint` version in `.github/workflows/ci-cli.yml` source-install step (e.g. `@v2.11.4`); never `@latest`
- [ ] T025 [P] Create `.github/CODEOWNERS` with `* @Bruno-Ghiberto` (solo-dev default); commit separately
- [ ] T026 Add top-of-file comment blocks to every workflow file documenting purpose/triggers/blockers per NFR-005

### Gate 1 — Orchestrator (Opus)

- [ ] T030 Orchestrator: verify A1 + A2 committed; `_ci-core.yml` parses via `yq eval '.' .github/workflows/_ci-core.yml > /dev/null`; all 4 callers reference it; `grep -rE 'uses: [a-zA-Z0-9._/-]+@v[0-9]+\b' .github/workflows/` returns zero lines; `grep -rLE 'timeout-minutes:' .github/workflows/` returns zero files; `.github/CODEOWNERS` exists
- [ ] T031 Pre-flip audit step 1: confirm starting private state `gh api repos/$(gh repo view --json nameWithOwner --jq .nameWithOwner) --jq .private` returns `true`
- [ ] T032 Pre-flip audit step 2: no tracked `.env*` files — `git ls-files | grep -E '^\.env' | head` returns empty
- [ ] T033 Pre-flip audit step 3: inline-secret grep across `backend/`, `frontend/`, `.github/` returns zero matches per `plan.md` § "Gate Check Protocol" pattern
- [ ] T034 Pre-flip audit step 4: scan git history for accidentally committed private prompt files — `git log --all --full-history -- 'Docs/PROMPTS/' | head` — confirm spec-20's rename to lowercase `docs/PROMPTS/` is clean
- [ ] T035 Pre-flip audit step 5: prompt the user explicitly — "About to flip repo PUBLIC. Any commits to rewrite first?" — wait for affirmative confirmation
- [ ] T036 Flip visibility: `gh repo edit --visibility public --accept-visibility-change-consequences`; verify via `gh repo view --json visibility --jq '.visibility'` returns `"public"`
- [ ] T037 Configure branch protection on `main` via `gh api --method PUT repos/:owner/:repo/branches/main/protection` with placeholder required-check roster (`ci-core-backend`, `ci-core-frontend`, `ci-core-integration`, `ci-core-rust`, `commit-lint`); `enforce_admins=true`, `required_pull_request_reviews.required_approving_review_count=1`, `allow_force_pushes=false`, `allow_deletions=false`
- [ ] T038 Configure branch protection on `develop` with the same ruleset as T037
- [ ] T039 Run shared gate checks from `plan.md` § "Gate Check Protocol": Makefile diff = 0, scope guard, YAML validity, SHA-pin sanity, timeout coverage, pre-flip secret audit (already done in T033), visibility verified
- [ ] T040 Commit Wave 1 boundary marker: all Gate 1 checks PASS; record timestamp of visibility flip in session log for A9's ADR in Wave 4

**Checkpoint**: Foundation ready. Repo is PUBLIC. Branch protection active. Reusable CI workflow created. Cross-cutting hygiene applied. User story implementation can now begin.

---

## Phase 3: User Story 1 — Block Broken Artifacts (Priority: P1) 🎯 MVP

**Goal**: Demonstrate that the gating scaffold built in Phase 2 actually blocks broken artifacts from reaching the registry or GitHub Releases.

**Independent Test**: On a short-lived branch, introduce a deliberate test failure, merge it to `main`, verify that `docker-publish.yml` does NOT publish a new image tag for that SHA. Push a deliberately-broken tag and verify no GitHub release is created. Both demonstrations are committed to `validation-report.md` as evidence.

### Implementation for User Story 1

**NOTE**: The gating SCAFFOLD (FR-001) is in Phase 2 (Wave 1 A1). US1's tasks here are the VALIDATION — red-CI demonstrations executed by Wave 4 A8.

- [ ] T050 [US1] Wave 4 A8: create short-lived branch `027-demo-red-ci-publish`; introduce a failing backend unit test; push; open draft PR; attempt merge to `main` (or confirm via dry-run using the branch protection preview); capture `gh run view` URL showing CI failed AND publish job did NOT trigger — evidence for AC-001
- [ ] T051 [US1] Wave 4 A8: push a deliberately-broken tag (e.g. `v0.3.0-red-demo`) on a red-CI commit; verify `release.yml` does NOT create a GitHub release; `gh release list` shows no new release; capture evidence for AC-002
- [ ] T052 [US1] Wave 4 A8: push a broken CLI tag (`cli/v9.9.9-red-demo`) on a red-CI commit; verify `release-cli.yml` does NOT create a release; capture evidence (FR-001 extended to CLI)
- [ ] T053 [US1] Wave 4 A8: clean up all US1 demo branches via `gh pr close --delete-branch` and `git push origin --delete <tag>` for the test tags; record evidence URLs in `specs/027-cicd-hardening/validation-report.md` under AC-001, AC-002
- [ ] T054 [US1] Wave 4 A8: write the AC-001 + AC-002 sections of `specs/027-cicd-hardening/validation-report.md` (draft — final finalization at Gate 4)

**Checkpoint**: User Story 1 complete. The gate that was scaffolded in Phase 2 is proven to block broken artifacts. This is the MVP — if spec-27 stops here, the primary problem ("broken artifacts reach users") is solved.

---

## Phase 4: User Story 2 — Quality Gates (Priority: P2)

**Goal**: Wire enforceable gates per language surface: Python (coverage, mypy, format, integration tests, pip-audit), Rust (ci-rust.yml), Go (govulncheck), Frontend (coverage, Playwright E2E), Docker (smoke test on build).

**Independent Test**: After Wave 2 + A6 smoke test completes, each gate is demonstrated with an intentional regression: drop coverage → fail, unformatted code → fail, mypy error → fail, broken QdrantStorage → fail, known-CVE dependency → fail, clippy warning → fail, crash-on-boot container → fail.

### Wave 2 A3 — Python Gates (python-expert, Sonnet)

- [ ] T060 [US2] Create a NEW `pyproject.toml` at repo root (file does NOT exist currently — verify via `test -f pyproject.toml`). Content: minimal PEP 621 `[project]` stub (name = "the-embedinator-backend", description, no new runtime deps) + `[tool.mypy]` block with `plugins = ["pydantic.mypy"]`, `python_version = "3.14"`, `no_implicit_optional = true`, `warn_unused_ignores = true`, `ignore_missing_imports = false`, exclude patterns (`^build/`, `^dist/`, `^\\.venv/`) + `[tool.pydantic-mypy]` sub-block with `init_forbid_extra=true`, `init_typed=true`, `warn_required_dynamic_aliases=true` per `research.md` § 3. Rationale: PEP 621 is the modern standard for Python tool config consolidation; a one-off `mypy.ini` would fragment future tooling choices (ruff migration, pytest config) that might move to pyproject.toml.
- [ ] T061 [P] [US2] Add `mypy`, `pydantic[mypy]`, `pip-audit` to `requirements.txt` as dev-deps (or `requirements-dev.txt` if that pattern exists; verify before picking)
- [ ] T062 [US2] Add `backend-test` step in `.github/workflows/_ci-core.yml` Python job: `pytest tests/ --cov=backend --cov-fail-under=80` (EXPLICITLY REMOVE `--no-cov` — this is the FR-002 fix; `pytest.ini` already declares the threshold)
- [ ] T063 [US2] Add `backend-format-check` step in `_ci-core.yml` Python job: `ruff format --check backend/` as a SEPARATE step from the existing `ruff check` step; fails CI on format drift
- [ ] T064 [US2] Add `backend-type-check` step in `_ci-core.yml` Python job: `mypy backend/` using the config from T060
- [ ] T065 [US2] Add `backend-integration` job in `_ci-core.yml` with `services: qdrant:` block (qdrant/qdrant image, port 6333 exposed, healthcheck); runs `pytest tests/ -m require_docker --no-cov`; **NO path filter** per Q3 — runs on every PR
- [ ] T066 [US2] Add `backend-pip-audit` step in `_ci-core.yml` Python job: `pip-audit --requirement requirements.txt` (FR-009 Python portion)

### Wave 2 A4 — Rust + Go Gates (devops-architect, Sonnet)

- [ ] T070 [P] [US2] Create `.github/workflows/ci-rust.yml` — triggers on `pull_request: paths: ['ingestion-worker/**']` and `push: branches: [main]: paths: ['ingestion-worker/**']`. Jobs: `fmt` (`cargo fmt --check`), `clippy` (`cargo clippy --all-targets --all-features -- -D warnings`), `test` (`cargo test --all-features`), `audit` (`cargo audit`). Toolchain via `dtolnay/rust-toolchain@<sha>` with `toolchain: 1.93.1`. Matrix on `ubuntu-latest` only
- [ ] T071 [US2] Add top-of-file comment block to `.github/workflows/ci-rust.yml` per NFR-005
- [ ] T072 [US2] Add `govulncheck` step to `.github/workflows/ci-cli.yml` Go job: `go install golang.org/x/vuln/cmd/govulncheck@<pinned-version>` then `govulncheck ./...`; fails PR on reported vuln; **PRESERVE** PR #2 fixes (commits `d8f6034`, `1b6b234`)

### Wave 2 A5 — Frontend Gates (frontend-architect, Sonnet)

- [ ] T080 [P] [US2] Edit `frontend/vitest.config.ts` — add `coverage: { lines: 70, branches: 70, functions: 70, statements: 70, thresholdAutoUpdate: false }`. Confirm 70% is achievable on current suite via `pnpm test --coverage` before landing
- [ ] T081 [US2] Add `frontend-coverage` step in `_ci-core.yml` frontend job: `pnpm test --coverage --coverage.thresholdAutoUpdate=false`; fails on threshold breach
- [ ] T082 [US2] Add `frontend-e2e` job in `_ci-core.yml` — triggered by path `frontend/**`; spins up backend+frontend stack (reuse `docker compose`); runs `pnpm exec playwright test`; uploads report as artifact on failure; timeout 20min
- [ ] T083 [US2] Verify `frontend/playwright.config.ts` `use.baseURL` matches CI target (backend service URL); adjust only if needed

### Wave 3 A6 — Docker Smoke Test (security-engineer, Opus) — US2 portion

- [ ] T090 [US2] Add `docker-build-smoke` job to `_ci-core.yml`: `docker compose build`, then `docker compose up -d --wait`, then `curl -sf http://localhost:8000/api/health` with retry loop (60×2s max), then `docker compose down -v` with `if: always()`. Timeout 25min. FR-007

### Gate 2 — Orchestrator

- [ ] T100 Gate 2: create throw-away branch `027-smoke-gate2`, push a no-op change, open draft PR, confirm all new jobs execute (expect green — no deliberate regressions yet). `gh pr checks --watch`
- [ ] T101 Gate 2: run shared gate checks (Makefile diff=0, scope guard, YAML validity, SHA-pin, timeouts); verify no new test regressions vs T004 baseline via external test runner
- [ ] T102 Gate 2: update branch protection `required_status_checks.contexts` via `gh api --method PUT` with the ACTUAL job names emitted by A3/A4/A5 (replace Gate 1's placeholders); roster per `plan.md` § "Workflow Contracts"
- [ ] T103 Gate 2: close the smoke PR and delete the branch via `gh pr close --delete-branch`

### Wave 4 A8 — US2 Red-CI Demonstrations

- [ ] T110 [P] [US2] Create branch `027-red-coverage`: drop a tested function's assertion to take coverage below 80%; open PR; verify CI fails at `backend-test` coverage step; capture evidence for AC-003; close + delete
- [ ] T111 [P] [US2] Create branch `027-red-unformatted`: insert deliberately-unformatted Python in any backend file; open PR; verify CI fails at `backend-format-check`; capture AC-007 evidence; close + delete
- [ ] T112 [P] [US2] Create branch `027-red-typing`: add a function passing `str` where `int` is expected in a freshly-authored helper; open PR; verify CI fails at `backend-type-check`; capture AC-006 evidence; close + delete
- [ ] T113 [P] [US2] Create branch `027-red-qdrant`: break `QdrantStorage.batch_upsert` signature in a backward-incompatible way; open PR; verify `backend-integration` fails; capture AC-004 evidence; close + delete
- [ ] T114 [P] [US2] Create branch `027-red-cve`: pin a known-CVE dependency in `requirements.txt` (e.g. old `cryptography` version with documented CVE); open PR; verify `backend-pip-audit` fails; capture AC-010 evidence; close + delete
- [ ] T115 [P] [US2] Create branch `027-red-rust-clippy`: introduce a clippy-flagged expression in `ingestion-worker/src/`; open PR; verify `ci-rust.yml` clippy job fails; capture AC-005 evidence; close + delete
- [ ] T116 [P] [US2] Create branch `027-red-smoke-broken`: introduce a deliberate boot-crash (e.g. missing env var handling) to a backend config; open PR; verify `docker-build-smoke` fails at health-check; capture AC-008 evidence; close + delete
- [ ] T117 [US2] Record all US2 red-CI evidence URLs in `specs/027-cicd-hardening/validation-report.md` under AC-003…AC-008, AC-010 sections

**Checkpoint**: User Story 2 complete. Every language's quality gate is enforceable and demonstrably catches regressions.

---

## Phase 5: User Story 3 — Harden Supply Chain (Priority: P3)

**Goal**: Sign published images with cosign (keyless OIDC), attach SPDX SBOMs, scan with trivy, extend CodeQL to Go, add goreleaser SBOMs.

**Independent Test**: Tag a smoke release; verify `cosign verify ghcr.io/<owner>/embedinator-backend:<tag>` succeeds; `cosign download attestation <image>` returns an SBOM; a PR with a HIGH/CRITICAL image vulnerability fails trivy; CodeQL logs show Go analysis.

### Wave 3 A6 — Supply Chain (security-engineer, Opus)

- [ ] T120 [US3] Edit `.github/workflows/docker-publish.yml` — add `aquasecurity/trivy-action@<sha>` step AFTER build, BEFORE push, with `severity: 'HIGH,CRITICAL'`, `exit-code: 1`, `ignore-unfixed: true`; scan backend AND frontend images
- [ ] T121 [US3] Edit `.github/workflows/docker-publish.yml` — add `sigstore/cosign-installer@<sha>` step, then `cosign sign --yes ghcr.io/<owner>/embedinator-backend@${DIGEST}` after push; same for frontend; requires `permissions: id-token: write` at workflow level (inherited from `_ci-core.yml`)
- [ ] T122 [US3] Edit `.github/workflows/docker-publish.yml` — add SBOM generation via `anchore/sbom-action@<sha>` (SPDX or CycloneDX); attach via `cosign attest --predicate sbom.json ghcr.io/<owner>/embedinator-backend@${DIGEST}`; same for frontend
- [ ] T123 [US3] Edit `cli/.goreleaser.yml` — add `checksum:` block and `sboms:` block per goreleaser docs; produces `.sha256` + SBOM artifacts on CLI releases
- [ ] T124 [US3] Edit `.github/workflows/release-cli.yml` — ensure goreleaser invocation surfaces checksum + SBOM artifacts in the GitHub Release
- [ ] T125 [US3] Edit `.github/workflows/security.yml` — extend CodeQL `language` matrix to add `go`; preserve existing `python` and `javascript`/`typescript`; document Rust is covered by `cargo audit` + clippy per FR-011

### Gate 3 — Orchestrator (Opus)

- [ ] T130 Gate 3: create smoke PR `027-smoke-gate3` with a single-file backend change; confirm `docker-build-smoke` runs full up/health/down cycle and passes
- [ ] T131 Gate 3: tag `v0.3.0-spec27-smoke` on `027-cicd-hardening`; push tag; confirm `docker-publish.yml` runs: `_ci-core.yml` passes → build → trivy scan → push → cosign sign → SBOM attest
- [ ] T132 Gate 3: verify cosign signature via `cosign verify ghcr.io/<repo>-backend:v0.3.0-spec27-smoke --certificate-identity-regexp=".*" --certificate-oidc-issuer="https://token.actions.githubusercontent.com"`; confirm success
- [ ] T133 Gate 3: download attested SBOM via `cosign download attestation ghcr.io/<repo>-backend:v0.3.0-spec27-smoke | jq -r '.payload' | base64 -d | jq '.predicate.packages | length'`; confirm >0 packages listed
- [ ] T134 Gate 3: verify `security.yml` CodeQL Go job ran via `gh run view --log --job <go-analysis-job-id>`
- [ ] T135 Gate 3: delete the smoke tag and its release via `git push origin --delete v0.3.0-spec27-smoke` and `gh release delete v0.3.0-spec27-smoke --yes`; also delete the image via `gh api -X DELETE /user/packages/container/embedinator-backend/versions/<version-id>` (or `orgs/<org>/...` for org repos)
- [ ] T136 Gate 3: run shared gate checks; no new test regressions vs baseline; Makefile diff=0

### Wave 4 A8 — US3 Red-CI Demonstration

- [ ] T140 [US3] Create branch `027-red-image-cve`: introduce a base-image reference with a known CVE (e.g. an outdated Alpine tag); open PR targeting `027-cicd-hardening`; verify `trivy` scan fails on the HIGH/CRITICAL finding; capture evidence for AC-010 (image-scanning portion) extending the dependency-scan AC; close + delete
- [ ] T141 [US3] Record AC-011, AC-012 evidence in `specs/027-cicd-hardening/validation-report.md` — cosign verify transcript from T132, SBOM package count from T133, CodeQL Go log from T134

**Checkpoint**: User Story 3 complete. Published images are signed, scanned, and traceable.

---

## Phase 6: User Story 4 — Workflow Polish (Priority: P4)

**Goal**: Enforce pre-commit parity in CI, block non-conventional PR titles, validate goreleaser config on relevant PRs, and ensure every workflow has the polish items already applied in Phase 2 (timeouts, CODEOWNERS).

**Independent Test**: Open a PR with title "fix stuff" (non-conventional) — CI fails at `pr-title.yml`. Touch `cli/.goreleaser.yml` with a syntax error on a PR — `goreleaser check` step fails. Run `pre-commit` locally-dirty and push — CI `pre-commit-parity` job fails.

### Wave 3 A7 — Polish (devops-architect, Sonnet)

- [ ] T150 [US4] Add `pre-commit-parity` job to `.github/workflows/_ci-core.yml`: runs `pre-commit/action@<sha>` with `extra_args: --all-files`; uses Python 3.14.1; caches the venv per `research.md` § 11
- [ ] T151 [US4] Create `.github/workflows/pr-title.yml` — triggered by `pull_request: types: [opened, edited, synchronize]`; uses `amannn/action-semantic-pull-request@<sha>`; allowed types: `feat, fix, chore, docs, refactor, test, ci, build, perf, style, revert`; blocks merge on non-conforming per Q5
- [ ] T152 [US4] Add top-of-file comment block to `.github/workflows/pr-title.yml` per NFR-005
- [ ] T153 [US4] Add `goreleaser check` step to `.github/workflows/ci-cli.yml` — conditional on `cli/.goreleaser.yml` in the PR's changed files via `dorny/paths-filter@<sha>` or an inline `contains(github.event.pull_request.changed_files, 'cli/.goreleaser.yml')` check; runs `goreleaser check --config cli/.goreleaser.yml` after pinning goreleaser version per `research.md` § 13

### Wave 4 A8 — US4 Red-CI Demonstrations

- [ ] T160 [P] [US4] Create branch `027-red-broken-title`: open a PR titled "fix stuff" (no conventional prefix); verify `pr-title.yml` fails the PR; capture AC-016 evidence; close + delete
- [ ] T161 [P] [US4] Create branch `027-red-goreleaser`: introduce a syntax error to `cli/.goreleaser.yml`; open PR; verify `goreleaser check` step fails; capture evidence (AC-specific — extends AC-016 coverage); close + delete
- [ ] T162 [P] [US4] Create branch `027-red-precommit`: commit a file that would fail `pre-commit run --all-files` (e.g. trailing whitespace); open PR; verify `pre-commit-parity` job fails; capture evidence; close + delete
- [ ] T163 [US4] Verify `grep -c "timeout-minutes:" .github/workflows/*.yml` returns a line per job (no job lacks timeout) — evidence for AC-014
- [ ] T164 [US4] Verify `.github/CODEOWNERS` exists and is honored by GitHub — open a throw-away PR and confirm GitHub auto-requests review from `@Bruno-Ghiberto`; capture AC-015 evidence
- [ ] T164b [P] [US4] Verify `frontend-e2e` runs on `frontend/**` PRs — create branch `027-demo-frontend-e2e`, touch a trivial file under `frontend/` (e.g. append a comment to `frontend/README.md`), open draft PR, confirm `frontend-e2e` job fires (not SKIPPED) and passes; capture `gh run view` URL as AC-013 evidence; `gh pr close --delete-branch`
- [ ] T165 [US4] Record AC-013, AC-014, AC-015, AC-016 evidence in `specs/027-cicd-hardening/validation-report.md`

**Checkpoint**: User Story 4 complete. Polish items enforced; contributor workflow predictable.

---

## Phase 7: User Story 5 — Reporting, Policy, Debt (Priority: P5)

**Goal**: Coverage-delta PR comments via Codecov; written branch-protection ADR; GitHub issue tracking the 33 deferred Go lint items; `docs/cicd.md` newcomer walkthrough; README CI/CD section.

**Independent Test**: Open a PR that changes test coverage — Codecov comment appears. `docs/adr/0001-branch-protection.md` exists and is committed. `gh issue list --label tech-debt` shows the Go lint debt issue. `docs/cicd.md` reads in under 30 minutes and maps every gate to its FR.

### Wave 3 A7 — Reporting + Debt (devops-architect, Sonnet)

- [ ] T170 [US5] Add `codecov/codecov-action@<sha>` step to `_ci-core.yml` backend-test job — uploads `coverage.xml` (from pytest-cov); tokenless per `research.md` § 6 (public repo)
- [ ] T171 [US5] Add `codecov/codecov-action@<sha>` step to `_ci-core.yml` frontend-coverage job — uploads `lcov.info` (from vitest v8 coverage); tokenless
- [ ] T172 [US5] Create GitHub issue via `gh issue create --title "Tech-debt: 33 deferred Go lint items from cli/.golangci.yml" --label tech-debt --body <<'EOF' … EOF`; body lists the 32 errcheck + 1 unused items (from `cli/internal/engine/selfupdate.go` + `cli/internal/wizard/complete.go`), references PR #2 commits `d8f6034`+`1b6b234`, marks as follow-up to spec-27; record issue URL for AC-020

### Wave 4 A9 — Documentation (technical-writer, Sonnet)

- [ ] T180 [US5] Create `docs/adr/0001-branch-protection.md` — ADR format (Status, Context, Decision, Consequences, References). Status: Accepted 2026-04-16. Context: spec-20 open-source launch + spec-27 enforceability. Decision: PUBLIC + branch protection on `main` and `develop`. Consequences: positive (free enforcement) and negative (history public; reference the pre-flip audit from T031–T035). References: spec.md § FR-019, visibility flip timestamp from T036
- [ ] T181 [US5] Create `docs/cicd.md` (≤300 lines) — sections: Overview, Trigger map (table: workflow → triggers → required-status role), Gate roster (exact `required_status_checks.contexts` list from T102), Red-path examples (summary of T110–T116 + T140 + T160–T162), Signing + SBOM (how to `cosign verify`), Supply-chain (how to read trivy/pip-audit/cargo-audit output), Local mirror (matches `quickstart.md` § "Locally Mirroring CI"), **Merge strategy** (document that `squash-merge` is the required merge mode for `main` and `develop` — this is what makes FR-016's PR-title-only commit-lint sufficient to satisfy the constitution's "conventional commits REQUIRED" rule; the squashed PR title becomes the authoritative commit message on the protected branch), FAQ (including "Why is the repo public?" → ADR-0001; "Which merge mode?" → squash-only, link to Merge strategy section). Optionally add a task (not required) to set the repo's allowed merge types via `gh api --method PATCH /repos/:owner/:repo -f allow_squash_merge=true -f allow_merge_commit=false -f allow_rebase_merge=false` — leave commented as follow-up if not applied here.
- [ ] T182 [US5] Edit `README.md` — add a "CI/CD" section linking to `docs/cicd.md`; highlight "all images are signed with cosign; verify before running"; add one-line link to the ADR for branch-protection policy

### Wave 4 A8 — US5 Validation + Wall-Clock Measurement

- [ ] T190 [US5] Measure typical-PR wall-clock time: open a throw-away backend-only PR, timestamp from `git push` to all-checks-green (visible in `gh pr checks --watch` completion); record in `validation-report.md` under SC-007; evidence for AC-019
- [ ] T191 [US5] Verify Codecov comment lands on a PR — open a throw-away PR that changes test coverage modestly; confirm Codecov bot posts a single comment with coverage delta; capture AC-017 evidence
- [ ] T192 [US5] Verify `gh issue list --label tech-debt` includes the issue from T172 — evidence for AC-020

### Gate 4 — Orchestrator

- [ ] T200 Gate 4: finalize `specs/027-cicd-hardening/validation-report.md` — review A8's draft (built up from T054, T117, T141, T165, T190–T192); confirm all 20 ACs and all 12 SCs have PASS / FAIL / WAIVED with evidence artifact references
- [ ] T201 Gate 4: verify `gh repo view --json visibility --jq '.visibility'` returns `"public"`
- [ ] T202 Gate 4: verify `gh api repos/:owner/:repo/branches/main/protection | jq '.required_status_checks.contexts'` returns the populated roster matching `plan.md` § "Workflow Contracts"; same for `develop`
- [ ] T203 Gate 4: verify `docs/cicd.md`, `docs/adr/0001-branch-protection.md`, and the README CI/CD link all exist via `ls docs/cicd.md docs/adr/0001-branch-protection.md && grep -l 'CI/CD' README.md`
- [ ] T204 Gate 4: run shared gate checks (Makefile diff=0, scope guard, YAML validity, SHA-pin, timeouts); no new test regressions vs T004 baseline
- [ ] T205 Gate 4: confirm no short-lived demo branches remain in the repo (all cleaned up in T053, T117, T140, T160–T162, T190–T191)

**Checkpoint**: User Story 5 complete. Reporting, policy, and debt items all satisfied.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final close-out — open PR, tag version, archive spec.

- [ ] T210 Final cross-phase audit: every FR (FR-001…FR-020) ticked in `validation-report.md` with FR→AC mapping reference
- [ ] T211 Open PR from `027-cicd-hardening` → `develop` via `gh pr create --base develop --head 027-cicd-hardening --title "feat(spec-27): CI/CT/CD pipeline hardening — 20 FRs, 12 SCs, 20 ACs" --body-file .github/pr-body-spec27.md` (body-file summarizes the validation-report and the key clarifications locked)
- [ ] T212 After PR merges to `develop` and then `develop` → `main` per the project's merge cadence, tag the next version: `git tag v0.3.1` (or next — check `git tag --list 'v0.*'` for the latest) and push (`git push origin v0.3.1`); confirm release workflow gates on `_ci-core.yml` success
- [ ] T213 Archive spec context per project convention: run the SDD archive protocol or manually persist `specs/027-cicd-hardening/validation-report.md` as the spec-27 close-out artifact; update `memory/MEMORY.md` project status line

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Phase 2 — MVP exit point
- **US2 (Phase 4)**: Depends on Phase 2 (`_ci-core.yml` must exist); can be developed in parallel with US3/US4/US5 but is conventionally done first by priority
- **US3 (Phase 5)**: Depends on Phase 2 + US2's docker-smoke-test job (T090) existing in `_ci-core.yml`
- **US4 (Phase 6)**: Depends on Phase 2 (T150 adds a job to `_ci-core.yml` which must exist)
- **US5 (Phase 7)**: Depends on Phase 2 + US2 (Codecov uploads piggyback on A3/A5 coverage jobs) + Gate 1 visibility flip (ADR documents the flip)
- **Polish (Phase 8)**: Depends on all user stories complete

### Wave-to-Phase Mapping

| Wave | Agent slots | Phases covered |
|------|-------------|----------------|
| Wave 1 | A1, A2 | Phase 2 (Foundational) |
| Gate 1 | orchestrator | Phase 2 (visibility flip + branch protection) |
| Wave 2 | A3, A4, A5 | Phase 4 (US2) |
| Gate 2 | orchestrator | Phase 4 |
| Wave 3 | A6, A7 | Phase 4 (US2 smoke portion) + Phase 5 (US3) + Phase 6 (US4) + Phase 7 (US5 reporting) |
| Gate 3 | orchestrator | Phase 5 (cosign verify) |
| Wave 4 | A8, A9 | Phase 3 (US1 demos) + Phase 4 US2 demos + Phase 5 US3 demos + Phase 6 US4 demos + Phase 7 US5 (ADR + docs) |
| Gate 4 | orchestrator | Phase 7 (validation-report.md finalize) |

### Parallel Opportunities

- **Phase 1 Setup**: T002, T003, T004, T005 all parallel after T001.
- **Phase 2 Foundational**:
  - A1's T010–T014 are sequential per workflow file but can interleave with A2's T020–T026 (different files).
  - A2's T020, T022, T023, T024, T025 are largely parallel (different file edits / one-off command outputs).
- **Phase 4 US2**: A3 (T060–T066), A4 (T070–T072), A5 (T080–T083) run in 3 panes parallel; A6's T090 runs in Wave 3 but is logically US2.
  - T110–T116 red-CI demos are all parallel (different branches).
- **Phase 5 US3**: T120–T125 are largely parallel edits to different workflow files (docker-publish.yml, cli/.goreleaser.yml, release-cli.yml, security.yml); T121, T122 edit the same file sequentially.
- **Phase 6 US4**: T160, T161, T162 red-CI demos are all parallel; T164b (frontend-e2e positive demo on `frontend/**` branch) can run in parallel with them since it uses a distinct branch.
- **Phase 7 US5**: T170, T171 parallel (different jobs in `_ci-core.yml`); T172 parallel with T180, T181, T182 (all different surfaces).

### Within Each Story

- US1: scaffold (Phase 2) → red-CI demos (Phase 3) → evidence capture.
- US2: each agent slot (A3/A4/A5) runs in parallel; docker-smoke (A6 partial) follows; Gate 2 smoke PR confirms; red-CI demos follow.
- US3: A6 edits are sequential within `docker-publish.yml` (T121 after T120 after docker build exists) but parallel across other files; Gate 3 tagged smoke validates.
- US4: A7 edits parallel; red-CI demos parallel.
- US5: A7 Codecov + A7 issue + A9 ADR + A9 docs + A9 README all parallel; Gate 4 finalizes.

---

## Parallel Example: Wave 2 (User Story 2)

```bash
# Three tmux panes running in parallel:

# Pane 1 — A3 (python-expert):
Task: "Configure mypy + Pydantic plugin in pyproject.toml (T060)"
Task: "Add mypy, pydantic[mypy], pip-audit to requirements.txt (T061)"
Task: "Add backend-test step removing --no-cov in _ci-core.yml (T062)"
Task: "Add backend-format-check step in _ci-core.yml (T063)"
Task: "Add backend-type-check step in _ci-core.yml (T064)"
Task: "Add backend-integration job with Qdrant services in _ci-core.yml (T065)"
Task: "Add backend-pip-audit step in _ci-core.yml (T066)"

# Pane 2 — A4 (devops-architect):
Task: "Create .github/workflows/ci-rust.yml (T070)"
Task: "Add top-of-file doc block to ci-rust.yml (T071)"
Task: "Add govulncheck step to ci-cli.yml preserving PR #2 fixes (T072)"

# Pane 3 — A5 (frontend-architect):
Task: "Add coverage threshold to frontend/vitest.config.ts (T080)"
Task: "Add frontend-coverage step to _ci-core.yml (T081)"
Task: "Add frontend-e2e job (Playwright) to _ci-core.yml (T082)"
Task: "Verify frontend/playwright.config.ts baseURL (T083)"
```

---

## Parallel Example: Wave 4 Red-CI Demos

```bash
# All US2 red-CI demos run in parallel (different branches, no interdependencies):
Task: "Demo AC-003 coverage drop on branch 027-red-coverage (T110)"
Task: "Demo AC-007 unformatted code on branch 027-red-unformatted (T111)"
Task: "Demo AC-006 type error on branch 027-red-typing (T112)"
Task: "Demo AC-004 broken QdrantStorage on branch 027-red-qdrant (T113)"
Task: "Demo AC-010 known-CVE dep on branch 027-red-cve (T114)"
Task: "Demo AC-005 clippy warning on branch 027-red-rust-clippy (T115)"
Task: "Demo AC-008 crash-on-boot on branch 027-red-smoke-broken (T116)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (preflight + baseline).
2. Complete Phase 2: Foundational (Wave 1 A1 + A2 + Gate 1 public flip + branch protection).
3. Complete Phase 3: User Story 1 (Wave 4 A8 red-CI demos for AC-001, AC-002).
4. **STOP and VALIDATE**: red-CI demos prove the publish gate works. This is the MVP — the primary problem ("broken artifacts reach users") is solved.
5. Deploy / demo. If spec-27 had to ship here, US1 alone would be a meaningful release.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → MVP: gates block broken artifacts.
3. US2 → quality gates per language.
4. US3 → supply chain (signing + SBOMs + scans).
5. US4 → polish (timeouts + CODEOWNERS + commit-lint + pre-commit parity + goreleaser check).
6. US5 → reporting + ADR + docs + debt tracking.
7. Each story adds value without breaking previous stories; each is demonstrably testable independently.

### Wave-Parallel Team Strategy

This spec is executed via **Agent Teams Lite in tmux**, not by a human team:

- **Wave 1 (2 panes)**: orchestrator spawns A1 (devops) + A2 (security) in parallel.
- **Gate 1 (orchestrator)**: pre-flip audit + visibility flip + branch protection.
- **Wave 2 (3 panes)**: A3 (python) + A4 (devops) + A5 (frontend) in parallel.
- **Gate 2 (orchestrator)**: smoke PR + branch protection sync.
- **Wave 3 (2 panes)**: A6 (security) + A7 (devops) in parallel.
- **Gate 3 (orchestrator)**: tagged smoke + cosign verify.
- **Wave 4 (2 panes)**: A8 (quality) + A9 (writer) in parallel.
- **Gate 4 (orchestrator)**: final validation-report.md; open PR to develop.

See `plan.md` § "Wave-by-Wave Plan" for full agent responsibilities and `docs/PROMPTS/spec-27-cicd-hardening/27-plan.md` Appendix A for tmux session setup.

---

## Notes

- **[P] markers**: Tasks in different files with no unfinished dependencies. Do NOT parallelize two tasks that edit the same file.
- **[US*] labels**: map to the user story the task discharges. Tasks in Phase 1, 2, and 8 have no story label.
- **Tests**: NOT traditional unit/integration tests. "Tests" here are red-CI demonstrations on short-lived branches — how every CI gate is validated.
- **Production code untouched**: every gate check runs the scope guard from `plan.md` § "Gate Check Protocol". Any task that attempts to edit `backend/**/*.py`, `frontend/src/**`, `ingestion-worker/src/**`, `Makefile`, `embedinator.sh`, `embedinator.ps1`, `docker-compose.yml`, or `tests/**` MUST be rejected before execution.
- **Preserve PR #2 fixes**: commits `d8f6034`, `1b6b234` in `ci-cli.yml` are NOT to be reverted. T014 and T072 explicitly call this out.
- **Short-lived demo branches**: T050–T052, T110–T116, T140, T160–T162, T190–T191 create branches for red-CI demonstrations. These are CLOSED and DELETED after evidence capture. They are NEVER merged to `027-cicd-hardening`.
- **Clarifications locked**: Q1 PUBLIC, Q2 reusable workflow, Q3 integration every PR, Q4 mypy + Pydantic baseline, Q5 PR-title-only commit-lint block. The plan (and every agent instruction) treats these as fixed inputs — do NOT relitigate in tasks execution.
- Commit after each task or logical group (bisectable history).
- Stop at any checkpoint to validate story independently.
