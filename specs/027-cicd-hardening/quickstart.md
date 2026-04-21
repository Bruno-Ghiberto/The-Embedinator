# Quickstart: CI/CT/CD Pipeline Hardening

**Feature**: Spec 27 — CI/CT/CD Pipeline Hardening
**Branch**: `027-cicd-hardening`
**Audience**: Implementation operator (you, or a future contributor post-Gate-4)

---

## Preflight

Before running any `/speckit.implement` workflow, confirm:

```bash
# 1) Inside tmux
[ -n "$TMUX" ] || { echo "ERROR: not inside tmux"; exit 1; }

# 2) Agent Teams flag exported
[ "$CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS" = "1" ] \
  || export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1

# 3) gh CLI authenticated
gh auth status

# 4) On the right branch
git branch --show-current   # expect 027-cicd-hardening

# 5) Baseline test run captured (for regression comparison at each gate)
zsh scripts/run-tests-external.sh -n spec27-baseline --no-cov tests/
cat Docs/Tests/spec27-baseline.status   # record for Gate comparisons
cat Docs/Tests/spec27-baseline.summary  # record failure count
```

---

## Reproducing "Red CI Blocks Publish" (AC-001, AC-002)

Goal: prove that a broken commit on `main` does NOT result in a container image publish, and that a broken tag does NOT produce a GitHub release.

```bash
# Short-lived demo branch
git checkout -b 027-demo-red-ci

# Introduce a deliberate test failure
python -c "import pathlib; p = pathlib.Path('tests/unit/test_config.py'); t = p.read_text(); p.write_text(t.replace('def test_default_settings', 'def test_default_settings_broken_on_purpose'))"
git commit -am "demo(ci): red-CI → no publish (temporary)"
git push -u origin 027-demo-red-ci

# Open PR + watch checks
gh pr create --title "demo: red-CI → no publish" --body "Intentional failure for AC-001/AC-002 demonstration" --draft
gh pr checks --watch
# Expected: CI fails at backend-test; docker-publish does NOT trigger.

# Verify registry state
gh api "repos/$(gh repo view --json nameWithOwner --jq .nameWithOwner)/packages/container/embedinator-backend/versions" \
  | jq '.[0].metadata.container.tags'
# Expected: no new tag matching the demo-red-ci commit SHA

# Cleanup
gh pr close --delete-branch
git checkout 027-cicd-hardening
git branch -D 027-demo-red-ci
```

Record the `gh run view` URL for the failed CI run in `validation-report.md` under AC-001.

---

## Verifying a Published Image Signature (AC-011, SC-012)

Post-Gate-3, verify that every published image is signed and has an attached SBOM:

```bash
REPO=$(gh repo view --json nameWithOwner --jq '.nameWithOwner' | tr '[:upper:]' '[:lower:]')
IMAGE="ghcr.io/${REPO}-backend"
TAG=$(gh api "repos/$(gh repo view --json nameWithOwner --jq .nameWithOwner)/packages/container/embedinator-backend/versions" \
  | jq -r '.[0].metadata.container.tags[0]')

# 1. Verify cosign signature (keyless, OIDC)
cosign verify "${IMAGE}:${TAG}" \
  --certificate-identity-regexp=".*" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com" \
  | jq .

# Expected: signature payload with:
#   - subject: GitHub Actions workflow path
#   - issuer: token.actions.githubusercontent.com
#   - repository + ref + commit SHA

# 2. Download and inspect the SBOM
cosign download attestation "${IMAGE}:${TAG}" \
  | jq -r '.payload' \
  | base64 -d \
  | jq '.predicate' > /tmp/sbom.json

jq '.packages | length' /tmp/sbom.json
# Expected: >0 packages listed (SPDX format)
```

---

## Reading `docs/cicd.md` (SC-005)

Post-Gate-4, the `docs/cicd.md` file is the authoritative newcomer walkthrough. It covers:

1. **What every workflow does** and what it blocks.
2. **The required-status-check roster** (mirrors the `_ci-core.yml` job names).
3. **Red-path examples** — what happens if you drop coverage, push unformatted code, introduce a type error, break a Qdrant-dependent test, add a known-CVE dependency, ship a clippy warning, open a non-conventional PR title.
4. **Signing and SBOM verification** (see "Verifying a Published Image Signature" above).
5. **Local mirror** — how to run the same checks locally before pushing.

Target: a first-time contributor reads it in under 30 minutes and can describe every gate.

---

## Adding a New Required Status Check (post-Gate-1)

For future contributors adding a new CI gate:

