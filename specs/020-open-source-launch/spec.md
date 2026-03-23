# Feature Specification: Open-Source Launch Preparation

**Feature Branch**: `020-open-source-launch`
**Created**: 2026-03-19
**Status**: Draft
**Input**: Polish, document, test-stabilize, and package The Embedinator for its first public release on GitHub — transforming a well-engineered private project into a credible, contributor-ready open-source repository.

## Overview

The Embedinator is a production-grade agentic RAG system with 19 completed specifications, 1,487 tests at 87% coverage, a 3-layer LangGraph agent architecture, hybrid search with cross-encoder reranking, a polished shadcn/ui frontend, and single-command cross-platform startup. The engineering is done. The packaging is not.

This specification covers everything needed to transform a private repository into a credible open-source project: adding standard governance files (license, code of conduct, security policy), rewriting the README to reflect the current single-command experience, creating CI/CD pipelines that validate every contribution, stabilizing the test suite for automated runs, removing internal development artifacts, capturing screenshots of the redesigned UI, and preparing the first versioned release. No production code is changed — every requirement in this spec concerns documentation, configuration, test annotation, or repository infrastructure.

The outcome is a repository that a developer can discover on GitHub, understand within five minutes, install with a single command, and contribute to with confidence — backed by automated quality gates, clear governance, and transparent architecture documentation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Repository Discovery and First Impression (Priority: P1)

A developer discovers The Embedinator on GitHub — through a search, a recommendation, or a social media link. They land on the repository page and within two minutes decide whether this project is worth their time. They look for: a clear description of what the tool does, visual proof that it works (screenshots), signals of quality (CI badges, test coverage, license), and a straightforward way to get started.

**Why this priority**: First impressions determine adoption. If the README is stale, the license is missing, or there are no screenshots, technically excellent software will be dismissed. This story covers the repository's public face — everything a visitor sees before they clone.

**Independent Test**: Visit the GitHub repository page as an unauthenticated user. Verify that the README renders correctly with badges, screenshots, a clear value proposition, and a single-command quick start. Verify that GitHub's sidebar shows the license, contributing link, and code of conduct.

**Acceptance Scenarios**:

1. **Given** a visitor lands on the GitHub repository page, **When** they view the README, **Then** they see a project title, tagline, active CI/coverage/license badges, at least three screenshots of the application, and a Quick Start section showing a single-command setup.
2. **Given** a visitor inspects the repository sidebar, **When** they look for governance files, **Then** GitHub displays the license type, links to CONTRIBUTING.md and CODE_OF_CONDUCT.md, and shows configured topics describing the project.
3. **Given** a visitor clicks the LICENSE file, **When** they read it, **Then** it contains a recognized open-source license that GitHub identifies and labels automatically.
4. **Given** a visitor looks at the README specs table, **When** they count entries, **Then** all 19 specifications (001 through 019) are listed with their completion status.
5. **Given** a visitor reads the Quick Start section, **When** they follow the instructions, **Then** the only prerequisite listed is Docker Desktop, and the setup command is `./embedinator.sh` (not a multi-step process requiring Python, Node.js, or Rust).

---

### User Story 2 — Automated Quality Gates (Priority: P1)

A project maintainer merges contributions with confidence because every pull request is automatically validated by CI. The CI pipeline runs backend linting, backend tests, frontend linting, frontend tests, and Docker build validation. All checks pass on the main branch. Contributors see immediate feedback on their PRs without waiting for manual review.

**Why this priority**: Without CI, the maintainer must manually run tests for every contribution, and contributors have no way to validate their changes before submitting. CI is the foundation of sustainable open-source maintenance. It is co-equal with the README because a repository with a green CI badge signals active, quality-conscious development.

**Independent Test**: Create a pull request with a minor change. Verify that GitHub Actions workflows trigger automatically, run lint and test jobs, and report results on the PR. Verify that the main branch shows a passing CI badge.

**Acceptance Scenarios**:

