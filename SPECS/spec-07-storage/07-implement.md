# Spec 07: Storage Architecture -- Implementation Context

## Implementation Scope

### Files to Create
- `backend/storage/sqlite_db.py` -- SQLiteDB class with async connection and all table operations
- `backend/storage/qdrant_client.py` -- QdrantStorage class with collection management and hybrid search
- `backend/storage/parent_store.py` -- ParentStore convenience layer for parent chunk operations
- `backend/providers/key_manager.py` -- Fernet-based API key encryption/decryption

### Files to Modify
- `backend/config.py` -- Add storage-related configuration fields
- `backend/main.py` -- Initialize storage on app startup (lifespan)

## Code Specifications

### SQLiteDB (backend/storage/sqlite_db.py)

```python
import aiosqlite
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS collections (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    description TEXT,
    embedding_model     TEXT NOT NULL DEFAULT 'nomic-embed-text',
    chunk_profile       TEXT NOT NULL DEFAULT 'default',
    qdrant_collection_name  TEXT NOT NULL UNIQUE,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id              TEXT PRIMARY KEY,
    collection_id   TEXT NOT NULL REFERENCES collections(id),
    filename        TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    file_hash       TEXT NOT NULL,
    status          TEXT NOT NULL,
    chunk_count     INTEGER DEFAULT 0,
    ingested_at     TEXT,
    UNIQUE(collection_id, file_hash)
);

CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id              TEXT PRIMARY KEY,
    document_id     TEXT NOT NULL REFERENCES documents(id),
    status          TEXT NOT NULL,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    error_msg       TEXT,
    chunks_processed INTEGER DEFAULT 0,
    chunks_skipped  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS parent_chunks (
    id              TEXT PRIMARY KEY,
    collection_id   TEXT NOT NULL REFERENCES collections(id),
    document_id     TEXT NOT NULL REFERENCES documents(id),
    text            TEXT NOT NULL,
    metadata_json   TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_parent_chunks_collection ON parent_chunks(collection_id);
CREATE INDEX IF NOT EXISTS idx_parent_chunks_document ON parent_chunks(document_id);

CREATE TABLE IF NOT EXISTS query_traces (
    id                      TEXT PRIMARY KEY,
    session_id              TEXT NOT NULL,
    query                   TEXT NOT NULL,
    sub_questions_json      TEXT,
    collections_searched    TEXT,
    chunks_retrieved_json   TEXT,
    meta_reasoning_triggered INTEGER DEFAULT 0,
    latency_ms              INTEGER,
    llm_model               TEXT,
    embed_model             TEXT,
    confidence_score        REAL,
    created_at              TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_traces_session ON query_traces(session_id);
CREATE INDEX IF NOT EXISTS idx_traces_created ON query_traces(created_at);

CREATE TABLE IF NOT EXISTS settings (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS providers (
    name       TEXT PRIMARY KEY,
    api_key_encrypted TEXT,
    base_url   TEXT,
    is_active  INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

class SQLiteDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db: Optional[aiosqlite.Connection] = None

    async def connect(self):
        self.db = await aiosqlite.connect(self.db_path)
        self.db.row_factory = aiosqlite.Row
        await self.db.execute("PRAGMA journal_mode=WAL")
        await self.db.execute("PRAGMA foreign_keys=ON")
        await self._init_schema()

    async def _init_schema(self):
        await self.db.executescript(SCHEMA_SQL)
        await self.db.commit()

    async def close(self):
        if self.db:
            await self.db.close()

    # --- Collections ---

    async def create_collection(
        self, name: str, description: str | None,
        embedding_model: str, chunk_profile: str,
        qdrant_collection_name: str,
    ) -> dict:
        coll_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute(
            """INSERT INTO collections (id, name, description, embedding_model,
               chunk_profile, qdrant_collection_name, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (coll_id, name, description, embedding_model, chunk_profile,
             qdrant_collection_name, now),
        )
        await self.db.commit()
        return {"id": coll_id, "name": name, "created_at": now}

    async def list_collections(self) -> list[dict]:
        cursor = await self.db.execute("SELECT * FROM collections ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_collection(self, collection_id: str) -> dict | None:
        cursor = await self.db.execute("SELECT * FROM collections WHERE id = ?", (collection_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def delete_collection(self, collection_id: str) -> bool:
        cursor = await self.db.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
        await self.db.commit()
        return cursor.rowcount > 0

    # --- Documents ---

    async def create_document(
        self, collection_id: str, filename: str, file_path: str,
        file_hash: str, status: str = "pending", doc_id: str | None = None,
    ) -> str:
        doc_id = doc_id or str(uuid.uuid4())
        await self.db.execute(
            """INSERT INTO documents (id, collection_id, filename, file_path, file_hash, status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (doc_id, collection_id, filename, file_path, file_hash, status),
        )
        await self.db.commit()
        return doc_id

    async def get_document_by_hash(self, collection_id: str, file_hash: str) -> dict | None:
        cursor = await self.db.execute(
            "SELECT * FROM documents WHERE collection_id = ? AND file_hash = ?",
            (collection_id, file_hash),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def update_document(self, doc_id: str, **kwargs) -> None:
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [doc_id]
        await self.db.execute(f"UPDATE documents SET {sets} WHERE id = ?", values)
        await self.db.commit()

    async def list_documents(self, collection_id: str) -> list[dict]:
        cursor = await self.db.execute(
            "SELECT * FROM documents WHERE collection_id = ? ORDER BY ingested_at DESC",
            (collection_id,),
        )
        return [dict(row) for row in await cursor.fetchall()]

    # --- Ingestion Jobs ---

    async def create_ingestion_job(self, job_id: str, document_id: str, status: str = "started") -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute(
            "INSERT INTO ingestion_jobs (id, document_id, status, started_at) VALUES (?, ?, ?, ?)",
            (job_id, document_id, status, now),
        )
        await self.db.commit()

    async def update_ingestion_job(self, job_id: str, **kwargs) -> None:
        if "status" in kwargs and kwargs["status"] in ("completed", "failed"):
            kwargs["finished_at"] = datetime.now(timezone.utc).isoformat()
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [job_id]
        await self.db.execute(f"UPDATE ingestion_jobs SET {sets} WHERE id = ?", values)
        await self.db.commit()

    async def get_ingestion_job(self, job_id: str) -> dict | None:
        cursor = await self.db.execute("SELECT * FROM ingestion_jobs WHERE id = ?", (job_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    # --- Parent Chunks ---

    async def insert_parent_chunks(self, collection_id: str, document_id: str, parents: list[dict]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        rows = [
            (p["id"], collection_id, document_id, p["text"], json.dumps(p["metadata"]), now)
            for p in parents
        ]
        await self.db.executemany(
            "INSERT OR REPLACE INTO parent_chunks (id, collection_id, document_id, text, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        await self.db.commit()

    async def get_parent_by_id(self, parent_id: str) -> dict | None:
        cursor = await self.db.execute("SELECT * FROM parent_chunks WHERE id = ?", (parent_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_parents_by_ids(self, parent_ids: list[str]) -> list[dict]:
        placeholders = ",".join("?" * len(parent_ids))
        cursor = await self.db.execute(
            f"SELECT * FROM parent_chunks WHERE id IN ({placeholders})", parent_ids,
        )
        return [dict(row) for row in await cursor.fetchall()]

    # --- Query Traces ---

    async def insert_query_trace(self, trace: dict) -> None:
        await self.db.execute(
            """INSERT INTO query_traces (id, session_id, query, sub_questions_json,
               collections_searched, chunks_retrieved_json, meta_reasoning_triggered,
               latency_ms, llm_model, embed_model, confidence_score, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (trace["id"], trace["session_id"], trace["query"],
             json.dumps(trace.get("sub_questions")),
             json.dumps(trace.get("collections_searched")),
             json.dumps(trace.get("chunks_retrieved")),
             1 if trace.get("meta_reasoning_triggered") else 0,
             trace.get("latency_ms"), trace.get("llm_model"),
             trace.get("embed_model"), trace.get("confidence_score"),
             trace["created_at"]),
        )
        await self.db.commit()

    async def list_query_traces(self, page: int = 1, limit: int = 50, session_id: str | None = None) -> list[dict]:
        offset = (page - 1) * limit
        if session_id:
            cursor = await self.db.execute(
                "SELECT * FROM query_traces WHERE session_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (session_id, limit, offset),
            )
        else:
            cursor = await self.db.execute(
                "SELECT * FROM query_traces ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        return [dict(row) for row in await cursor.fetchall()]

    # --- Providers ---

    async def get_providers(self) -> list[dict]:
        cursor = await self.db.execute("SELECT * FROM providers")
        return [dict(row) for row in await cursor.fetchall()]

    async def upsert_provider_key(self, name: str, encrypted_key: str) -> None:
        await self.db.execute(
            """INSERT INTO providers (name, api_key_encrypted, is_active)
               VALUES (?, ?, 1) ON CONFLICT(name) DO UPDATE SET
               api_key_encrypted = excluded.api_key_encrypted, is_active = 1""",
            (name, encrypted_key),
        )
        await self.db.commit()

    async def delete_provider_key(self, name: str) -> bool:
        cursor = await self.db.execute(
            "UPDATE providers SET api_key_encrypted = NULL, is_active = 0 WHERE name = ?",
            (name,),
        )
        await self.db.commit()
        return cursor.rowcount > 0

    # --- Settings ---

    async def get_setting(self, key: str) -> str | None:
        cursor = await self.db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row["value"] if row else None

    async def set_setting(self, key: str, value: str) -> None:
        await self.db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
        await self.db.commit()
```

