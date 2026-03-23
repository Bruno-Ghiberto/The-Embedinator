# Tasks: Open-Source Launch Preparation

**Input**: Design documents from `/specs/020-open-source-launch/`
**Prerequisites**: plan.md (required), spec.md (required)

**Tests**: No new test files. Only test annotations (xfail/skip) on existing tests.

**Organization**: Tasks follow the 4-wave dependency structure. User story labels indicate which story each task primarily serves. Many tasks serve multiple stories (e.g., LICENSE serves US1, US4, US5).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1=Discovery, US2=CI, US3=Contributing, US4=Evaluation, US5=Security, US6=Release

---

## Phase 1: Setup

**Purpose**: Verify branch and understand the scope

- [x] T001 Verify on branch `020-open-source-launch` and read spec.md + plan.md + 20-plan.md

---

## Phase 2: Foundational — Repository Cleanup (Wave 1, Agent A1)

**Purpose**: Restructure the repository for public consumption. All subsequent phases depend on the new `docs/` paths.

**⚠️ CRITICAL**: Docs rename and artifact removal MUST complete before Contributing Guide or README work begins.

- [x] T002 Update `.gitignore` to add dev tooling exclusions: CLAUDE.md, AGENTS.md, skills-lock.json, .agents/, .claude/, .specify/, .serena/, .gitnexus/, .coverage, frontend/test-results/, Docs/PROMPTS/ — file: `.gitignore`
- [x] T003 Remove individual dev artifacts from git tracking via `git rm --cached CLAUDE.md AGENTS.md skills-lock.json .coverage` — preserves local files (FR-034)
- [x] T004 Remove dev directories from git tracking via `git rm -r --cached .agents/ .specify/` — preserves local dirs (FR-035)
- [x] T005 Remove Docs/PROMPTS/ from git tracking via `git rm -r --cached Docs/PROMPTS/` — preserves 174 local files (FR-036)
- [x] T006 Create `docs/` directory structure and move content from `Docs/Project Blueprints/` — move architecture-design.md, api-reference.md, data-model.md, security-model.md, testing-strategy.md, runbook.md, contributing.md, changelog.md to `docs/` (FR-050)
- [x] T007 Move ADRs from `Docs/Project Blueprints/adr/` to `docs/adr/` — all 8 ADR files (FR-051)
- [x] T008 Move `Docs/DEVELOPMENT-STATUS.md` and `Docs/REFLECTION-COMPETITIVE-ANALYSIS.md` to `docs/`
- [x] T009 [P] Fix stale references in `docs/contributing.md` — replace `claudedocs/` with `docs/`, replace `<repo-url>` with `https://github.com/Bruno-Ghiberto/The-Embedinator`. Also search entire repo for stale `claudedocs/` refs: `grep -r 'claudedocs/' --include='*.md' . --exclude-dir=.git --exclude-dir=Docs/PROMPTS` (FR-018)
- [x] T010 [P] Update `docs/DEVELOPMENT-STATUS.md` to cover specs 018 (UX/UI Redesign) and 019 (Cross-Platform DX) — add rows to table, update test count (FR-037)
- [x] T011 [P] Audit `docker-compose.prod.yml` against current `docker-compose.yml` — remove if stale/redundant (FR-038)
- [x] T012 Remove empty `Docs/Project Blueprints/` directory after all content moved
- [x] T013 Verify cleanup: `git ls-files CLAUDE.md AGENTS.md .agents/ .specify/ Docs/PROMPTS/ | wc -l` must be 0

**Checkpoint**: Repository structure clean. `docs/` exists with all documentation. Dev artifacts untracked.

---

## Phase 3: Foundational — Test Stabilization (Wave 1, Agent A2)

**Purpose**: Make the test suite CI-ready by addressing all 39 pre-existing failures.

**⚠️ CRITICAL**: CI (Phase 5) cannot pass until tests are green.

