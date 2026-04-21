# Tasks: Security Hardening

**Input**: Design documents from `/specs/013-security-hardening/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Included — 5 test files, ~21 tests total (per quickstart.md and plan.md).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## FR Numbering Cross-Reference

Spec.md and plan.md/data-model.md/quickstart.md use different FR numbering schemes. This table maps between them. **Tasks below use spec.md numbering.**

| Spec FR | Plan FR | Description | File |
|---------|---------|-------------|------|
| FR-001 | FR-001 | Chat message truncation | backend/api/chat.py |
| FR-002 | FR-002 | Filter key whitelist | backend/retrieval/searcher.py |
| FR-003 | FR-003a | Filename sanitization | backend/api/ingest.py |
| FR-004 | FR-003b | PDF magic byte check | backend/api/ingest.py |
| FR-005 | *(implicit in FR-003b)* | No magic for non-PDF | backend/api/ingest.py |
| FR-006 | FR-004 | Log field redaction | backend/main.py |
| FR-007 | *(not in plan)* | No encrypted keys in responses | *(existing — verification only)* |
| FR-008 | *(not in plan)* | Preserve existing security | *(regression suite)* |

---

## Phase 1: Pre-Flight Audit

**Purpose**: Read and audit all target files to confirm insertion points, identify exact line numbers, and document pre-existing test baseline. No code changes in this phase.

- [x] T001 Audit backend/api/chat.py — locate `body.message` usages inside `generate()` for FR-001 insertion point
- [x] T002 [P] Audit backend/retrieval/searcher.py — locate `_build_filter()` method for FR-002 whitelist insertion
- [x] T003 [P] Audit backend/api/ingest.py — locate filename assignment and content read for FR-003 (sanitize) + FR-004 (PDF magic) insertion points; confirm operation order matches data-model.md steps 1–11; document existing error response pattern used by FILE_FORMAT_NOT_SUPPORTED to match for FILE_CONTENT_MISMATCH
- [x] T004 [P] Audit backend/main.py — locate `_configure_logging()` and structlog processor chain for FR-006 insertion point
- [x] T005 [P] Run full test suite to document pre-existing failure baseline (expected: 39 pre-existing failures) via `zsh scripts/run-tests-external.sh -n spec13-baseline tests/`

**Checkpoint**: All insertion points confirmed. Pre-existing test baseline documented. Implementation can begin.

---

## Phase 2: User Story 1 — Safe Document Ingestion (Priority: P1) 🎯 MVP

**Goal**: Protect against malicious filenames (path traversal) and forged PDF files (wrong magic bytes) at the ingest endpoint. Existing extension and size checks remain intact.

**Independent Test**: Upload a file with `../../etc/passwd.txt` as filename and a forged PDF (random bytes with `.pdf` extension) — both must be handled safely without affecting other features.

**FRs**: FR-003 (filename sanitization), FR-004 (PDF magic check), FR-005 (no magic for non-PDF), FR-008 (existing checks preserved)

### Tests for User Story 1

- [x] T006 [P] [US1] Create tests/unit/api/test_ingest_security.py with ~7 tests: path traversal filename sanitized, pure-traversal filename returns "upload" fallback, valid PDF passes magic check, forged PDF rejected with FILE_CONTENT_MISMATCH, short PDF (<4 bytes) rejected, non-PDF skips magic check, existing extension check preserved

### Implementation for User Story 1

- [x] T007 [US1] Add `import re as _re` and `_SAFE_FILENAME = _re.compile(r"[^a-zA-Z0-9._-]")` constant at module level in backend/api/ingest.py
- [x] T008 [US1] Add `_sanitize_filename(raw: str) -> str` function in backend/api/ingest.py — replace `\` with `/`, take last segment, remove `..`, regex-replace unsafe chars, fallback to `"upload"`
- [x] T009 [US1] Insert PDF magic byte check (`content[:4] != b"%PDF"`) after size check and before collection existence check in `ingest_file()` in backend/api/ingest.py — raise HTTPException 400 with FILE_CONTENT_MISMATCH error envelope; match the exact error response pattern used by existing FILE_FORMAT_NOT_SUPPORTED (discovered in T003 audit)
- [x] T010 [US1] Replace filename assignment with `filename = _sanitize_filename(file.filename or f"document{suffix}")` after collection existence check in `ingest_file()` in backend/api/ingest.py
- [x] T011 [US1] Run US1 tests via `zsh scripts/run-tests-external.sh -n spec13-us1 tests/unit/api/test_ingest_security.py` — all ~7 tests must pass

**Checkpoint**: User Story 1 complete. Forged PDFs rejected, path traversal filenames sanitized, existing upload behavior preserved.

---

## Phase 3: User Story 2 — Protected Chat Input (Priority: P1)

**Goal**: Silently truncate chat messages exceeding 10,000 characters before processing and trace storage. Users experience no error.

**Independent Test**: Submit a 15,000-character message and verify only the first 10,000 characters are stored and sent to the language model.

**FRs**: FR-001 (silent truncation)

### Tests for User Story 2

- [x] T012 [P] [US2] Create tests/unit/api/test_chat_security.py with ~4 tests: message over 10k truncated to 10k, message under 10k unchanged, message exactly 10k preserved (no off-by-one), truncated message used in both HumanMessage and create_query_trace

### Implementation for User Story 2

- [x] T013 [US2] Add `message = body.message[:10_000]` before `initial_state` construction in `generate()` in backend/api/chat.py and replace both `body.message` references with `message` (HumanMessage content and db.create_query_trace query)
- [x] T014 [US2] Run US2 tests via `zsh scripts/run-tests-external.sh -n spec13-us2 tests/unit/api/test_chat_security.py` — all ~4 tests must pass

**Checkpoint**: User Story 2 complete. Oversized messages silently truncated. Under-limit messages unchanged.

---

## Phase 4: User Story 3 — Restricted Search Filters (Priority: P2)

**Goal**: Whitelist Qdrant filter keys to prevent arbitrary payload field access. Unknown keys silently ignored.

**Independent Test**: Submit a search query with an unknown filter key and verify it is silently dropped while known keys work correctly.

**FRs**: FR-002 (filter key whitelist)

### Tests for User Story 3

- [x] T015 [P] [US3] Create tests/unit/retrieval/test_searcher_security.py with ~4 tests: known key passes through, unknown key silently dropped, mixed known+unknown filters only keep known, all-unknown filters return None (unfiltered)

### Implementation for User Story 3

- [x] T016 [US3] Add `ALLOWED_FILTER_KEYS = {"doc_type", "source_file", "page", "chunk_index"}` constant at module level (before class definition) in backend/retrieval/searcher.py
- [x] T017 [US3] Add `if key not in ALLOWED_FILTER_KEYS: continue` guard inside the `_build_filter()` loop in backend/retrieval/searcher.py
- [x] T018 [US3] Run US3 tests via `zsh scripts/run-tests-external.sh -n spec13-us3 tests/unit/retrieval/test_searcher_security.py` — all ~4 tests must pass

**Checkpoint**: User Story 3 complete. Unknown filter keys silently ignored. Known keys unaffected.

---

## Phase 5: User Story 4 — Sensitive Data Redaction in Logs (Priority: P2)

**Goal**: Redact sensitive field values (api_key, password, secret, token, authorization) in all log output. Provider API responses show `has_key` presence indicator, never the encrypted key value.

**Independent Test**: Trigger a log event with an `api_key` field and verify JSON output shows `[REDACTED]`. Check `GET /api/providers` response for `has_key` presence and absence of `api_key_encrypted`.

**FRs**: FR-006 (log redaction), FR-007 (no encrypted keys in responses)

### Tests for User Story 4

- [x] T019 [P] [US4] Create tests/unit/test_main_security.py with ~4 tests: api_key redacted, password/secret/token/authorization redacted, non-sensitive key unchanged, processor is at position -2 in chain (before JSONRenderer)
- [x] T020 [P] [US4] Create tests/unit/api/test_providers_security.py with ~2 tests: provider response includes has_key boolean, provider response does NOT include api_key_encrypted value. NOTE: FR-007 was already implemented in spec-08/spec-10 — these tests verify existing behavior, no production code changes needed

### Implementation for User Story 4

- [x] T021 [US4] Add `_strip_sensitive_fields(logger, method, event_dict: dict) -> dict` function above `_configure_logging()` in backend/main.py — iterate top-level keys, case-insensitive match against `{"api_key", "password", "secret", "token", "authorization"}`, replace value with `"[REDACTED]"`
- [x] T022 [US4] Insert `_strip_sensitive_fields` into the structlog processor chain at position -2 (immediately before `JSONRenderer`) in `_configure_logging()` in backend/main.py
- [x] T023a [US4] Run US4 log redaction tests via `zsh scripts/run-tests-external.sh -n spec13-us4-logs tests/unit/test_main_security.py` — all ~4 tests must pass
- [x] T023b [P] [US4] Run US4 provider response tests via `zsh scripts/run-tests-external.sh -n spec13-us4-providers tests/unit/api/test_providers_security.py` — all ~2 tests must pass

**Checkpoint**: User Story 4 complete. Sensitive fields redacted in logs. Provider responses expose only `has_key`.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Full regression, acceptance criteria verification, and dependency check.

- [x] T024 Run full regression suite via `zsh scripts/run-tests-external.sh -n spec13-full tests/` — all new tests pass, pre-existing failure count unchanged at 39
- [x] T025 Verify all 11 acceptance criteria from quickstart.md (AC-1 through AC-11)
- [x] T026 Verify SC-007: no new dependencies added to requirements.txt
- [x] T027 Verify FR-008: existing security behaviors (extension allowlist, file size limit, rate limiting, CORS, collection name validation) all function identically

**Checkpoint**: Spec-13 complete. All 8 FRs covered (4 implemented + FR-005 implicit + FR-007 verified + FR-008 regressed), ~21 new tests passing, 0 regressions, 0 new dependencies.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Pre-Flight Audit (Phase 1)**: No dependencies — can start immediately
- **User Stories (Phases 2–5)**: All depend on Phase 1 audit completion
  - US1 and US2 are both P1 but touch different files — can run in parallel
  - US3 and US4 are both P2 but touch different files — can run in parallel
  - All 4 user stories are fully independent (no cross-story dependencies)
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Independence

| Story | File(s) | Dependencies on Other Stories |
|-------|---------|-------------------------------|
| US1 (Ingest) | `backend/api/ingest.py` | None |
| US2 (Chat) | `backend/api/chat.py` | None |
| US3 (Search) | `backend/retrieval/searcher.py` | None |
| US4 (Logs) | `backend/main.py` | None |

All four user stories touch different files with zero overlap. They can be implemented in any order or fully in parallel.

### Within Each User Story

1. Tests written FIRST (fail before implementation)
2. Implementation tasks in order (constants → functions → integration into existing flow)
3. Story test run confirms all passing

### Parallel Opportunities

```
Phase 1:  T001 | T002 | T003 | T004 | T005  (all parallel)

