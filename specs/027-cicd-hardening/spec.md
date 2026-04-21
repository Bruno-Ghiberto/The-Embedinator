# Feature Specification: CI/CT/CD Pipeline Hardening

**Feature Branch**: `027-cicd-hardening`
**Created**: 2026-04-16
**Status**: Draft
**Input**: User description: "Read @docs/PROMPTS/spec-27-cicd-hardening/27-specify.md"

## Clarifications

### Session 2026-04-16

- Q: Which branch-protection path do we commit to, and how is that decision captured in writing? → A: Option A — Make the repo PUBLIC. Completes spec-20's open-source launch goal, enables branch protection at zero cost, and makes every other FR in this spec enforceable.
- Q: Which gating pattern do we commit to for `docker-publish.yml`, `release.yml`, and `release-cli.yml`? → A: Option B — Reusable workflow composition. A `_ci-core.yml` reusable workflow is called by `ci.yml` AND by each publish workflow; CI runs inside publish on the exact SHA, so no race window can leak a broken artifact. Accepts the ~20% extra CI minutes as the cost of P1 strictness.
- Q: When does the integration-test job (FR-003) run? → A: Option A — every PR, no path filter. Public-repo CI has effectively unlimited minutes; "required gate for merge" framing requires per-PR execution; path-filtering introduces bookkeeping without meaningful savings.
- Q: Which Python type checker and strictness level for FR-005? → A: Option A — `mypy` with the Pydantic plugin at baseline strictness (`--no-implicit-optional`, `--warn-unused-ignores`, plugin enabled; NOT `--strict`). Pydantic v2 correctness beats pyright's speed for this project; baseline strictness avoids annotation-churn on existing `backend/`.
- Q: Conventional-commit enforcement scope for FR-016? → A: Option A — PR title only, block non-conforming. The PR title is what lands on `main` under squash-merge, so enforcing there is sufficient; blocking matches the CLAUDE.md MUST policy; per-commit enforcement would create friction with WIP commits.

## Overview

Transform The Embedinator's CI/CT/CD pipeline from an **advisory, partially-blind** setup into a **professionally gated quality pipeline** that prevents broken code from reaching `main`, blocks untested container images from publishing to the registry, and stops broken GitHub releases before they happen — without turning every PR into an hour-long CI run.

This is an **audit-and-harden** effort, NOT a rebuild. The existing workflow fan-out (Python lint/test, frontend lint/test, CLI matrix, security scans, Dependabot, issue templates) is sound. The defects are specific blind spots WITHIN existing jobs (e.g. `--no-cov` silently disables the coverage threshold) and MISSING gates between CI and publication (e.g. `docker-publish.yml` fires on push to `main` with no dependency on CI passing).

## Problem Statement

The repository has six GitHub Actions workflows (`ci.yml`, `ci-cli.yml`, `docker-publish.yml`, `release.yml`, `release-cli.yml`, `security.yml`), plus Dependabot, pre-commit, ruff, and pytest-cov configs. Much of it is individually reasonable — but **the pipeline as a whole has critical blind spots** that allow broken code to ship:

- **Container images publish without CI passing**: `docker-publish.yml` triggers on push to `main` with no dependency on CI. A broken merge to `main` immediately publishes the `:latest` backend/frontend images as broken images.
- **GitHub releases publish without CI passing**: `release.yml` and `release-cli.yml` trigger on tag pushes with no CI dependency — tag a broken commit, ship a broken release.
- **Backend coverage threshold is silently bypassed**: `pytest.ini` declares `--cov-fail-under=80`, but `ci.yml` runs pytest with `--no-cov`, disabling the coverage plugin entirely. The 80% threshold is never enforced.
- **Integration tests never run in CI**: Today's pytest invocation excludes `-m "not require_docker"`, skipping every test that needs Qdrant or Ollama. Core retrieval, reranking, and provider-adapter regressions are invisible to CI.
- **Rust ingestion-worker has ZERO CI coverage**: The `ingestion-worker/` crate has no workflow — no format check, no clippy, no tests, no vulnerability audit. Any regression ships unvalidated.
- **Branch protection unavailable** on GitHub Free + private repo. Required status checks are impossible to enforce; CI is advisory only.
- **Supply chain unhardened**: Actions are pinned to mutable tags (not commit SHAs); `golangci-lint@latest` is a moving target; no vulnerability scanning (`govulncheck`, `cargo audit`, `pip-audit`, `trivy`), no image signing, no SBOM generation.
- **No Python type checking** despite heavy Pydantic v2 + FastAPI + LangGraph usage. Type drift accumulates silently.
- **`docker-build` job only compiles** — no runtime smoke test. A container that builds but crashes on boot ships green.
- **Minor-only version pins** (`go-version: "1.25"`, `node-version: "22"`, `python-version: "3.14"`) produce non-reproducible builds across runs.

**Net effect**: CI passing green is not a reliable signal of shippable code, and nothing in the pipeline actually blocks a broken artifact from reaching users.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Block broken artifacts from ever publishing (Priority: P1)

