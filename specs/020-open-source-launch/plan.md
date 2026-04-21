# Implementation Plan: Open-Source Launch Preparation

**Branch**: `020-open-source-launch` | **Date**: 2026-03-19 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/020-open-source-launch/spec.md`

## Summary

Transform The Embedinator repository from a private development project into a credible, contributor-ready open-source repository. This spec changes **zero production code** — all 52 FRs concern documentation, configuration, CI/CD pipelines, test annotations, and repository cleanup. The approach uses 7 agents across 4 waves with 1 manual step (screenshots), organized by dependency: cleanup and stabilization first, infrastructure and guides second, README last (it depends on everything), release preparation final.

## Technical Context

**Language/Version**: N/A (no production code changes). CI pipelines target Python 3.14 + Node 22.
**Primary Dependencies**: GitHub Actions (CI/CD), ruff (linting config), pre-commit (hooks). No new application dependencies.
**Storage**: N/A — no database or storage changes.
**Testing**: pytest (backend, existing), vitest (frontend, existing). Only test annotations (xfail/skip) added — no new test logic.
**Target Platform**: GitHub repository infrastructure (GitHub Actions runners: Ubuntu latest).
**Project Type**: Repository packaging — documentation, governance, CI/CD, and release management.
**Performance Goals**: CI workflow completes in < 15 minutes (NFR-001).
**Constraints**: Zero production code changes. Makefile preserved (14 targets unchanged). Files removed from tracking via `git rm --cached` (preserved on local filesystem).
**Scale/Scope**: ~20 new files created, ~200+ files removed from git tracking, 1 major file rewrite (README.md), up to 39 test files annotated.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Rationale |
|-----------|---------|-----------|
| I. Local-First Privacy | PASS | No production code changes. No new outbound calls. CI runs on GitHub infrastructure (standard for open-source). |
| II. Three-Layer Agent Architecture | PASS | No agent code changes. Architecture documentation is improved (ADR links in CONTRIBUTING.md). |
| III. Retrieval Pipeline Integrity | PASS | No retrieval code changes. |
| IV. Observability from Day One | PASS | No observability code changes. Trace recording is unaffected. |
| V. Secure by Design | PASS | Positive alignment: SECURITY.md created with disclosure policy. Pre-commit hooks add detect-secrets. Dev artifacts (which could contain workflow details) removed from public tracking. Fernet key handling unchanged. |
| VI. NDJSON Streaming Contract | PASS | No streaming code changes. |
| VII. Simplicity by Default | PASS | CI/CD, governance files, and templates are standard OSS infrastructure, not application complexity. Docker services remain exactly 4. No new application dependencies. |
| VIII. Cross-Platform Compatibility | PASS | No changes to Docker or platform code. CI runs on Ubuntu (standard). Launcher scripts preserved unchanged. |

**Gate result: ALL PASS. No violations. No complexity tracking needed.**

**Post-Phase 1 re-check**: Constitution still fully satisfied. The docs/ directory rename is organizational, not architectural. Test annotations (xfail/skip) don't change test behavior — they only affect CI reporting.

## Project Structure

### Documentation (this feature)

```text
specs/020-open-source-launch/
├── spec.md              # Feature specification (52 FRs, 12 SCs)
├── plan.md              # This file
├── research.md          # Phase 0 output (minimal — all technologies are established)
├── checklists/
│   └── requirements.md  # Spec quality checklist (all items passing)
├── validation-report.md # Phase 7 output (SC-001 through SC-012)
└── release-notes.md     # Phase 7 output (v0.2.0 release notes draft)
```

### Repository Changes (this feature)

```text
# NEW FILES (root level)
LICENSE                    # Apache 2.0
CODE_OF_CONDUCT.md         # Contributor Covenant v2.1
SECURITY.md                # Vulnerability disclosure policy
CONTRIBUTING.md            # Root-level contributing guide
CHANGELOG.md               # Full project changelog (specs 001-019)
.editorconfig              # Cross-editor settings
.pre-commit-config.yaml    # Pre-commit hooks
ruff.toml                  # Ruff linter configuration

