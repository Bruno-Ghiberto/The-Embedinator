# Contract: POST /api/collections/{collection_id}/ingest

**Modified by**: spec-13 FR-003a, FR-003b
**File**: `backend/api/ingest.py`

## Request

Multipart form upload:

| Field | Type | Constraint | Change |
|-------|------|------------|--------|
| `file` | UploadFile | Required | Filename sanitized; PDF content verified |
| `collection_id` | path param str | Required | Unchanged |

## Existing Checks (Unchanged)

| Check | Error | Code |
|-------|-------|------|
| Extension not in allowlist | HTTP 400 | `FILE_FORMAT_NOT_SUPPORTED` |
| File size > `max_upload_size_mb` | HTTP 413 | `FILE_TOO_LARGE` |

## New Checks (spec-13)

### FR-003b — PDF Magic Byte Check

Applied after size check, before collection existence check.

| Condition | HTTP Status | Error Code |
|-----------|-------------|------------|
| Extension is `.pdf` AND `content[:4] == b"%PDF"` | Continue normally | — |
| Extension is `.pdf` AND `content[:4] != b"%PDF"` | 400 | `FILE_CONTENT_MISMATCH` |
| Extension is NOT `.pdf` | No check applied | — |

Error response body:
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

### FR-003a — Filename Sanitization

Applied after collection existence check, before saving to disk.

```python
filename = _sanitize_filename(file.filename or f"document{suffix}")
```

The sanitized name is used for both:
- On-disk file path: `upload_dir / filename`
- Database record: `db.create_document(filename=filename, ...)`

#### `_sanitize_filename(raw: str) -> str` behaviour

| Input | Output |
|-------|--------|
| `"../../etc/passwd.txt"` | `"passwd.txt"` (or similar safe name) |
| `"report (final).pdf"` | `"report__final_.pdf"` |
| `"normal-file.md"` | `"normal-file.md"` (unchanged) |
| `"../../"` | `"upload"` (empty fallback) |
| `""` | `"upload"` (empty fallback) |

## Operation Order (post-spec-13)

```
1.  Extension check     → 400 FILE_FORMAT_NOT_SUPPORTED
2.  Read content
3.  Size check          → 413 FILE_TOO_LARGE
4.  PDF magic check     → 400 FILE_CONTENT_MISMATCH  ← NEW
5.  Collection exists?  → 404 (existing)
6.  Sanitize filename   ← NEW
7.  Save file to disk
8.  Hash + dedup check
9.  Changed-file check
10. Create document + job records
11. Launch ingestion background task
```

## Success Response

```json
{
  "job_id": "string",
  "document_id": "string",
  "filename": "string",   ← sanitized filename (may differ from uploaded name)
  "status": "pending"
}
```

## Rate Limiting

Unchanged: 10 requests/min per IP (spec-08 `RateLimitMiddleware`). HTTP 429 on breach.