1. **Given** a pull request is opened against the main branch, **When** CI triggers, **Then** separate jobs run for backend lint, backend tests, frontend lint, frontend tests, and Docker build validation.
2. **Given** CI runs backend tests, **When** the test suite executes, **Then** all tests either pass or are explicitly marked as expected failures, and the overall suite result is green.
3. **Given** CI runs on the main branch after merge, **When** the workflow completes, **Then** the CI badge in the README reflects a passing status.
4. **Given** a contributor introduces a linting violation, **When** CI runs, **Then** the lint job fails with clear error messages indicating which files and lines need correction.
5. **Given** the repository has been public for one week, **When** Dependabot checks for dependency updates, **Then** it creates pull requests for any outdated dependencies across all four ecosystems (Python, Node.js, Rust, GitHub Actions).

---

### User Story 3 — First-Time Contributor Onboarding (Priority: P2)

A developer wants to contribute a bug fix or small feature to The Embedinator. They read the contributing guide, set up their development environment, make a change, run tests locally, and submit a pull request. The process is well-documented, and the PR template guides them through the submission checklist.

**Why this priority**: Open-source projects live or die by contributor experience. A clear, friction-free contribution path turns users into contributors. This story depends on the README and CI being in place (Stories 1 and 2) but adds the contributor-specific documentation and templates.

**Independent Test**: Follow the CONTRIBUTING.md guide from scratch on a clean machine. Clone the repo, set up the dev environment using the documented steps, make a trivial change, run tests, and submit a PR. Verify the PR template appears and CI runs on the PR.

**Acceptance Scenarios**:

1. **Given** a first-time contributor reads CONTRIBUTING.md, **When** they follow the development setup section, **Then** they can run the project locally using the documented commands (both Docker-based and native development modes).
2. **Given** a contributor opens a new pull request, **When** the PR creation form appears, **Then** it is pre-populated with a template containing sections for summary, type of change, testing done, and a submission checklist.
3. **Given** a contributor reads CONTRIBUTING.md, **When** they look for code style guidance, **Then** they find documented conventions for Python, TypeScript, and Rust, along with instructions for running the linter.
4. **Given** a contributor wants to understand an architectural decision, **When** they follow the ADR links in CONTRIBUTING.md, **Then** they can read the relevant Architecture Decision Record explaining the rationale.
5. **Given** a new contributor browses the issue tracker, **When** they filter by the "good first issue" label, **Then** they find at least five well-described, self-contained issues suitable for a first contribution.

---

### User Story 4 — Experienced Developer Evaluation (Priority: P2)

An experienced developer is evaluating The Embedinator against competing RAG tools (RAGFlow, LangChain-based solutions). They want to assess: architectural sophistication, test quality, CI maturity, community governance, and license compatibility with their organization's policies. They spend 10-15 minutes reviewing the repository before deciding whether to recommend it.

**Why this priority**: Enterprise adoption and developer advocacy depend on the repository meeting professional standards. Missing governance files, absent CI, or stale documentation are disqualifying signals for experienced evaluators. This story validates the "expert eye" perspective.

**Independent Test**: Review the repository as an evaluator. Check for: license clarity, CI status, test coverage metrics, architecture documentation, security policy, and changelog. Compare the repository's completeness against GitHub's community standards checklist.

**Acceptance Scenarios**:

1. **Given** an evaluator checks the repository's community profile, **When** they view GitHub's "Community Standards" page, **Then** all recommended items are marked as present: README, CODE_OF_CONDUCT, CONTRIBUTING, LICENSE, SECURITY, issue templates, and PR template.
2. **Given** an evaluator examines the changelog, **When** they read CHANGELOG.md, **Then** they find a structured history covering the project's development from initial architecture through all 19 specifications.
3. **Given** an evaluator inspects the CI configuration, **When** they review the workflow files, **Then** they find separate jobs for linting, testing, and security scanning with appropriate caching and path filtering.
4. **Given** an evaluator checks the security posture, **When** they read SECURITY.md, **Then** they find a vulnerability disclosure policy with a contact method and expected response timeline.

