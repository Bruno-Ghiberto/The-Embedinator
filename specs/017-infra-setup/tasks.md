# Tasks: Project Infrastructure

**Input**: Design documents from `specs/017-infra-setup/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: No new test files — this is an infrastructure audit/remediation spec. Existing test suite is used as a regression gate via `scripts/run-tests-external.sh`.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US5)

---

## Phase 1: Setup (Audit & Baseline)

**Purpose**: Establish post-spec-16 baseline and produce a complete gap report before any files are modified.

- [X] T001 Run baseline test suite and record exact passing count AND pre-existing failure count: `zsh scripts/run-tests-external.sh -n spec17-baseline --no-cov tests/`
- [X] T002 Audit `Dockerfile.backend` against FR-004 (multi-stage Rust+Python) and FR-015 (non-root user) — record gaps
- [X] T003 [P] Audit `Makefile` against FR-011 (14 named targets) and FR-012 (coverage gate) — list missing targets
- [X] T004 [P] Audit `backend/config.py` against FR-009: check `api_key_encryption_secret` for `EMBEDINATOR_FERNET_KEY` alias, `confidence_threshold` type (must be int), `default_llm_model` value, all spec-04/10/15 fields
- [X] T005 [P] Audit `.env.example` against FR-010: count documented variables vs Settings fields
- [X] T006 [P] Audit `docker-compose.yml` against FR-006 (health checks), FR-007 (volumes), FR-008 (GPU passthrough), FR-014 (restart policies)
- [X] T007 [P] Create `Docs/PROMPTS/spec-17-infra/agents/` directory and write instruction files `A2-instructions.md` through `A5-instructions.md` based on audit gaps

**Checkpoint**: Baseline test count recorded. All gaps documented. Instruction files ready.

---

## Phase 2: Foundational (Shared Verification)

**Purpose**: Verify shared infrastructure files that all user stories depend on.

**⚠️ CRITICAL**: These files underpin all 5 user stories — verify before beginning any story phase.

- [X] T008 Verify `requirements.txt` has correct package names: `langchain-core` (not `langchain`), `langchain-ollama` (not `langchain-community`), `langgraph-checkpoint-sqlite>=2.0` — add any missing entries
- [X] T009 [P] Verify `.gitignore` covers: `data/`, `.env`, `.venv/`, `node_modules/`, `.next/`, `target/`, `__pycache__/`, `*.pyc` — add any missing patterns
- [X] T010 [P] Verify `ingestion-worker/Cargo.toml` has all required Rust deps: `serde = "1"`, `serde_json = "1"`, `pulldown-cmark = "0.12"`, `pdf-extract = "0.8"`, `clap = "4"`, `regex = "1"` — add any missing crates

**Checkpoint**: Shared infrastructure verified. All 5 user story phases can begin.

---

## Phase 3: User Story 1 — First-Time Developer Setup (Priority: P1) 🎯 MVP

**Goal**: A developer runs `make setup` on a clean checkout and gets a fully working environment with no manual steps (SC-001).

**Independent Test**: Run `make setup` on a clean machine; verify Python deps, Node deps, and Rust binary are installed without errors.

- [X] T011 [US1] Add `setup` target to `Makefile` that sequentially runs: `pip install -r requirements.txt`, `cd frontend && npm install`, `$(MAKE) build-rust`
- [X] T012 [US1] Add `build-rust` target to `Makefile` that runs `cargo build --release` inside `ingestion-worker/` and verifies the binary exists at `ingestion-worker/target/release/embedinator-worker`
- [X] T013 [US1] Add `pull-models` target to `Makefile` that runs `docker exec` (or `ollama pull`) to download `qwen2.5:7b` and `nomic-embed-text` models

**Checkpoint**: `make setup` + `make build-rust` work end-to-end. US1 independently testable.

---

## Phase 4: User Story 2 — Developer-Mode Iteration (Priority: P2)

**Goal**: A developer runs `make dev` and code changes appear in under 3 seconds with no container rebuilds (SC-002).

**Independent Test**: Start `make dev`; modify a backend source file; verify the backend process reloads within 3 seconds.

- [X] T014 [US2] Add `dev-infra` target to `Makefile` that starts Qdrant + Ollama only via `docker-compose.dev.yml`: `docker compose -f docker-compose.dev.yml up -d`
- [X] T015 [P] [US2] Add `dev-backend` target to `Makefile` that runs: `uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000`
- [X] T016 [P] [US2] Add `dev-frontend` target to `Makefile` that runs: `cd frontend && npm run dev`
- [X] T017 [US2] Add `dev` target to `Makefile` that calls `dev-infra` then starts `dev-backend` and `dev-frontend` in background processes (or instructs to run them in separate terminals)
- [X] T018 [US2] Verify `docker-compose.dev.yml` contains exactly 2 services (Qdrant + Ollama) and does NOT start backend or frontend containers — if backend/frontend services are present, remove them

**Checkpoint**: `make dev-infra` + `make dev-backend` + `make dev-frontend` all work independently. US2 independently testable.

---

## Phase 5: User Story 3 — Full Production Deployment (Priority: P3)

**Goal**: `make up` starts all 4 services healthy within 120 seconds, with non-root containers and persistent data (SC-003, SC-004, SC-007).

**Independent Test**: Run `make up` on a machine with Docker; verify all 4 services report healthy; stop and restart; verify data persists.

- [X] T019 [US3] Rewrite `Dockerfile.backend` as multi-stage build — Stage 1: `FROM rust:1.93 AS rust-builder`, compiles `ingestion-worker/`, Stage 2: `FROM python:3.14-slim`, copies compiled binary to `ingestion-worker/target/release/embedinator-worker`, installs Python deps, copies `backend/` (FR-004)
- [X] T020 [US3] Add non-root user to `Dockerfile.backend` before `CMD`: `RUN addgroup --system appgroup && adduser --system --ingroup appgroup --no-create-home appuser` then `USER appuser` (FR-015)
- [X] T021 [P] [US3] Verify `frontend/Dockerfile` has non-root user (`USER nextjs`) and copies from `.next/standalone` — read-only verification, no changes expected (FR-005, FR-015)
- [X] T022 [US3] Verify/add NVIDIA GPU passthrough block to Ollama service in `docker-compose.yml` under `deploy.resources.reservations.devices` (FR-008)
- [X] T023 [P] [US3] Verify all 4 services in `docker-compose.yml` have `healthcheck` sections with `test`, `interval`, `timeout`, `retries`, `start_period` (FR-006)
- [X] T024 [P] [US3] Verify all 4 services in `docker-compose.yml` have `restart: unless-stopped` (FR-014)
- [X] T025 [P] [US3] Verify named volumes in `docker-compose.yml` cover: Qdrant storage, SQLite database, uploaded files — add any missing volume declarations (FR-007)
- [X] T026 [US3] Add/verify Docker networking env var overrides on the backend service in `docker-compose.yml`: `QDRANT_HOST: qdrant`, `OLLAMA_BASE_URL: http://ollama:11434`, `SQLITE_PATH: /data/embedinator.db`, `UPLOAD_DIR: /data/uploads`, `LOG_LEVEL_OVERRIDES: ${LOG_LEVEL_OVERRIDES:-}`, `RUST_WORKER_PATH: /app/ingestion-worker/target/release/embedinator-worker`
- [X] T027 [US3] Rename existing `docker-up` target to `up` in `Makefile` (or replace body with `docker compose up --build -d`) — do NOT add a second target; FR-011 requires exactly 14 named targets
- [X] T028 [P] [US3] Rename existing `docker-down` target to `down` in `Makefile` (or replace body with `docker compose down`) — do NOT add a second target
- [X] T029 [P] [US3] Add header comment to `docker-compose.prod.yml` explaining it is a production override file for backend + frontend resource limits and production env vars; update `Makefile` `up` target to optionally merge it