- [x] T014 Update `pytest.ini` — add `testpaths = tests` directive (FR-044)
- [x] T015 Run full test suite to catalog current failures: `zsh scripts/run-tests-external.sh -n test-triage --no-cov tests/`
- [x] T016 Triage and annotate test failures: `test_config.py::test_default_settings` (1 failure) — fix or xfail with reason (FR-042)
- [x] T017 [P] Triage and annotate test failures: conversation graph tests — SessionContinuity, ClarificationInterrupt, TwoRoundClarificationCap (3 failures) — xfail with reason (FR-042)
- [x] T018 [P] Triage and annotate test failures: `test_app_startup` (1 failure) — xfail AsyncMock/LangGraph incompatibility (FR-042)
- [x] T019 Triage and annotate remaining 34 test failures — individually fix where simple, xfail/skip the rest with descriptive reasons (FR-042)
- [x] T020 Verify tests green: `zsh scripts/run-tests-external.sh -n test-stabilized -m "not require_docker" --no-cov tests/` — status must be PASSED (FR-043)

**Checkpoint**: Test suite produces green result with `-m "not require_docker"`. All failures either fixed or annotated.

---

## Phase 4: Foundational — Governance Files & Linting Config (Wave 1, Agent A3)

**Purpose**: Create all standard OSS governance files and formalize linting configuration.

- [x] T021 [P] [US5] Create `LICENSE` file with standard Apache License 2.0 text — copyright holder: Bruno Ghiberto, year: 2026 (FR-001)
- [x] T022 [P] [US5] Create `CODE_OF_CONDUCT.md` using Contributor Covenant v2.1 template — fill in maintainer contact method (FR-002)
- [x] T023 [P] [US5] Create `SECURITY.md` with vulnerability disclosure policy — supported versions (v0.2.0+), private email for reports, 48h acknowledgment, 90-day disclosure (FR-003)
- [x] T024 [P] Create `.editorconfig` — Python 4-space, TS/JS/JSON 2-space, Rust 4-space, YAML 2-space, MD preserve trailing whitespace, UTF-8, LF (FR-004)
- [x] T025 [P] Create `ruff.toml` — target Python 3.14, line length 120, exclude .venv/data/.git, sensible rule set — verify existing code passes with `ruff check backend/ --config ruff.toml` (FR-046)
- [x] T026 [P] Create `.pre-commit-config.yaml` — ruff-pre-commit (lint+format), pre-commit-hooks (trailing-whitespace, end-of-file-fixer, check-yaml, check-json) — pin versions (FR-045)

**Checkpoint**: All governance files exist. Ruff config validates existing codebase.

---

## GATE CHECK 1 (After Phases 2, 3, 4)

```bash
git ls-files CLAUDE.md AGENTS.md .agents/ .specify/ Docs/PROMPTS/ | wc -l  # must be 0
test -d docs/adr && echo "PASS" || echo "FAIL"
grep -r 'claudedocs/' docs/ && echo "FAIL" || echo "PASS"
cat Docs/Tests/test-stabilized.status  # must be PASSED
for f in LICENSE CODE_OF_CONDUCT.md SECURITY.md .editorconfig ruff.toml .pre-commit-config.yaml; do
  test -f "$f" && echo "PASS: $f" || echo "FAIL: $f"
done
diff <(git show HEAD:Makefile) Makefile && echo "PASS: Makefile" || echo "FAIL"
```

---

## Phase 5: US2 — GitHub Infrastructure (Wave 2, Agent A4)

**Goal**: Create CI/CD pipelines, issue/PR templates, and dependency monitoring so every PR is automatically validated.

**Independent Test**: Open a PR with a minor change — CI triggers, lint and test jobs run, results appear on PR.

