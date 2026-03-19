# Storage Layer Quick Start Guide

**Feature**: Storage Architecture | **Date**: 2026-03-13 | **Target**: Backend developers

## Overview

This guide walks through the Storage Architecture layer: dual-store persistence using SQLite (metadata) + Qdrant (vectors). See [data-model.md](data-model.md) for entity details and [contracts/](contracts/) for interface specifications.

## Architecture at a Glance

```
┌─────────────────────────────────────────────────┐
│          Application Layer (Chat, Ingestion)    │
└──────────────────┬──────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
  ┌─────▼─────┐        ┌─────▼─────────┐
  │  SQLiteDB │        │ QdrantStorage │
  │ (metadata)│        │  (vectors)    │
  └─────────────────────┘
        │                    │
  ┌──────▼──────┐    ┌──────▼───────┐
  │SQLite WAL   │    │Qdrant Hybrid  │
  │- 7 tables   │    │- Dense 768d   │
  │- FK/indexes │    │- Sparse BM25  │
  └─────────────┘    └───────────────┘

Parent/Child Link: Qdrant point.payload.parent_id → SQLite parent_chunks.id
```

## Quick Setup

### 1. Initialization

```python
from backend.storage.sqlite_db import SQLiteDB
from backend.storage.qdrant_client import QdrantStorage

# SQLite (async context manager)
async with SQLiteDB("data/embedinator.db") as db:
    await db.init_schema()  # Create tables, enable WAL + FKs
    # Ready to use

# Qdrant (manual connection)
qdrant = QdrantStorage(host="localhost", port=6333)
await qdrant.health_check()  # Verify connection
```

### 2. Collections & Documents

```python
import uuid

# Create a collection
collection_id = str(uuid.uuid4())
await db.create_collection(
    id=collection_id,
    name="my-research",
    description="Internal research documents",
    embedding_model="all-MiniLM-L6-v2",
    chunk_profile="default",
    qdrant_collection_name="my_research_qdrant"
)

# Create Qdrant collection (mirrors SQLite collection)
await qdrant.create_collection(
    collection_name="my_research_qdrant",
    vector_size=768,
    distance="cosine"
)

# Create document
doc_id = str(uuid.uuid4())
await db.create_document(
    id=doc_id,
    collection_id=collection_id,
    filename="report.pdf",
    file_path="/path/to/report.pdf",
    file_hash="abc123...",  # SHA256
    status="pending"
)
```

### 3. Ingestion: Store Parent Chunks

Parent chunks are 2000–4000 character segments with deterministic UUID5 IDs (content-based). Ideal for LLM retrieval.

```python
import json
import uuid
from uuid import uuid5, NAMESPACE_DNS

# During document chunking:
parent_text = """
  Full context text for this chunk (2000-4000 characters).
  Contains complete sentences/paragraphs for LLM use.
  ...
"""

# Generate deterministic UUID5 (same text = same ID)
parent_id = uuid5(
    NAMESPACE_DNS,
    f"{collection_id}:{document_id}:{parent_text}".encode()
)

# Store parent chunk in SQLite
await db.create_parent_chunk(
    id=str(parent_id),
    collection_id=collection_id,
    document_id=doc_id,
    text=parent_text,
    metadata_json=json.dumps({
        "page": 3,
        "section": "Introduction",
        "breadcrumb": "My Research > Report > Introduction",
        "source_file": "report.pdf"
    })
)
```

### 4. Ingestion: Store Child Vectors in Qdrant

Child chunks are ~300 character segments, embedded into vectors. Stored in Qdrant with parent_id payload for linking back.

```python
import uuid
from sentence_transformers import SentenceTransformer

# Embed all child chunks for this parent
model = SentenceTransformer("all-MiniLM-L6-v2")

child_chunks = [
    "First 300-char segment from parent...",
    "Second 300-char segment from parent...",
    # ...
]

# Generate embeddings
embeddings = model.encode(child_chunks)

# Prepare Qdrant points
from backend.storage.qdrant_client import QdrantPoint

points = []
for i, (child_text, embedding) in enumerate(zip(child_chunks, embeddings)):
    point = QdrantPoint(
        id=int(uuid.uuid4().int % (2**31)),  # 32-bit positive int
        vector=embedding.tolist(),
        payload={
            "text": child_text,
            "parent_id": str(parent_id),  # Link to SQLite
            "breadcrumb": "My Research > Report > Introduction",
            "source_file": "report.pdf",
            "page": 3,
            "chunk_index": i,
            "doc_type": "Prose",  # or "Code"
            "chunk_hash": "sha256_of_child_text",
            "embedding_model": "all-MiniLM-L6-v2",
            "collection_name": "my_research_qdrant",
            "ingested_at": "2026-03-13T10:00:00Z"
        }
    )
    points.append(point)

# Upsert batch to Qdrant
upserted = await qdrant.batch_upsert(
    collection_name="my_research_qdrant",
    points=points
)
print(f"Upserted {upserted} vectors")
```