**Checkpoint**: `make up` starts all 4 healthy services. `make down` + `make up` restores all data. US3 independently testable.

---

## Phase 6: User Story 4 — Environment Configuration (Priority: P4)

**Goal**: Every setting is documented in `.env.example`; `backend/config.py` reads all env vars correctly including `EMBEDINATOR_FERNET_KEY` (SC-005, Constitution V).

**Independent Test**: Count Settings fields in `config.py` and entries in `.env.example` — they must match. The app starts with a valid `.env` without reading source code.

- [X] T030 [US4] Fix `backend/config.py`: change `api_key_encryption_secret: str = ""` to `api_key_encryption_secret: str = Field(default="", alias="EMBEDINATOR_FERNET_KEY")` — add `from pydantic import Field` import if missing (Constitution V)
- [X] T031 [P] [US4] Verify `confidence_threshold: int = 60` in `backend/config.py` (must be `int`, not `float = 0.6`) — correct if wrong
- [X] T032 [P] [US4] Verify `default_llm_model: str = "qwen2.5:7b"` in `backend/config.py` — correct if wrong
- [X] T033 [P] [US4] Verify spec-04/10/15 fields exist in `backend/config.py` with correct types and defaults: `log_level_overrides`, `frontend_port`, `compression_threshold`, `meta_relevance_threshold`, `meta_variance_threshold`, `rate_limit_provider_keys_per_minute`, `rate_limit_general_per_minute` — add any missing fields
- [X] T034 [US4] Audit `.env.example` completeness: for every field in `Settings`, ensure a corresponding entry exists in `.env.example` with format `# Description. Expected: type. Default: value.\nENV_VAR=default` — add all missing entries; ensure `EMBEDINATOR_FERNET_KEY` entry exists with generation instructions (FR-010, SC-005)
- [X] T035 [US4] Gate check — run config tests: `zsh scripts/run-tests-external.sh -n spec17-config --no-cov tests/unit/test_config.py`; wait for completion and verify failure count does not exceed the pre-existing baseline failure count recorded in T001 (1 known pre-existing failure in test_config.py is acceptable)

