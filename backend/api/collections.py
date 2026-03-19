"""Collection CRUD endpoints — US1, FR-002/003/004/005."""

import re
import uuid

from fastapi import APIRouter, HTTPException, Request

from backend.agent.schemas import (
    CollectionCreateRequest,
    CollectionResponse,
)
from backend.config import settings

router = APIRouter()

_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


@router.get("/api/collections")
async def list_collections(request: Request) -> dict:
    """List all collections with document counts."""
    db = request.app.state.db
    collections = await db.list_collections()
    result = []
    for c in collections:
        docs = await db.list_documents(c["id"])
        result.append(CollectionResponse(
            id=c["id"],
            name=c["name"],
            description=c.get("description"),
            embedding_model=c["embedding_model"],
            chunk_profile=c["chunk_profile"],
            document_count=len(docs),
            created_at=c["created_at"],
        ).model_dump())
    return {"collections": result}


@router.post("/api/collections", status_code=201)
async def create_collection(body: CollectionCreateRequest, request: Request) -> dict:
    """Create a new collection with name regex validation."""
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

    await qdrant_storage.create_collection(qdrant_name, vector_size=768)

    await db.create_collection(
        id=collection_id,
        name=name,
        embedding_model=embedding_model,
        chunk_profile=chunk_profile,
        qdrant_collection_name=qdrant_name,
        description=body.description,
    )

    coll = await db.get_collection(collection_id)

    return CollectionResponse(
        id=collection_id,
        name=name,
        description=body.description,
        embedding_model=embedding_model,
        chunk_profile=chunk_profile,
        document_count=0,
        created_at=coll["created_at"],
    ).model_dump()


@router.delete("/api/collections/{collection_id}", status_code=204)
async def delete_collection(collection_id: str, request: Request):
    """Delete a collection with cascade: cancel jobs -> delete qdrant -> delete record."""
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
