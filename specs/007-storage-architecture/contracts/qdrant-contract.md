# Qdrant Vector Storage Contract

**Feature**: Storage Architecture | **Date**: 2026-03-13 | **Version**: 1.0

## Overview

Internal contract defining the QdrantStorage class interface. This is the vector database client used for hybrid search (dense embeddings + BM25 sparse vectors) and point management.

## Class: QdrantStorage

**Module**: `backend.storage.qdrant_client`

**Responsibility**: Collection management, batch upsert of vectors with payloads, hybrid search (dense + sparse), point deletion, connection pooling.

### Public Methods

#### Initialization & Lifecycle

```python
class QdrantStorage:
    def __init__(self, host: str = "localhost", port: int = 6333)
    async def health_check() -> bool
```

**Contract**:
- Initializes Qdrant client (async context)
- host/port: Qdrant service location
- health_check(): Returns True if Qdrant is reachable, False otherwise (used for circuit breaker)

---

#### Collection Management

```python
async def create_collection(
    collection_name: str,
    vector_size: int = 768,
    distance: str = "cosine"
) -> None

async def collection_exists(collection_name: str) -> bool

async def delete_collection(collection_name: str) -> None

async def get_collection_info(collection_name: str) -> dict
```

**Contract**:
- create_collection: Creates Qdrant collection with:
  - Dense vector config: vector_size dims (default 768), cosine distance
  - Sparse vector config: BM25 with IDF modifier for keyword search
  - Idempotent: Does not fail if collection exists (app checks beforehand or handles error)
- collection_exists: Returns True/False
- delete_collection: Removes collection and all points
- get_collection_info: Returns {name, points_count, vector_size, status}
- Raises: QdrantError on connection failure or invalid parameters

---

#### Batch Vector Upsert

```python
async def batch_upsert(
    collection_name: str,
    points: list[QdrantPoint]
) -> int  # Count of upserted points

class QdrantPoint:
    id: int  # Unique point ID within collection (incremental or hash-based)
    vector: list[float]  # Dense embedding (768 dims)
    sparse_vector: SparseVector | None  # BM25 token indices + weights
    payload: dict  # Metadata (parent_id, text, breadcrumb, etc.)
```

**Contract**:
- Upserts all points in batch (replace if ID exists, insert if new)
- Returns count of points upserted
- Sparse vector: Optional, computed from text via BM25 tokenizer
- Payload structure (required fields):
  ```json
  {
    "text": "child chunk text (~300 chars)",
    "parent_id": "uuid5_of_parent_chunk",
    "breadcrumb": "Collection > Document > Section",
    "source_file": "report.pdf",
    "page": 3,
    "chunk_index": 5,
    "doc_type": "Prose|Code",
    "chunk_hash": "sha256",
    "embedding_model": "all-MiniLM-L6-v2",
    "collection_name": "qdrant_collection_name",
    "ingested_at": "2026-03-13T10:00:00Z"
  }
  ```
- Idempotent: Re-upserting same point ID replaces vectors and payload
- Raises:
  - QdrantError if collection doesn't exist
  - QdrantError if batch timeout (Qdrant unavailable)

**Batch Failure Strategy**:
- Entire batch fails on Qdrant timeout/error
- No partial upsert tracking
- Orchestrator retries entire batch when Qdrant recovers (safe via idempotency)

---

#### Hybrid Search

```python
async def search_hybrid(
    collection_name: str,
    dense_vector: list[float],
    sparse_vector: SparseVector | None,
    top_k: int = 10,
    dense_weight: float = 0.6,
    sparse_weight: float = 0.4,
    score_threshold: float | None = None
) -> list[SearchResult]

class SearchResult:
    id: int  # Point ID
    score: float  # Hybrid score (0.0–1.0 after normalization)
    payload: dict  # Parent metadata from point payload
```

**Contract**:
- Performs rank fusion of dense (cosine) + sparse (BM25) results
- Weights: dense_weight + sparse_weight should ideally sum to 1.0 (default 0.6 + 0.4)
- top_k: Limit results (default 10, typical 10–100 for chat context)
- score_threshold: Optional filter (if provided, only return scores >= threshold)
- Returns: List of SearchResult objects, ordered by hybrid score descending
- Payload includes parent_id (link to SQLite parent_chunks table)
- Raises:
  - QdrantError if collection doesn't exist
  - QdrantError if vector dimensions mismatch
  - QdrantError if Qdrant unavailable (timeout)

**Performance Target**:
- <100ms for hybrid search on 100K vectors
- Uses Qdrant's built-in HNSW index for dense vectors
- BM25 sparse vectors preprocessed at ingestion time

---

#### Point Deletion

```python
async def delete_points(
    collection_name: str,
    point_ids: list[int]
) -> int  # Count of deleted points

async def delete_points_by_filter(
    collection_name: str,
    filter: dict
) -> int  # Count of deleted points
```

**Contract**:
- delete_points: Removes specific points by ID
- delete_points_by_filter: Removes points matching filter (e.g., {payload.document_id == doc_id})
- Returns count of deleted points
- Raises: QdrantError if collection doesn't exist

**Use Cases**:
- Document deletion: Remove all points for document_id (called when document marked as deleted)
- Re-ingestion: Delete old vectors before upserting new ones (optional, handled by idempotent upsert)

---

#### Point Retrieval

```python
async def get_point(collection_name: str, point_id: int) -> dict | None

async def get_points_by_ids(
    collection_name: str,
    point_ids: list[int]
) -> list[dict]
```