---

### User Story 5 — Security-Conscious User (Priority: P3)

A security-conscious user or compliance officer reviews The Embedinator before deploying it in their organization. They need to verify the license terms, understand how vulnerabilities are reported, and confirm that the project follows security best practices (dependency scanning, secret detection).

**Why this priority**: Security and compliance are table stakes for enterprise adoption. While The Embedinator is a local-first tool, organizations still require license review and vulnerability disclosure processes before deploying any open-source software.

**Independent Test**: Review the repository for security-relevant files and configurations. Verify that SECURITY.md exists with disclosure instructions, that Dependabot is monitoring dependencies, and that the license is clearly stated.

**Acceptance Scenarios**:

1. **Given** a security reviewer reads SECURITY.md, **When** they look for a disclosure process, **Then** they find an email address for reporting vulnerabilities, an expected acknowledgment timeline, and a disclosure policy.
2. **Given** a compliance officer checks the LICENSE file, **When** they verify compatibility, **Then** the license is a recognized permissive license compatible with all project dependencies.
3. **Given** a security reviewer checks for dependency monitoring, **When** they inspect the repository configuration, **Then** Dependabot is configured to monitor all four dependency ecosystems (Python, Node.js, Rust, GitHub Actions).

---

### User Story 6 — Maintainer Release Workflow (Priority: P3)

The project maintainer (Bruno) creates a versioned release of The Embedinator. They tag the release, and automated workflows generate a GitHub Release with release notes. The changelog is up to date, and the version number is consistent across all project files.

**Why this priority**: A structured release process signals project maturity and gives users confidence that they are running a specific, tested version. This story enables the initial public release and establishes the pattern for future releases.

**Independent Test**: Create a version tag and push it. Verify that the release workflow triggers, creates a GitHub Release, and attaches release notes derived from the changelog.

**Acceptance Scenarios**:

1. **Given** the maintainer creates an annotated version tag, **When** the tag is pushed to the remote, **Then** a GitHub Actions workflow creates a GitHub Release with the tag name, release notes, and links to the changelog.
2. **Given** a release is published, **When** a user visits the Releases page, **Then** they see the version number, a summary of changes, and instructions for getting started.
3. **Given** the maintainer checks version numbers across the project, **When** they inspect the changelog, frontend package.json, and any version files, **Then** all version numbers are consistent and match the release tag.

---

### Edge Cases

- What happens when a user clones the repository on Windows and opens files with a text editor that doesn't respect `.editorconfig`? Line endings should still be correct due to `.gitattributes` enforcement.
- What happens when CI runs on a fork? Workflows should be configured to handle fork PRs safely (limited permissions, no secret access).
- What happens when a badge service (shields.io) is temporarily unavailable? The README should degrade gracefully — broken badge images should not prevent understanding the content.
- What happens when a contributor submits a PR that adds a file matching a `.gitignore` pattern (e.g., `.env`)? CI should not allow secrets to be committed; pre-commit hooks should catch this locally.
- What happens when Dependabot creates a PR that fails CI? The PR should be clearly marked as failing, and the maintainer should be notified to review.

## Requirements *(mandatory)*

### Functional Requirements

#### Area 1: License & Legal

- **FR-001** `[LEGAL]`: The repository MUST contain an Apache License 2.0 file at the root, recognized by GitHub's license detection. The full license text MUST be the standard Apache 2.0 text with the copyright holder set to the project maintainer.
- **FR-002** `[LEGAL]`: The repository MUST contain a CODE_OF_CONDUCT.md at the root using the Contributor Covenant v2.1, with the maintainer's contact information filled in.
- **FR-003** `[LEGAL]`: The repository MUST contain a SECURITY.md at the root with: supported versions, a private email address for vulnerability reports, an expected acknowledgment timeline (48 hours), and a disclosure policy (90-day coordinated disclosure).
- **FR-004** `[LEGAL]`: The repository MUST contain an `.editorconfig` file at the root specifying indent style and size for Python (4 spaces), TypeScript/JavaScript/JSON (2 spaces), Rust (4 spaces), YAML (2 spaces), and Markdown (trailing whitespace preserved). All files MUST use UTF-8 encoding and LF line endings (except `.ps1` which uses CRLF, already enforced by `.gitattributes`).