```bash
# 1. Add the job to _ci-core.yml (or a sibling workflow)
# 2. Update branch protection to include the new check name
REPO=$(gh repo view --json nameWithOwner --jq .nameWithOwner)
gh api "repos/${REPO}/branches/main/protection" --jq '.required_status_checks.contexts' > /tmp/current-checks.json
# Append your new check name to the list
jq '. + ["CI / your-new-check"]' /tmp/current-checks.json > /tmp/new-checks.json

gh api --method PUT "repos/${REPO}/branches/main/protection/required_status_checks" \
  --raw-field "contexts=$(cat /tmp/new-checks.json)"

# 3. Repeat for develop
gh api --method PUT "repos/${REPO}/branches/develop/protection/required_status_checks" \
  --raw-field "contexts=$(cat /tmp/new-checks.json)"

# 4. Update docs/cicd.md § "Required-check roster" to match
```

---

## Locally Mirroring CI

Before pushing, run the equivalent checks locally:

```bash
# Python
pre-commit run --all-files              # FR-013 parity
ruff format --check backend/            # FR-006 format drift
ruff check backend/                     # Existing lint
mypy backend/                           # FR-005 type check
pytest tests/ -m "not require_docker" --cov=backend --cov-fail-under=80  # FR-002 coverage
pip-audit --requirement requirements.txt  # FR-009 Python

# Rust (if touching ingestion-worker)
cd ingestion-worker
cargo fmt --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test --all-features
cargo audit
cd -

# Go (if touching cli)
cd cli
go vet ./...
govulncheck ./...
golangci-lint run --config .golangci.yml --default standard ./...
cd -

# Frontend
cd frontend
pnpm lint
pnpm test --coverage --coverage.thresholdAutoUpdate=false
# Optional: Playwright E2E (requires stack running)
pnpm exec playwright test
cd -

# Docker smoke (if touching anything infra-adjacent)
docker compose build
docker compose up -d --wait
curl -sf http://localhost:8000/api/health | jq .
docker compose down -v
```

If everything above passes locally, CI is virtually guaranteed to pass.

---

## Implementing Spec-27: The Full `/speckit.implement` Flow

After `/speckit.tasks` produces `tasks.md`, the implementation sequence is:

```bash
# 1. Start a fresh tmux session for spec-27
tmux new-session -d -s embedinator-27
tmux split-window -h
tmux split-window -v
tmux select-pane -t 0
tmux split-window -v
tmux select-layout tiled
tmux attach-session -t embedinator-27

# 2. Export Agent Teams flag in every pane
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1

# 3. Invoke /speckit.implement
# → orchestrator spawns Wave 1 (A1 + A2) via TeamCreate / TaskCreate / Agent
# → after Wave 1 completes, Gate 1 runs the pre-flip audit
# → user approves; orchestrator runs gh repo edit --visibility public
# → orchestrator runs gh api branch protection PUT
# → orchestrator spawns Wave 2 (A3 + A4 + A5)
# → Gate 2 runs smoke-PR dry-run + branch-protection sync
# → orchestrator spawns Wave 3 (A6 + A7)
# → Gate 3 runs tagged smoke + cosign verify
# → orchestrator spawns Wave 4 (A8 + A9)
# → Gate 4 finalizes validation-report.md, opens PR to develop
```

Expected wall-clock: ~3–5 hours of orchestrator + agent time (most of it is CI runs, not agent work).

---

## Troubleshooting

**cosign verify fails with "no matching signatures"**: the publish workflow is missing `permissions: id-token: write`. Check `_ci-core.yml` and `docker-publish.yml`.

**Branch protection configuration fails with 403**: repo is still private. Confirm Gate 1's visibility flip executed (`gh repo view --json visibility`).

**Required status check name mismatch after Wave 2**: A3/A4/A5 emitted job names that don't match the placeholder `gh api` config from Gate 1. The orchestrator updates the config at Gate 2 — run `gh api repos/:owner/:repo/branches/main/protection --jq .required_status_checks.contexts` and diff against the Workflow Contracts roster in `plan.md`.

**Pre-flip audit finds a tracked secret**: DO NOT flip visibility. Run `git filter-repo` to purge the offending commit(s), force-push all affected branches, then retry Gate 1. Consider rotating any credentials that were exposed.

**PR #2 CI-CLI fixes disappeared**: A4 or A7 accidentally reverted `d8f6034` or `1b6b234`. Restore via `git cherry-pick` and re-dispatch the agent with explicit instructions to preserve those commits.

---

## References

- [spec.md](./spec.md) — authoritative requirements
- [plan.md](./plan.md) — wave plan + gates
- [research.md](./research.md) — tool choice rationale
- [checklists/requirements.md](./checklists/requirements.md) — spec quality validation
- [docs/PROMPTS/spec-27-cicd-hardening/27-plan.md](../../docs/PROMPTS/spec-27-cicd-hardening/27-plan.md) — planning context prompt
- [docs/adr/0001-branch-protection.md](../../docs/adr/0001-branch-protection.md) — branch-protection ADR (created in Wave 4 A9)
- [docs/cicd.md](../../docs/cicd.md) — newcomer walkthrough (created in Wave 4 A9)
