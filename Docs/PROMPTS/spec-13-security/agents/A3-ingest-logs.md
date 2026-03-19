# A3: Ingest + Logs Hardening

**Agent type**: `python-expert`
**Model**: **Sonnet 4.6** (`model="sonnet"`)

You implement FR-003 (filename sanitization), FR-004 (PDF magic byte check), and FR-006 (log field redaction). You modify 2 production files and create 2 test files.

## Assigned Tasks

T006-T011 from `specs/013-security-hardening/tasks.md` (Phase 2: US1) and T019-T023b (Phase 5: US4).

| Task | FR | Description |
|------|-----|-------------|
| T006 | FR-003/004 | Create `tests/unit/api/test_ingest_security.py` with ~7 tests |
| T007 | FR-003 | Add `import re as _re` and `_SAFE_FILENAME` constant in `backend/api/ingest.py` |
| T008 | FR-003 | Add `_sanitize_filename(raw: str) -> str` function in `backend/api/ingest.py` |
| T009 | FR-004 | Insert PDF magic byte check in `ingest_file()` after size check, before collection verify |
| T010 | FR-003 | Replace filename assignment with `_sanitize_filename(...)` call |
| T011 | FR-003/004 | Run US1 tests via external runner |
| T019 | FR-006 | Create `tests/unit/test_main_security.py` with ~4 tests |
| T020 | FR-007 | Create `tests/unit/api/test_providers_security.py` with ~2 tests (verification only) |
| T021 | FR-006 | Add `_strip_sensitive_fields` function in `backend/main.py` |
| T022 | FR-006 | Insert `_strip_sensitive_fields` into structlog processor chain |
| T023a | FR-006 | Run US4 log redaction tests via external runner |
| T023b | FR-007 | Run US4 provider response tests via external runner |

## Source Documents to Read

Read these files in order before starting any work:

1. `Docs/PROMPTS/spec-13-security/13-implement.md` -- read the "Exact Insertion Points" section for FR-003, FR-004, and FR-006
2. `Docs/Tests/spec13-a1-audit.md` -- A1's audit report (confirms insertion points and line numbers)
3. `specs/013-security-hardening/tasks.md` -- your task definitions (Phase 2 + Phase 5)
4. `specs/013-security-hardening/contracts/ingest-endpoint.md` -- FR-003/FR-004 contract details
5. `specs/013-security-hardening/data-model.md` -- filename sanitization rules, PDF magic check rules, log redaction rules, and ingest operation order

## FR-003: Filename Sanitization (backend/api/ingest.py)

### Production Changes

**Change 1** -- Add import at the top of `ingest.py` (after the existing `import asyncio`, `import uuid` lines):
```python
import re as _re
```

**Change 2** -- Add constant and function after the `ALLOWED_EXTENSIONS` set (after line 19):
```python
_SAFE_FILENAME = _re.compile(r"[^a-zA-Z0-9._-]")


def _sanitize_filename(raw: str) -> str:
    """Strip path traversal sequences and unsafe characters from a filename."""
    name = raw.replace("\\", "/").split("/")[-1]
    name = name.replace("..", "")
    name = _SAFE_FILENAME.sub("_", name)
    return name or "upload"
```

**Change 3** -- Replace the filename assignment (currently at line ~74 inside step "4. Save file"):

Current:
```python
    filename = file.filename or f"document{suffix}"
```

After:
```python
    filename = _sanitize_filename(file.filename or f"document{suffix}")
```

## FR-004: PDF Magic Byte Check (backend/api/ingest.py)

### Production Change

Insert this block after the size check (which ends with the `FILE_TOO_LARGE` HTTPException block) and BEFORE the collection existence check (`collection = await db.get_collection(collection_id)`):

```python
    # PDF magic byte check (FR-004)
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
```

**CRITICAL**: The error envelope format MUST match the existing pattern used by `FILE_FORMAT_NOT_SUPPORTED` and `FILE_TOO_LARGE` in the same function. Each guard block fetches `trace_id = getattr(request.state, "trace_id", "")` locally.

**CRITICAL**: The check is PDF-only. Do NOT add magic byte checks for `.md`, `.txt`, `.py`, or any other extension (FR-005).

### Ingest Operation Order (after changes)

Verify the final order matches:
1. Validate extension (existing)
2. Read content (existing)
3. Validate size (existing)
4. PDF magic byte check (NEW -- FR-004)
5. Verify collection exists (existing)
6. Sanitize filename (NEW -- FR-003)
7. Save file to disk (existing)
8. Hash + dedup (existing)
9. Changed-file check (existing)
10. Create document + job records (existing)
11. Launch background ingestion (existing)

### Test File (tests/unit/api/test_ingest_security.py)