#### Area 2: README

- **FR-005** `[README]`: The README Quick Start section MUST show `./embedinator.sh` as the primary setup command with Docker Desktop as the sole prerequisite. The multi-tool developer setup (Python, Node.js, Rust) MUST be moved to a secondary "Development Setup" section.
- **FR-006** `[README]`: The README MUST display at least four live badges: CI status, test coverage percentage, license type, and primary language version. Badges MUST NOT be commented-out HTML.
- **FR-007** `[README]`: The README MUST include at least three screenshots of the running application embedded as images: (1) the chat interface with a conversation showing citations and confidence, (2) the collections or documents page, and (3) the observability dashboard. At least one screenshot MUST show dark mode.
- **FR-008** `[README]`: The README specifications table MUST list all 19 specifications (001 through 019) with their completion status.
- **FR-009** `[README]`: The README License section MUST name the chosen license and link to the LICENSE file. The Contributing section MUST link to CONTRIBUTING.md.
- **FR-010** `[README]`: The README project structure tree MUST reflect the current file layout including spec-18 frontend reorganization (shadcn/ui components, theme provider, sidebar layout).
- **FR-011** `[README]`: The README MUST include a "Why The Embedinator?" or equivalent section that differentiates the project from simpler RAG tools by highlighting the 3-layer agent architecture, meta-reasoning recovery, grounded answer verification, and 5-signal confidence scoring.

#### Area 3: Contributing Guide

- **FR-012** `[CONTRIB]`: A CONTRIBUTING.md file MUST exist at the repository root. GitHub MUST detect it and display the "Contributing" link in the repository sidebar.
- **FR-013** `[CONTRIB]`: CONTRIBUTING.md MUST include a "First-Time Contributors" section with step-by-step instructions: fork, clone, create branch, make changes, run tests, submit PR.
- **FR-014** `[CONTRIB]`: CONTRIBUTING.md MUST include a "Development Setup" section covering both Docker-based development (`./embedinator.sh --dev`) and native development (Makefile targets).
- **FR-015** `[CONTRIB]`: CONTRIBUTING.md MUST document code style conventions for Python (ruff), TypeScript (project conventions), and Rust (cargo fmt), with commands to run each linter.
- **FR-016** `[CONTRIB]`: CONTRIBUTING.md MUST reference the Code of Conduct and link to all 8 Architecture Decision Records in the documentation directory.
- **FR-017** `[CONTRIB]`: CONTRIBUTING.md MUST document the commit message convention (conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `chore:`, `refactor:`, `ci:`).
- **FR-018** `[CONTRIB]`: All references to `claudedocs/` in the existing contributing guide MUST be updated to the correct documentation path. All `<repo-url>` placeholders MUST be replaced with the actual GitHub repository URL.

#### Area 4: Changelog

- **FR-019** `[CHANGELOG]`: A CHANGELOG.md file MUST exist at the repository root following the Keep a Changelog format (keepachangelog.com).
- **FR-020** `[CHANGELOG]`: The changelog MUST cover the full project history grouped into logical releases. Changes MUST be categorized as: Added, Changed, Fixed, or Infrastructure.
- **FR-021** `[CHANGELOG]`: The changelog MUST accurately reflect the capabilities added by all 19 specifications, grouped by functional area (Agent Architecture, Retrieval Pipeline, Ingestion, API, Frontend, Providers, Quality & Testing, Infrastructure, UX/UI, Cross-Platform).

#### Area 5: GitHub Infrastructure