### 5. Search: Retrieve Top-K Vectors

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")

# User query
user_query = "What is the research methodology?"

# Embed query
query_embedding = model.encode(user_query).tolist()

# Hybrid search (dense + BM25)
search_results = await qdrant.search_hybrid(
    collection_name="my_research_qdrant",
    dense_vector=query_embedding,
    sparse_vector=None,  # App can compute BM25 if needed
    top_k=10,
    dense_weight=0.6,
    sparse_weight=0.4
)

# Results include parent_id in payload
for result in search_results:
    parent_id = result.payload["parent_id"]
    score = result.score
    child_text = result.payload["text"]
    print(f"Score: {score:.2f}, Parent: {parent_id}, Text: {child_text[:50]}...")
```

### 6. Retrieval: Get Parent Chunks from SQLite

```python
# Extract parent IDs from search results
parent_ids = [r.payload["parent_id"] for r in search_results]

# Batch retrieve from SQLite
parents = await db.get_parent_chunks_batch(parent_ids)

# Use full parent text in LLM context
for parent in parents:
    print(f"Parent ID: {parent['parent_id']}")
    print(f"Collection: {parent['collection']}")
    print(f"Text:\n{parent['text']}\n")
    # Pass parent['text'] to LLM for answer generation
```

### 7. Observability: Record Query Trace

```python
import json
from datetime import datetime

# After completing a chat query
await db.create_query_trace(
    id=str(uuid.uuid4()),
    session_id=user_session_id,
    query=user_query,
    sub_questions_json=json.dumps(["sub_q1", "sub_q2"]),  # or None
    collections_searched=json.dumps([collection_id]),
    chunks_retrieved_json=json.dumps([
        {"parent_id": pid, "score": score} for pid, score in zip(parent_ids, scores)
    ]),
    latency_ms=int(elapsed_time * 1000),
    llm_model="ollama-mistral",
    embed_model="all-MiniLM-L6-v2",
    confidence_score=0.87,  # 5-signal aggregation (0.0–1.0)
    meta_reasoning_triggered=False
)
```

### 8. API Key Management

```python
from backend.providers.key_manager import KeyManager

km = KeyManager()  # Loads key from EMBEDINATOR_SECRET_KEY env var

# Encrypt API key before storing
plaintext_key = "sk-proj-1234567890abcdef"
ciphertext = km.encrypt(plaintext_key)

# Store in database
await db.create_provider(
    name="openai",
    api_key_encrypted=ciphertext,
    base_url=None,
    is_active=True
)

# Later: Retrieve and decrypt
provider = await db.get_provider("openai")
plaintext_key = km.decrypt(provider["api_key_encrypted"])
# Use plaintext_key for API request
# Key cleared from memory when scope ends
```

---

## Key Patterns

### Idempotent Resume

Parent chunks use deterministic UUID5 IDs, enabling safe re-runs on failure:

```python
# First run: Create parent chunk
await db.create_parent_chunk(
    id=str(parent_id),  # UUID5, deterministic
    collection_id=collection_id,
    document_id=doc_id,
    text=parent_text,
    ...
)

# Ingestion fails, then retries
# Second run: Same parent_id → PRIMARY KEY constraint rejects duplicate
# No rollback needed; idempotent upsert replaces in Qdrant
```

### Batch Operations

Batch operations are faster and transactional:

```python
# Retrieve multiple parents at once
parent_ids = [id1, id2, id3, ...]
parents = await db.get_parent_chunks_batch(parent_ids)  # Single query, <10ms

