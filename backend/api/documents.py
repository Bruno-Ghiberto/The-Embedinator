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
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": f"Document '{doc_id}' not found",
                    "details": {},
                },
                "trace_id": trace_id,
            },
        )
    return doc


@router.delete("/api/documents/{doc_id}", status_code=204)
async def delete_document(doc_id: str, request: Request):
    """Delete a document."""
    db = request.app.state.db
    doc = await db.get_document(doc_id)
    if not doc:
        trace_id = getattr(request.state, "trace_id", "")
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": f"Document '{doc_id}' not found",
                    "details": {},
                },
                "trace_id": trace_id,
            },
        )
    await db.delete_document(doc_id)
