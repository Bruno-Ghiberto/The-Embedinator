# Tasks: Comprehensive E2E Testing

**Input**: Design documents from `/specs/023-e2e-testing/`
**Prerequisites**: plan.md (required), spec.md (required), contracts/testing-protocol.md

**Tests**: Not applicable -- this spec IS the testing process.

**Organization**: Tasks are grouped by testing phase, mapping to user stories. Phases execute sequentially with mandatory gate checks between them.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel within the same phase
- **[Story]**: Which user story this task validates (US1-US7)
- **AUTOMATED**: Orchestrator executes (command/MCP tool)
- **MANUAL**: User performs in browser/terminal, orchestrator confirms

---

## Phase 1: Setup (Testing Infrastructure)

**Purpose**: Create deliverable files and prepare testing environment

- [x] T001 Create `Docs/PROMPTS/spec-23-E2E-Test/logs.md` with initial template (session header, environment info)
- [x] T002 Create `Docs/PROMPTS/spec-23-E2E-Test/e2e-guide.md` with phase scaffold (11 section headers, prerequisites)
- [x] T003 Save session start to Engram via `mem_session_start`

**Checkpoint**: Testing infrastructure ready -- logs.md and e2e-guide.md exist with scaffolding.

---

## Phase 2: Foundational -- Environment Pre-flight (Phase 0)

**Purpose**: Verify all infrastructure prerequisites before installation

**FR**: FR-001 through FR-004 | **SC**: SC-001

**CRITICAL**: Cannot proceed to TUI installation until all pre-flight checks pass

- [x] T004 [P] [US1] AUTOMATED -- Verify Docker Engine is running and is native (not Desktop) via `sg docker -c "docker info"`
- [x] T005 [P] [US1] AUTOMATED -- Verify GPU accessible via `sg docker -c "docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu24.04 nvidia-smi"`
- [x] T006 [P] [US1] AUTOMATED -- Check `~/.docker/config.json` credsStore is `""` (not `"desktop"`)
- [x] T007 [P] [US1] AUTOMATED -- Check port availability (3000, 8000, 6333, 11434) via `ss -tlnp`
- [x] T008 [US1] AUTOMATED -- Wipe stale data: `rm -f data/embedinator.db data/checkpoints.db`
- [x] T009 [US1] AUTOMATED -- Verify Go binary exists or build: `ls ./embedinator || (cd cli && go build -o ../embedinator ./cmd/embedinator)`
- [x] T010 [US1] Log all Phase 0 results to `logs.md` and update `e2e-guide.md` Phase 0 section
- [x] T011 [US1] Present Phase 0 Gate Report -- wait for user confirmation

**Checkpoint**: Environment verified. All pre-flight checks pass. Ready for TUI installation.

---

## Phase 3: User Story 1 -- First-Run Installation (Priority: P1)

**Goal**: Install the application via TUI and have all services running and healthy

**FR**: FR-005 through FR-012 | **SC**: SC-001, SC-002

**Independent Test**: TUI completes, 4 containers healthy, health endpoints respond, models available

### TUI Installation (Phase 1)

- [x] T012 [US1] MANUAL -- Instruct user to run `./embedinator` or `./embedinator setup`
- [x] T013 [US1] MANUAL -- Guide user through wizard (ports, model selection, API keys)
- [x] T014 [US1] AUTOMATED -- Verify all 4 containers running: `sg docker -c "docker compose ps"`
- [x] T015 [P] [US1] AUTOMATED -- Verify backend health: `curl -sf http://localhost:8000/api/health`
- [x] T016 [P] [US1] AUTOMATED -- Verify frontend accessible: `curl -sf http://localhost:3000 -o /dev/null -w "%{http_code}"`
- [x] T017 [US1] AUTOMATED -- Verify models available: `sg docker -c "docker exec ollama ollama list"`
- [x] T018 [US1] AUTOMATED -- If `nomic-embed-text` missing, pull it: `sg docker -c "docker exec ollama ollama pull nomic-embed-text"` (KNOWN-006)
- [x] T019 [US1] MANUAL -- Ask user to confirm TUI showed success screen
- [x] T020 [US1] Log Phase 1 results to `logs.md` and update `e2e-guide.md`
- [x] T021 [US1] Present Phase 1 Gate Report -- wait for user confirmation

