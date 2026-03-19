# Quickstart: Security Hardening

**Branch**: `013-security-hardening` | **Date**: 2026-03-17

How to implement and verify spec-13 from scratch.

## Prerequisites

- Backend venv is active (or use the external test runner — it creates `.venv` automatically)
- Qdrant is running (for integration tests only; unit tests run without it)

## Implementation Order

Follow the Agent Teams plan at `Docs/PROMPTS/spec-13-security/13-plan.md`.

Quick reference — 4 surgical edits:

### 1. FR-001 — chat.py message truncation

In `backend/api/chat.py`, inside `generate()`, before `initial_state`:

```python
message = body.message[:10_000]  # FR-001: silent truncation
```

Replace both `body.message` usages with `message`:
- `HumanMessage(content=message)`
- `db.create_query_trace(..., query=message, ...)`

### 2. FR-002 — searcher.py filter key whitelist

In `backend/retrieval/searcher.py`, at module level (before class definition):

```python
ALLOWED_FILTER_KEYS = {"doc_type", "source_file", "page", "chunk_index"}
```

In `_build_filter()`:

```python
for key, value in filters.items():
    if key not in ALLOWED_FILTER_KEYS:
        continue  # silently ignore
    conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
```

### 3. FR-003a+b — ingest.py sanitization + PDF check

At top of `ingest.py`, add import:
```python
import re as _re
```

Add module-level constant and function:
```python
_SAFE_FILENAME = _re.compile(r"[^a-zA-Z0-9._-]")

def _sanitize_filename(raw: str) -> str:
    name = raw.replace("\\", "/").split("/")[-1]
    name = name.replace("..", "")
    name = _SAFE_FILENAME.sub("_", name)
    return name or "upload"
```

In `ingest_file()`, insert PDF magic check after size check:
```python
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

Replace filename assignment:
```python
filename = _sanitize_filename(file.filename or f"document{suffix}")
```

### 4. FR-004 — main.py log redaction

In `backend/main.py`, define function above `_configure_logging()`:

```python
def _strip_sensitive_fields(logger, method, event_dict: dict) -> dict:
    _SENSITIVE = {"api_key", "password", "secret", "token", "authorization"}
    for key in list(event_dict.keys()):
        if key.lower() in _SENSITIVE:
            event_dict[key] = "[REDACTED]"
    return event_dict
```

Insert into processor chain immediately before `JSONRenderer`:
```python
_strip_sensitive_fields,
structlog.processors.JSONRenderer(),
```

## Running Tests

**Never run pytest directly. Always use the external runner.**

```bash
# Unit tests only (fast, no Docker needed)
zsh scripts/run-tests-external.sh -n spec13-unit tests/unit/

# Full regression
zsh scripts/run-tests-external.sh -n spec13-full tests/

# Check status
cat Docs/Tests/spec13-unit.status   # RUNNING | PASSED | FAILED | ERROR
cat Docs/Tests/spec13-unit.summary  # ~20 lines
```

## Manual Verification

After tests pass, verify the 11 acceptance criteria:

| AC | Verification |
|----|-------------|
| AC-1 | Submit 15,000-char message; `query_traces.query` is 10,000 chars |
| AC-2 | Call `_build_filter({"arbitrary_field": "x"})` → returns `None` |
| AC-3 | Upload file named `../../etc/passwd.txt`; DB stores clean name |
| AC-4 | Upload `.pdf` file starting with `AAAA`; response is HTTP 400 `FILE_CONTENT_MISMATCH` |
| AC-5 | Upload `.md` file with any content; upload succeeds |
| AC-6 | Log event with `api_key="real-key"`; JSON log shows `api_key: "[REDACTED]"` |
| AC-7 | `GET /api/providers` → response has `has_key`, no `api_key_encrypted` |
| AC-8 | Upload `.exe` → HTTP 400 `FILE_FORMAT_NOT_SUPPORTED` |
| AC-9 | Upload file > 100 MB → HTTP 413 `FILE_TOO_LARGE` |
| AC-10 | Send 31 chat requests/60s → 31st returns HTTP 429 |
| AC-11 | `_configure_logging()` processor list: `_strip_sensitive_fields` at index -2 (before `JSONRenderer`) |

## Expected Test Counts

After implementation, new test files should provide:
- `test_chat_security.py`: ~4 tests (FR-001)
- `test_searcher_security.py`: ~4 tests (FR-002)
- `test_ingest_security.py`: ~7 tests (FR-003a, FR-003b)
- `test_main_security.py`: ~4 tests (FR-004)
- `test_providers_security.py`: ~2 tests (AC-7)

Pre-existing failure count must remain at **39**.