# Upsert 1000 vectors atomically
upserted = await qdrant.batch_upsert(
    collection_name=coll_name,
    points=big_point_list
)
```

### Sequential Queuing

Single-threaded orchestrator processes documents one at a time:

```python
# In ingestion pipeline (orchestrator)
for document_id in document_queue:
    try:
        # Process document (chunking, embedding, storage)
        await ingest_document(document_id)
    except Exception as e:
        # Log failure, mark job as failed
        await db.update_ingestion_job(job_id, status="failed", error_msg=str(e))
        # Continue to next document (don't block queue)
```

### Error Handling

```python
import sqlite3
from qdrant_client.http.exceptions import QdrantError

# SQLite errors
try:
    await db.create_document(...)
except sqlite3.IntegrityError:
    # Unique constraint violation (duplicate file)
    # Handle gracefully (mark as duplicate, continue)
    pass

# Qdrant errors
try:
    await qdrant.batch_upsert(...)
except QdrantError as e:
    # Network error, timeout
    # Log, fail entire batch, let orchestrator retry when Qdrant recovers
    logger.error(f"Qdrant unavailable: {e}")
    raise
```

---

## Configuration

### Environment Variables

```bash
# SQLite (optional, defaults to data/embedinator.db)
# EMBEDINATOR_DB_PATH="data/embedinator.db"

# Qdrant service location
# QDRANT_HOST="localhost"
# QDRANT_PORT=6333

# Encryption key (required for API key storage)
export EMBEDINATOR_SECRET_KEY="base64-encoded-secret"

# LLM provider keys (encrypted in storage)
# export OPENAI_API_KEY="..." (NOT stored in DB, used at request time if no DB record)
```

### Settings Table

```python
# Store configurable settings in SQLite
await db.set_setting("max_ingestion_batch_size", "100")
await db.set_setting("qdrant_timeout_ms", "5000")
await db.set_setting("confidence_threshold", "60")
```

---

## Testing

Use external test runner (never pytest inside Claude Code):

```bash
# Run storage layer tests
zsh scripts/run-tests-external.sh -n storage-tests tests/unit/test_sqlite_db.py
zsh scripts/run-tests-external.sh -n storage-integration tests/integration/test_storage_integration.py

# Monitor progress
cat Docs/Tests/storage-tests.status
cat Docs/Tests/storage-integration.summary
```

See [contracts/](contracts/) for unit test examples.

---

## Performance Tips

1. **Batch operations**: Retrieve/insert multiple items at once
2. **Index usage**: Ensure queries use indexed columns (collection_id, document_id, parent_id)
3. **WAL mode**: Concurrent readers don't block writers
4. **Qdrant hybrid search**: Tune dense_weight/sparse_weight per collection type
5. **Connection pooling**: Reuse SQLite connection via context manager

---

## Troubleshooting

### SQLite Lock Error

```
sqlite3.OperationalError: database is locked
```

**Cause**: Multiple writers. **Solution**: Ensure single-threaded orchestrator only.

### Qdrant Connection Refused

```
QdrantError: Connection refused
```

**Cause**: Qdrant service not running. **Solution**: Start Qdrant service (`docker compose up qdrant`).

### Parent ID Mismatch

Search returns parent_id that doesn't exist in SQLite. **Cause**: Qdrant and SQLite out of sync. **Solution**: Validate referential integrity (see integration tests).

### Decryption Failure

```
cryptography.InvalidToken: Failed to decrypt provider key
```

**Cause**: Wrong encryption key or corrupted ciphertext. **Solution**: Verify EMBEDINATOR_SECRET_KEY, re-encrypt provider keys.

---

## Related Docs

- [spec.md](spec.md) — Feature specification and user stories
- [data-model.md](data-model.md) — 7 entities, relationships, validation rules
- [contracts/sqlite-contract.md](contracts/sqlite-contract.md) — SQLiteDB interface
- [contracts/qdrant-contract.md](contracts/qdrant-contract.md) — QdrantStorage interface
- [contracts/key-manager-contract.md](contracts/key-manager-contract.md) — KeyManager encryption
- [plan.md](plan.md) — Implementation planning and Agent Teams structure
- [CLAUDE.md](../../CLAUDE.md) — Project development guidelines

---

## Next Steps

1. Implement backend/storage/ modules (SQLiteDB, QdrantStorage, KeyManager)
2. Write unit tests in tests/unit/
3. Write integration tests in tests/integration/
4. Connect to Spec 06 (Ingestion Pipeline) for document processing
5. Connect to Spec 08 (REST API) for external access

**Start with `spec-07-tasks.md` for implementation task breakdown.**