### Backend Health and API Verification (Phase 2)

- [x] T022 [P] [US1] AUTOMATED -- Hit `/api/health` -- verify all services healthy (FR-009)
- [x] T023 [P] [US1] AUTOMATED -- Hit `/api/stats` -- verify response structure (FR-009)
- [x] T024 [P] [US1] AUTOMATED -- Hit `/api/models/llm` -- verify at least one LLM model (FR-010)
- [x] T025 [P] [US1] AUTOMATED -- Hit `/api/models/embed` -- verify at least one embed model (FR-010)
- [x] T026 [P] [US1] AUTOMATED -- Hit `/api/providers` -- verify provider list (FR-010)
- [x] T027 [P] [US1] AUTOMATED -- Hit `/api/settings` -- verify settings with defaults (FR-011)
- [x] T028 [US1] AUTOMATED -- Verify Qdrant reachable from backend container (FR-012)
- [x] T029 [US1] AUTOMATED -- Verify database schema (all expected tables exist in embedinator.db) (FR-012)
- [x] T030 [US1] Log Phase 2 results to `logs.md` and update `e2e-guide.md`
- [x] T031 [US1] Present Phase 2 Gate Report -- wait for user confirmation

**Checkpoint**: Application fully installed, all services healthy, all APIs responding.

---

## Phase 4: User Story 4 -- Frontend Navigation (Priority: P2)

**Goal**: Every page loads correctly with consistent layout, theme, and navigation

**FR**: FR-013 through FR-017 | **SC**: SC-003

**Independent Test**: Visit all 7 pages, toggle dark mode, collapse sidebar, open command palette -- zero JS errors

### Navigation Testing (Phase 3)

- [x] T032 [US4] AUTOMATED -- Navigate to `http://localhost:3000/` via Playwright -- verify redirect to /chat (FR-014)
- [x] T033 [P] [US4] AUTOMATED -- Navigate to `/chat` via Playwright -- capture screenshot + console messages (FR-013)
- [x] T034 [P] [US4] AUTOMATED -- Navigate to `/collections` via Playwright -- capture screenshot + console messages (FR-013)
- [x] T035 [P] [US4] AUTOMATED -- Navigate to `/settings` via Playwright -- capture screenshot + console messages (FR-013)
- [x] T036 [P] [US4] AUTOMATED -- Navigate to `/observability` via Playwright -- capture screenshot + console messages (FR-013)
- [x] T037 [US4] AUTOMATED -- Check console errors via Browser Tools MCP `getConsoleErrors` -- should be empty or benign (FR-013)
- [x] T038 [US4] MANUAL -- User opens browser, navigates to each page, confirms layout loads correctly
- [x] T039 [US4] MANUAL -- User confirms Chat page: sidebar, toolbar, input, message area render (FR-013)
- [x] T040 [US4] MANUAL -- User confirms Collections page loads (empty state OK) (FR-013)
- [x] T041 [US4] MANUAL -- User confirms Settings page: all 4 tabs visible (Providers, Models, Inference, System) (FR-013)
- [x] T042 [US4] MANUAL -- User confirms Observability page: dashboard structure renders (FR-013)
- [x] T043 [US4] MANUAL -- User toggles dark/light mode on 2-3 pages -- confirms consistent theming (FR-015)
- [x] T044 [US4] MANUAL -- User collapses/expands sidebar -- confirms animation and content adjustment (FR-016)
- [x] T045 [US4] MANUAL -- User presses Ctrl+K -- confirms command palette opens (FR-017)
- [x] T046 [US4] Log Phase 3 results to `logs.md` and update `e2e-guide.md`
- [x] T047 [US4] Present Phase 3 Gate Report -- wait for user confirmation