### QdrantStorage (backend/storage/qdrant_client.py)

```python
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, SparseVectorParams, Distance,
    BM25Modifier, PointStruct, Filter, FieldCondition, MatchValue,
)
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

class QdrantStorage:
    def __init__(self, host: str, port: int):
        self.client = QdrantClient(host=host, port=port)
        self.circuit_breaker = CircuitBreaker()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=1, max=10, jitter=0.5), reraise=True)
    async def create_collection(self, collection_name: str, dense_dim: int) -> None:
        await self.client.create_collection(
            collection_name=collection_name,
            vectors_config={
                "dense": VectorParams(size=dense_dim, distance=Distance.COSINE),
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams(modifier=BM25Modifier.IDF),
            },
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=1, max=10, jitter=0.5), reraise=True)
    async def batch_upsert(self, collection_name: str, children: list[dict], batch_size: int = 50) -> None:
        points = []
        for child in children:
            point = PointStruct(
                id=child["point_id"],
                vector={
                    "dense": child["embedding"],
                },
                payload={
                    "text": child["text"],
                    "parent_id": child["parent_id"],
                    "breadcrumb": child["breadcrumb"],
                    "source_file": child["source_file"],
                    "page": child["page"],
                    "chunk_index": child["chunk_index"],
                    "doc_type": child["doc_type"],
                    "chunk_hash": child.get("chunk_hash", ""),
                    "embedding_model": child.get("embedding_model", ""),
                    "collection_name": child.get("collection_name", ""),
                    "ingested_at": child.get("ingested_at", ""),
                },
            )
            points.append(point)

        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            await self.client.upsert(collection_name=collection_name, points=batch)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=1, max=10, jitter=0.5), reraise=True)
    async def delete_by_source(self, collection_name: str, source_file: str) -> None:
        await self.client.delete(
            collection_name=collection_name,
            points_selector=Filter(
                must=[FieldCondition(key="source_file", match=MatchValue(value=source_file))]
            ),
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=1, max=10, jitter=0.5), reraise=True)
    async def delete_collection(self, collection_name: str) -> None:
        await self.client.delete_collection(collection_name=collection_name)

    async def health_check(self) -> dict:
        try:
            info = await self.client.get_collections()
            return {"status": "ok"}
        except Exception:
            return {"status": "error"}
```

