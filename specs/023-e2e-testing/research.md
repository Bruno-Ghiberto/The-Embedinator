# Research: Comprehensive E2E Testing

**Feature**: 023-e2e-testing
**Date**: 2026-03-25

## Research Summary

All unknowns in the Technical Context were pre-resolved through the intelligence analysis of prior E2E attempts (Spec 21, Guided Hybrid E2E Loop, Backend-Frontend Fix session). No NEEDS CLARIFICATION markers existed in the spec. This research document consolidates the key findings.

## Decision 1: Testing Execution Model

**Decision**: Single orchestrator + user (sequential), NOT parallel agent waves.
**Rationale**: E2E testing requires real-time user interaction (browser navigation, visual verification, quality evaluation). Parallel agents cannot substitute for human judgment on UI quality, response coherence, or visual integrity.
**Alternatives considered**:
- Fully automated Playwright-only approach -- rejected because all existing Playwright tests except `workflow.spec.ts` are mocked against fake data. Live browser testing requires real services.
- Parallel agent waves (like Spec 21) -- rejected because testing is inherently sequential (later phases depend on data created in earlier phases).

## Decision 2: Environment Prerequisites

**Decision**: Require native Docker Engine (not Desktop) with nvidia-container-toolkit.
**Rationale**: Docker Desktop on Linux cannot pass NVIDIA GPU to containers (confirmed via official docs, GitHub issue #497, open since 2022, no timeline). Chat pipeline is unusable without GPU (27.7s with GPU vs unusable on CPU).
**Alternatives considered**:
- Docker Desktop with CPU-only testing -- rejected because chat latency makes the E2E experience unrealistic.
- WSL2 GPU passthrough -- not applicable on native Linux (already running native).

## Decision 3: Impasse Protocol Severity Classification

**Decision**: 4-tier severity (BLOCKER/HIGH/MEDIUM/LOW) with automatic halt on BLOCKER/HIGH.
**Rationale**: Spec 21 found 22 bugs across all severity levels. A flat "stop on every failure" approach would be impractical. The tiered approach allows LOW/MEDIUM issues to be documented without blocking progress, while ensuring critical failures are addressed immediately.
**Alternatives considered**:
- Binary pass/fail (all failures block) -- rejected, too rigid for 91+ checks
- No severity classification (log everything, continue always) -- rejected, risks missing critical issues

## Decision 4: Stale Data Handling

**Decision**: Wipe `embedinator.db` and `checkpoints.db` in Phase 0 for clean start.
**Rationale**: The guided-hybrid session (2026-03-22) proved that stale data causes false failures (UNIQUE constraint violations, old schema without new columns, `CREATE TABLE IF NOT EXISTS` being no-op). The schema migration path is unreliable.
**Alternatives considered**:
- Run migrations on existing data -- rejected because `ALTER TABLE ADD COLUMN` rejects non-constant defaults in SQLite, and existing tables may have old schemas.
- Test with existing data -- rejected because stale collections trip the circuit breaker.

## Decision 5: Known Issues as Expected Failures

**Decision**: Pre-document 6 known issues (KNOWN-001 through KNOWN-006) as expected failures that should be logged but not block testing.
**Rationale**: These issues were discovered in prior E2E attempts and represent architectural gaps (raw RetrievedChunk repr, confidence=0, disabled meta-reasoning) that require dedicated fix specs, not E2E testing patches.
**Alternatives considered**:
- Fix all known issues before E2E testing -- rejected because the E2E should test the system as-is and document its real state.
- Ignore known issues entirely -- rejected because they still need to be documented for the acceptance report.

## Decision 6: Deliverable Format

**Decision**: Three files -- e2e-guide.md (operational), logs.md (execution log), acceptance-report.md (summary).
**Rationale**: The guide enables reproducibility (NFR-004), the log provides audit trail (SC-009), the report provides the acceptance decision (FR-054).
**Alternatives considered**:
- Single monolithic document -- rejected, too hard to maintain during real-time testing.
- Structured database (SQLite) -- rejected, overkill for a single-session testing workflow.

## Prior E2E Bug Reference

25 bugs were fixed across prior E2E efforts:
- **Spec 21**: 22 bugs (4 Docker/Infra, 2 Backend, 1 Frontend, 4 Ingestion, 8 LangGraph/Chat, 3 Orchestrator)
- **Guided Hybrid**: 3 bugs (hot-reload crash, embed endpoint fallback, chunk ID collisions)

Full bug list is in `Docs/PROMPTS/spec-23-E2E-Test/23.specify.md` under "Reference: 22 Bugs Fixed in Spec 21".