Write ~7 tests covering:
- `_sanitize_filename("../../etc/passwd.txt")` returns a safe name (no `..` or `/`)
- `_sanitize_filename("../../")` returns `"upload"` (empty fallback)
- `_sanitize_filename("file name!@#.pdf")` returns name with unsafe chars replaced by `_`
- Valid PDF (content starts with `b"%PDF"`) passes the magic check
- Forged PDF (content starts with `b"AAAA"`) returns HTTP 400 `FILE_CONTENT_MISMATCH`
- Short PDF (content < 4 bytes, e.g. `b"AB"`) returns HTTP 400 `FILE_CONTENT_MISMATCH`
- Non-PDF file (`.md`) with arbitrary content succeeds (no magic check applied)

**Test approach for endpoint tests**: Use `httpx.AsyncClient` with the FastAPI app, or mock the dependencies (`db`, `qdrant`, `request.app.state`) and call `ingest_file()` directly. For `_sanitize_filename` tests, call the function directly (it has no dependencies).

## FR-006: Log Field Redaction (backend/main.py)

### Production Changes

**Change 1** -- Define function and constant at module level, above `_configure_logging()` (insert before line 29):
```python
_SENSITIVE_KEYS = {"api_key", "password", "secret", "token", "authorization"}


def _strip_sensitive_fields(logger, method, event_dict: dict) -> dict:
    """Redact sensitive field values in log records (FR-006)."""
    for key in list(event_dict.keys()):
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = "[REDACTED]"
    return event_dict
```

**Change 2** -- Insert `_strip_sensitive_fields` into the processor chain immediately before `JSONRenderer`:

Current:
```python
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
```

After:
```python
            structlog.processors.format_exc_info,
            _strip_sensitive_fields,
            structlog.processors.JSONRenderer(),
```

**No new imports needed.**

### Test File (tests/unit/test_main_security.py)

Write ~4 tests covering:
- `_strip_sensitive_fields` replaces `api_key` value with `"[REDACTED]"`
- `password`, `secret`, `token`, and `authorization` are all redacted
- Non-sensitive field (e.g., `event`, `level`) is unchanged
- Processor is at position -2 in the chain (before `JSONRenderer`) -- import `_configure_logging` or inspect the structlog config

**Test approach**: Call `_strip_sensitive_fields(None, None, {"api_key": "sk-1234", "event": "test"})` directly and assert the return value. For the processor chain position test, call `_configure_logging()` and inspect `structlog.get_config()["processors"]`.

## FR-007: Provider Response Verification (tests only)

### Test File (tests/unit/api/test_providers_security.py)

Write ~2 tests covering:
- Provider response includes `has_key` boolean field
- Provider response does NOT include `api_key_encrypted` value

**No production code changes.** FR-007 was already implemented in spec-10. These tests verify existing behavior.

## Key Constraints

- **NEVER run pytest directly** -- use `zsh scripts/run-tests-external.sh -n <name> <target>`
- **External test runner accepts ONE target** -- use separate invocations for multiple test directories
- **No new dependencies** -- only `re` (stdlib), imported as `import re as _re`
- **Match existing error response pattern** -- the `FILE_CONTENT_MISMATCH` error envelope must match `FILE_FORMAT_NOT_SUPPORTED` and `FILE_TOO_LARGE` exactly
- **Pre-existing failures: 39** -- any increase is a regression
- **Do NOT modify** `backend/providers/key_manager.py`, `backend/middleware.py`, `backend/config.py`, or any file not listed in your assigned tasks

## Test Execution

After implementing US1 (ingest):
```bash
zsh scripts/run-tests-external.sh -n spec13-us1 tests/unit/api/test_ingest_security.py
```

After implementing US4 (logs + providers):
```bash
zsh scripts/run-tests-external.sh -n spec13-us4-logs tests/unit/test_main_security.py
zsh scripts/run-tests-external.sh -n spec13-us4-providers tests/unit/api/test_providers_security.py
```

Final combined run:
```bash
zsh scripts/run-tests-external.sh -n spec13-a3 tests/unit/
```

Poll status:
```bash
cat Docs/Tests/spec13-a3.status
cat Docs/Tests/spec13-a3.summary
```

## Success Criteria

- `backend/api/ingest.py` has `_sanitize_filename()` function, PDF magic check, and updated filename assignment
- `backend/main.py` has `_strip_sensitive_fields()` function and updated processor chain
- `tests/unit/api/test_ingest_security.py` exists with ~7 passing tests
- `tests/unit/test_main_security.py` exists with ~4 passing tests
- `tests/unit/api/test_providers_security.py` exists with ~2 passing tests
- `Docs/Tests/spec13-a3.status` is `PASSED`
- No increase in pre-existing failure count

## After Completing All Tasks

Report completion to the orchestrator. The orchestrator will verify your test results before spawning Wave 3.