Phase 2–5 (all 4 stories in parallel):
  US1: T006 → T007 → T008 → T009 → T010 → T011
  US2: T012 → T013 → T014
  US3: T015 → T016 → T017 → T018
  US4: T019 + T020 → T021 → T022 → T023a + T023b

Phase 6:  T024 → T025 + T026 + T027  (regression first, then verifications in parallel)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Pre-Flight Audit
2. Complete Phase 2: User Story 1 — Safe Document Ingestion
3. **STOP and VALIDATE**: Run US1 tests independently
4. File uploads are now protected against path traversal and forged PDFs

### Incremental Delivery

1. Complete audit (Phase 1) → baseline confirmed
2. Add US1 (Ingest hardening) → test independently → deploy
3. Add US2 (Chat truncation) → test independently → deploy
4. Add US3 (Filter whitelist) → test independently → deploy
5. Add US4 (Log redaction) → test independently → deploy
6. Full regression (Phase 6) → final validation

### Parallel Agent Teams Strategy (Recommended)

Per `Docs/PROMPTS/spec-13-security/13-plan.md`:

1. **Wave 1** (A1): Pre-Flight Audit — all T001–T005
2. **Wave 2** (A2 + A3 in parallel):
   - A2: US2 (chat) + US3 (search) — T012–T018
   - A3: US1 (ingest) + US4 (logs) — T006–T011, T019–T023b
3. **Wave 3** (A4): Full regression + AC verification — T024–T027

---

## Notes

- **External test runner ONLY**: `zsh scripts/run-tests-external.sh -n <name> <target>` — NEVER run pytest directly
- **Pre-existing failures**: 39 expected; any change is a regression
- **No new dependencies**: stdlib `re` only; SC-007 enforced
- **~30 lines of production code**: This is a small, surgical spec
- All tasks reference exact file paths from plan.md and data-model.md
- Error envelope format for FILE_CONTENT_MISMATCH defined in contracts/ingest-endpoint.md
