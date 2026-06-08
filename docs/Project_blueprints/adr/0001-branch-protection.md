# ADR-0001: Branch Protection via Repository Visibility Flip

**Status**: Accepted
**Date**: 2026-04-17 (flip executed at `2026-04-17T18:47:41Z`)
**Deciders**: @Bruno-Ghiberto
**Spec reference**: spec-27 FR-019, Q1

---

## Context

The Embedinator was a **private** GitHub repository until 2026-04-17. The GitHub Free plan does not
allow branch protection rules on private repositories — any attempt to configure required status
checks or merge restrictions returned HTTP 403 ("Upgrade to GitHub Pro or make this repository
public").

This blocked spec-27's core requirement: making CI gates *actually enforceable*. Without branch
protection:

- CI is advisory — a broken PR can merge even if every check fails.
- Required status check names are impossible to enforce, regardless of workflow correctness.
- spec-20's open-source launch goal remained incomplete.

The visibility flip was the only zero-cost path to enforceable branch protection. It was planned
in spec-20 and deferred; spec-27 completes it.

## Decision

**Flip the repository to PUBLIC** and configure required status checks on `main` and `develop`.

The required-status roster chose **Shape X** (9 checks) over the originally-designed 18-check
roster. Shape Y dead-locked because 107 pre-existing test failures made those jobs red on every
PR. Shape X enforces only the checks that are currently green; the failing jobs run in visibility
mode (`continue-on-error: true`) and are tracked as tech debt in
[issue #4](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/4).

### Shape X — 9 required checks (main + develop, `strict: true`)

| Check name | What it enforces |
|---|---|
| `ci / aggregate` | Overall gate: `true` only when all Shape X jobs pass or skip |
| `ci / backend-lint` | `ruff check backend/` — import errors, undefined names, unused vars |
| `ci / backend-format-check` | `ruff format --check` — format drift |
| `ci / backend-pip-audit` | `pip-audit` — known CVEs in Python dependencies |
| `ci / frontend-test` | `vitest` unit tests (≥70% coverage) |
| `ci / docker-build-smoke` | Build stack → `curl /api/health` → teardown (boot-crash detection) |
| `ci / pre-commit-parity` | `pre-commit run --all-files` — local hook parity |
| `ci / detect-frontend-changes` | Path detector — `skipped` counts as pass on non-frontend PRs |
| `PR Title / semantic` | Conventional Commits on PR title (required by squash-merge policy) |

### 5 non-blocking jobs (upgrade path)

These jobs run with `continue-on-error: true` until issue #4 is resolved:
`ci / backend-test`, `ci / backend-type-check`, `ci / backend-integration`,
`ci / frontend-lint`, `ci / frontend-coverage`.

Once the test baseline is green, remove `continue-on-error: true` to make them blocking.

## Consequences

### Positive

- Branch protection enforced at zero additional cost (GitHub Free + public repo).
- spec-20 open-source launch goal is now complete — the repository is publicly discoverable.
- Codecov can upload coverage reports without a secret token (public-repo tokenless mode).
- cosign keyless OIDC signing works (Fulcio certificate transparency requires public repos).
- External contributors can fork and submit PRs; CI runs automatically on their forks.

### Negative

| Risk | Mitigation |
|---|---|
| Full git history is world-readable | Pre-flip audit confirmed no tracked secrets or credentials in history |
| Drive-by PRs from unknown contributors | CODEOWNERS assigns @Bruno-Ghiberto as required reviewer; PR template in place |
| Planning docs and spec files are public | `docs/PROMPTS/` is in `.gitignore`; spec files contain no secrets or credentials |

## Alternatives Considered

- **Option B — GitHub Pro** ($4/user/month): Enables branch protection on private repos. Rejected:
  ongoing cost with zero feature benefit over public + GitHub Free; contradicts spec-20's explicit
  open-source goal.
- **Option C — Document risk acceptance**: Acknowledge that CI is advisory-only and proceed without
  enforcement. Rejected: undermines the entire motivation for spec-27 and leaves broken artifacts
  able to reach users.

## References

- [spec-20 — Open-Source Launch](../../specs/020-open-source-launch/spec.md)
- [spec-27 — CI/CD Hardening](../../specs/027-cicd-hardening/spec.md) — FR-019, Q1 (decision locked 2026-04-16)
- [docs/cicd.md](../cicd.md) — full required-check roster and verification commands
- [GitHub issue #4](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/4) — tech-debt: 33 deferred Go lint items + 107 pre-existing test failures
- [GitHub Docs — Branch protection rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)

## Follow-ups

- Resolve the 107 pre-existing test failures (issue #4), then flip the 5 non-blocking jobs to
  required checks.
- Raise the backend coverage threshold (`--cov-fail-under=80`) and frontend threshold (≥70%) once
  the baseline is consistently green.
- Enforce squash-only merges in GitHub repository settings: `allow_squash_merge=true`,
  `allow_merge_commit=false`, `allow_rebase_merge=false` (currently documented policy; not yet
  enforced at the settings level).
- Tighten the cosign `--certificate-identity-regexp` from `.*` to the exact workflow path once
  signing stabilises post-ship.
