"""Ingestion endpoints -- file upload and job status polling."""

import asyncio
import re as _re
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

_SAFE_FILENAME = _re.compile(r"[^a-zA-Z0-9._-]")


def _sanitize_filename(raw: str) -> str:
    """Strip path traversal sequences and unsafe characters from a filename."""
    name = raw.replace("\\", "/").split("/")[-1]
    name = name.replace("..", "")
    name = _SAFE_FILENAME.sub("_", name)
    return name or "upload"


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

    # 3. PDF magic byte check (FR-004)
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

    # 4. Verify collection exists
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
    filename = _sanitize_filename(file.filename or f"document{suffix}")
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
                "message": "A document with identical content already exists in this collection",
                "details": {"existing_document_id": existing_id},
            },
            "trace_id": trace_id,
        })

    # 6. Check for changed file (same filename, different hash)
    registry = getattr(request.app.state, "registry", None)
    embedding_provider = await registry.get_embedding_provider() if registry is not None else None
    pipeline = IngestionPipeline(db=db, qdrant=qdrant, embedding_provider=embedding_provider)
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
    return IngestionJobResponse(
        job_id=job_id,
        document_id=doc_id,
        status="started",
        chunks_processed=0,
        chunks_total=None,
        error_message=None,
        started_at=None,
        completed_at=None,
    )


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
    return IngestionJobResponse(
        job_id=job["id"],
        document_id=job["document_id"],
        status=job["status"],
        chunks_processed=job.get("chunks_processed", 0) or 0,
        chunks_total=None,
        error_message=job.get("error_msg"),
        started_at=job.get("started_at"),
        completed_at=job.get("finished_at"),
    )
