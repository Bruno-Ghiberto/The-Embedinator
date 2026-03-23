# Implementation Plan: End-to-End Debug & Verification

**Branch**: `021-e2e-debug-verification` | **Date**: 2026-03-20 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/021-e2e-debug-verification/spec.md`
**Context Prompt**: [`Docs/PROMPTS/spec-21-debug/21-plan.md`](../../Docs/PROMPTS/spec-21-debug/21-plan.md)

## Summary

Make The Embedinator work end-to-end for the first time. Despite 20 specs implementing
conversation graph, retrieval pipeline, ingestion, API, frontend, and infrastructure, the
application has never been operationally verified as a complete system. This spec debugs
startup failures, fixes configuration issues, seeds test data, verifies every user flow
(startup → ingestion → chat with citations → all pages), and establishes a repeatable
smoke test suite. All fixes are minimal and targeted (NFR-001) — no refactoring, no feature
additions.

## Technical Context

**Language/Version**: Python 3.14+ (backend), TypeScript 5.7 (frontend), Rust 1.93.1 (ingestion worker — unchanged)
**Primary Dependencies**: FastAPI >=0.135, Next.js 16, LangGraph >=1.0.10, Docker Compose v2, httpx >=0.28
**Storage**: SQLite WAL mode (`data/embedinator.db`), Qdrant (vector search) — no schema changes
**Testing**: pytest (backend), vitest (frontend), `scripts/smoke_test.py` (new E2E), Playwright MCP (browser verification)
**Target Platform**: Docker Desktop on Windows 11+, macOS 13+, Linux (Ubuntu/Fedora/Debian) — Constitution VIII
**Project Type**: Full-stack web application (Python API + Next.js SPA + Docker infrastructure)
**Performance Goals**: Services healthy <5 min (SC-001), ingestion <3 min (SC-003), chat response <30s (SC-004)
**Constraints**: NFR-001 (minimal fixes only), NFR-002 (Makefile byte-identical), NFR-003 (zero test regressions), NFR-004 (clear commit rationale)
**Scale/Scope**: 1-5 concurrent users, 4 Docker services, 6 known root causes + undiscovered bugs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Evaluation |
|---|-----------|--------|------------|
| I | Local-First Privacy | **PASS** | No cloud dependencies added. All fixes target existing local-first architecture (Docker, Ollama, SQLite). No authentication introduced. |
| II | Three-Layer Agent Architecture | **PASS** | Agent architecture not modified. Spec verifies the existing 3-layer graph works end-to-end. A2 verifies LangGraph graph compilation during startup. |
| III | Retrieval Pipeline Integrity | **PASS** | Retrieval pipeline not modified. Spec verifies existing hybrid search + cross-encoder reranking works with real data. Seeding uses existing chunking pipeline. |
| IV | Observability from Day One | **PASS** | Trace recording not modified. Spec verifies existing `query_traces` table receives records from E2E chat queries. Observability page verified in FR-020. |
| V | Secure by Design | **PASS** | A2 verifies `EMBEDINATOR_FERNET_KEY` auto-generation (or graceful `key_manager=None` on missing key). No security controls weakened. Parameterized SQL preserved. |
| VI | NDJSON Streaming Contract | **PASS** | Streaming protocol not modified. A5 verifies existing NDJSON streaming works E2E: chunk frames, metadata frame with citations. |
| VII | Simplicity by Default | **PASS** | 4 Docker services maintained (no 5th service). SQLite unchanged. New scripts (`seed_data.py`, `smoke_test.py`) use existing dependencies only (httpx). YAGNI enforced via NFR-001. |
| VIII | Cross-Platform Compatibility | **PASS** | Docker remains sole deployment mechanism. All fixes target Docker Compose config (compose.yml, Dockerfiles). No platform-specific assumptions introduced. Seed/smoke scripts use `pathlib.Path` if filesystem access needed. |

**Gate Result**: **ALL PASS** — no violations. Proceeding to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/021-e2e-debug-verification/
├── spec.md              # Feature specification (exists)
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── smoke-test.md    # Smoke test script contract
│   └── seed-data.md     # Seed data script contract
└── checklists/
    └── requirements.md  # Quality checklist (exists)
```

### Source Code (repository root)

```text
# Existing structure — spec-21 adds minimal files

backend/
├── api/
│   ├── health.py        # FIX: /api/health/live endpoint registration
│   ├── chat.py          # VERIFY: NDJSON streaming E2E
│   ├── collections.py   # VERIFY: collection CRUD
│   └── ingest.py        # VERIFY: file upload + ingestion
├── config.py            # FIX: populate_by_name, fernet_key defaults
├── main.py              # FIX: router registration, lifespan startup
└── storage/
    └── sqlite_db.py     # VERIFY: table creation on first run

frontend/
├── app/
│   ├── chat/page.tsx         # VERIFY: renders, no console errors
│   ├── collections/page.tsx  # VERIFY: renders with real data
│   ├── settings/page.tsx     # VERIFY: renders provider config
│   ├── observability/page.tsx # VERIFY: renders health + traces
│   └── healthz/route.ts      # VERIFY: returns 200
├── lib/api.ts           # VERIFY: relative URLs correct
├── next.config.ts       # VERIFY: rewrites proxy to BACKEND_URL
└── Dockerfile           # FIX: if build fails (diagnose exit code 1)

scripts/
├── seed_data.py         # NEW: idempotent data seeding
└── smoke_test.py        # NEW: automated E2E verification

docs/
├── fixes-log.md         # NEW: all bugs documented
├── known-issues.md      # NEW: remaining issues
└── runbook.md           # UPDATE: E2E verification section

docker-compose.yml       # FIX: build/env configuration if needed
.env.example             # FIX: document all required vars

tests/                   # NO CHANGES (only new smoke_test.py)
Makefile                 # SACRED: zero changes (SC-009)
```