**Checkpoint**: All pages render correctly, no JS errors, UI shell is stable.

---

## Phase 5: User Story 2 -- Document Ingestion and Management (Priority: P1)

**Goal**: Create collections, upload documents in PDF/MD/TXT, verify chunks are searchable

**FR**: FR-018 through FR-029 | **SC**: SC-004

**Independent Test**: Create collection, upload 3 files (one per format), verify documents and chunks exist

### Collection Management (Phase 4)

- [x] T048 [US2] MANUAL -- User creates collection "test-collection-1" via UI (FR-018)
- [x] T049 [US2] AUTOMATED -- Verify collection in API: `curl -sf http://localhost:8000/api/collections` (FR-019)
- [x] T050 [US2] AUTOMATED -- Verify Qdrant collection exists via docker exec (FR-019)
- [x] T051 [US2] MANUAL -- User confirms collection appears in list immediately (FR-019)
- [x] T052 [US2] MANUAL -- User creates second collection "test-collection-2" (FR-022)
- [x] T053 [US2] MANUAL -- User tries invalid name (special characters) -- confirms error message (FR-021)
- [x] T054 [US2] MANUAL -- User deletes "test-collection-2" -- confirms removal (FR-020)
- [x] T055 [US2] AUTOMATED -- Verify deletion in API and Qdrant (FR-020)
- [x] T056 [US2] Log Phase 4 results to `logs.md` and update `e2e-guide.md`
- [x] T057 [US2] Present Phase 4 Gate Report -- wait for user confirmation

### Document Ingestion (Phase 5)

- [x] T058 [US2] MANUAL -- User navigates to test-collection-1 documents page (FR-023)
- [x] T059 [US2] MANUAL -- User uploads a PDF document via drag-and-drop or file picker (FR-023, FR-025)
- [x] T060 [US2] MANUAL -- User observes upload progress indication (FR-024)
- [x] T061 [US2] AUTOMATED -- Poll ingestion job status until complete (FR-024)
- [x] T062 [US2] AUTOMATED -- Verify chunks created in Qdrant (collection has vectors) (FR-025)
- [x] T063 [US2] AUTOMATED -- Verify parent chunks in SQLite (FR-025)
- [x] T064 [US2] MANUAL -- User uploads a Markdown (.md) file (FR-025)
- [x] T065 [US2] MANUAL -- User uploads a plain text (.txt) file (FR-025)
- [x] T066 [US2] MANUAL -- User tries unsupported file (.exe or .zip) -- confirms error (FR-026)
- [x] T067 [US2] MANUAL -- User tries empty (0-byte) file -- confirms error (FR-027)
- [x] T068 [US2] AUTOMATED -- Test re-ingestion of same file -- document behavior (FR-029, KNOWN-004)
- [x] T069 [US2] MANUAL -- User confirms document list shows all 3 uploaded files (FR-028)
- [x] T070 [US2] Log Phase 5 results to `logs.md` and update `e2e-guide.md`
- [x] T071 [US2] Present Phase 5 Gate Report -- wait for user confirmation

**Checkpoint**: Collections CRUD works. At least 3 documents ingested. Chunks searchable.

---

## Phase 6: User Story 3 -- Chat and Knowledge Retrieval (Priority: P1)

**Goal**: Ask questions about uploaded documents, get streaming natural-language answers with citations

**FR**: FR-030 through FR-038 | **SC**: SC-005

**Independent Test**: Select collection, ask question, verify stream events, evaluate response quality, test follow-up and session persistence

### Chat and RAG Testing (Phase 6)