- **FR-022** `[GITHUB]`: A CI workflow MUST trigger on every pull request and push to the main branch. It MUST run: backend linting, backend tests (excluding Docker-dependent tests), frontend linting, frontend tests, and Docker image build validation.
- **FR-023** `[GITHUB]`: The CI workflow MUST use path filtering so that changes to backend files only trigger backend jobs, and changes to frontend files only trigger frontend jobs. Changes to Docker or CI configuration files MUST trigger all jobs.
- **FR-024** `[GITHUB]`: The CI workflow MUST cache dependencies (Python packages, Node modules) across runs to reduce execution time.
- **FR-025** `[GITHUB]`: A security scanning workflow MUST run on push to main and on a weekly schedule. It MUST include static analysis for Python and TypeScript code.
- **FR-026** `[GITHUB]`: A release workflow MUST trigger when a version tag (matching `v*`) is pushed. It MUST create a GitHub Release with the tag name and release notes.
- **FR-027** `[GITHUB]`: Bug report and feature request issue templates MUST exist as YAML forms in `.github/ISSUE_TEMPLATE/`. The bug report template MUST include fields for: description, steps to reproduce, expected behavior, actual behavior, environment (OS, Docker version), and logs. The feature request template MUST include fields for: problem description, proposed solution, and alternatives considered.
- **FR-028** `[GITHUB]`: An issue template configuration file MUST redirect general questions to GitHub Discussions instead of allowing blank issues.
- **FR-029** `[GITHUB]`: A pull request template MUST exist at `.github/PULL_REQUEST_TEMPLATE.md` with sections for: summary of changes, type of change (bug fix / feature / docs / other), testing performed, and a checklist (tests pass, lint passes, no secrets committed, documentation updated if needed).
- **FR-030** `[GITHUB]`: A Dependabot configuration file MUST exist at `.github/dependabot.yml` monitoring: Python packages (requirements.txt), Node packages (frontend/package.json), Rust crates (ingestion-worker/Cargo.toml), and GitHub Actions versions.
- **FR-031** `[GITHUB]`: GitHub Discussions MUST be enabled with at least four categories: Announcements (maintainer-only), Q&A, Ideas, and Show and Tell.
- **FR-032** `[GITHUB]`: At least five issues MUST be created and labeled "good first issue" before the public launch. Each issue MUST include a clear description, acceptance criteria, and relevant file paths.

#### Area 6: Repository Cleanup

- **FR-033** `[CLEANUP]`: The `.gitignore` file MUST be updated to exclude: `CLAUDE.md`, `AGENTS.md`, `skills-lock.json`, `.agents/`, `.claude/`, `.specify/`, `.serena/`, `.gitnexus/`, `.coverage`, `frontend/test-results/`, and `Docs/PROMPTS/`.
- **FR-034** `[CLEANUP]`: The files `CLAUDE.md`, `AGENTS.md`, and `skills-lock.json` MUST be removed from git tracking (via `git rm --cached`) while preserving them on the local filesystem.
- **FR-035** `[CLEANUP]`: The directories `.agents/` and `.specify/` MUST be removed from git tracking (via `git rm -r --cached`) while preserving them on the local filesystem.
- **FR-036** `[CLEANUP]`: The `Docs/PROMPTS/` directory (174 internal agent instruction files) MUST be removed from git tracking (via `git rm -r --cached`) and added to `.gitignore`. The files MUST be preserved on the local filesystem. The README MAY optionally mention that the project was built using AI-assisted development with Claude Code.
- **FR-037** `[CLEANUP]`: The `Docs/DEVELOPMENT-STATUS.md` file MUST be updated to reflect the current project state including specifications 018 (UX/UI Redesign) and 019 (Cross-Platform DX).
- **FR-038** `[CLEANUP]`: The `docker-compose.prod.yml` file MUST be audited for correctness against the current `docker-compose.yml`. If it is non-functional or redundant, it MUST be removed.

#### Area 7: Screenshots & Media