# NEW DIRECTORY (reorganized docs)
docs/
├── architecture-design.md
├── api-reference.md
├── data-model.md
├── security-model.md
├── testing-strategy.md
├── runbook.md
├── DEVELOPMENT-STATUS.md
├── REFLECTION-COMPETITIVE-ANALYSIS.md
├── images/                 # Screenshots for README
│   ├── chat-light.png
│   ├── chat-dark.png
│   ├── collections.png
│   ├── observability.png
│   └── social-preview.png
└── adr/                    # 8 Architecture Decision Records
    ├── 001-sqlite-over-postgres.md
    ├── 002-three-layer-agent.md
    ├── 003-rust-ingestion-worker.md
    ├── 004-cross-encoder-reranking.md
    ├── 005-parent-child-chunking.md
    ├── 006-observability-from-day-one.md
    ├── 007-sse-streaming.md
    └── 008-multi-provider-architecture.md

# NEW DIRECTORY (GitHub infrastructure)
.github/
├── workflows/
│   ├── ci.yml              # Lint + test + Docker build
│   ├── security.yml        # CodeQL + dependency review
│   └── release.yml         # Tag-triggered GitHub Release
├── ISSUE_TEMPLATE/
│   ├── bug_report.yml      # Structured bug report form
│   ├── feature_request.yml # Structured feature request form
│   └── config.yml          # Template config (redirect to Discussions)
├── PULL_REQUEST_TEMPLATE.md
└── dependabot.yml
```

**Structure Decision**: No new source code directories. All changes are to repository infrastructure (governance files, CI config, documentation). The existing `backend/`, `frontend/`, `ingestion-worker/`, and `tests/` directories are untouched except for test annotation decorators in `tests/`.

## Phase 0: Research

All technologies used in this spec are established standards with extensive documentation:

- **Apache 2.0 License**: Standard text available from apache.org and SPDX
- **Contributor Covenant v2.1**: Template at contributor-covenant.org
- **GitHub Actions**: Extensively documented at docs.github.com/en/actions
- **Dependabot**: Configuration reference at docs.github.com/en/code-security/dependabot
- **ruff**: Configuration reference at docs.astral.sh/ruff
- **pre-commit**: Hook configuration at pre-commit.com
- **Keep a Changelog**: Format specification at keepachangelog.com
- **EditorConfig**: Specification at editorconfig.org

**No NEEDS CLARIFICATION items remain.** All decisions were resolved during the specify phase:
- License: Apache 2.0 (resolved in speckit.clarify)
- Version: v0.2.0 (reasonable default matching frontend/package.json)
- Internal artifacts: Remove from public repo (resolved in speckit.clarify)
- Docs directory: Rename to `docs/` (reasonable default, GitHub convention)

### Research Findings (consolidated)

| Decision | Rationale | Alternatives Rejected |
|----------|-----------|----------------------|
| Apache 2.0 license | Patent grant for AI tools, enterprise-friendly, matches Qdrant | MIT (no patent grant), AGPL (too restrictive) |
| v0.2.0 version | Pre-1.0 signals early stage, matches frontend/package.json | v1.0.0 (no public validation yet), v0.1.0 (already used internally) |
| Remove dev artifacts | Cleaner public tree, less confusion for contributors | Keep (174 files of noise), archive branch (unnecessary complexity) |
| `docs/` lowercase | GitHub convention, Pages-compatible, clean paths | Keep `Docs/Project Blueprints/` (spaces in paths, non-standard) |
| Manual screenshots | Faster for launch, real app data | Automated Playwright (complex setup, deferred to post-launch) |
| ruff for Python linting | Already installed, fast, modern | flake8 (slower, less features), pylint (too opinionated) |
| dorny/paths-filter for CI | Smart path filtering, widely used | Manual path conditions (verbose, error-prone) |

**Output**: No separate `research.md` file needed — all decisions are documented above and in the spec clarifications.

## Phase 1: Design

### Data Model

N/A — this spec creates no new data entities, database tables, or state machines. All changes are to files, configuration, and documentation.

### Interface Contracts

N/A — this spec exposes no new APIs, CLI commands, or programmatic interfaces. The CI workflow YAML files are configuration, not contracts. The issue/PR templates are GitHub infrastructure.

### Implementation Architecture

The implementation follows the 7-agent, 4-wave structure defined in `Docs/PROMPTS/spec-20-open-source-launch/20-plan.md`. Key architectural decisions:

#### Wave 1 (Parallel: A1 + A2 + A3)
- **A1 (devops-architect)**: Repository cleanup + docs reorganization. Foundation phase — all path references depend on the new `docs/` structure.
- **A2 (quality-engineer)**: Test stabilization. CI blocker — the 39 pre-existing failures must be triaged and annotated before CI can pass.
- **A3 (technical-writer)**: Governance files + linting config. Independent — creates new root-level files with no dependencies on other phases.
- **Zero file overlap**: A1 touches .gitignore + docs/, A2 touches test files + pytest.ini, A3 creates new governance files.

#### Wave 2 (Parallel: A4 + A5)
- **A4 (devops-architect)**: GitHub infrastructure — CI workflows, issue/PR templates, Dependabot.
- **A5 (technical-writer)**: Contributing guide + Changelog — depends on A1's docs/ rename for correct ADR paths.
- **Zero file overlap**: A4 creates files under .github/, A5 creates root-level CONTRIBUTING.md and CHANGELOG.md.

#### Manual Step: Screenshots (between Gate 2 and Wave 3)
- Requires the application running with realistic data
- 4+ screenshots captured from the spec-18 "Intelligent Warmth" UI
- Stored at `docs/images/`

#### Wave 3 (Solo: A6)
- **A6 (technical-writer)**: README major rewrite — depends on everything (screenshots, badges, LICENSE, CONTRIBUTING.md, updated project tree).

#### Wave 4 (Solo: A7)
- **A7 (quality-engineer)**: Release preparation + full SC validation — final phase after all content is in place.

### Agent Context Update

No new technologies or dependencies are introduced to the application. The only new tooling is:
- GitHub Actions (CI/CD) — external service, not a project dependency
- ruff configuration formalization — ruff was already installed
- pre-commit hooks — optional developer tooling

No updates to agent context files are needed.

## Quickstart

### For Implementors

```bash
# 1. Ensure you're on the correct branch
git checkout 020-open-source-launch