- [x] T027 [P] [US2] Create `.github/workflows/ci.yml` — backend lint (ruff --output-format=github), backend test (pytest -m "not require_docker" --no-cov), frontend lint (next lint), frontend test (vitest), Docker build validation. Path filtering via dorny/paths-filter. Caching for pip+npm. Triggered on PR + push to main. (FR-022, FR-023, FR-024)
- [x] T028 [P] [US2] Create `.github/workflows/security.yml` — CodeQL analysis for Python + TypeScript. Triggered on push to main + weekly schedule. (FR-025)
- [x] T029 [P] [US2] Create `.github/workflows/release.yml` — triggered on tag push matching `v*`. Creates GitHub Release with tag name and release notes from CHANGELOG.md. (FR-026)
- [x] T030 [P] [US2] Create `.github/ISSUE_TEMPLATE/bug_report.yml` — YAML form: description, steps to reproduce, expected/actual behavior, environment (OS, Docker version), logs (FR-027)
- [x] T031 [P] [US2] Create `.github/ISSUE_TEMPLATE/feature_request.yml` — YAML form: problem description, proposed solution, alternatives considered (FR-027)
- [x] T032 [P] [US2] Create `.github/ISSUE_TEMPLATE/config.yml` — disable blank issues, add link to Discussions for questions (FR-028)
- [x] T033 [P] [US3] Create `.github/PULL_REQUEST_TEMPLATE.md` — summary, type of change, testing done, checklist (tests pass, lint passes, no secrets, docs updated) (FR-029)
- [x] T034 [P] [US2] Create `.github/dependabot.yml` — monitor pip (requirements.txt), npm (frontend/package.json), cargo (ingestion-worker/Cargo.toml), github-actions. Weekly schedule. (FR-030)
- [x] T035 Validate all YAML workflow files: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`

**Checkpoint**: All GitHub infrastructure files exist and are valid YAML.

---

## Phase 6: US3+US4 — Contributing Guide & Changelog (Wave 2, Agent A5)

**Goal**: Create the root-level contributing guide and comprehensive project changelog.

**Independent Test**: Read CONTRIBUTING.md — developer setup instructions work. Read CHANGELOG.md — all 19 specs represented.

- [x] T036 [US3] Create root `CONTRIBUTING.md` — consolidate from docs/contributing.md. Include: First-Time Contributors (fork/clone/branch/test/PR), Development Setup (Docker --dev + native Makefile), Code Style (ruff/TS/Rust), Commit Conventions, ADR links (docs/adr/), Code of Conduct reference. Use GitHub URL: `https://github.com/Bruno-Ghiberto/The-Embedinator`. (FR-012 to FR-018)
- [x] T037 [US4] Create root `CHANGELOG.md` — Keep a Changelog format. Version [0.2.0] (Unreleased). Group changes by functional area: Agent Architecture (specs 002-004), Retrieval Pipeline (003, 005), Ingestion (006), Storage (007), API (008), Frontend (009, 018), Providers (010), Interfaces (011), Error Handling (012), Security (013), Performance (014), Observability (015), Testing (016), Infrastructure (017), Cross-Platform (019). Include [0.1.0] section from existing docs/changelog.md. (FR-019 to FR-021)
- [x] T038 Verify: `grep -q 'First-Time Contributors' CONTRIBUTING.md` and `grep -q '0.2.0' CHANGELOG.md` and no stale refs

**Checkpoint**: CONTRIBUTING.md and CHANGELOG.md exist at root with all required sections.

---

## GATE CHECK 2 (After Phases 5, 6)

```bash
for f in .github/workflows/ci.yml .github/workflows/security.yml .github/workflows/release.yml \
         .github/ISSUE_TEMPLATE/bug_report.yml .github/ISSUE_TEMPLATE/feature_request.yml \
         .github/ISSUE_TEMPLATE/config.yml .github/PULL_REQUEST_TEMPLATE.md .github/dependabot.yml; do
  test -f "$f" && echo "PASS: $f" || echo "FAIL: $f"
done
test -f CONTRIBUTING.md && echo "PASS" || echo "FAIL"
test -f CHANGELOG.md && echo "PASS" || echo "FAIL"
grep -q 'docs/adr' CONTRIBUTING.md && echo "PASS: ADR links" || echo "FAIL"
diff <(git show HEAD:Makefile) Makefile && echo "PASS: Makefile" || echo "FAIL"
```

---

## Phase 7: Screenshots & Media (Manual Step)

**Purpose**: Capture application screenshots for the README. Requires the app running with realistic data.

- [x] T039 Start application via `./embedinator.sh` and seed data — create a collection, upload sample documents, ask questions to generate conversation with citations
- [x] T040 Create `docs/images/` directory
- [x] T041 [US1] Capture screenshots: (1) chat page with conversation, citations, confidence badge in light mode, (2) chat page in dark mode, (3) collections or documents page with data, (4) observability dashboard with traces and charts — store as PNG in `docs/images/` (FR-039, FR-040)
- [x] T042 [US1] Create social preview image (1280x640px) — include project name, tagline, visual element — store at `docs/images/social-preview.png` (FR-041)

**Checkpoint**: `ls docs/images/*.png | wc -l` returns >= 5.

---

## Phase 8: US1 — README Rewrite (Wave 3, Agent A6)

**Goal**: Rewrite README.md so a developer landing on GitHub can understand, evaluate, and start using the project within 5 minutes.

**Independent Test**: Visit the GitHub repo page — README renders with badges, screenshots, single-command quickstart. No "TBD" text, no commented-out badges.

