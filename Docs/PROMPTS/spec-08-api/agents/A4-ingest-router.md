# A4: Ingest Router

**Agent type:** `backend-architect`
**Model:** Sonnet 4.6
**Tasks:** T012, T013, T014, T017
**Wave:** 2 (parallel with A3)

---

## Assigned Tasks

### T012: Write tests/unit/test_collections_router.py (US2 portion)
Partial -- only collection-related ingest validation tests. A5 handles the full collections router tests.

### T013: Write tests/unit/test_documents_router.py (US2 portion)
Partial -- A5 handles the full documents router tests.

### T014: Write tests/unit/test_ingest_router.py
Full unit tests for the new ingest router.

### T017: Create backend/api/ingest.py
New router for file upload ingestion and job status polling.

---

## File Targets

| File | Action |
|------|--------|
| `backend/api/ingest.py` | Create new |
| `tests/unit/test_ingest_router.py` | Create new |

---

## Implementation: backend/api/ingest.py

This is a NEW file. It contains two endpoints:

### POST /api/collections/{collection_id}/ingest

Upload a file and trigger background ingestion. Returns 202.

**Flow:**

1. Validate file extension against 12 allowed types
2. Read file content, validate size <= 100 MB
3. Verify collection exists (404 if not)
4. Compute SHA-256 hash via `IncrementalChecker.compute_file_hash()`
5. Check for duplicate via `IncrementalChecker.check_duplicate()` (409 if duplicate)
6. Check for changed file via `IncrementalChecker.check_change()` (delete old data if changed)
7. Save file to `settings.upload_dir/{collection_id}/{filename}`
8. Create document record via `db.create_document(id, collection_id, filename, file_hash, file_path, status="pending")`
9. Create ingestion job via `db.create_ingestion_job(id, document_id)`
10. Launch `IngestionPipeline.ingest_file()` via `asyncio.create_task()`
11. Return 202 with `IngestionJobResponse`

**Code structure:**

```python
"""Ingestion endpoints -- file upload and job status polling."""

import asyncio
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile, File

from backend.agent.schemas import IngestionJobResponse
from backend.config import settings
from backend.ingestion.incremental import IncrementalChecker
from backend.ingestion.pipeline import IngestionPipeline

router = APIRouter()

ALLOWED_EXTENSIONS = {
    ".pdf", ".md", ".txt", ".py", ".js", ".ts",
    ".rs", ".go", ".java", ".c", ".cpp", ".h",
}


@router.post("/api/collections/{collection_id}/ingest", status_code=202)
async def ingest_file(
    collection_id: str,
    request: Request,
    file: UploadFile = File(...),
):
    db = request.app.state.db
    qdrant = request.app.state.qdrant

    # 1. Validate extension
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        trace_id = getattr(request.state, "trace_id", "")
        raise HTTPException(status_code=400, detail={
            "error": {
                "code": "FILE_FORMAT_NOT_SUPPORTED",
                "message": f"File type '{suffix}' is not supported. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
                "details": {"allowed_extensions": sorted(ALLOWED_EXTENSIONS)},
            },
            "trace_id": trace_id,
        })

    # 2. Read and validate size
    content = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        trace_id = getattr(request.state, "trace_id", "")
        raise HTTPException(status_code=413, detail={
            "error": {
                "code": "FILE_TOO_LARGE",
                "message": f"File exceeds maximum size of {settings.max_upload_size_mb} MB",
                "details": {"max_size_mb": settings.max_upload_size_mb, "file_size_bytes": len(content)},
            },
            "trace_id": trace_id,
        })

    # 3. Verify collection exists
    collection = await db.get_collection(collection_id)
    if not collection:
        trace_id = getattr(request.state, "trace_id", "")
        raise HTTPException(status_code=404, detail={
            "error": {
                "code": "COLLECTION_NOT_FOUND",
                "message": f"Collection '{collection_id}' not found",
                "details": {},
            },
            "trace_id": trace_id,
        })

    # 4. Save file
    filename = file.filename or f"document{suffix}"
    upload_dir = Path(settings.upload_dir) / collection_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / filename
    with open(file_path, "wb") as f:
        f.write(content)

    # 5. Compute hash and check duplicates
    checker = IncrementalChecker(db)
    file_hash = IncrementalChecker.compute_file_hash(str(file_path))

    is_dup, existing_id = await checker.check_duplicate(collection_id, file_hash)
    if is_dup:
        file_path.unlink(missing_ok=True)
        trace_id = getattr(request.state, "trace_id", "")
        raise HTTPException(status_code=409, detail={
            "error": {
                "code": "DUPLICATE_DOCUMENT",
                "message": f"A document with identical content already exists in this collection",
                "details": {"existing_document_id": existing_id},
            },
            "trace_id": trace_id,
        })

    # 6. Check for changed file (same filename, different hash)
    pipeline = IngestionPipeline(db=db, qdrant=qdrant)
    is_changed, old_doc_id = await checker.check_change(collection_id, filename, file_hash)
    if is_changed and old_doc_id:
        await pipeline.delete_old_document_data(
            collection_name=collection_id,
            source_file=filename,
            old_document_id=old_doc_id,
        )
        await db.update_document(old_doc_id, status="deleted")

    # 7. Create document and job records
    doc_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())

    await db.create_document(
        id=doc_id,
        collection_id=collection_id,
        filename=filename,
        file_hash=file_hash,
        file_path=str(file_path),
        status="pending",
    )
    await db.create_ingestion_job(id=job_id, document_id=doc_id)

    # 8. Launch background ingestion
    asyncio.create_task(
        pipeline.ingest_file(
            file_path=str(file_path),
            filename=filename,
            collection_id=collection_id,
            document_id=doc_id,
            job_id=job_id,
            file_hash=file_hash,
        )
    )

    # 9. Return 202
    return {
        "job_id": job_id,
        "document_id": doc_id,
        "status": "started",
        "filename": filename,
        "chunks_processed": 0,
        "chunks_total": None,
        "error_message": None,
        "started_at": None,
        "completed_at": None,
    }


@router.get("/api/collections/{collection_id}/ingest/{job_id}")
async def get_ingestion_job(collection_id: str, job_id: str, request: Request):
    db = request.app.state.db
    job = await db.get_ingestion_job(job_id)
    if not job:
        trace_id = getattr(request.state, "trace_id", "")
        raise HTTPException(status_code=404, detail={
            "error": {
                "code": "JOB_NOT_FOUND",
                "message": f"Ingestion job '{job_id}' not found",
                "details": {},
            },
            "trace_id": trace_id,
        })
    return {
        "job_id": job["id"],
        "document_id": job["document_id"],
        "status": job["status"],
        "chunks_processed": job.get("chunks_processed", 0),
        "chunks_total": None,
        "error_message": job.get("error_msg"),
        "started_at": job.get("started_at"),
        "completed_at": job.get("finished_at"),
    }
```

