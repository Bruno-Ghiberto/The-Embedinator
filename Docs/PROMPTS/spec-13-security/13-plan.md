# Spec 13: Security Hardening — Implementation Plan Context

> **AGENT TEAMS -- tmux IS REQUIRED**
>
> This spec uses 3 waves with 4 agents. Waves run sequentially; each wave gate
> must pass before the next wave begins. Wave 2 runs agents in parallel.
>
> **Orchestrator protocol**:
> 1. Read THIS file first (you are doing this now)
> 2. Spawn agents by wave, one per tmux pane
> 3. Each agent's FIRST action is to read its instruction file
> 4. Wait for wave gate before spawning the next wave
>
> Spawn command for every agent (no exceptions):
> ```
> Agent(
>   subagent_type="<type>",
>   model="<model>",
>   prompt="Read your instruction file at Docs/PROMPTS/spec-13-security/agents/<file>.md FIRST, then execute all assigned tasks"
> )
> ```

---

## Component Overview

### What Spec-13 Adds

Spec-13 closes four specific security gaps in the existing codebase. All changes are small, surgical additions to existing files. No new modules are created. No new pip dependencies are required.

| FR | File | Change |
|----|------|--------|
| FR-001 | `backend/api/chat.py` | Truncate `body.message` to 10,000 chars silently before building `initial_state` |
| FR-002 | `backend/retrieval/searcher.py` | Add `ALLOWED_FILTER_KEYS` constant; silently skip unknown keys in `_build_filter()` |
| FR-003a | `backend/api/ingest.py` | Add `_sanitize_filename()` function; apply before saving to disk and DB |
| FR-003b | `backend/api/ingest.py` | Add PDF magic byte check (`b"%PDF"`) after size check; return HTTP 400 on mismatch |
| FR-004 | `backend/main.py` | Add `_strip_sensitive_fields` processor to structlog chain, before `JSONRenderer` |

Total scope: ~30 lines of new code across 4 existing files.

### What Is Already Built — Do NOT Reimplement

The following were completed in earlier specs. Agents must not touch these:

| Component | Spec | Location |
|-----------|------|----------|
| `KeyManager` (Fernet encryption) | spec-07 | `backend/providers/key_manager.py` |
| `RateLimitMiddleware` (per-IP, 4 buckets) | spec-08 | `backend/middleware.py` |
| `CORSMiddleware` registration | spec-08 | `backend/main.py` `create_app()` |
| Extension allowlist + size check | spec-08 | `backend/api/ingest.py` |
| Collection name regex validation | spec-08 | `backend/api/collections.py` |
| All rate limit + CORS settings fields | spec-08 | `backend/config.py` |

The `_configure_logging()` function already exists in `backend/main.py` with 6 processors ending in `JSONRenderer`. Spec-13 adds one processor to this existing chain.

---

## Wave Definitions

### Wave 1 — Pre-Flight Audit (Sequential)

| Field | Value |
|-------|-------|
| Agent | A1 |
| Type | quality-engineer |
| Model | claude-opus-4-5 |
| Tasks | T001–T008 |
| Output | `Docs/Tests/spec13-a1-audit.md` |

**Gate condition**: Audit report exists AND confirms:
- All 4 target files are in the pre-FR state (no partial application of FR-001 through FR-004)
- `key_manager.py`, `middleware.py`, `config.py` are confirmed complete and in scope to leave untouched
- `providers.py` `GET /api/providers` response already returns `has_key` and does NOT expose `api_key_encrypted`

Do not spawn Wave 2 until the audit report is written and conditions above are met.

---

### Wave 2 — Implementation (Parallel)

Both A2 and A3 run simultaneously in separate tmux panes. They modify different files and do not conflict.

#### A2 — FR-001 + FR-002

