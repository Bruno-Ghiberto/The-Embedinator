# API Contract: Document Ingestion

**Endpoint**: `POST /api/collections/{collection_id}/ingest`
**Content-Type**: `multipart/form-data`
**Auth**: None (trusted local network per Constitution Principle I)

## Request

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `collection_id` | string (UUID) | Yes | Target collection for ingestion |

### Body (multipart/form-data)

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `file` | file | Yes | Max 100MB, allowed extensions only | Document to ingest |

### Allowed File Extensions

`.pdf`, `.md`, `.txt`, `.py`, `.js`, `.ts`, `.rs`, `.go`, `.java`, `.c`, `.cpp`, `.h`

## Responses

### 202 Accepted — Ingestion Started

```json
{
  "document_id": "uuid4-string",
  "job_id": "uuid4-string",
  "status": "started",
  "filename": "report.pdf",
  "message": "Ingestion started"
}
```

### 400 Bad Request — Invalid File

```json
{
  "error": "INVALID_FILE",
  "message": "Unsupported file type: .exe. Allowed: .pdf, .md, .txt, .py, .js, .ts, .rs, .go, .java, .c, .cpp, .h"
}
```

### 404 Not Found — Collection Not Found

```json
{
  "error": "COLLECTION_NOT_FOUND",
  "message": "Collection {collection_id} does not exist"
}
```

### 409 Conflict — Duplicate Document

```json
{
  "error": "DUPLICATE_DOCUMENT",
  "message": "File with hash {hash} already exists in collection {collection_id} with status 'completed'"
}
```

### 413 Request Entity Too Large — File Too Large

```json
{
  "error": "FILE_TOO_LARGE",
  "message": "File exceeds maximum size of 100MB"
}
```

### 500 Internal Server Error — Pipeline Failure

```json
{
  "error": "INGESTION_ERROR",
  "message": "Failed to start ingestion: {details}"
}
```

## Behavior

1. Validate file extension against allowlist → 400 if invalid
2. Validate file size ≤ 100MB → 413 if too large
3. Validate collection exists → 404 if not found
4. Validate MIME type for PDF files → 400 if not `application/pdf`
5. Compute SHA256 hash of file content
6. Check for duplicate (same hash + collection + status=completed) → 409 if duplicate
7. If same hash exists with status=failed → allow re-ingestion
8. If different hash exists for same filename → delete old data, re-ingest
9. Save file to `upload_dir/{collection_id}/{filename}`
10. Create `documents` record (status=`pending`)
11. Create `ingestion_jobs` record (status=`started`)
12. Launch ingestion pipeline as background task
13. Return 202 with document_id and job_id

## Rate Limiting

- 10 uploads per minute per client (per Constitution Principle V)
- Applied at middleware level

---

## Job Status Endpoint (Future — spec-08)

**Endpoint**: `GET /api/collections/{collection_id}/ingest/{job_id}`

This endpoint will be implemented in spec-08 (API). For now, job status is queryable directly via the `ingestion_jobs` table.

Expected response shape:

```json
{
  "job_id": "uuid4-string",
  "document_id": "uuid4-string",
  "status": "embedding",
  "started_at": "2026-03-13T10:30:00Z",
  "finished_at": null,
  "chunks_processed": 450,
  "chunks_skipped": 2,
  "error_msg": null
}
```
