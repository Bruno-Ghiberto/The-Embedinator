# Research: CI/CT/CD Pipeline Hardening

**Feature**: Spec 27 — CI/CT/CD Pipeline Hardening
**Date**: 2026-04-16
**Purpose**: Resolve the residual documentation lookups after `/speckit.clarify` locked 5 major decisions. Every item here has **Decision**, **Rationale**, **Alternatives considered**, and **Verification reference**.

---

## 1. Reusable Workflow (`workflow_call`) Semantics

**Decision**: `.github/workflows/_ci-core.yml` uses `on: workflow_call` with explicit `inputs:`, `outputs:`, and `permissions:`. Callers (`ci.yml`, `docker-publish.yml`, `release.yml`, `release-cli.yml`) use `uses: ./.github/workflows/_ci-core.yml` (same-repo relative path, no version pin needed). Permissions flow via `permissions: inherit` at the caller OR an explicit `permissions:` block inside the reusable workflow — we use explicit permissions on the reusable for defense-in-depth.

**Rationale**:

- Relative-path same-repo reusable workflows run in the calling commit's context. This avoids the `workflow_run` race where the subscribed publish workflow runs against the default-branch workflow definition, not the commit's.
- Explicit `inputs:` + `outputs:` makes the interface auditable; a future spec can change the contract visibly via the `_ci-core.yml` diff, not a hidden dependency.
- Setting `id-token: write` at the reusable's `permissions:` block is REQUIRED because cosign keyless signing (A6 in Wave 3) runs inside the reusable workflow flow; without this permission, the OIDC token request fails silently.

**Alternatives considered**:

