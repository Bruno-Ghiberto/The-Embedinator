# Implementation Plan: Testing Strategy

**Branch**: `016-testing-strategy` | **Date**: 2026-03-18 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/016-testing-strategy/spec.md`

## Summary

Spec 16 fills test coverage gaps in The Embedinator without touching any production code. Specs 01–15 produced 1405 passing tests; this spec adds: a shared `tests/conftest.py` with 4 reusable fixtures, 5 unit test files for uncovered modules (`Reranker`, `normalize_scores`, `chunk_text`, `index_chunks`, `EmbeddinatorError`), 3 Python backend E2E tests in `tests/e2e/`, 3 Docker-dependent integration tests, and 3 committed binary fixture files. The 80% coverage gate is enforced as a hard exit via `--cov-fail-under=80` in `pytest.ini`. Implementation uses a 5-wave Agent Team pattern with parallel waves for the bulk of test writing.

---

## Technical Context

**Language/Version**: Python 3.14+ (backend tests); TypeScript 5.7 (frontend tests — out of scope, already passing)
**Primary Dependencies**: pytest >= 8.0, pytest-asyncio >= 0.24, pytest-cov >= 6.0, httpx >= 0.28 — all already installed
**Storage**: In-memory SQLite (`:memory:`) for all unit tests; real Qdrant on `localhost:6333` for `@pytest.mark.require_docker` tests
**Testing**: `zsh scripts/run-tests-external.sh` — the only permitted test invocation method inside Claude Code agents
**Target Platform**: Linux (CI), macOS (development) — identical via Python
**Project Type**: Test infrastructure (pure test files + configuration; no production code)
**Performance Goals**: Unit suite (`tests/unit/`) completes in < 30 seconds, single-process
**Constraints**: Zero regressions; total passing count must reach >= 1405; coverage >= 80% (hard gate)
**Scale/Scope**: 5 new unit test files, 3 E2E test files, 3 integration test files, 1 conftest.py, 1 pytest.ini, 3 fixture binary files

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Local-First Privacy** | ✅ PASS | No production code changes; no network calls introduced. Tests use `:memory:` SQLite and mock/real-local services only. |
| **II. Three-Layer Agent Architecture** | ✅ PASS | Tests verify the three-layer graph (Conversation → Research → MetaReasoning) — do not alter it. `tests/mocks.py` already provides `build_mock_research_graph()`. |
| **III. Retrieval Pipeline Integrity** | ✅ PASS | New tests for `Reranker`, `normalize_scores`, `HybridSearcher` verify the mandatory pipeline components. No component is removed or replaced. |
| **IV. Observability from Day One** | ✅ PASS | E2E test `test_observability_e2e.py` verifies trace records exist after queries. Coverage gate ensures observability code paths are tested. |
| **V. Secure by Design** | ✅ PASS | Tests use `:memory:` SQLite, never commit API keys, no plaintext credentials. `pytest.ini` does not disable security fixtures. |
| **VI. NDJSON Streaming Contract** | ✅ PASS | `test_chat_e2e.py` verifies `retrieval_complete`, `answer_chunk`, and `done` event types in NDJSON stream. |
| **VII. Simplicity by Default** | ✅ PASS | No `testcontainers` package required (socket-check instead). No new services. No new abstractions. YAGNI applied throughout. |
| **VIII. Cross-Platform Compatibility** | ✅ PASS | Test files are pure Python (cross-platform). `pytest.ini` is cross-platform. `scripts/run-tests-external.sh` is bash/zsh — constitution explicitly permits this; Windows users use WSL. |

**All 8 principles pass. No gate violations. No Complexity Tracking required.**

---

## Project Structure

### Documentation (this feature)

```text
specs/016-testing-strategy/
├── plan.md              ← This file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/           ← Phase 1 output
│   └── test-contracts.md
└── tasks.md             ← Phase 2 output (/speckit.tasks — not created here)
```

### Source Code (this feature adds only test files)

```text
tests/
├── conftest.py                        ← NEW (P1) — 4 shared fixtures + marker hooks
├── pytest.ini                         ← NEW (Wave 4) — markers + --cov-fail-under=80
├── unit/
│   ├── test_reranker.py               ← NEW (P2, A2)
│   ├── test_score_normalizer.py       ← NEW (P2, A2)
│   ├── test_storage_chunker.py        ← NEW (P2, A2)
│   ├── test_storage_indexing.py       ← NEW (P2, A3)
│   └── test_errors.py                 ← NEW (P2, A3)
├── e2e/
│   ├── __init__.py                    ← NEW
│   ├── test_ingest_e2e.py             ← NEW (P3, A4)
│   ├── test_chat_e2e.py               ← NEW (P3, A4)
│   └── test_collection_e2e.py         ← NEW (P3, A4)
├── integration/
│   ├── test_qdrant_integration.py     ← NEW (P4, A5)
│   ← test_hybrid_search.py            ← NEW (P4, A5)
│   └── test_circuit_breaker.py        ← NEW (P4, A5)
└── fixtures/
    ├── sample.pdf                     ← NEW committed binary (P5, A6)
    ├── sample.md                      ← NEW committed text (P5, A6)
    └── sample.txt                     ← NEW committed text (P5, A6)

