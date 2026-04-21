"""Document embedding and Qdrant indexing pipeline."""

import uuid

import structlog

logger = structlog.get_logger().bind(component=__name__)


async def index_chunks(app, doc_id: str, chunks: list[dict]):
    """Embed document chunks and insert into Qdrant.

    Args:
        app: FastAPI app instance (for accessing state.qdrant and state.registry)
        doc_id: Document ID for metadata
        chunks: List of chunk dicts from chunker
    """
    if not chunks:
        logger.warning("storage_no_chunks_to_index", doc_id=doc_id)
        return

    qdrant = app.state.qdrant
    registry = app.state.registry
    embed_provider = await registry.get_embedding_provider()

    # Ensure collection exists
    dimension = embed_provider.get_dimension()
    await qdrant.ensure_collection("embeddings", vector_size=dimension)

    # Embed chunks in batches
    texts = [c["text"] for c in chunks]
    embeddings = await embed_provider.embed(texts)

    # Prepare points for Qdrant
    points = []
    for chunk, embedding in zip(chunks, embeddings):
        point_id = str(uuid.uuid4())
        points.append(
            {
                "id": point_id,
                "vector": embedding,
                "payload": {
                    "document_id": doc_id,
                    "text": chunk["text"],
                    "chunk_index": chunk["chunk_index"],
                    "start_offset": chunk["start_offset"],
                    "end_offset": chunk["end_offset"],
                },
            }
        )

    # Upsert to Qdrant
    await qdrant.upsert("embeddings", points)
    logger.info("storage_chunks_indexed", doc_id=doc_id, count=len(points))