# 2. Read the authoritative files in order:
#    a. Your agent instruction file (Docs/PROMPTS/spec-20-open-source-launch/agents/A{N}-instructions.md)
#    b. The spec (specs/020-open-source-launch/spec.md)
#    c. The implementation plan (Docs/PROMPTS/spec-20-open-source-launch/20-plan.md)

# 3. Key verification commands:
#    Dev artifacts removed from tracking:
git ls-files CLAUDE.md AGENTS.md skills-lock.json .agents/ .specify/ Docs/PROMPTS/ | wc -l  # must be 0

#    Tests green:
zsh scripts/run-tests-external.sh -n spec20-check -m "not require_docker" --no-cov tests/
cat Docs/Tests/spec20-check.status  # must be PASSED

#    Governance files exist:
for f in LICENSE CODE_OF_CONDUCT.md SECURITY.md CONTRIBUTING.md CHANGELOG.md; do
  test -f "$f" && echo "PASS: $f" || echo "FAIL: $f"
done

#    GitHub infra exists:
test -d .github/workflows && echo "PASS" || echo "FAIL"

#    Makefile unchanged:
diff <(git show HEAD:Makefile) Makefile  # must show zero diff

# 4. This spec changes ZERO production code. If you find yourself editing
#    backend/*.py, frontend/components/*.tsx, or similar — STOP. You're out of scope.
```

### For Orchestrator (Agent Teams)

Follow the wave execution sequence in `Docs/PROMPTS/spec-20-open-source-launch/20-plan.md`:
1. Wave 1: Spawn A1 + A2 + A3 in parallel (3 tmux panes)
2. Gate Check 1
3. Manual: Capture screenshots
4. Wave 2: Spawn A4 + A5 in parallel (2 tmux panes)
5. Gate Check 2
6. Wave 3: Spawn A6 solo
7. Gate Check 3
8. Wave 4: Spawn A7 solo

## Complexity Tracking

> No Constitution violations detected. This section is empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| *(none)* | — | — |
