# Data Model: Security Hardening

**Branch**: `013-security-hardening` | **Date**: 2026-03-17

## Overview

Spec-13 introduces no new database tables, columns, or Qdrant payload fields. It adds validation and transformation logic applied to four existing data flows.

---

## Entity: Chat Message

**Where processed**: `backend/api/chat.py`, `chat()` endpoint
**Already exists**: `ChatRequest.message: str` in `backend/agent/schemas.py`

### Transformation

| Field | Before Spec-13 | After Spec-13 |
|-------|----------------|---------------|
| `body.message` | Passed directly | Truncated at 10,000 chars via `message = body.message[:10_000]` |
| `HumanMessage(content=...)` | Uses `body.message` | Uses `message` (truncated) |
| `db.create_query_trace(query=...)` | Uses `body.message` | Uses `message` (truncated) |

### Validation Rules

- Max length: 10,000 characters
- Truncation is silent (no error, no warning)
- Under-limit messages are unchanged (no off-by-one)
- Empty message (`""`) is unchanged (length 0 ≤ 10,000)

---

## Entity: Search Filter

**Where processed**: `backend/retrieval/searcher.py`, `_build_filter()` method

### Allowed Keys

```python
ALLOWED_FILTER_KEYS = {"doc_type", "source_file", "page", "chunk_index"}
```

| Key | Type | Qdrant payload field |
|-----|------|----------------------|
| `doc_type` | str | `doc_type` (e.g., `"Prose"`, `"Code"`) |
| `source_file` | str | `source_file` (filename) |
| `page` | int | `page` (page number) |
| `chunk_index` | int | `chunk_index` |

### Validation Rules

- Unknown keys: silently ignored via `continue` (no error, no log)
- All-unknown filter dict: returns `None` (unfiltered results)
- Empty filter dict: returns `None` (existing behaviour preserved)
- Known keys: passed to `FieldCondition(key=key, match=MatchValue(value=value))` unchanged

---

## Entity: Uploaded File

**Where processed**: `backend/api/ingest.py`, `ingest_file()` endpoint

### Filename Sanitization (FR-003a)

Function: `_sanitize_filename(raw: str) -> str`

| Step | Operation | Example Input → Output |
|------|-----------|------------------------|
| 1 | Replace `\` with `/`, take last segment | `../../etc/passwd.txt` → `passwd.txt` |
| 2 | Remove all `..` substrings | `..passwd..` → `passwd` |
| 3 | Replace `[^a-zA-Z0-9._-]` with `_` | `file name!.pdf` → `file_name_.pdf` |
| 4 | If empty after step 3, return `"upload"` | `../../` → `"upload"` |

The sanitized filename is used for **both** the on-disk path and `db.create_document(filename=...)`.

### PDF Magic Byte Check (FR-003b)

| Condition | Action |
|-----------|--------|
| `suffix == ".pdf"` and `content[:4] == b"%PDF"` | Pass through |
| `suffix == ".pdf"` and `content[:4] != b"%PDF"` | HTTP 400 `FILE_CONTENT_MISMATCH` |
| `suffix == ".pdf"` and `len(content) < 4` | HTTP 400 `FILE_CONTENT_MISMATCH` (short content fails equality) |
| `suffix != ".pdf"` | No magic check (any content passes) |

### Ingest Operation Order (after spec-13)

```
1.  Validate extension (existing — ALLOWED_EXTENSIONS set)
2.  Read content into memory (existing)
3.  Validate size (existing — settings.max_upload_size_mb)
4.  ← NEW: PDF magic byte check (FR-003b)
5.  Verify collection exists (existing)
6.  ← NEW: Sanitize filename (FR-003a)
7.  Save file using sanitized filename (existing — modified to use sanitized name)
8.  Compute hash and check duplicates (existing)
9.  Check for changed file (existing)
10. Create document and job records (existing)
11. Launch background ingestion (existing)
```

### Error Response Format (FR-003b)

```json
{
  "error": {
    "code": "FILE_CONTENT_MISMATCH",
    "message": "File content does not match declared type",
    "details": {"expected_magic": "%PDF"}
  },
  "trace_id": "<uuid>"
}
```

HTTP status: `400`

---

## Entity: Log Record

**Where processed**: `backend/main.py`, `_configure_logging()` structlog processor chain

### Sensitive Field Redaction (FR-004)

Function: `_strip_sensitive_fields(logger, method, event_dict: dict) -> dict`

| Sensitive key (case-insensitive) | Action |
|----------------------------------|--------|
| `api_key` | Value replaced with `"[REDACTED]"` |
| `password` | Value replaced with `"[REDACTED]"` |
| `secret` | Value replaced with `"[REDACTED]"` |
| `token` | Value replaced with `"[REDACTED]"` |
| `authorization` | Value replaced with `"[REDACTED]"` |

### Rules

- Matching is case-insensitive (`key.lower() in _SENSITIVE`)
- The key **remains present** in the record (value replaced, not deleted)
- Top-level keys only — nested dicts are not inspected
- Non-sensitive keys are passed through unchanged

### Processor Chain (after spec-13)

```
Position 1:  structlog.contextvars.merge_contextvars
Position 2:  structlog.processors.add_log_level
Position 3:  structlog.processors.TimeStamper(fmt="iso")
Position 4:  structlog.processors.StackInfoRenderer()
Position 5:  structlog.processors.format_exc_info
Position 6:  _strip_sensitive_fields        ← NEW
Position 7:  structlog.processors.JSONRenderer()
```

---

## What Does NOT Change

| Component | Status | Notes |
|-----------|--------|-------|
| `query_traces` table schema | Unchanged | `query` column stores truncated text (max 10k chars) |
| `documents` table schema | Unchanged | `filename` column stores sanitized name |
| Qdrant payload schema | Unchanged | Filter whitelist is read-only validation |
| `ChatRequest` Pydantic model | Unchanged | Truncation applied after deserialization |
| HTTP response schemas | Unchanged | All existing response models untouched |