### Key Manager (backend/providers/key_manager.py)

```python
from cryptography.fernet import Fernet

class KeyManager:
    def __init__(self, secret: str):
        if not secret:
            self._key = Fernet.generate_key()
        else:
            self._key = secret.encode() if isinstance(secret, str) else secret
        self.fernet = Fernet(self._key)

    @property
    def secret_str(self) -> str:
        return self._key.decode() if isinstance(self._key, bytes) else self._key

    def encrypt(self, plaintext: str) -> str:
        return self.fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self.fernet.decrypt(ciphertext.encode()).decode()
```

## Configuration

Relevant fields in `backend/config.py` `Settings` class:

```python
# Qdrant
qdrant_host: str = "localhost"
qdrant_port: int = 6333

# SQLite
sqlite_path: str = "data/embedinator.db"

# Security
api_key_encryption_secret: str = ""  # auto-generated on first run if empty
```

## Error Handling

- **SQLite connection failure**: Log error and raise on startup. The app cannot function without SQLite.
- **SQLite schema migration conflicts**: Use CREATE TABLE IF NOT EXISTS for idempotency. Future migrations can use a version number in the `settings` table.
- **Qdrant connection failure**: Log warning on startup. QdrantStorage methods have circuit breaker protection. Health check returns `{"status": "error"}`.
- **Qdrant collection already exists**: Handle gracefully in `create_collection()` -- check if collection exists first, return without error if it does.
- **Fernet decryption failure** (wrong key): Raise `ValueError` with clear message. This happens if the encryption secret changed between restarts.
- **Foreign key violation**: SQLite raises `IntegrityError`. Catch and return appropriate HTTP error through the API layer.

