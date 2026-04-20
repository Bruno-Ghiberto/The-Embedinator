# CI/CD Reference

> **Audience**: First-time contributor. Read top to bottom in ~20 minutes to understand every gate
> and debug any red CI.

## Overview

Six workflows live in `.github/workflows/`. Only `_ci-core.yml` contains actual job logic; every
other workflow either calls it (`ci.yml`, `docker-publish.yml`, `release.yml`, `release-cli.yml`)
or runs independently (`pr-title.yml`, `ci-rust.yml`, `security.yml`). CI runs **inside** each
publish workflow on the exact same commit SHA — no race window between "CI passed" and "image
published."

```
PR Opened
    │
    ├──► ci.yml (thin dispatcher)
    │         │
    │         └──► _ci-core.yml ──► backend-lint ──────────────┐
    │                          ├──► backend-format-check ────── │
    │                          ├──► backend-pip-audit ───────── │
    │                          ├──► frontend-test ────────────── │──► ci / aggregate
    │                          ├──► docker-build-smoke ───────── │
    │                          ├──► pre-commit-parity ─────────── │
    │                          └──► detect-frontend-changes ──── ┘
    │
    └──► pr-title.yml ──► PR Title / semantic
                                   │
                    ───────────────┘
                          │
                ┌─────────▼──────────┐
                │  Branch Protection  │◄── required: ci/aggregate
                │  Gate (main/develop)│◄── required: PR Title/semantic
                └─────────┬──────────┘
                          │ all 9 checks pass
                          ▼
                     Merge Allowed
```

## Trigger map

| Workflow | Triggers | Role | Blocks publication? |
|---|---|---|---|
| `ci.yml` | PR (all branches), push `main` | Thin dispatcher → calls `_ci-core.yml` | N/A (is the trigger) |
| `_ci-core.yml` | `workflow_call` only | All CI jobs live here | N/A (is the CI) |
| `docker-publish.yml` | push `main`, tags `v*` | Build + Trivy scan + cosign sign + push images | YES — calls `_ci-core.yml` first |
| `release.yml` | tags `v*` | Create GitHub Release | YES — calls `_ci-core.yml` first |
| `release-cli.yml` | tags `cli/v*` | goreleaser binaries + Homebrew tap | YES — calls `_ci-core.yml` first |
| `ci-rust.yml` | PR/push touching `ingestion-worker/**` | cargo fmt/clippy/test/audit | Path-conditional required |
| `ci-cli.yml` | PR/push touching `cli/**` | go vet + build + test + govulncheck | Path-conditional required |
| `pr-title.yml` | PR opened/edited/synchronized | Conventional Commits on PR title | YES — blocks merge |
| `security.yml` | push `main`, weekly schedule | CodeQL (Python + TS + Go) | ADVISORY only |

## Gate roster

### Required checks (Shape X — must pass or skip to merge)

Verified live via `gh api repos/:owner/:repo/branches/main/protection --jq '.required_status_checks.contexts'`
as of 2026-04-20.

| Check name | Source | What it catches |
|---|---|---|
| `ci / aggregate` | `_ci-core.yml` | All-pass gate — `true` only when all Shape X jobs pass or are skipped |
| `ci / backend-lint` | `_ci-core.yml` | `ruff check backend/` — import errors, undefined names, unused vars |
| `ci / backend-format-check` | `_ci-core.yml` | `ruff format --check backend/` — format drift |
| `ci / backend-pip-audit` | `_ci-core.yml` | `pip-audit` — known CVEs in Python deps |
| `ci / frontend-test` | `_ci-core.yml` | `vitest` unit tests (≥70% coverage) |
| `ci / docker-build-smoke` | `_ci-core.yml` | Build stack → `curl /api/health` → teardown (boot-crash detection) |
| `ci / pre-commit-parity` | `_ci-core.yml` | `pre-commit run --all-files` — local hook drift |
| `ci / detect-frontend-changes` | `_ci-core.yml` | Path detector — `skipped` = pass for non-frontend PRs |
| `PR Title / semantic` | `pr-title.yml` | Conventional Commits format on PR title |

### Non-blocking jobs (`continue-on-error: true`)

