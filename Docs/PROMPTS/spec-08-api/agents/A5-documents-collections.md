# A5: Documents + Collections

**Agent type:** `refactoring-expert`
**Model:** Sonnet 4.6
**Tasks:** T015, T016
**Wave:** 3 (parallel with A6)

---

## Assigned Tasks

### T015: Extend backend/api/collections.py
Add name regex validation with proper error codes, extend DELETE for cascade.

### T016: Rewrite backend/api/documents.py
Remove legacy ingest code, keep only GET/DELETE endpoints, align to spec-07 schemas.

---

## File Targets

| File | Action |
|------|--------|
| `backend/api/collections.py` | Extend |
| `backend/api/documents.py` | Rewrite (remove legacy, keep GET/DELETE) |
| `tests/unit/test_collections_router.py` | Create new |
| `tests/unit/test_documents_router.py` | Create new |

---

## Implementation: backend/api/collections.py

Read the current file first. It has 3 endpoints: GET list, POST create, DELETE.

### Changes Required

**1. POST /api/collections -- Improve validation and error handling**

The `CollectionCreateRequest` schema (updated by A1) already has `pattern=r"^[a-z0-9][a-z0-9_-]*$"`. FastAPI will auto-reject invalid names with 422. To return 400 with the correct error code instead, catch the validation error OR add explicit validation:

```python
import re
import uuid

from backend.agent.schemas import (
    CollectionCreateRequest,
    CollectionResponse,
)
from backend.config import settings

_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

@router.post("/api/collections", status_code=201)
async def create_collection(body: CollectionCreateRequest, request: Request):
    db = request.app.state.db
    qdrant_storage = request.app.state.qdrant_storage
    trace_id = getattr(request.state, "trace_id", "")

    name = body.name.strip()
    if not _NAME_PATTERN.match(name):
        raise HTTPException(status_code=400, detail={
            "error": {
                "code": "COLLECTION_NAME_INVALID",
                "message": f"Collection name '{name}' must match pattern: lowercase alphanumeric, hyphens, underscores, start with alphanumeric",
                "details": {"pattern": "^[a-z0-9][a-z0-9_-]*$"},
            },
            "trace_id": trace_id,
        })

    # Check for duplicate name
    existing = await db.get_collection_by_name(name)
    if existing:
        raise HTTPException(status_code=409, detail={
            "error": {
                "code": "COLLECTION_NAME_CONFLICT",
                "message": f"Collection '{name}' already exists",
                "details": {},
            },
            "trace_id": trace_id,
        })

    collection_id = str(uuid.uuid4())
    embedding_model = body.embedding_model or settings.default_embed_model
    chunk_profile = body.chunk_profile or "default"
    qdrant_name = f"emb-{collection_id}"

    # Create Qdrant collection
    await qdrant_storage.create_collection(qdrant_name, dim=768)  # nomic-embed-text default

    # Create in SQLite
    await db.create_collection(
        id=collection_id,
        name=name,
        embedding_model=embedding_model,
        chunk_profile=chunk_profile,
        qdrant_collection_name=qdrant_name,
        description=body.description,
    )

    # Count documents (new collection = 0)
    docs = await db.list_documents(collection_id)

    return CollectionResponse(
        id=collection_id,
        name=name,
        description=body.description,
        embedding_model=embedding_model,
        chunk_profile=chunk_profile,
        document_count=len(docs),
        created_at=...,  # fetch from db or use current time
    )
```

Note: After calling `db.create_collection()`, you need the `created_at` value. Either:
- Fetch: `coll = await db.get_collection(collection_id)` then use `coll["created_at"]`
- Or compute it before the insert and pass it through

**2. DELETE /api/collections/{collection_id} -- Add cascade**

The cascade order is critical (FR-005):

```python
@router.delete("/api/collections/{collection_id}", status_code=204)
async def delete_collection(collection_id: str, request: Request):
    db = request.app.state.db
    qdrant_storage = request.app.state.qdrant_storage
    trace_id = getattr(request.state, "trace_id", "")

    collection = await db.get_collection(collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail={
            "error": {
                "code": "COLLECTION_NOT_FOUND",
                "message": f"Collection '{collection_id}' not found",
                "details": {},
            },
            "trace_id": trace_id,
        })

    # Step 1: Cancel active ingestion jobs (set to failed)
    documents = await db.list_documents(collection_id)
    for doc in documents:
        jobs = await db.list_ingestion_jobs(doc["id"])
        for job in jobs:
            if job["status"] not in ("completed", "failed"):
                await db.update_ingestion_job(
                    job["id"],
                    status="failed",
                    error_msg="Collection deleted",
                )

    # Step 2: Delete Qdrant collection
    qdrant_name = collection["qdrant_collection_name"]
    try:
        await qdrant_storage.delete_collection(qdrant_name)
    except Exception:
        pass  # Qdrant collection may not exist

    # Step 3: Delete collection (CASCADE deletes documents and jobs via FK)
    await db.delete_collection(collection_id)
```

**3. GET /api/collections -- Add document_count**

```python
@router.get("/api/collections")
async def list_collections(request: Request):
    db = request.app.state.db
    collections = await db.list_collections()
    result = []
    for c in collections:
        docs = await db.list_documents(c["id"])
        result.append({
            **c,
            "document_count": len(docs),
        })
    return {"collections": result}
```

### Key Detail: qdrant_storage vs qdrant

