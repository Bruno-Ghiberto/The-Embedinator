# Spec 13: Security — Feature Specification Context

## Feature Description

Spec 13 hardens the defense-in-depth posture of The Embedinator, a self-hosted single-user RAG application. The core encryption, CORS, and rate limiting infrastructure was built in specs 07 and 08. This spec adds the remaining gaps: input truncation, filter key whitelisting in the retrieval path, file upload content validation, and logging security. No new dependencies are required.

---

## Already Implemented — Do NOT Reimplement

### API Key Encryption — `backend/providers/key_manager.py` (spec-07)

`KeyManager` is fully implemented:
- `__init__()` reads `EMBEDINATOR_FERNET_KEY` directly from the environment. Raises `ValueError` if absent. No SHA-256 derivation. No dev fallback.
- `encrypt(plaintext: str) -> str`
- `decrypt(ciphertext: str) -> str`
- `is_valid_key(ciphertext: str) -> bool`

`main.py` lifespan sets `app.state.key_manager = None` on `ValueError` (graceful degradation). Provider key endpoints return HTTP 503 when `key_manager` is `None`.

**Do not add SHA-256 key derivation. Do not add a dev fallback. Constitution §V is explicit: "There is no dev fallback."**

### Rate Limiting — `backend/middleware.py` (spec-08)

`RateLimitMiddleware` is fully implemented as a `BaseHTTPMiddleware` subclass:
- Per-IP, 60-second sliding window using an in-memory `defaultdict`
- Four buckets: provider keys (5/min), chat (30/min), ingest (10/min), general (120/min)
- Returns HTTP 429 with `Retry-After: 60` header and `{"error": {...}, "trace_id": ...}` envelope
- Configured via `settings.rate_limit_*_per_minute` fields

### CORS — `backend/main.py` (spec-08)

`CORSMiddleware` is registered in `create_app()` with `allow_origins` parsed from `settings.cors_origins` (default: `"http://localhost:3000,http://127.0.0.1:3000"`). Note: the current implementation uses `allow_methods=["*"]` (not the restricted list shown in the security blueprint — this is intentional and should not be changed by spec-13).

### Middleware Registration Order — `backend/main.py`

Order in `create_app()` (outermost first):
1. `RateLimitMiddleware`
2. `RequestLoggingMiddleware`
3. `TraceIDMiddleware`
4. `CORSMiddleware`

Do not change this order.

### File Upload — Extension Allowlist and Size Check — `backend/api/ingest.py` (spec-08)

`POST /api/collections/{collection_id}/ingest` already performs:
- Extension allowlist check against `ALLOWED_EXTENSIONS` (the set of 12 extensions) — returns HTTP 400 `FILE_FORMAT_NOT_SUPPORTED`
- Size check against `settings.max_upload_size_mb * 1024 * 1024` — returns HTTP 413 `FILE_TOO_LARGE`
- File is read fully into memory (`content = await file.read()`) before size check, then written to `upload_dir / filename`

### Collection Name Validation — `backend/api/collections.py` (spec-08)

`create_collection` validates `body.name` against `_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")` — returns HTTP 400 `COLLECTION_NAME_INVALID`.

### Existing Settings Fields — `backend/config.py`

These fields already exist. Do not add them again:
```
api_key_encryption_secret: str = ""     # dead field — not used by KeyManager
max_upload_size_mb: int = 100
cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
rate_limit_chat_per_minute: int = 30
rate_limit_ingest_per_minute: int = 10
rate_limit_provider_keys_per_minute: int = 5
rate_limit_general_per_minute: int = 120
```

---

## Functional Requirements (Spec-13 Scope Only)

### FR-001: Chat Message Truncation

**File**: `backend/api/chat.py`
**Gap**: `body.message` is passed directly to `HumanMessage(content=body.message)` with no length check.
**Required**: In `chat()`, before building `initial_state`, truncate `body.message` to 10,000 characters. No error is raised — truncation is silent.

```python
message = body.message[:10_000]
# then use `message` in place of `body.message` for HumanMessage and db.create_query_trace()
```

This prevents context window abuse. The truncation must apply to both the `HumanMessage` content and the `query` field passed to `db.create_query_trace()`.

### FR-002: Qdrant Filter Key Whitelist

**File**: `backend/retrieval/searcher.py`
**Gap**: `_build_filter(self, filters: dict | None)` iterates over any keys in the `filters` dict without validation, allowing arbitrary Qdrant payload field queries.
**Required**: In `_build_filter`, skip any key not in the allowed set `{"doc_type", "source_file", "page", "chunk_index"}`. Unknown keys are silently ignored (not an error).

```python
ALLOWED_FILTER_KEYS = {"doc_type", "source_file", "page", "chunk_index"}

def _build_filter(self, filters: dict | None) -> Filter | None:
    if not filters:
        return None
    conditions = []
    for key, value in filters.items():
        if key not in ALLOWED_FILTER_KEYS:
            continue  # silently ignore unknown keys
        conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
    return Filter(must=conditions) if conditions else None
```

### FR-003: File Upload Validation Hardening

**File**: `backend/api/ingest.py`
**Already present**: Extension allowlist, size check.
**Still missing**:

**FR-003a — Filename sanitization**: Strip path traversal components and enforce safe character set. Apply before saving to disk. A file named `../../etc/passwd.txt` must be sanitized to a safe name.

```python
import re as _re

_SAFE_FILENAME = _re.compile(r"[^a-zA-Z0-9._-]")

def _sanitize_filename(raw: str) -> str:
    # Strip path separators and traversal sequences
    name = raw.replace("\\", "/").split("/")[-1]  # take basename
    name = name.replace("..", "")
    name = _SAFE_FILENAME.sub("_", name)
    return name or "upload"
```