- [ ] T072 [US3] MANUAL -- User selects test-collection-1 in chat config panel (FR-030)
- [ ] T073 [US3] MANUAL -- User asks: "What topics are covered in the uploaded documents?" (FR-031)
- [ ] T074 [US3] MANUAL -- User observes streaming response (tokens appearing progressively) (FR-031)
- [ ] T075 [US3] AUTOMATED -- Verify NDJSON stream via curl: check for session, status, chunk, confidence, done events (FR-031)
- [ ] T076 [US3] MANUAL -- User evaluates response QUALITY: natural language or raw RetrievedChunk repr? (FR-032, KNOWN-001)
- [ ] T077 [US3] MANUAL -- User checks citations: numbered badges, hover cards visible? (FR-033)
- [ ] T078 [US3] MANUAL -- User asks follow-up: "Can you elaborate on the first topic?" -- test session continuity (FR-034, KNOWN-005)
- [ ] T079 [US3] MANUAL -- User asks about content NOT in documents: "What is the weather today?" -- test graceful handling (FR-035)
- [ ] T080 [US3] AUTOMATED -- Verify confidence score present in done event (expected: 0, KNOWN-002) (FR-033)
- [ ] T081 [US3] AUTOMATED -- Verify trace_id present and trace recorded in SQLite: `curl -sf http://localhost:8000/api/traces` (FR-044)
- [ ] T082 [US3] MANUAL -- User checks response latency: acceptable (< 30s with GPU)? (FR-036)
- [ ] T083 [US3] AUTOMATED -- Verify chat session persisted (can be resumed after reload) (FR-037)
- [ ] T084 [US3] MANUAL -- User reloads page, checks chat history in sidebar -- sees previous session? (FR-038)
- [ ] T085 [US3] Log Phase 6 results to `logs.md` and update `e2e-guide.md`
- [ ] T086 [US3] Present Phase 6 Gate Report -- wait for user confirmation

**Checkpoint**: Chat produces streaming responses. Quality issues documented. Citations tested. Session persistence verified.

---

## Phase 7: User Story 5 -- Settings and Configuration (Priority: P2)

**Goal**: Configure settings, add/remove API keys, verify persistence across reloads

**FR**: FR-039 through FR-042 | **SC**: SC-006

**Independent Test**: Change model, add API key, reload page, verify all changes persisted

### Settings Testing (Phase 7)

- [ ] T087 [US5] MANUAL -- User navigates to Settings page (FR-039)
- [ ] T088 [US5] MANUAL -- User changes LLM model selection (FR-039)
- [ ] T089 [US5] AUTOMATED -- Verify setting persisted: `curl -sf http://localhost:8000/api/settings` (FR-040)
- [ ] T090 [US5] MANUAL -- User adds API key for cloud provider (e.g., `sk-test-12345` for OpenRouter) (FR-041)
- [ ] T091 [US5] AUTOMATED -- Verify key stored: `curl -sf http://localhost:8000/api/providers` (FR-042)
- [ ] T092 [US5] MANUAL -- User reloads page (F5) -- confirms settings and key persist (FR-040)
- [ ] T093 [US5] MANUAL -- User deletes the test API key -- confirms removal (FR-041)
- [ ] T094 [US5] AUTOMATED -- Verify key deleted: `curl -sf http://localhost:8000/api/providers` (FR-042)
- [ ] T095 [US5] Log Phase 7 results to `logs.md` and update `e2e-guide.md`
- [ ] T096 [US5] Present Phase 7 Gate Report -- wait for user confirmation

**Checkpoint**: Settings save, persist, survive reloads. API key CRUD works.

---

## Phase 8: User Story 6 -- Observability and System Health (Priority: P2)

**Goal**: View real usage metrics and health status after actual chat interactions

**FR**: FR-043 through FR-046 | **SC**: SC-007

**Independent Test**: After Phase 6 chat queries, observability shows real data in charts and traces

### Observability Testing (Phase 8)