- **`workflow_run` subscription**: rejected in `/speckit.clarify` Q2. Would introduce a race on tag pushes (publish workflow runs with default-branch definition, not the tagged commit's).
- **Composite actions** (`type: composite` under `.github/actions/<name>/action.yml`): viable for small helpers but cannot express job-level parallelism, `services:`, matrix jobs, or different runners per step. Spec-27 needs all of those.
- **Hybrid**: `workflow_run` for `push: main` + reusable for `tags: v*`: rejected for complexity; the reusable pattern handles both uniformly.

**Verification reference**:

- GitHub docs: `docs.github.com/en/actions/using-workflows/reusing-workflows` — "Access and permissions" section, "Using outputs from a reusable workflow".
- Example repo: `actions/starter-workflows` publishes reusable workflow patterns for standard stacks.

---

## 2. cosign Keyless OIDC Signing

**Decision**: Use `sigstore/cosign-installer@<sha>` action to install cosign, then `cosign sign --yes ghcr.io/<owner>/<image>@${DIGEST}` with no explicit key material. Attestation (SBOM) uses `cosign attest --predicate sbom.json ghcr.io/...`. The workflow MUST declare `permissions: id-token: write` — without this, the OIDC token for GitHub's Fulcio instance is unavailable and signing fails with `error: OIDC token request failed`.

**Rationale**:

- Keyless signing eliminates private-key management. The signing identity is bound to the GitHub repo + workflow + commit via Fulcio-issued certificates.
- Verification uses `cosign verify --certificate-identity-regexp=".*" --certificate-oidc-issuer="https://token.actions.githubusercontent.com"`. A tighter `--certificate-identity` pinning the exact workflow path is a post-ship hardening item.
- Public repos are natively supported by Fulcio without any paid tier.

**Alternatives considered**:

- **Managed keys (Fulcio-less)**: rejected — requires storing a private key in GitHub Secrets, introducing a secret-rotation burden and a theft surface.
- **Notary v2 / ORAS signing**: more heavyweight; tooling is less mature. cosign is industry default for `ghcr.io`.
- **No signing, just SHA attestation**: fails FR-010's explicit "signed with cosign" requirement.

**Verification reference**:

- `docs.sigstore.dev/cosign/verifying/verify/` — keyless verify patterns.
- `docs.github.com/en/actions/deployment/security-hardening-your-deployments/using-openid-connect-with-your-cloud-provider` — OIDC token permissions.
- GitHub starter workflow: `ghcr-actions/cosign-starter` demonstrates the `id-token: write` requirement.

---

## 3. `pydantic.mypy` Plugin Activation

**Decision**: Configure in `pyproject.toml` under `[tool.mypy]` (preferred) OR `mypy.ini`. Concrete block:

```toml
[tool.mypy]
plugins = ["pydantic.mypy"]
python_version = "3.14"
no_implicit_optional = true
warn_unused_ignores = true
ignore_missing_imports = false
follow_imports = "normal"
exclude = [
    "^build/",
    "^dist/",
    "^\\.venv/",
    "^migrations/",  # none today, future-proofing
]

[tool.pydantic-mypy]
init_forbid_extra = true
init_typed = true
warn_required_dynamic_aliases = true
```

**Rationale**:

- The Pydantic plugin models Pydantic v2's generics, validators (`@field_validator`, `@model_validator`), and `BaseSettings` field aliasing — none of which mypy handles correctly out of the box.
- `init_forbid_extra = true` catches accidental typos when constructing models (e.g., `Settings(debug_mdoe=True)` would flag instead of silently passing).
- `warn_required_dynamic_aliases = true` catches fields created via `Field(alias=...)` where the alias type doesn't match — relevant to this project per the spec-17 memory note ("pydantic-settings alias requires `populate_by_name=True`").
- Baseline strictness (no `--strict`) is locked by Q4.

**Alternatives considered**:

- `pyright` with `pyright.basic` mode: rejected in Q4. Faster but weaker Pydantic v2 modeling.
- `mypy --strict`: rejected in Q4. Would require a massive annotation sweep across existing `backend/` before CI can pass.
- No type-check plugin: fails FR-005.

**Verification reference**:

- `docs.pydantic.dev/latest/integrations/mypy/` — plugin docs and config reference.
- Pydantic repo: `tests/plugin/` — real-world plugin behavior.

---

## 4. `trivy` Action vs CLI Install

**Decision**: Use `aquasecurity/trivy-action@<sha>` for image scanning in `docker-publish.yml`. Use the CLI (`trivy` installed via the action) for ad-hoc filesystem scans in other workflows if needed.

**Rationale**:

- The action handles installation + caching + GitHub-friendly output formatting (SARIF upload, PR annotations) in one line.
- `exit-code: 1` + `severity: 'HIGH,CRITICAL'` + `ignore-unfixed: true` is the standard "fail the PR on HIGH/CRITICAL fixable vulns" pattern.
- Scanning the built image (not the filesystem) catches base-image CVEs that dependency scanners (pip-audit, cargo-audit) miss.

**Alternatives considered**:

- **`snyk/actions/docker`**: requires Snyk API token (new secret). Fails NFR-006 hygiene unless justified.
- **`anchore/scan-action`**: viable alternative. `aquasecurity/trivy-action` is more widely used (larger SHA-pin history for Dependabot) and has lower per-scan time on ubuntu-latest runners.
- **CLI install + custom parsing**: fails NFR-003 (no justification for rolling our own).

**Verification reference**:

- `github.com/aquasecurity/trivy-action` README — inputs, outputs, SARIF upload.
- `docs.aquasec.com/v0.51/docs/scanner/vuln/` — severity levels and ignore-unfixed semantics.

---

## 5. `commitlint` vs `action-semantic-pull-request`

**Decision**: Use `amannn/action-semantic-pull-request@<sha>` for PR-title-only conventional-commit enforcement.

**Rationale**:

- PR-title-only enforcement is locked by Q5. `action-semantic-pull-request` was purpose-built for this exact pattern.
- No Node.js setup, no `commitlint.config.js` file, no separate `pnpm install` step required. Shorter CI runtime.
- Allowed types are configured inline via the action's `types:` input: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `ci`, `build`, `perf`, `style`, `revert`.
- The action blocks merge on non-conforming titles by default (exit code non-zero), which matches Q5's "block" decision.

**Alternatives considered**:

- **`commitlint` via `wagoid/commitlint-github-action`**: viable but requires `commitlint.config.js` as a separate file. Over-engineered for title-only enforcement.
- **`commitizen-tools/commitizen-action`**: checks every commit, not the PR title. Rejected by Q5 (per-commit enforcement creates WIP-commit friction).

**Verification reference**:

- `github.com/amannn/action-semantic-pull-request` README — inputs and default allowed types.

---

## 6. Coverage-Reporting Provider (Codecov, Public Repo, Tokenless)

**Decision**: `codecov/codecov-action@<sha>` for upload. On a PUBLIC repo (post-Gate-1), Codecov accepts tokenless uploads from GitHub Actions (authenticated via repo metadata + commit SHA). No `CODECOV_TOKEN` secret is required, satisfying NFR-006 (no new secrets).

**Rationale**:

- Codecov offers free PR-comment coverage deltas for public repos.
- Tokenless mode is specific to public repos — if the repo were staying private (rejected in Q1), a token would be required.
- PR-comment UX: Codecov posts/updates a single comment per PR with the coverage delta vs base branch, satisfying FR-018 without per-commit spam.

**Alternatives considered**:

- **Coveralls**: comparable feature set, older service. Codecov has broader GitHub integration and better PR-comment formatting.
- **`py-cov-action/python-coverage-comment-action`**: self-hosted comment action (no third-party service). Viable backup if Codecov's uptime becomes a concern, but adds CI runtime and PR-comment-bot noise.
- **No external reporting**: fails FR-018 (explicit "coverage delta comment" requirement).

**Verification reference**:

- `docs.codecov.com/docs/codecov-tokens#tokenless-uploads` — tokenless policy for public repos.
- `github.com/codecov/codecov-action` — action inputs.

---

## 7. Frontend Coverage Threshold (70% baseline)

**Decision**: Frontend `vitest.config.ts` coverage threshold set to 70% across `lines`, `branches`, `functions`, `statements`. Enforced in CI via `--coverage --coverage.thresholdAutoUpdate=false`.

**Rationale**:

- 70% is a common "already-covered-code-stays-covered" baseline for TypeScript frontends of this size.
- Memory notes from spec-18 confirm 53/53 frontend tests pass with no specified threshold — current coverage is likely above 70% on the tested surface but has gaps (untested pages, components).
- Starting at 70% avoids a mass-annotation PR; future specs can raise the floor incrementally.

**Alternatives considered**:

- **80%** (match backend): rejected — the frontend has more presentational code where unit-testing adds less signal than visual/E2E coverage. Forcing 80% would push contributors to low-value tests.
- **No threshold**: fails FR-002 (frontend).
- **90%+**: premature for a pre-v1 frontend.

**Verification reference**:

- `vitest.dev/guide/coverage` — threshold config.
- Empirical: A5 will run `pnpm test --coverage` on the current frontend to confirm 70% is achievable before landing the threshold.

---

## 8. SHA-Pinning Workflow for `@latest` → 40-char SHA

**Decision**: A2 uses `gh api repos/<owner>/<action>/commits/<tag> --jq .sha` to resolve each `@vX.Y.Z` tag to its 40-char SHA, then replaces `uses: <owner>/<action>@vX.Y.Z` with `uses: <owner>/<action>@<sha> # vX.Y.Z` (trailing comment keeps Dependabot updates human-readable).

**Rationale**:

- Git tags are mutable; SHAs are immutable. An attacker with repo-write on an upstream action could move `@v4` to a malicious commit. Pinning to SHA neutralizes this attack.
- Trailing `# vX.Y.Z` comment is a Dependabot convention: Dependabot parses the version, opens PRs to bump the SHA-pin AND the comment together.
- Automatable: a shell one-liner in the A2 prompt, no bespoke tooling required.

**Alternatives considered**:

- **`zizmor` or `ratchet` CLI** (SHA-pin tools): add a new dependency with its own trust footprint. The two-line `gh api` approach is equivalent in hygiene with zero new tooling.
- **Leave `@vX.Y.Z` tags and rely on trust**: rejected — fails FR-008 and SC-003.

**Verification reference**:

- `docs.github.com/en/actions/security-guides/security-hardening-for-github-actions#using-third-party-actions` — "Pin actions to a full length commit SHA".
- `docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file#package-ecosystem` — Dependabot SHA-pin support.

---

## 9. Python Runtime Version Pin

**Decision**: Pin `python-version: "3.14.1"` (or whatever the current `python-version: "3.14"` resolves to on runs dated 2026-04-16 — A2 verifies via `gh run view --log` of a recent backend-test job).

**Rationale**:

- NFR-002 deterministic builds: `"3.14"` resolves to whatever patch version the runner's `actions/setup-python@<sha>` cached tarball is for today; tomorrow, it could be different.
- Full semver pin neutralizes this. Bumping to a new patch is a deliberate Dependabot PR.

**Alternatives considered**:

- **Single `.python-version` file** (pyenv-style): viable, adds a file. Pinning inline in workflows keeps the source of truth in one place and is SC-004-aligned.
- **No pin**: fails FR-008c.

**Verification reference**:

- `github.com/actions/setup-python#specifying-a-python-version`.

---

## 10. Rust Toolchain Pin

**Decision**: A4's `ci-rust.yml` uses `dtolnay/rust-toolchain@<sha>` with `toolchain: 1.93.1` (matches the project's `ingestion-worker` target from spec-06). `cargo fmt --check`, `cargo clippy --all-targets --all-features -- -D warnings`, `cargo test --all-features`, `cargo audit` as four separate jobs (or one job with four steps — A4's choice, impacts parallelism).

**Rationale**:

- `dtolnay/rust-toolchain` is the community-accepted toolchain installer (superseded `actions-rs/toolchain` which is archived).
- Pinning to `1.93.1` matches the `ingestion-worker` builds; a mismatch would invalidate CI as a trust signal.
- `-D warnings` promotes clippy warnings to errors — this is the "block on clippy warning" behavior FR-004 demands.

**Alternatives considered**:

- **Nightly**: would invalidate reproducibility. Rejected.
- **`stable` channel**: rolls with every release; same determinism concern as unpinned Python.

**Verification reference**:

- `github.com/dtolnay/rust-toolchain` README.
- `cli/.golangci.yml` pattern (PR #2) as a precedent for tool-version determinism in this repo.

---

## 11. Pre-commit Parity Strategy

**Decision**: A7 adds a `pre-commit-parity` job in `_ci-core.yml`:

```yaml
pre-commit-parity:
  runs-on: ubuntu-latest
  timeout-minutes: 10
  steps:
    - uses: actions/checkout@<sha>
    - uses: actions/setup-python@<sha>
      with: { python-version: "3.14.1" }
    - uses: pre-commit/action@<sha>
      with: { extra_args: --all-files }
```

**Rationale**:

- `pre-commit/action` caches the venv and `.pre-commit-cache` between runs — fast.
- Running `--all-files` catches drift that `pre-commit run --from-ref origin/main --to-ref HEAD` would miss on large PRs.
- Satisfies FR-013 with minimal new tooling.

**Alternatives considered**:

- **Run `pre-commit` as a step inside backend-lint**: entangles concerns. A dedicated job is easier to debug when it fails.
- **Only run on changed files**: incomplete coverage; drift goes undetected.

**Verification reference**:

- `github.com/pre-commit/action` README.

---

## 12. Docker Smoke-Test Strategy (FR-007)

**Decision**: A6 adds the following steps to `_ci-core.yml`'s `docker-build-smoke` job:

```yaml
- name: Build stack
  run: docker compose build
- name: Start stack
  run: docker compose up -d --wait
- name: Wait for backend health
  run: |
    for i in {1..60}; do
      if curl -sf http://localhost:8000/api/health; then exit 0; fi
      sleep 2
    done
    echo "Backend never became healthy"; exit 1
- name: Tear down stack
  if: always()
  run: docker compose down -v
```

**Rationale**:

- `docker compose up -d --wait` waits for healthchecks declared in `docker-compose.yml` to report healthy; failing early here catches image-level boot failures.
- The explicit `/api/health` curl loop (60×2s = 120s max) is a secondary check in case compose healthchecks aren't defined or are misconfigured.
- `if: always()` on tear-down prevents orphan containers between runs.
- 5-minute total timeout (overall job `timeout-minutes: 25` accommodates build + 2-min wait + cleanup).

**Alternatives considered**:

- **Use `wait-for-it.sh`**: introduces an extra tool. `curl` + shell loop is equivalent and toolless.
- **Run full integration tests against the stack**: conflates concerns; integration tests already run in a separate job with a service-container Qdrant. The smoke test's job is "does it even boot?", not "does it work correctly?".

**Verification reference**:

- `docs.docker.com/compose/reference/up/#wait` — `--wait` flag semantics.

---

## 13. goreleaser Config Validation (FR-017)

**Decision**: A7 adds to `ci-cli.yml` a conditional step:

```yaml
- name: Validate goreleaser config
  if: contains(github.event.pull_request.changed_files, 'cli/.goreleaser.yml')
  run: |
    go install github.com/goreleaser/goreleaser/v2@latest
    goreleaser check --config cli/.goreleaser.yml
```

(Or substitute `@v2.x.y` for `@latest` to honor NFR-002 — version picked by A7 at implementation time.)

**Rationale**:

- `goreleaser check` parses the config and flags errors BEFORE the tag-push moment. Catches typos, invalid templates, missing fields.
- Conditional on `cli/.goreleaser.yml` being in the PR changed files — zero overhead on PRs that don't touch the config.
- `@latest` here is a first-draft — A7 pins the version per NFR-002 before commit.

**Alternatives considered**:

- **Run `goreleaser check` in every PR**: wastes CI minutes on PRs that don't touch the config.
- **Only run it at tag-push time in `release-cli.yml`**: reproduces the current bug (config errors surface at release, too late).

**Verification reference**:

- `goreleaser.com/commands/goreleaser_check/`.

---

## 14. GitHub Issue Filing for Deferred Go Lint Debt (FR-020)

**Decision**: A7 runs `gh issue create` with a detailed body enumerating the 32 errcheck + 1 unused items in `cli/internal/engine/selfupdate.go` and `cli/internal/wizard/complete.go`, labels it `tech-debt`, and references the PR #2 commits (`d8f6034`, `1b6b234`) that silenced them in `cli/.golangci.yml`.

**Rationale**:

- FR-020 mandates issue tracking, not resolution.
- The issue body should include: the enumeration (from `golangci-lint run --config cli/.golangci.yml --default standard cli/...`), the PR #2 context, and a follow-up-spec placeholder.
- Label `tech-debt` makes the issue discoverable via `gh issue list --label tech-debt`, satisfying SC-006-adjacent discoverability.

**Alternatives considered**:

- **TODO comments in code**: rot fast, aren't searchable outside the repo, fail SC-006 visibility.
- **Defer the issue filing to a post-merge manual step**: fragile; easy to forget. Automating it in A7 ensures it's done before Gate 3.

**Verification reference**:

- `cli.github.com/manual/gh_issue_create`.

---

## Summary

All 14 documentation lookups are resolved. No `NEEDS CLARIFICATION` markers remain in the Technical Context. The plan is design-ready and every tool choice ties back to a specific FR.