| Field | Value |
|-------|-------|
| Agent | A2 |
| Type | python-expert |
| Model | claude-sonnet-4-5 |
| Tasks | T009–T015 |
| Files modified | `backend/api/chat.py`, `backend/retrieval/searcher.py` |
| New test files | `tests/unit/api/test_chat_security.py`, `tests/unit/retrieval/test_searcher_security.py` |

#### A3 — FR-003a + FR-003b + FR-004

| Field | Value |
|-------|-------|
| Agent | A3 |
| Type | python-expert |
| Model | claude-sonnet-4-5 |
| Tasks | T016–T022 |
| Files modified | `backend/api/ingest.py`, `backend/main.py` |
| New test files | `tests/unit/api/test_ingest_security.py`, `tests/unit/test_main_security.py` |

**Wave 2 gate condition**: Both A2 and A3 complete all assigned tasks. Each agent's external test run of `tests/unit/` returns `PASSED`. The pre-existing failure count does not increase.

---

### Wave 3 — Regression and Acceptance (Sequential)

| Field | Value |
|-------|-------|
| Agent | A4 |
| Type | quality-engineer |
| Model | claude-sonnet-4-5 |
| Tasks | T023–T030 |
| Output | `Docs/Tests/spec13-a4-final.md` |

**Wave 3 gate condition (final)**: All 11 acceptance criteria pass. Pre-existing failure count remains at 39. Final report written.

---

## Task Table