Apply this to `file.filename` before using it as `filename` (the variable currently set on line 72 of `ingest.py`). The sanitized name must be used for both the on-disk path and the `filename` stored in the database.

**FR-003b — Magic number content sniffing for PDF files**: After reading `content`, verify that files with extension `.pdf` start with the magic bytes `b"%PDF"`. If a `.pdf` file does not start with those bytes, return HTTP 400.

```python
if suffix == ".pdf" and not content[:4] == b"%PDF":
    raise HTTPException(status_code=400, detail={
        "error": {
            "code": "FILE_CONTENT_MISMATCH",
            "message": "File content does not match declared type",
            "details": {"expected_magic": "%PDF"},
        },
        "trace_id": trace_id,
    })
```

Note: Magic number checking is only required for PDF in this spec. Other file types do not have reliable single magic bytes across all variants (`.md`, `.txt`, `.py`, `.js`, etc. are plain text — no magic bytes to check).

### FR-004: Logging Security

**File**: `backend/main.py`
**Gap**: The structlog processor chain in `_configure_logging()` does not strip sensitive field names from log records.
**Required**: Add a custom processor that removes any log record key whose name matches (case-insensitive): `api_key`, `password`, `secret`, `token`, `authorization`.

The processor must be inserted before `JSONRenderer` in the processor chain:

```python
def _strip_sensitive_fields(logger, method, event_dict: dict) -> dict:
    _SENSITIVE = {"api_key", "password", "secret", "token", "authorization"}
    for key in list(event_dict.keys()):
        if key.lower() in _SENSITIVE:
            event_dict[key] = "[REDACTED]"
    return event_dict
```

Add `_strip_sensitive_fields` to the processors list in `_configure_logging()`, immediately before `structlog.processors.JSONRenderer()`.

**Verification (not a code change)**: Confirm that `GET /api/providers` and `GET /api/providers/{name}` return `has_key: bool` and never return the `api_key_encrypted` field. This is implemented in `backend/api/providers.py` — verify it is correct and add a test assertion if it is not.

---

## Non-Functional Requirements

- Key encryption/decryption latency must be sub-millisecond (already satisfied by Fernet — do not change).
- No new pip dependencies may be added for spec-13. All changes use Python stdlib (`re`, `os`) and already-required packages.
- Parameterized SQL statements are already enforced everywhere in `backend/storage/sqlite_db.py` — do not change.
- `EMBEDINATOR_FERNET_KEY` must be a pre-generated Fernet key (output of `Fernet.generate_key()`), not a password or arbitrary string.

---

## Key Technical Details

### Insertion Points Summary

| FR | File | Method/Location | Change Type |
|----|------|-----------------|-------------|
| FR-001 | `backend/api/chat.py` | `chat()` — before `initial_state` dict | Add truncation |
| FR-002 | `backend/retrieval/searcher.py` | `_build_filter()` | Add key whitelist |
| FR-003a | `backend/api/ingest.py` | `ingest_file()` — line ~72, filename assignment | Add sanitization function |
| FR-003b | `backend/api/ingest.py` | `ingest_file()` — after size check | Add magic byte check |
| FR-004 | `backend/main.py` | `_configure_logging()` processor chain | Add strip processor |

### `ingest.py` Operation Order After Changes

1. Validate extension (existing)
2. Read content (existing)
3. Validate size (existing)
4. **NEW: Magic number check for PDF**
5. Verify collection exists (existing)
6. **NEW: Sanitize filename**
7. Save file using sanitized filename (existing, modified)
8. Compute hash and check duplicates (existing)
9. Check for changed file (existing)
10. Create document/job records (existing)
11. Launch background ingestion (existing)

### `chat.py` Message Handling After Changes

```python
@router.post("/api/chat")
async def chat(body: ChatRequest, request: Request):
    ...
    message = body.message[:10_000]   # FR-001: truncate silently
    ...
    # Use `message` (not body.message) in:
    #   HumanMessage(content=message)
    #   db.create_query_trace(..., query=message, ...)
```

---

## Dependencies

- `cryptography >= 44.0` — already in `requirements.txt` (used by `KeyManager`)
- No new packages required for spec-13

**Internal module dependencies**:
- `backend/providers/key_manager.py` — spec-07, do not modify
- `backend/middleware.py` — spec-08, do not modify
- `backend/main.py` — modify `_configure_logging()` only
- `backend/api/ingest.py` — add sanitization and magic number check
- `backend/api/chat.py` — add message truncation
- `backend/retrieval/searcher.py` — add filter key whitelist

---

## Acceptance Criteria

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

## Architecture Reference

Relevant files for this spec:

| File | Role in spec-13 |
|------|-----------------|
| `backend/api/chat.py` | FR-001: add message truncation |
| `backend/retrieval/searcher.py` | FR-002: add `ALLOWED_FILTER_KEYS` whitelist in `_build_filter` |
| `backend/api/ingest.py` | FR-003: add `_sanitize_filename()` and PDF magic byte check |
| `backend/main.py` | FR-004: add `_strip_sensitive_fields` processor to structlog |
| `backend/providers/key_manager.py` | Reference only — do not modify |
| `backend/middleware.py` | Reference only — do not modify |
| `backend/config.py` | Reference only — all needed settings already exist |

## Out of Scope for Spec-13

- Authentication or authorization (single-user system, no auth layer)
- TLS termination (handled by reverse proxy in production)
- Virus scanning (noted in blueprint as post-MVP ClamAV hook)
- MIME type verification via `python-magic` (would add a new system dependency; the extension allowlist + PDF magic bytes satisfy the constitution)
- Fernet key rotation (not supported in MVP per security model)
- `api_key_encryption_secret` Settings field cleanup (dead field — leave as-is to avoid migration risk)