**Checkpoint**: `backend/config.py` reads `EMBEDINATOR_FERNET_KEY`. All fields documented. Config test failure count ≤ baseline. US4 independently testable.

---

## Phase 7: User Story 5 — Test Execution and Coverage (Priority: P5)

**Goal**: `make test-cov` enforces ≥80% coverage and exits non-zero when below threshold; `make test-frontend` runs vitest (SC-006).

**Independent Test**: Run `make test-cov`; verify it exits non-zero when coverage < 80%; run `make test-frontend`; verify frontend tests execute.

- [X] T036 [US5] Add `test-cov` target to `Makefile`: `pytest --cov=backend --cov-report=term-missing --cov-fail-under=80 tests/` (FR-012, SC-006) — ensure this is distinct from existing `test` target
- [X] T037 [P] [US5] Add `test-frontend` target to `Makefile`: `cd frontend && npm run test` (or `npx vitest run`)
- [X] T038 [P] [US5] Verify `clean` target in `Makefile` removes `data/` directory contents without affecting Docker volumes or model downloads — fix if it does not
- [X] T039 [P] [US5] Add `clean-all` target to `Makefile`: runs `docker compose down -v`, removes `data/`, removes `ingestion-worker/target/`, removes `frontend/.next/`

**Checkpoint**: `make test-cov` enforces coverage gate. `make test-frontend` runs. US5 independently testable.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Self-documentation, final validation, and reporting.

- [X] T040 Add `## Short description` comment to ALL 14 FR-011 Makefile targets (SC-008); add `help` target that auto-prints all targets with descriptions using `grep -E '^[a-zA-Z_-]+:.*?## '`
- [X] T041 [P] Verify `next.config.ts` in `frontend/` has `output: "standalone"` (FR-013)
- [X] T042 [P] Verify `data/` directory path is git-ignored and not committed — check `.gitignore` and `git status`
- [X] T043 Run final validation suite: `zsh scripts/run-tests-external.sh -n spec17-final tests/` — wait for status, compare passing count to baseline from T001
- [X] T044 Write `specs/017-infra-setup/validation-report.md` with: final test count + coverage %, per-FR status (PASS/FAIL/N/A), per-SC status, Constitution V compliance confirmation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Can start after Phase 1 audit is complete
- **User Stories (Phase 3–7)**: Depend on Foundational (Phase 2) completion; can then proceed in any order (P1→P5) or in parallel
- **Polish (Phase 8)**: Depends on all user story phases complete

### User Story Dependencies