| Task | Agent | Description |
|------|-------|-------------|
| T001 | A1 | Read `Docs/PROMPTS/spec-13-security/13-specify.md` fully — confirm 4 FRs, 11 ACs, no new pip deps |
| T002 | A1 | Read `backend/api/chat.py` — confirm `body.message` is not truncated; note both usages (line ~77 `HumanMessage` and line ~177 `create_query_trace`) |
| T003 | A1 | Read `backend/retrieval/searcher.py` `_build_filter()` — confirm no `ALLOWED_FILTER_KEYS` whitelist exists |
| T004 | A1 | Read `backend/api/ingest.py` — confirm extension allowlist (lines ~31–42) and size check (lines ~44–56) exist; confirm no `_sanitize_filename` function and no PDF magic byte check |
| T005 | A1 | Read `backend/main.py` `_configure_logging()` — confirm the 6-processor chain ends with `JSONRenderer` and does not include `_strip_sensitive_fields` |
| T006 | A1 | Read `backend/api/providers.py` `list_providers()` — verify response serialises via `ProviderDetailResponse` (which has `has_key` but not `api_key_encrypted`); verify raw DB row is NOT exposed |
| T007 | A1 | Confirm `backend/providers/key_manager.py` exists and implements `KeyManager` — note: do not plan any modifications to this file |
| T008 | A1 | Write audit report `Docs/Tests/spec13-a1-audit.md` — one section per target file, one section for "do not touch" files, overall PASS/FAIL verdict |
| T009 | A2 | In `backend/api/chat.py` `chat()`: add `message = body.message[:10_000]` before the `generate()` function definition; replace `body.message` with `message` in `HumanMessage(content=...)` and in `db.create_query_trace(..., query=..., ...)` (both occurrences) |
| T010 | A2 | In `backend/retrieval/searcher.py`: add module-level `ALLOWED_FILTER_KEYS = {"doc_type", "source_file", "page", "chunk_index"}`; update `_build_filter()` to skip unknown keys with `continue` (no error, no log) |
| T011 | A2 | Write `tests/unit/api/test_chat_security.py` — test cases: message exactly 10,000 chars passes unchanged; message of 15,000 chars is truncated to 10,000; truncation applies to both `HumanMessage` content and `query` passed to `create_query_trace` |
| T012 | A2 | Write `tests/unit/retrieval/test_searcher_security.py` — test cases: known filter key `doc_type` passes through; unknown key `arbitrary_field` is silently ignored; mixed dict with one known + one unknown key results in filter with only the known key; empty filter dict returns `None` |
| T013 | A2 | Run external tests: `zsh scripts/run-tests-external.sh -n spec13-a2 tests/unit/` — poll until status is not `RUNNING`; read summary |
| T014 | A2 | Confirm `Docs/Tests/spec13-a2.status` is `PASSED`; confirm no new failures in pre-existing searcher or chat tests |
| T015 | A2 | Report completion to orchestrator via task update |
| T016 | A3 | In `backend/api/ingest.py`: add `import re as _re` at the top imports block; add module-level `_SAFE_FILENAME = _re.compile(r"[^a-zA-Z0-9._-]")` constant |
| T017 | A3 | In `backend/api/ingest.py`: add `_sanitize_filename(raw: str) -> str` function (strip path separators, take basename, remove `..`, replace unsafe chars with `_`, return `"upload"` if result is empty) |
| T018 | A3 | In `backend/api/ingest.py` `ingest_file()`: insert PDF magic byte check immediately after the size validation block (step 4 in operation order) — fetch `trace_id = getattr(request.state, "trace_id", "")` and raise `HTTPException(status_code=400)` with code `FILE_CONTENT_MISMATCH` when `suffix == ".pdf"` and `content[:4] != b"%PDF"` |
| T019 | A3 | In `backend/api/ingest.py` `ingest_file()`: at the filename assignment (step 6 in operation order, after collection verify and before save), replace `filename = file.filename or f"document{suffix}"` with `filename = _sanitize_filename(file.filename or f"document{suffix}")` |
| T020 | A3 | In `backend/main.py`: define `_strip_sensitive_fields(logger, method, event_dict: dict) -> dict` function at module level (above `_configure_logging`); function replaces values of keys matching (case-insensitive) `api_key`, `password`, `secret`, `token`, `authorization` with `"[REDACTED]"` |
| T021 | A3 | In `backend/main.py` `_configure_logging()`: insert `_strip_sensitive_fields` into the processors list at position 5 (immediately before `structlog.processors.JSONRenderer()`) |
| T022 | A3 | Write `tests/unit/api/test_ingest_security.py` — test cases: `_sanitize_filename("../../etc/passwd.txt")` returns safe name without `..` or `/`; `_sanitize_filename("file name!@#.pdf")` returns name with unsafe chars replaced by `_`; `_sanitize_filename("")` returns `"upload"`; PDF with wrong magic bytes returns HTTP 400 `FILE_CONTENT_MISMATCH`; non-PDF file (`.md`) with arbitrary bytes succeeds; PDF with correct `b"%PDF"` bytes passes; write `tests/unit/test_main_security.py` — test that `_strip_sensitive_fields` replaces `api_key` value with `[REDACTED]`; test `password` and `token` fields are also redacted; test that non-sensitive fields are unchanged; run `zsh scripts/run-tests-external.sh -n spec13-a3 tests/unit/` and confirm PASSED |
| T023 | A4 | Run full test suite: `zsh scripts/run-tests-external.sh -n spec13-a4-full tests/` — poll until complete |
| T024 | A4 | Read `Docs/Tests/spec13-a4-full.summary` — verify all 4 new security test files are present and passing |
| T025 | A4 | Verify all 11 acceptance criteria from `13-specify.md` against test output and code inspection (see AC list below) |
| T026 | A4 | Confirm pre-existing failure count is still 39 (established in spec-12 baseline) — any increase is a regression that must be investigated and fixed before final report |
| T027 | A4 | Read `backend/api/ingest.py` and verify operation order matches the spec's 11-step sequence exactly: extension → read → size → magic-byte-PDF → collection-verify → sanitize-filename → save → hash-dedup → changed-file → create-records → launch-ingestion |
| T028 | A4 | Read `backend/api/chat.py` and verify `message` (not `body.message`) appears in both `HumanMessage(content=message)` and `db.create_query_trace(..., query=message, ...)` |
| T029 | A4 | Read `backend/api/providers.py` and confirm `GET /api/providers` response uses `ProviderDetailResponse.model_dump()` — verify `api_key_encrypted` is not present in the serialized output; if no existing test covers this, write one in `tests/unit/api/test_providers_security.py` |
| T030 | A4 | Write final report `Docs/Tests/spec13-a4-final.md` — one row per acceptance criterion with PASS/FAIL, total new test count, pre-existing failure count |