- **FR-039** `[MEDIA]`: At least four screenshots MUST be captured from the running application with realistic data (not empty states): (1) chat page with conversation, citations, and confidence badge in light mode, (2) chat page in dark mode, (3) collections or documents page, (4) observability dashboard with traces and charts.
- **FR-040** `[MEDIA]`: Screenshots MUST be stored in a `docs/images/` directory (lowercase) and referenced from the README using relative paths.
- **FR-041** `[MEDIA]`: A social preview image (1280x640 pixels) MUST be created for the GitHub repository settings. It MUST include the project name, tagline, and a visual element (screenshot or architecture diagram).

#### Area 8: Test Stabilization

- **FR-042** `[TEST]`: All 39 pre-existing test failures MUST be addressed so that the CI test suite produces a green result. Each failure MUST be resolved by one of: (a) fixing the underlying issue, (b) marking with `@pytest.mark.xfail(reason="...")` for known limitations, or (c) marking with `@pytest.mark.skip(reason="...")` for infrastructure-dependent tests.
- **FR-043** `[TEST]`: The CI workflow MUST run backend tests with the marker filter that excludes Docker-dependent tests (those marked `require_docker`).
- **FR-044** `[TEST]`: The `pytest.ini` file MUST include a `testpaths = tests` directive to speed up test discovery.

#### Area 9: Pre-commit Hooks & Linting Config

- **FR-045** `[HOOKS]`: A `.pre-commit-config.yaml` file MUST be created with hooks for: Python linting and formatting (ruff), trailing whitespace removal, end-of-file newline enforcement, YAML validation, and JSON validation.
- **FR-046** `[HOOKS]`: A ruff configuration file MUST be created (either `ruff.toml` or a `[tool.ruff]` section in `pyproject.toml`) specifying: the target Python version, line length, selected rule sets, and excluded directories.

#### Area 10: Release Preparation

- **FR-047** `[RELEASE]`: The initial release MUST use semantic versioning with the version number v0.2.0, matching the existing `frontend/package.json` version.
- **FR-048** `[RELEASE]`: An annotated git tag MUST be created for the release version (format: `v0.2.0`).
- **FR-049** `[RELEASE]`: A GitHub Release MUST be created from the version tag, including: a summary of the project's capabilities, key features, prerequisites (Docker Desktop), and a quick start command.

#### Area 11: Documentation

- **FR-050** `[DOCS]`: The documentation directory MUST be reorganized from `Docs/Project Blueprints/` to `docs/` (lowercase, no spaces) to follow GitHub conventions. All internal references to the old path MUST be updated.
- **FR-051** `[DOCS]`: The Architecture Decision Records (8 ADRs) MUST remain accessible at `docs/adr/` and linked from CONTRIBUTING.md.
- **FR-052** `[DOCS]`: GitHub repository settings MUST include relevant topics for discoverability. At minimum: `rag`, `retrieval-augmented-generation`, `llm`, `self-hosted`, `python`, `fastapi`, `nextjs`, `docker`, `langgraph`, `qdrant`, `ollama`.

### Key Entities

- **Governance File**: A standard open-source governance document (LICENSE, CODE_OF_CONDUCT.md, SECURITY.md, CONTRIBUTING.md) that GitHub recognizes and surfaces in the repository sidebar and community standards checklist.
- **CI Workflow**: A GitHub Actions workflow definition (YAML file in `.github/workflows/`) that automatically validates code quality, test results, and build integrity on every pull request and push to main.
- **Issue Template**: A YAML-based form definition (in `.github/ISSUE_TEMPLATE/`) that guides users to provide structured, actionable information when reporting bugs or requesting features.
- **Release**: A versioned, tagged snapshot of the repository published as a GitHub Release, with release notes summarizing changes since the last version.
- **Screenshot**: A PNG image captured from the running application that visually demonstrates a feature or page, stored in the repository and embedded in the README.

### Non-Functional Requirements