| Story | Depends On | Depends On Other Stories? |
|-------|-----------|--------------------------|
| US1 (setup) | Phase 2 (requirements.txt, Cargo.toml) | No |
| US2 (dev mode) | Phase 2 (docker-compose.dev.yml verified) | No |
| US3 (production) | Phase 2; US1 (build-rust needed for Dockerfile.backend) | US1 for Dockerfile.backend |
| US4 (config) | Phase 2 | No |
| US5 (testing) | Phase 2; US4 (test_config.py must pass) | US4 for gate check T035 |

### Within Each User Story

- Verification tasks before modification tasks
- `backend/config.py` changes (US4) before any integration that depends on them
- Gate check runs AFTER all modifications in that story are complete
- Commit after each user story phase completes

### Parallel Opportunities

**Phase 1**: T002, T003, T004, T005, T006, T007 all [P] — run simultaneously after T001
**Phase 2**: T009, T010 [P] alongside T008
**US3 Phase**: T021, T023, T024, T025, T028, T029 all [P] — run after T019/T020
**US4 Phase**: T031, T032, T033 [P] — run after T030 (Field import change) completes
**US5 Phase**: T037, T038, T039 [P] — run alongside T036

---

## Parallel Execution Examples

### Phase 1 (after T001 baseline completes)
```
Parallel batch A:
  T002 - Audit Dockerfile.backend
  T003 - Audit Makefile
  T004 - Audit backend/config.py
  T005 - Audit .env.example
  T006 - Audit docker-compose.yml
  T007 - Create agent instruction files
```

### US3 Production Deployment (after T019+T020 complete)
```
Parallel batch B:
  T021 - Verify frontend/Dockerfile (read-only)
  T023 - Verify health checks in docker-compose.yml
  T024 - Verify restart policies in docker-compose.yml
  T025 - Verify named volumes in docker-compose.yml
  T028 - Add `down` target to Makefile
  T029 - Add docker-compose.prod.yml header
```

### US4 Configuration (after T030 Field import fix)
```
Parallel batch C:
  T031 - Verify confidence_threshold int type
  T032 - Verify default_llm_model value
  T033 - Verify spec-04/10/15 fields
```

---

## Agent Teams Mapping

| Wave | Agents | Tasks |
|------|--------|-------|
| Wave 1 (A1) | infrastructure-engineer (Sonnet) | T001–T007 |
| Wave 2 (A2) | python-expert (Sonnet) | T030–T035 (US4) |
| Wave 2 (A3) | python-expert (Sonnet, parallel) | T019–T021 (US3 Docker) |
| Wave 3 (A4) | backend-architect (Sonnet) | T011–T018 (US1+US2), T022–T029 (US3 compose+Makefile), T036–T039 (US5) |
| Wave 4 (A5) | quality-engineer (Sonnet) | T040–T044 (Polish + validation) |

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (audit + baseline)
2. Complete Phase 2: Foundational (requirements.txt, .gitignore, Cargo.toml)
3. Complete Phase 3: US1 — `make setup` + `make build-rust` targets
4. **STOP and VALIDATE**: `make setup` works end-to-end on a clean checkout
5. Continue to US2–US5 incrementally

### Incremental Delivery (Recommended)

1. Phase 1 + Phase 2 → Foundation verified
2. US4 (config) first — fixes Constitution V violation, unblocks all other stories
3. US1 (setup) → US2 (dev mode) → US3 (production) → US5 (testing)
4. Phase 8 (polish) → final validation report

### Agent Teams Parallel Execution

**Wave 2 runs A2 + A3 in parallel**:
- A2 handles US4 (config.py + .env.example) — T030–T035
- A3 handles US3 Dockerfile work — T019–T021
- Both complete before Wave 3 (A4) begins

---

## Notes

- [P] tasks = different files, no conflicting edits, safe to run in parallel
- [Story] label maps each task to a specific user story for traceability
- No new test files are created — this spec validates existing infrastructure only
- Tests run via `zsh scripts/run-tests-external.sh` — NEVER `pytest` directly inside Claude Code
- The script accepts ONE target; run separate invocations for multi-file gates
- Commit after each user story phase completes and gate check passes
- Baseline passing count + pre-existing failure count (T001) are the regression reference for final validation (T043)