## Testing Requirements

### Unit Tests
- `test_sqlite_init_schema`: Verify all tables are created on connection.
- `test_sqlite_collections_crud`: Create, list, get, delete collections.
- `test_sqlite_documents_crud`: Create, list, get by hash, update status.
- `test_sqlite_ingestion_jobs`: Create, update status, get.
- `test_sqlite_parent_chunks`: Batch insert, get by id, get by ids.
- `test_sqlite_query_traces`: Insert, list with pagination, list by session_id.
- `test_sqlite_providers`: Upsert key, get providers, delete key.
- `test_sqlite_settings`: Set, get, update settings.
- `test_sqlite_foreign_keys`: Verify FK enforcement (e.g., inserting a document with invalid collection_id fails).
- `test_sqlite_unique_constraints`: Verify UNIQUE(collection_id, file_hash) on documents.
- `test_key_manager_encrypt_decrypt`: Round-trip encryption/decryption.
- `test_key_manager_auto_generate`: Verify key auto-generation when secret is empty.
- `test_qdrant_create_collection`: Verify dense + sparse config.
- `test_qdrant_batch_upsert`: Verify points are stored with correct payload.
- `test_qdrant_delete_by_source`: Verify points are removed by source_file filter.

### Integration Tests
- `test_storage_round_trip`: Create collection, ingest document, verify Qdrant points and SQLite parent_chunks, search, verify results.
- `test_wal_concurrent_reads`: Verify multiple concurrent reads succeed while a write is in progress.

## Done Criteria

- [ ] SQLiteDB class connects, creates all 7 tables with correct schema, and runs with WAL + foreign_keys PRAGMAs
- [ ] All CRUD methods for collections, documents, ingestion_jobs, parent_chunks, query_traces, settings, providers are implemented
- [ ] QdrantStorage creates collections with both dense and sparse vector configurations
- [ ] QdrantStorage batch_upsert stores points with complete payload schema
- [ ] QdrantStorage delete_by_source removes points by source_file filter
- [ ] All Qdrant methods have @retry decorators with exponential backoff
- [ ] KeyManager encrypts and decrypts API keys using Fernet
- [ ] KeyManager auto-generates encryption secret when none is configured
- [ ] Indexes exist on parent_chunks(collection_id), parent_chunks(document_id), query_traces(session_id), query_traces(created_at)
- [ ] UNIQUE(collection_id, file_hash) constraint enforced on documents table
- [ ] Storage is initialized in app startup (lifespan)
- [ ] Unit tests pass for all CRUD operations and key management