- **NFR-001**: The CI workflow MUST complete all jobs within 15 minutes for a typical pull request on GitHub-hosted runners.
- **NFR-002**: All images embedded in the README MUST render correctly on GitHub's web interface. No broken image links.
- **NFR-003**: All hyperlinks in the README and CONTRIBUTING.md MUST resolve to valid targets (no dead links, no placeholder URLs).
- **NFR-004**: CONTRIBUTING.md MUST be detected by GitHub and displayed in the repository sidebar under the "Contributing" heading.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The repository has a LICENSE file that GitHub automatically identifies and displays in the repository sidebar (e.g., "Apache-2.0" or "MIT" label).
- **SC-002**: The CI workflow passes on the main branch, and the CI status badge in the README displays a green "passing" state.
- **SC-003**: The README Quick Start section shows `./embedinator.sh` as a single-command setup with Docker Desktop as the only prerequisite — no mention of Python, Node.js, or Rust installation for end-users.
- **SC-004**: At least three screenshots of the running application are visible in the README, rendering correctly on GitHub's web interface.
- **SC-005**: CONTRIBUTING.md exists at the repository root and is linked from both the README and the GitHub sidebar.
- **SC-006**: All pre-existing test failures are either fixed or annotated (xfail/skip) so that the CI test suite produces a green result with zero unexpected failures.
- **SC-007**: No internal development artifacts (CLAUDE.md, AGENTS.md, skills-lock.json, .agents/, .specify/) appear in the repository's tracked files after the cleanup.
- **SC-008**: Dependabot is configured and monitoring at least Python (pip) and Node.js (npm) dependency ecosystems.
- **SC-009**: A GitHub Release exists with a version tag (v0.2.0), release notes, and a quick start command.
- **SC-010**: A new user can go from `git clone` to a running application by executing the single launcher command with zero manual intermediate steps (no `.env` creation, no model downloading, no tool installation beyond Docker).
- **SC-011**: CODE_OF_CONDUCT.md and SECURITY.md exist at the repository root. SECURITY.md includes a private contact method for vulnerability reports.
- **SC-012**: GitHub's Community Standards page (Settings > Community Standards) shows all recommended items as present: Description, README, Code of Conduct, Contributing, License, Security Policy, Issue Templates, Pull Request Template.

## Assumptions

- Docker Desktop is widely available on all three major operating systems (Windows, macOS, Linux) and is the accepted standard for running multi-service applications.
- The application is currently running with the spec-18 "Intelligent Warmth" UI and can be started locally to capture screenshots with realistic data.
- The 39 pre-existing test failures are documented in `Docs/DEVELOPMENT-STATUS.md` and can be categorized and annotated without changing production behavior.
- GitHub-hosted runners have sufficient resources to build Docker images and run the test suite within 15 minutes.
- The maintainer has a personal email address suitable for security vulnerability reports (not a public issue tracker).
- All 19 specifications have been implemented and committed to the repository.
- The current `frontend/package.json` version `0.2.0` is the intended launch version.
- GitHub Discussions can be enabled via repository settings without additional tooling.
- The `Docs/Project Blueprints/contributing.md` content is a valid starting point for the root CONTRIBUTING.md but requires updates (fixing stale references and adding new sections).
- The GitHub repository URL is `https://github.com/Bruno-Ghiberto/The-Embedinator`. All `<repo-url>` placeholders, badge URLs, and clone instructions MUST use this URL.

## Out of Scope

- No new application features — the app is feature-complete for launch
- No new test files — only modify existing tests (fix, xfail, skip)
- No PyPI or npm package publishing — the distribution model is Docker, not package managers
- No Docker Hub or GHCR image publishing — users build locally via the launcher script
- No Kubernetes, Helm charts, or cloud deployment — Docker Compose on a single machine only
- No authentication or multi-tenant features — trusted local network model is a design choice
- No MCP server integration — deprioritized in favor of cross-platform DX
- No production code changes — only documentation, configuration, CI/CD, and test annotations
- No Makefile changes — all 14 existing targets preserved unchanged
- No database schema changes
- No changes to the launcher scripts (embedinator.sh / embedinator.ps1)
- No GitHub Pages documentation site — README and docs/ directory are sufficient for v0.2.0
- No `.devcontainer` configuration for GitHub Codespaces — deferred to a future enhancement