---

## Acceptance Criteria Reference

These 11 criteria from `13-specify.md` are what A4 must verify in T025:

1. A chat message of 15,000 characters is processed without error; the query stored in `query_traces` is 10,000 characters.
2. A Qdrant filter dict containing an unknown key (e.g., `{"arbitrary_field": "value"}`) is silently ignored; `_build_filter` returns `None` or filters only on allowed keys.
3. Uploading a file named `../../etc/passwd.txt` results in the filename stored in the database being sanitized (no path separators or `..` components).
4. Uploading a `.pdf` file whose first 4 bytes are NOT `%PDF` returns HTTP 400 with code `FILE_CONTENT_MISMATCH`.
5. Uploading a `.md` file with valid content succeeds (no magic number check for non-PDF types).
6. A log record emitted with an `api_key` field has that field replaced with `[REDACTED]` in the JSON output.
7. `GET /api/providers` response never includes `api_key_encrypted`; it includes `has_key: bool`.
8. Uploading a `.exe` file still returns HTTP 400 `FILE_FORMAT_NOT_SUPPORTED` (existing behavior preserved).
9. Uploading a file larger than 100 MB still returns HTTP 413 `FILE_TOO_LARGE` (existing behavior preserved).
10. Sending 31 chat requests within 60 seconds still returns HTTP 429 on the 31st request (rate limiting unaffected).
11. The structlog processor chain order in `_configure_logging()` places `_strip_sensitive_fields` before `JSONRenderer`.

---

## Phase Assignment

All 4 FRs are MVP. There are no deferred phases. Spec-13 is a single-wave implementation with no optional components.

| FR | Status | Rationale |
|----|--------|-----------|
| FR-001 | MVP | Prevents context window abuse; zero risk, one-line change |
| FR-002 | MVP | Closes arbitrary Qdrant payload query vector; one-line change per key |
| FR-003a | MVP | Path traversal prevention; required by constitution §III |
| FR-003b | MVP | Content sniffing for PDF; required by constitution §III |
| FR-004 | MVP | Log redaction; required by constitution §VI |

---

## Integration Points

### Files Modified (4 total)

| File | FR | Change Type |
|------|----|-------------|
| `backend/api/chat.py` | FR-001 | Add one assignment + replace two `body.message` references |
| `backend/retrieval/searcher.py` | FR-002 | Add module-level constant + add `if key not in` guard in one method |
| `backend/api/ingest.py` | FR-003a, FR-003b | Add 1 import, 1 constant, 1 function; add 1 check block and modify 1 assignment |
| `backend/main.py` | FR-004 | Add 1 function above `_configure_logging`; insert 1 entry in processor list |

### Files Verified But NOT Modified

| File | Why Read | Action |
|------|----------|--------|
| `backend/api/providers.py` | Verify `has_key` returned correctly, `api_key_encrypted` not exposed | Read-only; add test if assertion missing |

### Files Explicitly NOT to Touch

| File | Reason |
|------|--------|
| `backend/providers/key_manager.py` | Complete from spec-07; do not modify |
| `backend/middleware.py` | Complete from spec-08; do not modify |
| `backend/config.py` | All required fields already present; do not add or remove |
| `backend/api/collections.py` | Collection name validation already implemented; do not modify |
| `backend/storage/sqlite_db.py` | Parameterized queries already enforced; do not modify |

---

## Key Constraints

### No New Dependencies

All changes use Python stdlib only:
- `re` — used in `ingest.py` for `_SAFE_FILENAME` regex (import as `import re as _re`)
- No import needed in `chat.py`, `searcher.py`, or `main.py` — all changes use constructs already available

### Silent Truncation (FR-001)