- [x] T043 [US1] Read current README.md (527 lines) in full before making any changes
- [x] T044 [US1] Rewrite Quick Start section — `./embedinator.sh` as sole command, Docker Desktop as only prereq. Move multi-tool dev setup to "Development Setup" section. (FR-005)
- [x] T045 [US1] Replace commented-out badge HTML with live badges — CI status, coverage (87%), license (Apache-2.0), Python (3.14+). Use shields.io format. (FR-006)
- [x] T046 [US1] Add Screenshots section — embed 3+ images from `docs/images/` using relative paths. At least one dark mode. (FR-007)
- [x] T047 [US1] Update specifications table — add rows for spec 018 (UX/UI Redesign) and 019 (Cross-Platform DX), both Complete. (FR-008)
- [x] T048 [US1] Update License section — "Apache License 2.0" with link to LICENSE. Update Contributing section — link to CONTRIBUTING.md. Remove all "TBD" text. (FR-009)
- [x] T049 [US1] Update project structure tree to reflect spec-18 frontend reorganization — shadcn/ui `components/ui/`, theme provider, sidebar layout, `docs/` directory. (FR-010)
- [x] T050 [US1] Add "Why The Embedinator?" section — differentiate from simpler RAG tools: 3-layer agent architecture, meta-reasoning recovery, grounded answer verification, 5-signal confidence scoring. (FR-011)
- [x] T051 [US1] Final README validation — verify: no "TBD", no commented badges, >= 4 badges, >= 3 screenshots, specs table has 19 rows, Quick Start shows embedinator.sh, all hyperlinks resolve (no dead links per NFR-003)

**Checkpoint**: README complete. `grep -q 'TBD' README.md` returns no matches.

---

## GATE CHECK 3 (After Phase 8)

```bash
grep -c '!\[' README.md    # >= 4 (badges + screenshots)
grep -q 'TBD' README.md && echo "FAIL: TBD remains" || echo "PASS"
grep -q 'embedinator.sh' README.md && echo "PASS: quickstart" || echo "FAIL"
grep -q 'Apache' README.md && echo "PASS: license" || echo "FAIL"
grep -q 'CONTRIBUTING.md' README.md && echo "PASS: contributing link" || echo "FAIL"
grep -c 'docs/images/' README.md   # >= 3 screenshots
diff <(git show HEAD:Makefile) Makefile && echo "PASS: Makefile" || echo "FAIL"
```

---

## Phase 9: US6 — Release Preparation & Final Validation (Wave 4, Agent A7)

**Goal**: Prepare the v0.2.0 release and validate all 12 success criteria.

**Independent Test**: Version tag exists, release notes drafted, all SCs verified.

- [x] T052 [P] [US3] Create 5+ good-first-issue GitHub issues — each with description, acceptance criteria, relevant file paths. Examples: add CSV ingestion support, improve port conflict error message, add collection search filter, add API pagination, documentation improvement. (FR-032)
- [x] T053 [P] [US6] Draft release notes at `specs/020-open-source-launch/release-notes.md` — project summary, key features, prerequisites (Docker Desktop), quick start command, link to CHANGELOG.md. (FR-049)
- [x] T054 [US4] Document post-push manual steps — enable GitHub Discussions (4 categories: Announcements, Q&A, Ideas, Show and Tell) (FR-031), set repository topics (FR-052), upload social preview image
- [x] T055 [US6] Validate all 12 success criteria + NFR-001 (CI < 15 min timing check) and write `specs/020-open-source-launch/validation-report.md` — SC-001 through SC-012 + NFR timing, each with PASS/FAIL and verification method
- [x] T056 [US6] Create annotated version tag: `git tag -a v0.2.0 -m "Release v0.2.0 — Open-Source Launch"` — do NOT push until validation report confirms all SCs pass (FR-047, FR-048)
- [x] T057 Final Makefile check: `diff <(git show HEAD:Makefile) Makefile` — must show zero diff