## File Impact Map

| File | Action | Purpose |
|------|--------|---------|
| `LICENSE` | CREATE | Open-source license file recognized by GitHub |
| `CODE_OF_CONDUCT.md` | CREATE | Contributor Covenant v2.1 behavioral expectations |
| `SECURITY.md` | CREATE | Vulnerability disclosure policy |
| `CONTRIBUTING.md` | CREATE | Root-level contributing guide (consolidated from Docs/) |
| `CHANGELOG.md` | CREATE | Full project changelog covering specs 001-019 |
| `.editorconfig` | CREATE | Cross-editor indentation and encoding consistency |
| `.pre-commit-config.yaml` | CREATE | Pre-commit hook configuration (ruff, whitespace, YAML) |
| `ruff.toml` | CREATE | Ruff linter configuration (rules, line length, target version) |
| `docs/` | CREATE | Renamed and reorganized documentation directory |
| `docs/images/` | CREATE | Screenshot storage for README |
| `docs/adr/` | CREATE | Architecture Decision Records (moved from Docs/Project Blueprints/adr/) |
| `.github/workflows/ci.yml` | CREATE | CI pipeline: lint, test, build on PR and push |
| `.github/workflows/security.yml` | CREATE | Security scanning: CodeQL, dependency review |
| `.github/workflows/release.yml` | CREATE | Tag-triggered GitHub Release creation |
| `.github/ISSUE_TEMPLATE/bug_report.yml` | CREATE | Structured bug report form |
| `.github/ISSUE_TEMPLATE/feature_request.yml` | CREATE | Structured feature request form |
| `.github/ISSUE_TEMPLATE/config.yml` | CREATE | Issue template configuration (redirect questions to Discussions) |
| `.github/PULL_REQUEST_TEMPLATE.md` | CREATE | PR submission template with checklist |
| `.github/dependabot.yml` | CREATE | Dependency update monitoring configuration |
| `README.md` | MODIFY | Major rewrite: badges, screenshots, updated quickstart, specs table |
| `.gitignore` | MODIFY | Add exclusions for dev tooling (CLAUDE.md, .agents/, .specify/, etc.) |
| `pytest.ini` | MODIFY | Add testpaths directive |
| `Docs/DEVELOPMENT-STATUS.md` | MODIFY | Update to cover specs 018-019 |
| `CLAUDE.md` | DELETE (from tracking) | Remove from git via `git rm --cached` (keep local) |
| `AGENTS.md` | DELETE (from tracking) | Remove from git via `git rm --cached` (keep local) |
| `skills-lock.json` | DELETE (from tracking) | Remove from git via `git rm --cached` (keep local) |
| `.agents/` | DELETE (from tracking) | Remove from git via `git rm -r --cached` (keep local) |
| `.specify/` | DELETE (from tracking) | Remove from git via `git rm -r --cached` (keep local) |
| `.coverage` | DELETE (from tracking) | Remove from git via `git rm --cached` (keep local) |
| `Docs/PROMPTS/` | DELETE (from tracking) | Remove 174 internal agent files via `git rm -r --cached` (keep local) |
| `Docs/Project Blueprints/` | DELETE | Replaced by `docs/` (content moved, not deleted) |
| `docker-compose.prod.yml` | DELETE or MODIFY | Audit and remove if stale, or update if functional |
| `Makefile` | PRESERVE | All 14 targets unchanged |
| `embedinator.sh` | PRESERVE | No changes |
| `embedinator.ps1` | PRESERVE | No changes |
| `docker-compose.yml` | PRESERVE | No changes |
| `docker-compose.dev.yml` | PRESERVE | No changes |
| `docker-compose.gpu-*.yml` | PRESERVE | No changes |
| `Dockerfile.backend` | PRESERVE | No changes |
| `frontend/Dockerfile` | PRESERVE | No changes |
| Tests (39 failing) | MODIFY | Add xfail/skip annotations, no production code changes |