The app has TWO Qdrant clients:
- `app.state.qdrant` -- `QdrantClientWrapper` (spec-02, used for search)
- `app.state.qdrant_storage` -- `QdrantStorage` (spec-07, used for collection management)

For `create_collection()` and `delete_collection()`, use `app.state.qdrant_storage`.

---

## Implementation: backend/api/documents.py

Read the current file first. It has:
- `upload_document()` -- LEGACY Phase 1 stub. REMOVE.
- `_process_document()` -- LEGACY background task. REMOVE.
- `ingest_document()` -- spec-06 code. REMOVE (moved to `ingest.py` by A4).
- `SUPPORTED_FORMATS` -- REMOVE (moved to `ingest.py`).
- `list_documents()` -- KEEP and fix.
- `get_document()` -- KEEP.
- `delete_document()` -- KEEP.

**Rewritten file:**

```python
"""Document listing and deletion endpoints."""

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get("/api/documents")
async def list_documents(request: Request, collection_id: str | None = None) -> dict:
    """List documents, optionally filtered by collection."""
    db = request.app.state.db
    if collection_id:
        documents = await db.list_documents(collection_id)
    else:
        # list_documents() requires collection_id, so aggregate across all collections
        collections = await db.list_collections()
        documents = []
        for c in collections:
            documents.extend(await db.list_documents(c["id"]))
    return {"documents": documents}


@router.get("/api/documents/{doc_id}")
async def get_document(doc_id: str, request: Request) -> dict:
    """Get document details."""
    db = request.app.state.db
    doc = await db.get_document(doc_id)
    if not doc:
        trace_id = getattr(request.state, "trace_id", "")
        raise HTTPException(status_code=404, detail={
            "error": {
                "code": "DOCUMENT_NOT_FOUND",
                "message": f"Document '{doc_id}' not found",
                "details": {},
            },
            "trace_id": trace_id,
        })
    return doc


@router.delete("/api/documents/{doc_id}", status_code=204)
async def delete_document(doc_id: str, request: Request):
    """Delete a document."""
    db = request.app.state.db
    doc = await db.get_document(doc_id)
    if not doc:
        trace_id = getattr(request.state, "trace_id", "")
        raise HTTPException(status_code=404, detail={
            "error": {
                "code": "DOCUMENT_NOT_FOUND",
                "message": f"Document '{doc_id}' not found",
                "details": {},
            },
            "trace_id": trace_id,
        })
    await db.delete_document(doc_id)
```

### Critical: list_documents() Signature

`SQLiteDB.list_documents(collection_id: str)` has a REQUIRED `collection_id` parameter. If the query parameter is None (no filter), you must iterate over all collections. This is acceptable for the 1-5 user scale.

---

## Test Specifications

### test_collections_router.py

Mock `SQLiteDB` and `QdrantStorage`. Test:

1. **Name regex validation**: Names with uppercase, spaces, special chars -> 400 `COLLECTION_NAME_INVALID`
2. **Valid names**: `my-docs`, `test_123`, `a` -> 201
3. **Duplicate name**: db.get_collection_by_name returns existing -> 409 `COLLECTION_NAME_CONFLICT`
4. **DELETE cascade**: Verify order -- jobs set to failed BEFORE qdrant delete BEFORE collection delete
5. **DELETE 404**: Non-existent collection_id -> 404 `COLLECTION_NOT_FOUND`
6. **GET list**: Returns collections with document_count
7. **Error response format**: All errors include `error.code`, `error.message`, `trace_id`

### test_documents_router.py

Mock `SQLiteDB`. Test:

1. **GET /documents**: Returns list of documents
2. **GET /documents with collection_id filter**: Filters correctly
3. **GET /documents/{id}**: Returns document detail
4. **GET /documents/{id} 404**: Returns `DOCUMENT_NOT_FOUND`
5. **DELETE /documents/{id}**: Returns 204
6. **DELETE /documents/{id} 404**: Returns `DOCUMENT_NOT_FOUND`

---

## Test Command

```bash
zsh scripts/run-tests-external.sh -n spec08-docscoll tests/unit/test_collections_router.py tests/unit/test_documents_router.py
cat Docs/Tests/spec08-docscoll.status
cat Docs/Tests/spec08-docscoll.summary
```

---

## Key Constraints

- `db.list_documents(collection_id)` requires collection_id -- it is NOT optional
- `db.list_ingestion_jobs(document_id)` takes document_id, NOT collection_id
- Use `app.state.qdrant_storage` (QdrantStorage) for collection create/delete, NOT `app.state.qdrant`
- All error responses must use the structured format: `{"error": {"code": ..., "message": ..., "details": {}}, "trace_id": ...}`
- The `delete_document()` in SQLiteDB does NOT return a boolean. Check existence first with `get_document()`.
- FK CASCADE in SQLite handles document/job cleanup when collection is deleted, but you must still cancel active jobs BEFORE deletion (FR-005 requires status transition to `failed`)

---

## What NOT to Do

- Do NOT keep any ingest-related code in documents.py -- it belongs in ingest.py (A4)
- Do NOT keep `SUPPORTED_FORMATS` in documents.py -- it is in ingest.py
- Do NOT keep `upload_document()`, `_process_document()`, or `ingest_document()` -- remove all three
- Do NOT import from `backend.ingestion` in documents.py -- that is ingest.py's concern
- Do NOT use `app.state.qdrant` (QdrantClientWrapper) for collection deletion -- use `app.state.qdrant_storage`
- Do NOT run pytest inside Claude Code -- use the external test runner
