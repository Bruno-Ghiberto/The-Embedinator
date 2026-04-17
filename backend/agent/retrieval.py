"""Query retrieval logic — T035.

Searches Qdrant for relevant passages and filters by collection membership.
"""

from backend.storage.qdrant_client import QdrantClientWrapper
from backend.storage.sqlite_db import SQLiteDB


async def retrieve_passages(
    query_vector: list[float],
    collection_ids: list[str],
    qdrant: QdrantClientWrapper,
    db: SQLiteDB,
    limit: int = 20,
    top_k: int = 5,
) -> list[dict]:
    """Search Qdrant for passages matching the query vector, filtered by collections.

    Returns top_k passages sorted by relevance score.
    """
    results = await qdrant.search("embeddings", query_vector, limit=limit)

    passages = []
    for r in results:
        payload = r.get("payload", {})
        doc_id = payload.get("document_id", "")
        doc = await db.get_document(doc_id)
        if doc and doc["status"] != "deleted":
            doc_collections = doc.get("collection_ids", [])
            if any(c in collection_ids for c in doc_collections):
                passages.append(
                    {
                        "id": r["id"],
                        "document_id": doc_id,
                        "document_name": doc.get("name", "unknown"),
                        "text": payload.get("text", ""),
                        "relevance_score": r["score"],
                        "chunk_index": payload.get("chunk_index", 0),
                        "source_removed": False,
                    }
                )

    # Sort by relevance and return top_k
    passages.sort(key=lambda p: p["relevance_score"], reverse=True)
    return passages[:top_k]