As the **project maintainer** (and as **downstream consumers** of the project's container images, GitHub releases, and CLI binaries), I need the CI/CD pipeline to guarantee that no artifact reaches a public distribution surface unless CI has passed on the exact commit that produced it. Today, a failed merge to `main` still publishes `:latest` images, and a tag pushed on a broken commit still cuts a release.

**Why this priority**: This is the single highest-impact defect. Every other gate improvement is moot if the final publication step doesn't check CI. This is the MVP: ship nothing else in this spec and we still gain the most important protection.

**Independent Test**: Introduce a deliberate test failure, merge it to `main`, and confirm no new images land in the registry. Separately, tag a known-broken commit and confirm no GitHub release is created. Both gates must fail closed.

**Acceptance Scenarios**:

1. **Given** a commit on `main` whose CI run ended in `failure`, **When** `docker-publish` would normally trigger, **Then** no container images are pushed to the registry for that commit SHA.
2. **Given** a tag pushed on a commit whose CI run ended in `failure`, **When** `release` would normally trigger, **Then** no GitHub release is created and no artifacts are attached.
3. **Given** a CLI tag pushed on a commit whose CLI CI ended in `failure`, **When** `release-cli` would normally trigger, **Then** no CLI release, binaries, or Homebrew tap update occurs.
4. **Given** a commit on `main` whose container image builds successfully but crashes on startup, **When** the publication workflow runs, **Then** the docker-smoke-test gate fails and nothing ships.
5. **Given** the backend unit test suite whose coverage drops below 80% on a PR, **When** CI runs, **Then** CI fails with a clear "coverage threshold not met" error and the PR cannot merge.

---

### User Story 2 - Enforce quality gates that are currently bypassed (Priority: P2)

As the **maintainer** reviewing a PR, I need the CI to enforce the full quality bar the project claims to hold: backend coverage ≥80%, integration tests executed against real Qdrant, Rust ingestion-worker formatted/linted/tested/audited, Python type-checked, format-drift detected, and containers smoke-tested. Today, most of these are either disabled (`--no-cov`), skipped (`-m "not require_docker"`), or entirely missing (no Rust workflow, no type checker).

**Why this priority**: These gates prevent regressions that would otherwise land silently. US1 blocks the final publication; US2 prevents the regression from reaching `main` in the first place. Less catastrophic than US1 (a regression on a branch is recoverable; a broken `:latest` image hurts users), but still central to professional-grade CI.

**Independent Test**: For each gate, introduce a deliberate regression on a feature branch — drop coverage to 79%, break a Qdrant-dependent test, add a Rust `clippy` warning, pass a `str` where `int` is expected, leave a file unformatted, break container startup — and verify each deliberate regression is caught by the corresponding gate on PR.

**Acceptance Scenarios**:

1. **Given** a PR whose backend unit coverage drops below 80%, **When** CI runs, **Then** the backend-test job fails with an explicit coverage-threshold error.
2. **Given** a PR introducing a change that breaks a `require_docker`-marked integration test, **When** CI runs, **Then** the integration-test job (running Qdrant as a service container) fails.
3. **Given** a PR touching `ingestion-worker/**`, **When** CI runs, **Then** format-check, clippy (warnings-as-errors), tests, and vulnerability audit all execute and must pass.
4. **Given** a PR introducing a Python type error (e.g. passing `str` where `int` is expected) in `backend/`, **When** CI runs, **Then** the type-check job fails with a clear error message pointing to the offending line.
5. **Given** a PR with unformatted Python code, **When** CI runs, **Then** a dedicated format-check step fails before the test step runs.
6. **Given** a container image that builds successfully but crashes on startup (e.g. missing env var, import error), **When** CI runs the docker-build job, **Then** the smoke test — which starts the stack, waits for health, curls `/api/health`, and tears down — fails and blocks the PR.

---

### User Story 3 - Harden the supply chain (Priority: P3)

As a **security-conscious downstream consumer** (or as the maintainer reasoning about the project's security posture), I need published artifacts to be signed, scanned, and traceable. Today, container images are unsigned, have no SBOMs, and no vulnerability scans run against dependencies or built images. Every third-party Action is pinned to a mutable tag, meaning a compromised upstream could inject code.

**Why this priority**: This is important for any project asking users to trust its binaries, but the blast radius is lower than US1/US2 (a signed but broken image is worse than an unsigned broken image — US1/US2 are upstream of this concern). It's prioritized third because the project is pre-v1.0 and the current userbase is small, but it becomes essential at v1.0 and beyond.

**Independent Test**: Pull a published image, verify the signature via the signing tool. Run `jq` over workflow files and confirm every `uses:` line has a 40-char commit SHA. Introduce a dependency with a known CVE on a PR and confirm the vulnerability scan fails.

**Acceptance Scenarios**:

1. **Given** a published container image on the registry, **When** a consumer runs the signature-verification command, **Then** the signature is valid and traces back to this repo's OIDC identity.
2. **Given** a published container image, **When** a consumer requests the SBOM, **Then** an SBOM is available and lists every package in the image.
3. **Given** a PR that introduces a dependency with a known CVE in `requirements.txt`, `Cargo.toml`, or any Go module, **When** CI runs, **Then** the relevant vulnerability scanner (pip/Python, cargo/Rust, govulncheck/Go) fails the PR.
4. **Given** any workflow file in the repository, **When** inspected for `uses:` directives referencing third-party actions, **Then** every directive pins a 40-char commit SHA (with the version as a trailing comment for Dependabot).
5. **Given** the security workflow, **When** it runs, **Then** CodeQL analyzes Python, JavaScript/TypeScript, AND Go. Rust is covered by `cargo audit` + `cargo clippy -D warnings` since CodeQL does not natively support Rust.

---

### User Story 4 - Polish workflow ergonomics and contributor experience (Priority: P4)

As a **contributor** (including future external contributors once the repo is public), I need the workflow configuration to be clear, predictable, and self-documenting. Today, job timeouts are absent (runaway jobs possible), CODEOWNERS doesn't exist (no review routing), pre-commit hooks are not enforced in CI (format drift possible), conventional commits are documented but not enforced, and the Playwright frontend E2E suite never runs automatically.

**Why this priority**: These improvements don't prevent broken code from shipping — they improve the development loop and remove paper cuts. Priority 4 because the pain is dispersed across many small issues rather than concentrated in one catastrophic one.

**Independent Test**: Each sub-item is independently testable: grep for `timeout-minutes:` across workflows; confirm CODEOWNERS exists and GitHub honors it on new PRs; open a PR with a non-conventional title and verify CI fails; open a PR on `frontend/**` and verify Playwright runs; open a PR with locally-unformatted code and verify the pre-commit parity job fails it.

**Acceptance Scenarios**:

1. **Given** every job in every workflow, **When** inspected, **Then** a `timeout-minutes` value is declared (default 15, tuned per job).
2. **Given** a new PR, **When** opened, **Then** GitHub applies reviewer suggestions based on a present `.github/CODEOWNERS` file.
3. **Given** a PR whose title is "fix stuff" (not a conventional commit), **When** CI runs, **Then** the conventional-commit lint job fails the PR.
4. **Given** a PR touching `frontend/**`, **When** CI runs, **Then** Playwright E2E tests execute against a running stack (or a dedicated mock API) and must pass.
5. **Given** a PR with locally-unformatted files that somehow slipped past a missing pre-commit install, **When** CI runs, **Then** a `pre-commit run --all-files` CI job detects the drift and fails.
6. **Given** a PR touching `cli/.goreleaser.yml`, **When** CI runs, **Then** a `goreleaser check` step validates the config before tag-push time.

---

### User Story 5 - Report, decide, and track debt (Priority: P5)

As the **maintainer** (and as **reviewers** of PRs), I need the CI to surface what it found (coverage deltas), the team to have made explicit decisions about policy (branch protection), and any deferred work to be tracked openly (the 33 Go lint issues currently silenced in `cli/.golangci.yml`).

**Why this priority**: These are reporting and policy items, not protective gates. They improve observability and governance but don't directly prevent shipping broken code. Still essential for the project to call itself professional-grade.

**Independent Test**: Open a PR that changes test coverage and confirm a coverage-delta comment appears on the PR from the reporting service. Search the docs for a branch-protection decision (ADR or similar) and confirm one exists with justification. Query the GitHub issue tracker and confirm an issue exists for the deferred Go lint items.

**Acceptance Scenarios**:

1. **Given** a PR is opened, **When** CI completes, **Then** a coverage-delta comment appears on the PR showing the backend coverage change compared to the base branch.
2. **Given** the repository's documentation, **When** searched for branch-protection policy, **Then** a written decision document exists (e.g. `docs/adr/0001-branch-protection.md`) naming one of: (A) repo goes public, (B) upgrade to GitHub Pro, or (C) explicitly accept the risk — each with justification.
3. **Given** the GitHub issue tracker, **When** filtered by the tech-debt label, **Then** an issue tracks the 33 deferred Go lint items (32 errcheck, 1 unused) currently silenced in `cli/.golangci.yml`.

---

### Edge Cases

- **Workflow race between CI and publish trigger**: What happens when a tag is pushed so quickly that CI hasn't started by the time `docker-publish` / `release` fires? The gating pattern MUST wait for CI rather than assume success or check "most recent run."
- **Forked PRs without secrets**: How does integration testing (Qdrant service container), image scanning, and coverage reporting behave when the PR is from a fork and has no access to repo secrets? The pipeline MUST degrade gracefully (run what it can, skip what needs secrets with a clear explanation) rather than fail opaquely.
- **Transient infrastructure failures**: What happens when `ghcr.io`, the signing OIDC provider, or CodeQL's action is temporarily down? The pipeline MUST fail loudly (not silently succeed with missing signatures) and retry on the next push.
- **Hotfix bypass**: What is the policy for emergency hotfixes that need to bypass a specific gate? Default: no bypass allowed. Document the escape hatch explicitly if one is adopted.
- **Dependabot PRs**: How do the new gates interact with automated Dependabot PRs? Expectation: Dependabot PRs run the full CI just like human PRs, with auto-merge only after all required checks pass.
- **Path-filtered workflows**: What happens when a PR touches both `frontend/**` and `backend/**`? The required-check set must adapt to the affected paths without leaving a newly-touched area ungated.
- **Very large PRs exceeding the 10-minute budget**: NFR-001 targets under 10 minutes for a "typical" PR. How is "typical" defined, and what is the acceptable ceiling for outlier PRs? Expectation: document the normal distribution but do not fail PRs solely for exceeding 10 minutes.
- **First-time contributor running on fork**: How is the experience for a first-time contributor whose PR requires approval to run workflows? The docs should describe the expected flow clearly.

## Requirements *(mandatory)*

### Functional Requirements

The FRs are the complete intended scope. No new FRs shall be added without explicit approval.

#### P1 — Block broken artifacts from publishing

- **FR-001 — Release gating on CI via reusable workflow**: No artifact (container image, GitHub release, CLI binary) MUST publish unless the corresponding CI workflow completed successfully on that exact commit SHA. Implementation strategy: **reusable workflow composition**. A `.github/workflows/_ci-core.yml` reusable workflow MUST be created and called by both the top-level `ci.yml` and by every publish workflow (`docker-publish.yml`, `release.yml`, `release-cli.yml`). CI runs INSIDE the publish workflow on the exact commit SHA, eliminating any race window between CI completion and artifact publication.
- **FR-002 — Coverage threshold enforcement**: Backend pytest runs in CI MUST enforce `--cov-fail-under=80` (threshold already declared in `pytest.ini`). The `--no-cov` flag MUST be removed. Frontend tests MUST enforce a coverage threshold to be decided during clarification (proposed baseline: ≥70%, raise over time).
- **FR-003 — Integration test execution in CI**: The `require_docker` test marker MUST be exercised in CI via a job that spins up Qdrant as a GitHub Actions service container and runs the full integration suite. The job MUST run on **every PR, with no path filter**, and MUST be a required gate for merge. It MAY run concurrently with the unit-test job. Rationale: the repo is public (FR-019), so GitHub Actions minutes are not a constraint; "required gate for merge" is only meaningful if it fires on every merge candidate.
- **FR-004 — Rust ingestion-worker CI**: A new workflow (`ci-rust.yml`) MUST run format-check, clippy (warnings-as-errors), tests, and vulnerability audit on every PR that touches `ingestion-worker/**`. Matrix on at least ubuntu-latest (expand to macOS/Windows only if the binary is distributed standalone).

#### P2 — Quality gates enforcement

- **FR-005 — Python type checking**: `mypy` with the `pydantic.mypy` plugin MUST run against `backend/` in CI at **baseline strictness**: `--no-implicit-optional`, `--warn-unused-ignores`, Pydantic plugin enabled, but NOT `--strict` (to avoid annotation churn on the existing codebase). Strictness MAY be raised over time in follow-up specs as annotations accumulate.
- **FR-006 — Formatter drift check**: A format-check step (`ruff format --check backend/`) MUST run in CI as a step separate from the linter. Format drift MUST fail CI.
- **FR-007 — Docker smoke test**: The `docker-build` job MUST not only build, but also start the stack (e.g. `docker compose up -d`), wait for health checks, curl `/api/health`, and tear down cleanly. A build that compiles but crashes on startup MUST fail CI.
- **FR-008 — Supply-chain hardening**: (a) All third-party GitHub Actions MUST be pinned to full commit SHAs (with the version as a trailing comment for Dependabot visibility); (b) `golangci-lint` install commands MUST pin an explicit version (e.g. `@v2.11.4`), not `@latest`; (c) Go/Node/Python runtime versions MUST be pinned to full semver (`1.25.3` not `1.25`) OR documented as intentionally floating.

#### P3 — Supply chain + security

- **FR-009 — Vulnerability scanning**: PR CI MUST include `govulncheck` on Go code (including `cli/`), `cargo audit` on `ingestion-worker/`, `pip-audit` (or equivalent) on Python dependencies, and a container image scan (`trivy` or equivalent) that fails on HIGH/CRITICAL findings.
- **FR-010 — Image signing and SBOM**: Container images published to the registry MUST be signed with keyless cosign (OIDC-based, GitHub-provenance) and include an SBOM. Release artifacts from `release-cli.yml` (goreleaser) MUST include checksums AND SBOMs.
- **FR-011 — CodeQL coverage parity**: The security workflow MUST extend CodeQL coverage to Go (`cli/`). Rust is not natively supported by CodeQL — `cargo audit` + `cargo clippy -D warnings` (already in FR-004, FR-009) serve as the equivalent security gate for Rust.

#### P4 — Workflow polish

- **FR-012 — Frontend E2E in CI**: The Playwright test suite in `frontend/` MUST run in CI on PRs that touch `frontend/**`, against a running stack or a dedicated mock API.
- **FR-013 — Pre-commit parity**: A CI job MUST run `pre-commit run --all-files` to guarantee that local pre-commit hooks match what CI would accept. Prevents "works on my machine" format drift.
- **FR-014 — Job timeouts**: Every job in every workflow MUST declare a `timeout-minutes` value (default: 15; tuned per job). Prevents runaway runner consumption.
- **FR-015 — CODEOWNERS**: A `.github/CODEOWNERS` file MUST exist and assign per-directory reviewers. Solo-project default: `* @Bruno-Ghiberto`. Future contributors may propose additions.
- **FR-016 — Conventional commit lint**: A CI job MUST enforce Conventional Commits on **PR titles only**, and MUST **block** non-conforming PRs from merging (not merely warn). Individual commits inside the PR are unrestricted. Enforcement via `commitlint` or `action-semantic-pull-request` (decided during design). Rationale: under squash-merge the PR title becomes the permanent `main` commit message; WIP commits inside the PR can use any format the author prefers.
- **FR-017 — goreleaser config validation**: A CI step MUST run `goreleaser check` on every PR that touches `cli/.goreleaser.yml`, validating the config before tag-push time (currently broken configs fail only at release cut).

#### P5 — Reporting, policy, and debt

- **FR-018 — Coverage reporting (not just enforcement)**: Coverage data MUST be uploaded to Codecov (or an equivalent service) so PRs receive a coverage-delta comment. The current workflow uploads `coverage.out` as an artifact but never computes or reports a delta.
- **FR-019 — Branch protection via repo visibility flip**: The repo MUST be flipped to **PUBLIC** visibility, completing spec-20's open-source launch goal and unlocking GitHub's free branch-protection features. Once public, required status checks MUST be configured on `main` (and `develop` if retained as the integration branch) so that every "required for merge" gate defined in this spec is actually enforced. The decision, rationale, and enforced-check roster MUST be captured in a written ADR (e.g. `docs/adr/0001-branch-protection.md`).
- **FR-020 — Follow-up debt tracking**: A GitHub issue MUST be filed tracking the 33 deferred Go lint items (32 errcheck, 1 unused) currently silenced via `cli/.golangci.yml`. These are NOT part of spec-27's deliverables but MUST be tracked for a future cleanup PR.

### Non-Functional Requirements

- **NFR-001 — PR feedback time**: Total PR CI wall-clock time (all required checks combined) SHOULD remain under 10 minutes for typical changes. Use matrix jobs, caching, and path filters aggressively.
- **NFR-002 — Deterministic builds**: CI runs on identical commits MUST produce identical lint/test results. No `@latest` anything.
- **NFR-003 — Supply-chain minimalism**: Every new Action added MUST be justified. Prefer first-party (`actions/*`, `docker/*`) or well-known community actions with SHA pins.
- **NFR-004 — Cost consciousness**: Supply-chain scans, E2E tests, and integration tests SHOULD be structured so that not every scan runs on every PR (path filters or scheduled nightly runs where appropriate).
- **NFR-005 — Documentation**: Every workflow file MUST include a top-of-file comment explaining: what it does, what triggers it, what blocks it from running, and what its required status is for merging.
- **NFR-006 — Secret hygiene**: No new secrets SHALL be introduced beyond what's already needed (`GITHUB_TOKEN`, `HOMEBREW_TAP_TOKEN`). If new secrets are required (e.g. `CODECOV_TOKEN`), the spec MUST justify them. Forked PRs MUST degrade gracefully when secrets are unavailable.
- **NFR-007 — Portability**: Workflows MUST work identically on public and private repo visibility. If the FR-019 decision is to go public, no migration work should be needed beyond flipping the visibility setting.

### Key Entities

- **Pipeline Gate**: A check on a commit that must pass before downstream events (publish, tag, merge) fire. Has a name, a trigger, a required/advisory status, a timeout, and a pass/fail outcome tied to a commit SHA.
- **Artifact**: A publishable output of the pipeline (container image, GitHub release, CLI binary, Homebrew tap entry). Has a commit SHA, a signature, an SBOM, a set of vulnerability scan results, and a distribution target.
- **Policy Document**: A written decision record (e.g. ADR) capturing governance choices such as branch-protection strategy. Must be committed to the repo, referenced from `README` or equivalent.
- **Debt Item**: A known-but-deferred issue (e.g. the 33 Go lint items) tracked in the issue tracker, labeled, and linked to the spec or PR that deferred it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

Spec-27 is "professional-grade" when these properties hold:

- **SC-001 — Zero unguarded publications**: No scenario exists where a broken build can produce a published artifact (image, release, binary). Verified by deliberate red-CI reproductions for each publication workflow (FR-001 reproducibility).
- **SC-002 — Every workflow self-documents**: Every workflow file has a top-of-file comment describing its role, triggers, blockers, and required-status state (NFR-005).
- **SC-003 — Immutable action pinning**: Every third-party Action referenced anywhere in `.github/workflows/` is pinned to a 40-char commit SHA. Verified by a single `grep` pass (FR-008a, AC-009).
- **SC-004 — Single source of truth for runtime versions**: Every runtime (Go, Node, Python, Rust) has one source of truth for its pinned version, referenced by every workflow that uses it. Verified by no duplicate inline pins across workflows.
- **SC-005 — Newcomer-comprehensible in 30 minutes**: A newcomer can clone the repo, read all workflow files top-to-bottom in under 30 minutes, and correctly describe what each gate enforces and why. Verified by a written walkthrough in `docs/cicd.md` (or equivalent).
- **SC-006 — Explicit required-check roster**: The total set of "required for merge" checks is explicitly listed in `.github/CODEOWNERS` or a dedicated README section so PR authors know what to expect. Verified by inspection (FR-015).
- **SC-007 — Measured PR wall-clock**: CI wall-clock time on a typical backend-only PR is measured and documented (target: under 10 minutes per NFR-001). A single measurement table lives in `docs/cicd.md` or the spec's validation report.
- **SC-008 — Written branch-protection decision**: A written decision on FR-019 (branch protection) is committed to the repo (e.g. `docs/adr/0001-branch-protection.md`) and referenced from the CI/CD documentation.
- **SC-009 — Coverage threshold actually enforced**: Running the backend test suite at below-threshold coverage on a PR fails CI with a clear coverage error (FR-002, AC-003).
- **SC-010 — Integration tests run on every PR**: The `require_docker`-marked test suite executes against a real Qdrant service container on every PR touching relevant paths (FR-003, AC-004).
- **SC-011 — Rust CI fully covers ingestion-worker**: Every PR touching `ingestion-worker/**` runs format, clippy (warnings-as-errors), tests, and vulnerability audit (FR-004, AC-005).
- **SC-012 — Signed and SBOM-equipped images**: Every image published to the registry after this spec lands has a verifiable cosign signature and an accessible SBOM (FR-010, AC-011).

## Current Repository Baseline (Verified State)

> The following facts were verified by direct file inspection on 2026-04-16 on branch `026-performance-debug` after PR #2 merged to `develop`. This section is GROUND TRUTH and MUST be preserved verbatim in any downstream design document.

### Workflows Present (`.github/workflows/`)

| File | Trigger | Purpose | Gate before publish? |
|------|---------|---------|---------------------|
| `ci.yml` | push/PR on `main` | Python lint + tests + frontend lint + tests + docker-build | N/A (is the CI) |
| `ci-cli.yml` | push/PR when `cli/**` changes | Go vet + build + test (3 OS matrix) + lint | N/A (is the CI) |
| `docker-publish.yml` | push `main`, tags `v*` | Build + push backend/frontend images to ghcr.io | **No** |
| `release.yml` | tags `v*` | Create GitHub Release | **No** |
| `release-cli.yml` | tags `cli/v*` | goreleaser CLI build + Homebrew tap push | **No** |
| `security.yml` | push `main`, weekly schedule | CodeQL (Python + JS/TS only) | N/A |

### Supporting Configuration

| File | Purpose | Blind spot |
|------|---------|-----------|
| `.github/dependabot.yml` | Weekly updates: pip, npm, cargo, github-actions | Good |
| `.pre-commit-config.yaml` | trailing-whitespace, eof-fixer, yaml/json check, ruff, ruff-format | Not run in CI |
| `ruff.toml` | py314, line-length 120, E/F/W selection | No format check in CI |
| `pytest.ini` | `--cov=backend --cov-fail-under=80` | **Bypassed via `--no-cov`** |
| `.github/ISSUE_TEMPLATE/` | bug_report.yml, feature_request.yml, config.yml | Good |
| `.github/PULL_REQUEST_TEMPLATE.md` | 533B standard PR template | Good |
| `.github/CODEOWNERS` | **Does not exist** | No auto-review routing |

### Repository Settings

- **Visibility**: `PRIVATE` (verified via `gh repo view`)
- **Default branch**: `main`
- **Branch protection**: Unavailable on GitHub Free + Private (returns HTTP 403 "Upgrade to GitHub Pro or make this repository public")
- **Required status checks**: None enforceable
- **CODEOWNERS**: None

### Recent Evidence of Blindness

- **PR #2 (`026-performance-debug` → `develop`)**: Exposed three pre-existing bugs in the Go CLI (spec-25) that had been merged to a feature branch without CI ever running on them. CI only ran when the `cli/` tree finally reached `develop` via this PR. Two commits (`d8f6034`, `1b6b234`) were required to reach green CI.
- **33 legitimate Go lint issues** in `cli/internal/engine/selfupdate.go` and `cli/internal/wizard/complete.go` were latent for weeks because the old `golangci-lint-action@v6` was failing at config-load time (Go version mismatch) and never actually running the linters.

### Existing Test Suite Reality

- Total tests: 1,487 passing at 87% coverage (spec-16 baseline).
- Test markers: `e2e` (in-process ASGI), `require_docker` (needs Qdrant at `localhost:6333`).
- Pre-existing failures: 39 documented, not regressions. Gate checks use baseline comparison, not absolute PASSED status.
- Integration tests exist but are systematically excluded from CI today.

### Existing Frontend Test Reality

- 53/53 frontend tests passing (spec-18, spec-22).
- Vitest v3 + React Testing Library v16 for unit.
- Playwright v1.50 for E2E — **not run in any workflow**.

## Already Implemented — Do NOT Reimplement

Spec-27 is an **audit-and-harden** spec, NOT a rebuild. The following MUST NOT be recreated:

- `ci.yml` job structure (changes, backend-lint, backend-test, frontend-lint, frontend-test, docker-build) — this fan-out is sound; the defects are specific steps within existing jobs.
- `ci-cli.yml` AFTER PR #2's fixes (commits `d8f6034`, `1b6b234`) — the Go 1.25 bump, `shell:bash` on Windows test, `golangci-lint`-from-source pattern, and build-tag split for Windows preflight are correct. Do NOT revert.
- Dependabot configuration — current 4-ecosystem setup is correct.
- Issue templates + PR template — already good.
- CodeQL for Python + JS/TS — keep, extend with Go.
- Docker buildx multi-arch (amd64, arm64) + GHA cache in `docker-publish.yml` — keep, add signing/SBOM on top.

## Dependencies and Scope Boundaries

### Depends On

- **Spec 16 (Testing Strategy)** — test markers, `require_docker` convention, coverage baseline.
- **Spec 17 (Infrastructure)** — Docker Compose, Makefile targets, service container patterns for integration testing.
- **Spec 20 (Open-Source Launch)** — original CI/CD implementation; this spec is the hardening follow-up.
- **Spec 25 (TUI installer)** — `cli/` Go code + goreleaser + `release-cli.yml`.
- **Spec 26 (Performance Debug)** — PR #2 resolution surfaced the CI-CLI failures that motivated this spec.

### External Dependencies Introduced

These are the only new external integrations this spec requires. Each is justified by a specific FR.

- **Coverage reporting service** (Codecov or equivalent) — for FR-018 coverage deltas. Requires a repo-scoped token; alternative is tokenless usage once the repo is public.
- **Image signing** (cosign, keyless, OIDC-based) — for FR-010 signing.
- **SBOM and vulnerability scanning** (syft + trivy, or equivalents) — for FR-009, FR-010.
- **Go vulnerability scanner** (`govulncheck`) — for FR-009.
- **Rust vulnerability scanner** (`cargo-audit`) — for FR-009.
- **Python vulnerability scanner** (`pip-audit` or equivalent) — for FR-009.
- **Conventional-commit enforcer** (`commitlint` or `action-semantic-pull-request`) — for FR-016.

## Out of Scope

Explicitly deferred to future specs or permanently excluded. This list MUST NOT expand without explicit approval.

- **Self-hosted runners** — requires infrastructure beyond this project's solo-dev scope. Reconsider if CI minutes become a cost concern.
- **Release automation / semantic-release** — generating `CHANGELOG.md` from conventional commits, auto-bumping versions, auto-creating tags. This is **spec-28 material**. This spec enforces conventional commits (FR-016) but does not automate releases from them.
- **Full CI observability** — runner metrics dashboards, flake detection, test execution time trending. Nice-to-have, not shipping-blocker.
- **Cross-repo dependency updates** — beyond Dependabot defaults (e.g. Renovate, custom update PRs). Current Dependabot setup is sufficient.
- **Test suite refactoring** — fixing the 39 pre-existing test failures, adding new test coverage beyond what exists today, changing test markers. This spec ENFORCES existing thresholds; it does not expand the test suite.
- **Rust Windows/macOS CI** — if the ingestion-worker binary is only ever built inside Docker (Linux), cross-OS Rust CI is wasted runner time. Scope FR-004 to ubuntu-latest unless the binary is distributed standalone.
- **Signed commits enforcement** — GPG/SSH commit signing is a separate policy decision unrelated to CI mechanics.
- **Secret rotation automation** — out of scope; manual rotation via GitHub Settings is sufficient for solo-dev.
- **Monorepo tooling** (Nx, Turborepo, Bazel) — the current per-language CI fan-out is sound; no monorepo build system needed.
- **Container registry alternatives** (DockerHub, AWS ECR) — stay on `ghcr.io`.

## Clarification Targets

> The following decisions are deliberately left open for `/speckit.clarify` to resolve via targeted questions before design begins. They are NOT `[NEEDS CLARIFICATION]` markers in the traditional sense — informed defaults have been proposed in the FRs — but each warrants an explicit choice that shapes design trade-offs.

1. ~~**Gating pattern (FR-001)**: Option A (`workflow_run`) versus Option B (reusable workflow composition)?~~ **RESOLVED 2026-04-16: Option B — reusable workflow composition** (see Clarifications section).
2. ~~**Type checker (FR-005)**: `mypy` vs `pyright`? Strictness level?~~ **RESOLVED 2026-04-16: `mypy` + Pydantic plugin, baseline strictness** (see Clarifications section).
3. **Frontend coverage threshold (FR-002)**: What baseline for frontend coverage? 70%? 80%? Currently unmeasured.
4. ~~**Conventional-commit enforcement scope (FR-016)**: title vs every commit, block vs warn?~~ **RESOLVED 2026-04-16: PR title only, block** (see Clarifications section).
5. ~~**Branch protection decision (FR-019)**: Public, Pro, or documented risk acceptance?~~ **RESOLVED 2026-04-16: repo → PUBLIC** (see Clarifications section).
6. ~~**Integration-test scheduling (FR-003)**: every PR vs main/develop only vs nightly?~~ **RESOLVED 2026-04-16: every PR, no path filter** (see Clarifications section).
7. **Coverage reporting provider (FR-018)**: Codecov, Coveralls, or a self-hosted coverage-comment action?
8. **Signing provider (FR-010)**: Keyless cosign via GitHub OIDC, or generate long-lived keys? Default: keyless (no key management burden).

## Assumptions

Reasonable defaults baked into the spec without requiring clarification:

- **CI provider remains GitHub Actions**. No migration to CircleCI, Jenkins, GitLab CI, or similar is contemplated.
- **Container registry remains `ghcr.io`**. No move to Docker Hub, AWS ECR, or others.
- **Solo-dev ownership**: The initial CODEOWNERS is `* @Bruno-Ghiberto`. Future contributors may update.
- **`main` remains the publication branch**; `develop` is the integration branch. This matches the current repository topology.
- **Keyless signing is preferred over managed keys** — reduces secret-management surface area.
- **Python type checker decided**: `mypy` with Pydantic plugin at baseline strictness (resolved in Q4 above). `pyright` is not adopted for this spec.
- **Coverage floor rises over time** — 70% frontend baseline is a floor, not a ceiling; the spec does not mandate the raise cadence.
- **Tagging triggers remain `v*` for app and `cli/v*` for CLI** — not renamed in this spec.

## Constitutional Alignment

This spec advances the project's constitutional principles:

- **Constitution I (Spec-First)**: This very file is the spec-first kickoff.
- **Constitution III (Test-First)**: Enforces coverage thresholds (FR-002), integration-test execution (FR-003), and pre-commit parity (FR-013).
- **Constitution V (Security)**: Supply-chain hardening (FR-008, FR-009, FR-010) and image signing — secrets are already Fernet-encrypted at rest; this spec extends the posture to the build pipeline itself.
- **Constitution VII (Observability)**: Coverage deltas (FR-018), CI timeouts (FR-014), and conventional-commit enforcement (FR-016) all improve the observability of the development process.

## Acceptance Criteria

A `/speckit.specify → /speckit.plan → /speckit.tasks → /speckit.implement` cycle is successful when ALL the following can be demonstrated:

1. **AC-001 (FR-001, FR-007)**: Pushing a commit to `main` that fails CI does NOT trigger a container publish. Demonstrable via a deliberate broken PR (red CI) merged, then verifying no image lands in the registry.
2. **AC-002 (FR-001)**: Pushing a broken tag does NOT trigger a GitHub release.
3. **AC-003 (FR-002)**: A PR that drops backend coverage below 80% fails CI with a clear "coverage threshold not met" error.
4. **AC-004 (FR-003)**: Integration tests requiring Qdrant run in CI and pass. Demonstrable by introducing a deliberate break in `QdrantStorage` and watching CI fail.
5. **AC-005 (FR-004)**: A PR that touches `ingestion-worker/**` runs the full Rust CI (fmt, clippy, test, audit) and fails on clippy warnings.
6. **AC-006 (FR-005)**: A PR introducing a Python type error fails CI with a type-checker error message.
7. **AC-007 (FR-006)**: A PR with unformatted Python code fails CI at the `ruff format --check` step.
8. **AC-008 (FR-007)**: The docker-build job starts the stack, confirms `/api/health` returns 200, then tears down cleanly.
9. **AC-009 (FR-008)**: Inspecting workflow files shows all external actions pinned to 40-char SHAs (not tags).
10. **AC-010 (FR-009)**: A PR that adds a dependency with a known CVE fails CI via the appropriate vulnerability scanner.
11. **AC-011 (FR-010)**: A published container image has a verifiable cosign signature and a downloadable SBOM.
12. **AC-012 (FR-011)**: The security workflow runs CodeQL across Python, JS/TS, and Go; Rust has `cargo audit` + clippy coverage.
13. **AC-013 (FR-012)**: Playwright E2E tests run on PRs touching `frontend/**`.
14. **AC-014 (FR-014)**: Grepping for `timeout-minutes:` in workflows returns at least one line per job — no job lacks a timeout.
15. **AC-015 (FR-015)**: `.github/CODEOWNERS` exists and is honored by GitHub on new PRs.
16. **AC-016 (FR-016)**: A PR with a non-conventional title fails CI.
17. **AC-017 (FR-018)**: A PR shows a coverage-delta comment from the chosen reporting provider.
18. **AC-018 (FR-019)**: The repo is flipped to PUBLIC visibility; `docs/adr/0001-branch-protection.md` exists; `main` (and `develop` if retained) has required status checks configured for every gate this spec deems "required for merge". Verifiable via `gh repo view` and `gh api repos/:owner/:repo/branches/main/protection`.
19. **AC-019 (NFR-001)**: A typical PR's CI wall-clock time is under 10 minutes from push to all-checks-green.
20. **AC-020 (FR-020)**: A follow-up GitHub issue exists tracking the 33 deferred Go lint items.

---

**Spec status**: Draft — ready for `/speckit.clarify` once reviewed. 8 clarification targets await resolution (section "Clarification Targets"). No `[NEEDS CLARIFICATION]` markers are used in FRs because each has a proposed default, but each target warrants an explicit answer before design begins.