**Checkpoint**: All 12 SCs PASS. Version tag created. Release notes drafted. Validation report written.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Cleanup)**: Depends on Phase 1 — BLOCKS Phases 6, 8 (paths must be correct)
- **Phase 3 (Test Stab)**: No dependency on Phase 2 — can run PARALLEL with Phases 2, 4
- **Phase 4 (Governance)**: No dependency on Phase 2 — can run PARALLEL with Phases 2, 3
- **Phase 5 (GitHub Infra)**: Depends on Phase 3 (tests must be green for CI)
- **Phase 6 (Contributing+Changelog)**: Depends on Phase 2 (docs/ paths)
- **Phase 7 (Screenshots)**: Depends on Phases 2-6 complete (manual step)
- **Phase 8 (README)**: Depends on Phases 4 (LICENSE), 5 (CI badge), 6 (CONTRIBUTING link), 7 (screenshots)
- **Phase 9 (Release)**: Depends on ALL previous phases

### Wave Parallelism

**Wave 1** (Phases 2, 3, 4 — all parallel):
- A1: T002–T013 (cleanup + docs rename)
- A2: T014–T020 (test stabilization)
- A3: T021–T026 (governance + lint config)

**Wave 2** (Phases 5, 6 — parallel after Gate 1):
- A4: T027–T035 (GitHub infrastructure)
- A5: T036–T038 (contributing + changelog)

**Wave 3** (Phase 8 — solo after Gate 2 + screenshots):
- A6: T043–T051 (README rewrite)

**Wave 4** (Phase 9 — solo after Gate 3):
- A7: T052–T057 (release + validation)

### User Story Dependencies

- **US1 (Discovery, P1)**: Depends on US2 (CI badge), US5 (LICENSE), screenshots — implemented last (Phase 8)
- **US2 (CI, P1)**: Depends on test stabilization — implemented in Phase 5
- **US3 (Contributing, P2)**: Depends on docs rename — implemented in Phase 6
- **US4 (Evaluation, P2)**: Depends on changelog + CI + governance — implemented across Phases 4-6
- **US5 (Security, P3)**: Independent — implemented in Phase 4 (governance files)
- **US6 (Release, P3)**: Depends on everything — implemented last (Phase 9)

---

## Parallel Examples

### Wave 1 (3 parallel agents)

```bash
# A1: Repository cleanup
Task: "Update .gitignore" (T002)
Task: "git rm --cached dev artifacts" (T003-T005)
Task: "Move docs to docs/" (T006-T008)

# A2: Test stabilization (simultaneously)
Task: "Update pytest.ini" (T014)
Task: "Triage 39 test failures" (T015-T019)
Task: "Verify green suite" (T020)

# A3: Governance files (simultaneously)
Task: "Create LICENSE" (T021)
Task: "Create CODE_OF_CONDUCT.md" (T022)
Task: "Create SECURITY.md" (T023)
Task: "Create .editorconfig" (T024)
Task: "Create ruff.toml" (T025)
Task: "Create .pre-commit-config.yaml" (T026)
```

### Wave 2 (2 parallel agents)

```bash
# A4: GitHub infrastructure
Task: "Create ci.yml" (T027)
Task: "Create security.yml" (T028)
Task: "Create release.yml" (T029)
Task: "Create issue templates" (T030-T032)
Task: "Create PR template" (T033)
Task: "Create dependabot.yml" (T034)

# A5: Contributing + Changelog (simultaneously)
Task: "Create CONTRIBUTING.md" (T036)
Task: "Create CHANGELOG.md" (T037)
```

---

## Implementation Strategy

### MVP First (US5 — Security + Governance)

1. Complete Phase 1: Setup
2. Complete Phase 4: Governance (LICENSE, CoC, SECURITY) — US5 fully satisfied
3. **STOP and VALIDATE**: `test -f LICENSE && test -f SECURITY.md`

### Incremental Delivery

1. Phases 2+3+4 → Cleanup + Tests + Governance ready (US5 complete)
2. Phase 5 → CI operational (US2 complete)
3. Phase 6 → Contributing + Changelog ready (US3, US4 complete)
4. Phases 7+8 → Screenshots + README (US1 complete)
5. Phase 9 → Release (US6 complete, all SCs validated)

### Agent Teams Strategy

7 agents across 4 waves. Detailed orchestration in `Docs/PROMPTS/spec-20-open-source-launch/20-plan.md`.

---

## Notes

- **Zero production code changes** — if you're editing `backend/*.py` or `frontend/components/*.tsx`, STOP
- **Makefile is SACRED** — every gate check verifies zero diff
- **`git rm --cached`** not `git rm` — files stay on disk, leave git tracking
- **All [P] tasks** within a phase can run in parallel (different files)
- **User story labels** indicate primary story served, but many tasks serve multiple stories
- Total: 57 tasks across 9 phases + 3 gate checks