- [ ] T097 [US6] MANUAL -- User navigates to Observability page (FR-043)
- [ ] T098 [US6] MANUAL -- User confirms charts render with REAL data (not empty placeholders) (FR-043)
- [ ] T099 [US6] AUTOMATED -- Verify traces exist: `curl -sf http://localhost:8000/api/traces` -- assert >= 3 (FR-044)
- [ ] T100 [US6] AUTOMATED -- Verify stats non-zero: `curl -sf http://localhost:8000/api/stats` -- assert total_queries > 0 (FR-046)
- [ ] T101 [US6] MANUAL -- User clicks trace row -- confirms detail view with stage timings (FR-044)
- [ ] T102 [US6] MANUAL -- User confirms health dashboard shows all services green (FR-045)
- [ ] T103 [US6] Log Phase 8 results to `logs.md` and update `e2e-guide.md`
- [ ] T104 [US6] Present Phase 8 Gate Report -- wait for user confirmation

**Checkpoint**: Observability shows real, meaningful data from actual usage.

---

## Phase 9: User Story 7 -- Error Resilience (Priority: P3)

**Goal**: Invalid actions produce helpful errors, app does not crash

**FR**: FR-047 through FR-050 | **SC**: SC-011

**Independent Test**: Send malformed requests, trigger UI errors, verify no white screens or crashes

### Edge Case Testing (Phase 9)

- [ ] T105 [P] [US7] AUTOMATED -- Send malformed request to `/api/chat`: `curl -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" -d '{"invalid": true}'` -- verify 422/400 (FR-047)
- [ ] T106 [P] [US7] AUTOMATED -- Send empty message: `curl -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" -d '{"message": "", "collection_ids": []}'` -- verify validation error (FR-047)
- [ ] T107 [P] [US7] AUTOMATED -- Invalid collection ID: `curl -sf http://localhost:8000/api/collections/nonexistent` -- verify 404 (FR-048)
- [ ] T108 [P] [US7] AUTOMATED -- Test file upload with 0-byte file -- verify proper error (FR-049)
- [ ] T109 [US7] AUTOMATED -- Rapid requests to test rate limiting (if configured) -- document 429 behavior (FR-047)
- [ ] T110 [US7] MANUAL -- User sends chat with no collection selected -- confirms user-friendly error (FR-050)
- [ ] T111 [US7] MANUAL -- User navigates to nonexistent URL (/nonexistent) -- confirms no white screen (FR-050)
- [ ] T112 [US7] MANUAL -- User checks error boundaries do not crash the app (FR-050)
- [ ] T113 [US7] Log Phase 9 results to `logs.md` and update `e2e-guide.md`
- [ ] T114 [US7] Present Phase 9 Gate Report -- wait for user confirmation

**Checkpoint**: Errors handled gracefully. No crashes. User-friendly messages.

---

## Phase 10: Polish -- Final Acceptance

**Purpose**: Run automated suites, user final walkthrough, generate acceptance report

**FR**: FR-051 through FR-054 | **SC**: SC-008 through SC-013

- [ ] T115 AUTOMATED -- Run full smoke test: `python3 scripts/smoke_test.py` -- target 13/13 (FR-051, SC-008)
- [ ] T116 AUTOMATED -- Run Playwright live test: `cd frontend && npx playwright test tests/e2e/workflow.spec.ts` (FR-052)
- [ ] T117 MANUAL -- User performs 5-minute speed run: Home -> Chat -> Collections -> Documents -> Settings -> Observability
- [ ] T118 MANUAL -- User does quick chat question during speed run -- verifies response
- [ ] T119 AUTOMATED -- Verify `logs.md` is complete (all phases have entries) (FR-053, SC-009)
- [ ] T120 AUTOMATED -- Generate `Docs/PROMPTS/spec-23-E2E-Test/acceptance-report.md` with phase matrix, bug summary, recommendation (FR-054, SC-010)
- [ ] T121 AUTOMATED -- Save session summary to Engram via `mem_session_summary` (SC-009)
- [ ] T122 Present FINAL Gate Report -- user makes acceptance decision (ACCEPT / CONDITIONAL / REJECT)