**Contract**:
- get_point: Returns point data {id, vector, sparse_vector, payload} or None
- get_points_by_ids: Batch retrieval for validation/debugging
- Raises: QdrantError if collection doesn't exist

---

#### Scroll (Iteration)

```python
async def scroll_points(
    collection_name: str,
    limit: int = 100,
    offset: int | None = None
) -> tuple[list[dict], int | None]
```

**Contract**:
- Iterates through collection in batches
- Returns (points, next_offset) for cursor-based pagination
- next_offset: None if end of collection
- Use case: Bulk export, analytics, validation

---

## Error Handling

### Expected Exceptions

| Exception | Scenario | Recovery |
|-----------|----------|----------|
| QdrantError | Connection refused, timeout | Retry with circuit breaker, log error |
| QdrantError | Collection not found | Check collection existence first, or create |
| QdrantError | Vector dimension mismatch | Verify embedding model matches collection config |
| grpc.RpcError | Network failure | Retry via tenacity with backoff |

### Resilience

- Circuit breaker: App-level (Spec 05), wraps QdrantStorage calls
- Timeouts: Default 30–60s (configurable)
- Retries: Tenacity with exponential backoff (app responsibility)

---

## Payload Structure

### Required Fields (All Points)

| Field | Type | Purpose |
|-------|------|---------|
| text | str | Child chunk text (~300 chars) for context |
| parent_id | str | UUID5 reference to SQLite parent_chunks.id |
| breadcrumb | str | Hierarchy breadcrumb (Collection > Doc > Section) |
| source_file | str | Original filename (e.g., report.pdf) |
| page | int | Page number (1-indexed, 0 if not applicable) |
| chunk_index | int | Sequential chunk number within document |
| doc_type | str | "Prose" or "Code" (no mixed types) |
| chunk_hash | str | SHA256 of chunk text (dedup indicator) |
| embedding_model | str | Model used for dense vector (e.g., all-MiniLM-L6-v2) |
| collection_name | str | Qdrant collection name (redundant but useful) |
| ingested_at | str | ISO8601 timestamp of ingestion |

### Optional Fields (For Future Extensions)

- confidence: Float 0.0–1.0 (reranker score if pre-computed)
- metadata: JSON object for extensibility

---

## Vector Configuration

### Dense Vector (Primary Search)

```
config: {
  size: 768,
  distance: "cosine",
  hnsw: {
    m: 16,
    ef_construct: 200
  }
}
```

- Uses HNSW (Hierarchical Navigable Small World) for fast approximate search
- 768 dimensions standard for sentence-transformer models (all-MiniLM-L6-v2, etc.)
- Cosine distance normalized to 0.0–1.0 score range

### Sparse Vector (Keyword Search)

```
config: {
  modifier: "idf",
  index: {
    on_disk: true
  }
}
```

- BM25 with IDF (Inverse Document Frequency) modifier
- On-disk index for memory efficiency on large collections
- Complements dense vectors for exact keyword matches

### Hybrid Fusion

- Linear weighted average: hybrid_score = dense_weight * dense_score + sparse_weight * sparse_score
- Normalized: Both dense and sparse scores in [0.0, 1.0]
- Tunable weights: Default (0.6, 0.4) can be adjusted per collection/query

---

## Performance Characteristics

| Operation | Target | Notes |
|-----------|--------|-------|
| create_collection() | <1s | Single-threaded, one-time setup |
| batch_upsert(1000 points) | <2s | Network time dominating |
| search_hybrid(top_k=10) | <100ms for 100K vectors | HNSW + BM25 indexes |
| delete_points(100 ids) | <500ms | Less optimized than search |
| scroll_points(limit=1000) | <1s | Cursor-based, streaming |

---

## Usage Example

```python
from backend.storage.qdrant_client import QdrantStorage, QdrantPoint, SparseVector

qdrant = QdrantStorage(host="localhost", port=6333)

# Create collection
await qdrant.create_collection(
    collection_name="my_research_qdrant",
    vector_size=768,
    distance="cosine"
)

# Prepare batch of vectors with payloads
points = [
    QdrantPoint(
        id=i,
        vector=embedding_1,  # 768-dim dense vector
        sparse_vector=SparseVector(indices=[...], values=[...]),  # BM25 tokens
        payload={
            "text": "child chunk text",
            "parent_id": "uuid5_parent",
            "breadcrumb": "My Research > Document > Section 1",
            "source_file": "document.pdf",
            "page": 3,
            "chunk_index": 5,
            "doc_type": "Prose",
            "chunk_hash": "sha256...",
            "embedding_model": "all-MiniLM-L6-v2",
            "collection_name": "my_research_qdrant",
            "ingested_at": "2026-03-13T10:00:00Z"
        }
    ),
    # ... more points
]

# Upsert batch
upserted_count = await qdrant.batch_upsert(
    collection_name="my_research_qdrant",
    points=points
)

# Hybrid search
results = await qdrant.search_hybrid(
    collection_name="my_research_qdrant",
    dense_vector=query_embedding,
    sparse_vector=query_sparse,
    top_k=10,
    dense_weight=0.6,
    sparse_weight=0.4
)

# Extract parent_ids and retrieve from SQLite
parent_ids = [r.payload["parent_id"] for r in results]
parents = await db.get_parent_chunks_batch(parent_ids)
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-13 | Initial contract definition for Qdrant storage |