### SQLiteDB Method Signatures (Reference)

```python
# These are the actual method signatures in sqlite_db.py:
await db.create_document(id, collection_id, filename, file_hash, file_path=None, status="pending")
await db.create_ingestion_job(id, document_id, status="started")
await db.get_ingestion_job(job_id) -> dict | None
await db.get_collection(collection_id) -> dict | None
await db.update_document(doc_id, **kwargs)
```

The caller MUST generate UUIDs for `id` parameters. SQLiteDB does NOT auto-generate IDs.

---

## Test Specifications: test_ingest_router.py

Mock `SQLiteDB`, `IngestionPipeline`, `IncrementalChecker`. Test:

1. **12 allowed extensions**: Upload files with each of `.pdf`, `.md`, `.txt`, `.py`, `.js`, `.ts`, `.rs`, `.go`, `.java`, `.c`, `.cpp`, `.h` -- all return 202
2. **Unsupported extension**: Upload `.exe` -> 400 with code `FILE_FORMAT_NOT_SUPPORTED`
3. **File too large**: Upload >100MB -> 413 with code `FILE_TOO_LARGE`
4. **Duplicate content hash**: IncrementalChecker returns duplicate -> 409 with code `DUPLICATE_DOCUMENT`
5. **Collection not found**: db.get_collection returns None -> 404 with code `COLLECTION_NOT_FOUND`
6. **GET job status**: Returns correct IngestionJobResponse shape
7. **GET job not found**: Returns 404 with code `JOB_NOT_FOUND`
8. **Background task launched**: Verify `asyncio.create_task` called with pipeline.ingest_file
9. **Response format**: 202 body contains `job_id`, `document_id`, `status`, `filename`

---

## Test Command

```bash
zsh scripts/run-tests-external.sh -n spec08-ingest tests/unit/test_ingest_router.py
cat Docs/Tests/spec08-ingest.status
cat Docs/Tests/spec08-ingest.summary
```

---

## Key Constraints

- 12 file types: `.pdf .md .txt .py .js .ts .rs .go .java .c .cpp .h`
- Size limit: 100 MB (from `settings.max_upload_size_mb`)
- Background ingestion: `asyncio.create_task()` (NOT `await`)
- Response code: 202 Accepted (not 200 or 201)
- Error responses: structured format with `error.code`, `error.message`, `error.details`, and `trace_id`
- UUIDs: caller generates via `str(uuid.uuid4())` for both doc_id and job_id
- `IncrementalChecker.compute_file_hash()` is a `@staticmethod` -- call on the class, not an instance

---

## What NOT to Do

- Do NOT put ingest endpoints in `collections.py` or `documents.py` -- this is a separate router
- Do NOT import from `documents.py` -- the legacy ingest code there will be removed by A5
- Do NOT use `await` on `asyncio.create_task()` -- the task runs in the background
- Do NOT validate MIME content-type for non-PDF files (spec only requires extension validation)
- Do NOT add a `chunks_total` field to the 202 response -- it is None until the pipeline computes it
- Do NOT run pytest inside Claude Code -- use the external test runner