**Structure Decision**: Existing monorepo structure preserved. Spec-21 adds 2 new scripts
(`scripts/seed_data.py`, `scripts/smoke_test.py`) and 2 new docs (`docs/fixes-log.md`,
`docs/known-issues.md`). All other changes are minimal fixes to existing files.

## SonarQube Code Quality Analysis

### Overview

A comprehensive static analysis of the entire codebase using SonarQube Community Edition,
executed via the SonarQube MCP server (`mcp__MCP_DOCKER__*` sonarqube tools). This runs
during the Polish phase after all fixes are applied, producing a quality baseline for the
first operational release.

### Language Targets

| Language | Target Paths | SonarQube CE Support | Notes |
|----------|-------------|---------------------|-------|
| **Python** | `backend/**/*.py` | Native | Full analysis: bugs, vulnerabilities, code smells, complexity, duplication |
| **TypeScript** | `frontend/**/*.ts`, `frontend/**/*.tsx` | Native | Full analysis including React/JSX patterns |
| **CSS (Tailwind)** | `frontend/app/globals.css`, `frontend/**/*.css` | Native (CSS) | Analyzes CSS syntax including `@tailwind` and `@apply` directives. Tailwind utility classes in TSX are covered by TypeScript analysis. |
| **Rust** | `ingestion-worker/src/**/*.rs` | Via plugin | `community-rust` plugin installed and confirmed (Rust rules available at `/coding_rules?languages=rust`). Full project-level analysis supported. |

### MCP Tools Used

| Tool | Purpose |
|------|---------|
| `ping_system` | Verify SonarQube server is reachable |
| `get_system_health` | Check server status (GREEN/YELLOW/RED) |
| `list_languages` | Confirm which languages the instance supports |
| `analyze_file_list` | Batch analyze files by absolute path (primary tool) |
| `analyze_code_snippet` | Analyze individual files/snippets with explicit language (fallback for Rust) |
| `search_sonar_issues_in_projects` | Query analysis results by severity |
| `get_component_measures` | Retrieve metrics: lines of code, complexity, coverage, violations |
| `search_dependency_risks` | Find SCA (dependency) vulnerabilities |

### Setup Requirements

The SonarQube MCP server is pre-configured in the Docker MCP gateway but requires:

1. **Running SonarQube instance**: Deploy via Docker:
   ```bash
   docker run -d --name sonarqube -p 9000:9000 sonarqube:community
   # Wait for startup (~2 min), then access http://localhost:9000
   # Default credentials: admin/admin (change on first login)
   ```

2. **Generate access token**: SonarQube UI → My Account → Security → Generate Token
   (type: "Global Analysis Token", name: "embedinator-mcp")

3. **Configure MCP**: Set environment variables for the SonarQube MCP server:
   ```bash
   # Via docker mcp config or .mcp.json
   SONARQUBE_URL=http://localhost:9000
   SONARQUBE_TOKEN=<generated-token>
   ```

4. **Create project**: Via SonarQube UI or API — project key: `the-embedinator`

### Analysis Approach

1. **Verify connectivity**: `ping_system` → "pong", `get_system_health` → "GREEN"
2. **Check language support**: `list_languages` → confirm Python, TypeScript, CSS, Rust all present
3. **Run batch analysis**: `analyze_file_list` for Python, TypeScript, and CSS files
4. **Run Rust analysis**: `analyze_code_snippet` per key Rust file (6-8 files in `ingestion-worker/src/`)
5. **Query results**: `search_sonar_issues_in_projects` filtered by severity (BLOCKER, CRITICAL first)
6. **Get metrics**: `get_component_measures` for LOC, complexity, duplication, coverage per component
7. **Check dependencies**: `search_dependency_risks` for known CVEs in pip/npm/cargo dependencies
8. **Triage**: BLOCKER/CRITICAL issues → fix (if in scope) or document in known-issues.md
9. **Generate report**: `docs/sonarqube-report.md` with per-language findings and metrics

### Output Artifact

`docs/sonarqube-report.md` containing:
- Analysis metadata (date, SonarQube version, languages, rule profiles)
- Per-language summary table (bugs, vulnerabilities, smells, hotspots by severity)
- BLOCKER/CRITICAL issue triage (disposition: fix / defer / false-positive)
- Dependency risk summary (CVEs found, if any)
- Metrics dashboard (LOC, complexity, duplication % per component)
- Recommendations for future quality gates

## Complexity Tracking

> No violations detected. Constitution check passed cleanly.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| *None* | — | — |