Docs/PROMPTS/spec-16-testing/agents/
├── a1-instructions.md                 ← Created by orchestrator before Wave 1
├── a2-instructions.md                 ← Created by A1
├── a3-instructions.md                 ← Created by A1
├── a4-instructions.md                 ← Created by A1
├── a5-instructions.md                 ← Created by A1
├── a6-instructions.md                 ← Created by A1
└── a7-instructions.md                 ← Created by A1
```

**Structure Decision**: Flat `tests/unit/` layout (matching existing structure), with `tests/e2e/` as the new backend E2E tier. No new subdirectories under `tests/unit/`.

---

## Agent Team Wave Structure

Implementation uses the 5-wave Agent Teams pattern established in specs 07–15.

### Wave 1 — A1 (quality-engineer, Opus 4.6)
**Scope**: Scaffold + baseline verification + instruction file authoring
- Confirm baseline: run `zsh scripts/run-tests-external.sh -n spec16-baseline --no-cov tests/` → verify 1405 tests
- Verify the 5 production modules exist at correct paths with correct symbol names
- Create `tests/conftest.py` with 4 shared fixtures (exact code from research.md)
- Create `pytest.ini` at project root
- Create `tests/fixtures/` directory
- Write instruction files a2–a7 in `Docs/PROMPTS/spec-16-testing/agents/`
- Gate: `zsh scripts/run-tests-external.sh -n spec16-after-scaffold --no-cov tests/unit/` must PASS

### Wave 2 — A2 + A3 (python-expert, Sonnet 4.6, parallel)
**A2**: `test_reranker.py`, `test_score_normalizer.py`, `test_storage_chunker.py`
**A3**: `test_storage_indexing.py`, `test_errors.py`
- Gate: each agent's target files must pass independently before Wave 3

### Wave 3 — A4 + A5 (python-expert, Sonnet 4.6, parallel)
**A4**: `tests/e2e/` — 3 backend Python E2E tests with `@pytest.mark.e2e` + `try/finally` teardown
**A5**: 3 Docker integration tests with `@pytest.mark.require_docker` + auto-skip when Qdrant unavailable
- Gate: A4 `e2e` marker run PASS; A5 shows all `require_docker` tests skip cleanly when Qdrant absent

### Wave 4 — A6 (python-expert, Sonnet 4.6)
**Scope**: Committed fixture files + coverage gate
- Create `tests/fixtures/sample.pdf` (valid PDF magic bytes, < 50 KB)
- Create `tests/fixtures/sample.md`, `tests/fixtures/sample.txt`
- Confirm `pytest.ini` has `--cov-fail-under=80`
- Gate: fixture files committed; coverage run shows gate active

### Wave 5 — A7 (quality-engineer, Sonnet 4.6)
**Scope**: Full suite validation
- Run `zsh scripts/run-tests-external.sh -n spec16-final tests/` — verify >= 1405 passing, 0 new failures
- Verify E2E tests pass; Docker tests auto-skip when Qdrant absent
- Verify coverage >= 80% (hard gate)
- Write `specs/016-testing-strategy/validation-report.md`