---

## Dependencies and Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies -- start immediately
- **Phase 2 (Pre-flight)**: Depends on Phase 1 -- BLOCKS all other phases
- **Phase 3 (Installation + API)**: Depends on Phase 2 -- BLOCKS all UI testing
- **Phase 4 (Navigation)**: Depends on Phase 3 -- can run before data phases
- **Phase 5 (Collections + Ingestion)**: Depends on Phase 3 -- needs running app
- **Phase 6 (Chat and RAG)**: Depends on Phase 5 -- needs ingested documents
- **Phase 7 (Settings)**: Depends on Phase 3 -- independent of Phases 5-6
- **Phase 8 (Observability)**: Depends on Phase 6 -- needs chat traces
- **Phase 9 (Edge Cases)**: Depends on Phase 3 -- can run after any data phase
- **Phase 10 (Acceptance)**: Depends on ALL phases completing

### User Story Dependencies

- **US-1 (Installation)**: Foundation -- all others depend on this
- **US-4 (Navigation)**: Depends on US-1 only -- first UI verification
- **US-2 (Ingestion)**: Depends on US-1 -- creates data for US-3
- **US-3 (Chat)**: Depends on US-2 -- needs documents to query
- **US-5 (Settings)**: Depends on US-1 -- independent of US-2/US-3
- **US-6 (Observability)**: Depends on US-3 -- needs traces from chat
- **US-7 (Error Cases)**: Depends on US-1 -- can run after any phase

### Critical Path

```
US-1 (Install) -> US-4 (Navigate) -> US-2 (Ingest) -> US-3 (Chat) -> US-6 (Observe) -> Final Acceptance
                                    /                                /
                  US-5 (Settings) --                                /
                  US-7 (Edge Cases) -------------------------------
```

### Parallel Opportunities

Within each phase, tasks marked [P] can run in parallel:
- Phase 2: T004-T007 (pre-flight checks) all [P]
- Phase 3 (Backend): T022-T027 (API endpoint checks) all [P]
- Phase 4 (Navigation): T033-T036 (Playwright page navigation) all [P]
- Phase 9 (Edge Cases): T105-T108 (bad request tests) all [P]

**Cross-phase parallelism**: US-5 (Settings) and US-7 (Edge Cases) can theoretically run in parallel with US-2 (Ingestion), but this is NOT recommended -- sequential execution with gate checks provides clearer bug isolation.

---

## Implementation Strategy

### MVP First (US-1 Installation Only)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 2: Pre-flight (T004-T011)
3. Complete Phase 3: Installation + API (T012-T031)
4. **STOP and VALIDATE**: App is running, APIs work, logs.md has 3 phases documented

### Full E2E (All User Stories)

1. MVP above -> Phase 4 (Navigation) -> Phase 5 (Ingestion) -> Phase 6 (Chat)
2. Phase 7 (Settings) + Phase 8 (Observability) + Phase 9 (Edge Cases)
3. Phase 10 (Final Acceptance) -> Acceptance Report

### Time Budget

| Phase | Tasks | Est. Time |
|-------|-------|-----------|
| Setup | T001-T003 | 5 min |
| Pre-flight | T004-T011 | 5 min |
| Installation + API | T012-T031 | 15 min |
| Navigation | T032-T047 | 15 min |
| Collections + Ingestion | T048-T071 | 25 min |
| Chat and RAG | T072-T086 | 20 min |
| Settings | T087-T096 | 10 min |
| Observability | T097-T104 | 10 min |
| Edge Cases | T105-T114 | 10 min |
| Acceptance | T115-T122 | 15 min |
| **Total** | **122 tasks** | **~2.5 hours** (without impasses) |

---

## FR Coverage Matrix

Every functional requirement maps to at least one task:

| FR | Task(s) | Phase |
|----|---------|-------|
| FR-001 | T004 | 2 |
| FR-002 | T005 | 2 |
| FR-003 | T007 | 2 |
| FR-004 | T008 | 2 |
| FR-005 | T012, T013 | 3 |
| FR-006 | T014 | 3 |
| FR-007 | T017, T018 | 3 |
| FR-008 | T019 | 3 |
| FR-009 | T022, T023 | 3 |
| FR-010 | T024, T025, T026 | 3 |
| FR-011 | T027 | 3 |
| FR-012 | T028, T029 | 3 |
| FR-013 | T033-T036, T038-T042 | 4 |
| FR-014 | T032 | 4 |
| FR-015 | T043 | 4 |
| FR-016 | T044 | 4 |
| FR-017 | T045 | 4 |
| FR-018 | T048 | 5 |
| FR-019 | T049, T050, T051 | 5 |
| FR-020 | T054, T055 | 5 |
| FR-021 | T053 | 5 |
| FR-022 | T052 | 5 |
| FR-023 | T058, T059 | 5 |
| FR-024 | T060, T061 | 5 |
| FR-025 | T059, T062, T063, T064, T065 | 5 |
| FR-026 | T066 | 5 |
| FR-027 | T067 | 5 |
| FR-028 | T069 | 5 |
| FR-029 | T068 | 5 |
| FR-030 | T072 | 6 |
| FR-031 | T073, T074, T075 | 6 |
| FR-032 | T076 | 6 |
| FR-033 | T077, T080 | 6 |
| FR-034 | T078 | 6 |
| FR-035 | T079 | 6 |
| FR-036 | T082 | 6 |
| FR-037 | T083 | 6 |
| FR-038 | T084 | 6 |
| FR-039 | T087, T088 | 7 |
| FR-040 | T089, T092 | 7 |
| FR-041 | T090, T093 | 7 |
| FR-042 | T091, T094 | 7 |
| FR-043 | T097, T098 | 8 |
| FR-044 | T081, T099, T101 | 8 |
| FR-045 | T102 | 8 |
| FR-046 | T100 | 8 |
| FR-047 | T105, T106, T109 | 9 |
| FR-048 | T107 | 9 |
| FR-049 | T108 | 9 |
| FR-050 | T110, T111, T112 | 9 |
| FR-051 | T115 | 10 |
| FR-052 | T116 | 10 |
| FR-053 | T119 | 10 |
| FR-054 | T120 | 10 |

---

## SC Coverage Matrix

| SC | Validated By | Phase |
|----|-------------|-------|
| SC-001 | T014, T015, T016, T017 | 3 |
| SC-002 | T022-T029 | 3 |
| SC-003 | T032-T045 | 4 |
| SC-004 | T048-T069 | 5 |
| SC-005 | T072-T084 | 6 |
| SC-006 | T087-T094 | 7 |
| SC-007 | T097-T102 | 8 |
| SC-008 | T115 | 10 |
| SC-009 | T010, T020, T030, T046, T056, T070, T085, T095, T103, T113, T119 | All |
| SC-010 | T002, T120 | 1, 10 |
| SC-011 | T105-T112 | 9 |
| SC-012 | T115, T116 | 10 |
| SC-013 | Time budget (< 5 hours) | All |

---

## Notes

- [P] tasks = different endpoints/pages, no dependencies within phase
- [US] label maps task to specific user story from spec.md
- ALL phases are SEQUENTIAL -- gate check required between each
- MANUAL tasks require user action in browser -- orchestrator MUST wait
- AUTOMATED tasks run via CLI commands or MCP tools -- orchestrator executes
- Impasse protocol adds 15-30 min per bug found
- KNOWN-NNN issues are pre-documented -- log but do not block
- Every task result goes into logs.md -- append-only
- NDJSON stream event type for text is `chunk` per Constitution Principle VI
- Use `sg docker -c "..."` for all Docker commands (group not propagated)