These run on every PR but do **not** block merge. Tracked in
[issue #4](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/4).

| Job name | What it runs | Upgrade path |
|---|---|---|
| `ci / backend-test` | pytest + `--cov-fail-under=80` | Remove CO-E after resolving issue #4 |
| `ci / backend-type-check` | mypy with Pydantic plugin | Remove CO-E after resolving issue #4 |
| `ci / backend-integration` | Qdrant service-container tests | Remove CO-E after resolving issue #4 |
| `ci / frontend-lint` | ESLint | Remove CO-E after resolving issue #4 |
| `ci / frontend-coverage` | Frontend coverage threshold | Remove CO-E after resolving issue #4 |

## Red-path examples

Deliberate regressions used to demonstrate each gate. Evidence (GitHub run URLs) lives in
`specs/027-cicd-hardening/validation-report.md`.

| AC | Regression introduced | Gate that caught it |
|---|---|---|
| AC-007 | Unformatted Python file | `ci / backend-format-check` |
| AC-008 | Container crashes on startup (env var removed) | `ci / docker-build-smoke` |
| AC-016 | PR title "fix stuff" (non-conventional) | `PR Title / semantic` |
| AC-003 | Backend coverage drops below 80% | `ci / backend-test` (visible, non-blocking until issue #4) |

## Signing + SBOM

Every image published after spec-27 is **cosign-signed** (keyless OIDC, GitHub-provenance) and
has a **syft SBOM** attached as an attestation.

> **Gotcha — cosign version**: Use cosign **v3.0.5+**. cosign v2 returns "no matching signatures
> found" on images signed with v3 because the signature bundle format changed. The CI installs
> v3.0.5 via the `sigstore/cosign-installer` action.

### Verify a signature

```bash
REPO=$(gh repo view --json nameWithOwner --jq '.nameWithOwner' | tr '[:upper:]' '[:lower:]')
IMAGE="ghcr.io/${REPO}-backend"
TAG="<tag>"   # e.g. latest or v0.3.0

cosign verify "${IMAGE}:${TAG}" \
  --certificate-identity-regexp=".*" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com" \
  | jq .
```

Expected payload includes: GitHub Actions workflow path, issuer `token.actions.githubusercontent.com`,
repository name, ref, and the exact commit SHA.

### Download + inspect the SBOM

```bash
cosign download attestation "${IMAGE}:${TAG}" \
  | jq '.payload | @base64d | fromjson | .predicate'
```

> **Note**: Only the backend image is currently signed and has an SBOM. The frontend image has
> Trivy findings that prevent it from reaching the sign step — tracked in issue #4.

## Supply-chain

Every vulnerability scanner surfaces its output as a CI check:

| Scanner | Language | Runs on | Blocks? |
|---|---|---|---|
| `pip-audit` | Python | Every PR | YES — `ci / backend-pip-audit` |
| `cargo audit` | Rust | PRs touching `ingestion-worker/**` | YES — path-conditional |
| `govulncheck` | Go | PRs touching `cli/**` | YES — path-conditional |
| Trivy | Container image | On `docker-publish.yml` only | YES — blocks publish |
| CodeQL | Python, TS, Go | push `main` + weekly | ADVISORY (security tab) |

All third-party Actions are SHA-pinned (no `@vX.Y.Z` tags). To add a new Action:

```bash
gh api repos/<owner>/<action>/commits/<tag> --jq .sha
# Then use:  uses: <owner>/<action>@<40-char-sha> # vX.Y.Z
```

## Local mirror

Run these before pushing to verify CI will pass locally:

```bash
# Python (runs on every PR)
pre-commit run --all-files
ruff format --check backend/
ruff check backend/
pytest tests/ -m "not require_docker" --cov=backend --cov-fail-under=80
pip-audit --requirement requirements.txt

# Rust (only if touching ingestion-worker/)
cd ingestion-worker
cargo fmt --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test --all-features
cargo audit
cd -

# Go (only if touching cli/)
cd cli && go vet ./... && govulncheck ./... && cd -

# Docker smoke (if touching anything infra-adjacent)
docker compose build
docker compose up -d --wait
curl -sf http://localhost:8000/api/health | jq .
docker compose down -v

# Frontend
cd frontend && npm run test && cd -
```

See `specs/027-cicd-hardening/quickstart.md` for full reproduction recipes.

## Merge strategy

All merges to `main` and `develop` use **squash-merge**. This is the required policy per
spec-27 Q5 (FR-016).

Why it matters: under squash-merge the **PR title** becomes the single commit that lands on the
protected branch. The `PR Title / semantic` required check (Conventional Commits enforcement)
is therefore equivalent to enforcing Conventional Commits on every commit to `main` and `develop`.
Commits inside the PR body can use any format the author prefers — only the title is enforced.

Enforce in GitHub settings: `allow_squash_merge=true`, `allow_merge_commit=false`,
`allow_rebase_merge=false` (currently documented policy; repository setting enforcement is a
follow-up task).

Reference: [ADR-0001](adr/0001-branch-protection.md), spec-27 Q5.

## FAQ

**Why is the repo public?**
To unlock GitHub Free branch protection at zero cost. See [ADR-0001](adr/0001-branch-protection.md).

**Which merge mode?**
Squash-merge only. See [§Merge strategy](#merge-strategy).

**What if Codecov or Fulcio (cosign OIDC) is down?**
Both integrations use `fail_ci_if_error: false` for uploads (NFR-006 graceful degradation). CI
still passes; the coverage delta comment and SBOM attestation will simply be absent for that run.

**How do I add a required status check?**
1. Add the job to `_ci-core.yml` (or a sibling workflow for path-conditional checks).
2. Push the change, confirm the job name in the Checks UI.
3. Update branch protection:
   ```bash
   REPO=$(gh repo view --json nameWithOwner --jq .nameWithOwner)
   gh api "repos/${REPO}/branches/main/protection" --jq '.required_status_checks.contexts' \
     > /tmp/checks.json
   jq '. + ["CI / your-new-check"]' /tmp/checks.json > /tmp/new.json
   gh api --method PUT "repos/${REPO}/branches/main/protection/required_status_checks" \
     --raw-field "contexts=$(cat /tmp/new.json)"
   # Repeat for develop.
   ```
4. Update the Gate roster table in this file.

**Where is the branch-protection ADR?**
[`docs/adr/0001-branch-protection.md`](adr/0001-branch-protection.md).

**What are the 5 non-blocking jobs and when do they become blocking?**
backend-test, backend-type-check, backend-integration, frontend-lint, frontend-coverage. They
become blocking once [issue #4](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/4)
(107 pre-existing test failures) is resolved. Remove `continue-on-error: true` from each job.