The message truncation MUST be silent. Do not:
- Raise an exception
- Emit a log warning
- Return an error response

The truncated value is simply used downstream. The client is not notified.

### Silent Filter Key Ignoring (FR-002)

Unknown filter keys MUST be silently ignored. Do not:
- Raise an exception
- Log a warning
- Return an error

Use `continue` inside the loop. The resulting `Filter` object includes only the known keys.

`ALLOWED_FILTER_KEYS` is defined at module level in `searcher.py` (not as a class attribute). This matches the code sample in `13-specify.md`.

### Filename Sanitization Behavior (FR-003a)

The `_sanitize_filename` function MUST:
1. Replace backslashes with forward slashes and take the last path segment (basename)
2. Remove all `..` substrings
3. Replace any character NOT in `[a-zA-Z0-9._-]` with `_`
4. Return `"upload"` if the result after all operations is an empty string

The sanitized filename is used for both the on-disk path (`file_path`) and the `filename` argument to `db.create_document()`. Because both downstream consumers use the single `filename` variable, replacing the assignment at step 6 covers all uses automatically.

### Magic Byte Check Placement (FR-003b)

The magic byte check MUST be placed after the size check and BEFORE the collection existence check. This matches the 11-step operation order in `13-specify.md`. The `trace_id` variable must be fetched locally for the HTTPException body, following the same pattern as the other error handlers in `ingest_file()` (each guard block calls `getattr(request.state, "trace_id", "")`).

The check is PDF-only. Do not add magic byte checks for `.md`, `.txt`, `.py`, or any other extension.

### Structlog Processor Order (FR-004)

The `_configure_logging()` function currently has 6 processors. After spec-13:

```
1. structlog.contextvars.merge_contextvars
2. structlog.processors.add_log_level
3. structlog.processors.TimeStamper(fmt="iso")
4. structlog.processors.StackInfoRenderer()
5. structlog.processors.format_exc_info
6. _strip_sensitive_fields          ← NEW (inserted at position 6)
7. structlog.processors.JSONRenderer()
```

`_strip_sensitive_fields` receives and modifies `event_dict` in-place by replacing sensitive field VALUES with `"[REDACTED]"`. It does NOT delete the keys. It returns the modified `event_dict`.

The sensitive key set is checked case-insensitively: `api_key`, `password`, `secret`, `token`, `authorization`.

### chat.py — Two Occurrences of body.message

`body.message` appears in `chat.py` in two distinct locations inside the `generate()` coroutine:
1. Line ~77: `HumanMessage(content=body.message)` — used to build `initial_state`
2. Line ~177: `db.create_query_trace(..., query=body.message, ...)` — written to the DB

Both MUST be replaced with the local `message` variable. The assignment `message = body.message[:10_000]` should be placed inside `generate()` before `initial_state` is built, or directly in `chat()` before `generate()` is defined. Either placement is correct as long as both usages are covered.

---

## Testing Protocol

**NEVER run pytest directly inside Claude Code.** All testing uses the external runner:

```bash
# Run a target
zsh scripts/run-tests-external.sh -n <name> <target>

# Check status (poll)
cat Docs/Tests/<name>.status        # RUNNING | PASSED | FAILED | ERROR

# Read results
cat Docs/Tests/<name>.summary       # ~20 lines, token-efficient
cat Docs/Tests/<name>.log           # full pytest output if needed
```

### External Test Run Schedule

| Agent | Run name | Target | When |
|-------|----------|--------|------|
| A2 | `spec13-a2` | `tests/unit/` | After T011–T012 complete |
| A3 | `spec13-a3` | `tests/unit/` | After T022 complete |
| A4 | `spec13-a4-full` | `tests/` | Wave 3 start (T023) |

### Wave Gates Summary

| Gate | Condition |
|------|-----------|
| Wave 1 → Wave 2 | `Docs/Tests/spec13-a1-audit.md` exists; all 4 target files confirmed in pre-FR state |
| Wave 2 → Wave 3 | `spec13-a2.status = PASSED` AND `spec13-a3.status = PASSED`; no new failures |
| Final | `spec13-a4-full.status = PASSED`; 11 ACs verified; pre-existing failure count = 39 |

### New Test File Locations

All new test files follow the existing project test layout:

```
tests/
  unit/
    api/
      test_chat_security.py        # A2 — FR-001
      test_ingest_security.py      # A3 — FR-003a, FR-003b
      test_providers_security.py   # A4 — AC-7 verification (if not already covered)
    retrieval/
      test_searcher_security.py    # A2 — FR-002
    test_main_security.py          # A3 — FR-004
```

---

## Appendix: Exact Insertion Points

This section gives agents the precise code context for each change so edits are unambiguous.

### FR-001 — chat.py

Current code (inside `generate()`, building initial_state):
```python
async def generate():
    start_time = time.monotonic()

    # Empty-collections guard
    if not body.collection_ids:
        ...

    # 1. Session event (BEFORE astream)
    yield json.dumps({"type": "session", "session_id": session_id}) + "\n"

    initial_state = {
        "session_id": session_id,
        "messages": [HumanMessage(content=body.message)],
        ...
    }
```

After change — add `message = body.message[:10_000]` before `initial_state`:
```python
    # 1. Session event (BEFORE astream)
    yield json.dumps({"type": "session", "session_id": session_id}) + "\n"

    message = body.message[:10_000]  # FR-001: truncate silently

    initial_state = {
        "session_id": session_id,
        "messages": [HumanMessage(content=message)],
        ...
    }
```

And in the `create_query_trace` call:
```python
    query=message,   # was: query=body.message
```

### FR-002 — searcher.py

Add after the imports, before the `class HybridSearcher` definition:
```python
ALLOWED_FILTER_KEYS = {"doc_type", "source_file", "page", "chunk_index"}
```

Update `_build_filter` method body:
```python
def _build_filter(self, filters: dict | None) -> Filter | None:
    if not filters:
        return None
    conditions = []
    for key, value in filters.items():
        if key not in ALLOWED_FILTER_KEYS:
            continue  # FR-002: silently ignore unknown keys
        conditions.append(
            FieldCondition(key=key, match=MatchValue(value=value))
        )
    return Filter(must=conditions) if conditions else None
```

### FR-003b — ingest.py magic byte check placement

Insert after the size check block (which ends at the `raise HTTPException(status_code=413, ...)` block) and before the collection existence check:

```python
    # 4. Magic number check for PDF (FR-003b)
    if suffix == ".pdf" and content[:4] != b"%PDF":
        trace_id = getattr(request.state, "trace_id", "")
        raise HTTPException(status_code=400, detail={
            "error": {
                "code": "FILE_CONTENT_MISMATCH",
                "message": "File content does not match declared type",
                "details": {"expected_magic": "%PDF"},
            },
            "trace_id": trace_id,
        })

    # 5. Verify collection exists
    collection = await db.get_collection(collection_id)
```

### FR-003a — ingest.py filename sanitization placement

Current line ~72 (after collection verify, before save):
```python
    # 4. Save file
    filename = file.filename or f"document{suffix}"
```

After change:
```python
    # 6. Sanitize filename (FR-003a) + save
    filename = _sanitize_filename(file.filename or f"document{suffix}")
```

The comment block number should update to reflect the new step numbering.

### FR-004 — main.py processor chain

Current `_configure_logging()` processor list:
```python
processors=[
    structlog.contextvars.merge_contextvars,
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
    structlog.processors.JSONRenderer(),
],
```

After change (insert `_strip_sensitive_fields` before `JSONRenderer`):
```python
processors=[
    structlog.contextvars.merge_contextvars,
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
    _strip_sensitive_fields,             # FR-004: redact sensitive fields
    structlog.processors.JSONRenderer(),
],
```

The `_strip_sensitive_fields` function is defined at module level, above `_configure_logging`.
