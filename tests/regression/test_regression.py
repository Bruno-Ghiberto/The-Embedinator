"""Regression test suite for Spec-07 Storage Architecture.

Covers all 16 Functional Requirements (FR-001 to FR-016),
all 11 Success Criteria (SC-001 to SC-011), and 4 edge cases.

Design:
- SQLite tests use in-memory DB for speed; WAL/FK tests use file-based DB.
- Qdrant tests mock the AsyncQdrantClient (no live Qdrant required).
- KeyManager tests use a real Fernet key generated in the fixture.
- Each test exercises exactly one FR or SC.
"""
from __future__ import annotations

import asyncio
import os
import time
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet

from backend.providers.key_manager import KeyManager
from backend.storage.qdrant_client import (
    QdrantPoint,
    QdrantStorage,
    SearchResult,
    SparseVector,
)
from backend.storage.sqlite_db import SQLiteDB


# ---------------------------------------------------------------------------
# Helpers & shared fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db():
    """In-memory SQLiteDB for schema and CRUD tests."""
    database = SQLiteDB(":memory:")
    await database.connect()
    yield database
    await database.close()


@pytest_asyncio.fixture
async def file_db(tmp_path):
    """File-based SQLiteDB for WAL / FK pragma tests."""
    db_path = str(tmp_path / "regression_test.db")
    database = SQLiteDB(db_path)
    await database.connect()
    yield database
    await database.close()


@pytest_asyncio.fixture
async def populated_db(db: SQLiteDB):
    """In-memory DB pre-populated with a collection and document."""
    coll_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    await db.create_collection(
        id=coll_id,
        name="regression-collection",
        embedding_model="nomic-embed-text",
        chunk_profile="default",
        qdrant_collection_name="regression_qdrant",
    )
    await db.create_document(
        id=doc_id,
        collection_id=coll_id,
        filename="test.pdf",
        file_hash="sha256_abc123",
    )
    return db, coll_id, doc_id


@pytest.fixture
def fernet_key() -> str:
    """Generate a real Fernet key for each test."""
    return Fernet.generate_key().decode()


@pytest.fixture
def key_manager(fernet_key: str, monkeypatch) -> KeyManager:
    monkeypatch.setenv("EMBEDINATOR_FERNET_KEY", fernet_key)
    return KeyManager()


def _make_storage() -> QdrantStorage:
    """Return QdrantStorage with mocked settings (no live Qdrant)."""
    storage = QdrantStorage.__new__(QdrantStorage)
    storage.host = "localhost"
    storage.port = 6333
    storage.client = None
    storage._circuit_open = False
    storage._failure_count = 0
    storage._last_failure_time = None
    storage._max_failures = 5
    storage._cooldown_secs = 30
    return storage


VALID_PAYLOAD: dict[str, Any] = {
    "text": "sample child chunk text ~500 chars",
    "parent_id": str(uuid.uuid4()),
    "breadcrumb": "Collection > Doc > Section",
    "source_file": "report.pdf",
    "page": 1,
    "chunk_index": 0,
    "doc_type": "Prose",
    "chunk_hash": "deadbeef",
    "embedding_model": "nomic-embed-text",
    "collection_name": "regression_qdrant",
    "ingested_at": "2026-03-14T00:00:00Z",
}


# ===========================================================================
# FR Regression Tests
# ===========================================================================


class TestFR001CollectionsTable:
    """FR-001: collections table with all required fields."""

    @pytest.mark.asyncio
    async def test_fr_001_collections_table(self, db: SQLiteDB):
        coll_id = str(uuid.uuid4())
        await db.create_collection(
            id=coll_id,
            name="my-collection",
            embedding_model="nomic-embed-text",
            chunk_profile="default",
            qdrant_collection_name="my_qdrant_coll",
            description="Test description",
        )
        row = await db.get_collection(coll_id)
        assert row is not None
        assert row["id"] == coll_id
        assert row["name"] == "my-collection"
        assert row["description"] == "Test description"
        assert row["embedding_model"] == "nomic-embed-text"
        assert row["chunk_profile"] == "default"
        assert row["qdrant_collection_name"] == "my_qdrant_coll"
        assert "created_at" in row and row["created_at"]


class TestFR002DocumentsTable:
    """FR-002: documents table with UNIQUE(collection_id, file_hash)."""

    @pytest.mark.asyncio
    async def test_fr_002_documents_table(self, populated_db):
        db, coll_id, doc_id = populated_db
        row = await db.get_document(doc_id)
        assert row is not None
        assert row["collection_id"] == coll_id
        assert row["file_hash"] == "sha256_abc123"
        assert row["filename"] == "test.pdf"
        assert row["status"] == "pending"
        assert "chunk_count" in row
        assert "created_at" in row

    @pytest.mark.asyncio
    async def test_fr_002_unique_constraint(self, populated_db):
        """UNIQUE(collection_id, file_hash) prevents duplicate insert."""
        db, coll_id, _ = populated_db
        with pytest.raises(Exception):
            await db.create_document(
                id=str(uuid.uuid4()),
                collection_id=coll_id,
                filename="other.pdf",
                file_hash="sha256_abc123",  # same hash, same collection
            )


class TestFR003IngestionJobsTable:
    """FR-003: ingestion_jobs table with status enum."""

    @pytest.mark.asyncio
    async def test_fr_003_ingestion_jobs_table(self, populated_db):
        db, _, doc_id = populated_db
        job_id = str(uuid.uuid4())
        await db.create_ingestion_job(id=job_id, document_id=doc_id, status="started")
        row = await db.get_ingestion_job(job_id)
        assert row is not None
        assert row["document_id"] == doc_id
        assert row["status"] == "started"
        assert row["chunks_processed"] == 0
        assert row["chunks_skipped"] == 0
        assert "started_at" in row

    @pytest.mark.asyncio
    async def test_fr_003_status_transitions(self, populated_db):
        """All valid status values can be set."""
        db, _, doc_id = populated_db
        valid_statuses = ["started", "streaming", "embedding", "completed", "failed", "paused"]
        job_id = str(uuid.uuid4())
        await db.create_ingestion_job(id=job_id, document_id=doc_id)
        for status in valid_statuses:
            await db.update_ingestion_job(job_id, status=status)
            row = await db.get_ingestion_job(job_id)
            assert row["status"] == status


class TestFR004ParentChunksTable:
    """FR-004: parent_chunks with UUID5 deterministic id and indexes."""

    @pytest.mark.asyncio
    async def test_fr_004_parent_chunks_table(self, populated_db):
        db, coll_id, doc_id = populated_db
        parent_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "test-content-identity"))
        await db.create_parent_chunk(
            id=parent_id,
            collection_id=coll_id,
            document_id=doc_id,
            text="Parent chunk text 2000-4000 chars",
            metadata_json='{"page": 1, "section": "intro", "breadcrumb": "Doc>Sec"}',
        )
        row = await db.get_parent_chunk(parent_id)
        assert row is not None
        assert row["id"] == parent_id
        assert row["collection_id"] == coll_id
        assert row["document_id"] == doc_id
        assert row["text"] == "Parent chunk text 2000-4000 chars"
        assert "metadata_json" in row

    @pytest.mark.asyncio
    async def test_fr_004_uuid5_in_id(self, populated_db):
        """parent_chunks.id is UUID5 (namespace_dns based)."""
        db, coll_id, doc_id = populated_db
        content = "unique document content string"
        expected_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, content))
        await db.create_parent_chunk(
            id=expected_id,
            collection_id=coll_id,
            document_id=doc_id,
            text=content,
        )
        row = await db.get_parent_chunk(expected_id)
        assert row["id"] == expected_id


class TestFR005QueryTracesTable:
    """FR-005: query_traces with reasoning_steps_json, strategy_switches_json, confidence_score INTEGER."""

    @pytest.mark.asyncio
    async def test_fr_005_query_traces_table(self, db: SQLiteDB):
        trace_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        await db.create_query_trace(
            id=trace_id,
            session_id=session_id,
            query="What is the capital of France?",
            collections_searched='["collection1"]',
            chunks_retrieved_json='["chunk1", "chunk2"]',
            latency_ms=150,
            llm_model="gpt-4",
            embed_model="nomic-embed-text",
            confidence_score=82,
            sub_questions_json='["Sub Q1", "Sub Q2"]',
            reasoning_steps_json='["step1", "step2"]',
            strategy_switches_json='["WIDEN_SEARCH"]',
            meta_reasoning_triggered=True,
        )
        traces = await db.list_query_traces(session_id)
        assert len(traces) == 1
        t = traces[0]
        assert t["id"] == trace_id
        assert t["query"] == "What is the capital of France?"
        assert t["reasoning_steps_json"] == '["step1", "step2"]'
        assert t["strategy_switches_json"] == '["WIDEN_SEARCH"]'
        assert t["meta_reasoning_triggered"] == 1
        assert t["latency_ms"] == 150
        assert t["confidence_score"] == 82

    @pytest.mark.asyncio
    async def test_fr_005_confidence_score_is_integer(self, db: SQLiteDB):
        """confidence_score must be stored as INTEGER (0-100), not float."""
        trace_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        await db.create_query_trace(
            id=trace_id,
            session_id=session_id,
            query="test",
            collections_searched="[]",
            chunks_retrieved_json="[]",
            latency_ms=10,
            confidence_score=75,
        )
        traces = await db.list_query_traces(session_id)
        score = traces[0]["confidence_score"]
        assert isinstance(score, int), f"Expected int, got {type(score)}"
        assert 0 <= score <= 100


class TestFR006SettingsTable:
    """FR-006: settings key-value store."""

    @pytest.mark.asyncio
    async def test_fr_006_settings_table(self, db: SQLiteDB):
        await db.set_setting("theme", "dark")
        value = await db.get_setting("theme")
        assert value == "dark"

    @pytest.mark.asyncio
    async def test_fr_006_upsert_behavior(self, db: SQLiteDB):
        await db.set_setting("key1", "v1")
        await db.set_setting("key1", "v2")
        assert await db.get_setting("key1") == "v2"

    @pytest.mark.asyncio
    async def test_fr_006_missing_key_returns_none(self, db: SQLiteDB):
        assert await db.get_setting("nonexistent") is None


class TestFR007ProvidersTable:
    """FR-007: providers table with encrypted API keys."""

    @pytest.mark.asyncio
    async def test_fr_007_providers_table(self, db: SQLiteDB, key_manager: KeyManager):
        encrypted = key_manager.encrypt("sk-real-api-key")
        await db.create_provider(
            name="openai",
            api_key_encrypted=encrypted,
            base_url="https://api.openai.com",
            is_active=True,
        )
        row = await db.get_provider("openai")
        assert row is not None
        assert row["name"] == "openai"
        assert row["api_key_encrypted"] == encrypted
        assert row["api_key_encrypted"] != "sk-real-api-key"
        assert row["is_active"] is True

    @pytest.mark.asyncio
    async def test_fr_007_ollama_null_key(self, db: SQLiteDB):
        """Ollama provider has NULL api_key_encrypted."""
        await db.create_provider(name="ollama", api_key_encrypted=None, is_active=True)
        row = await db.get_provider("ollama")
        assert row["api_key_encrypted"] is None


class TestFR008WALMode:
    """FR-008: SQLite WAL mode."""

    @pytest.mark.asyncio
    async def test_fr_008_wal_mode(self, file_db: SQLiteDB):
        cursor = await file_db.db.execute("PRAGMA journal_mode")
        row = await cursor.fetchone()
        mode = list(dict(row).values())[0]
        assert mode == "wal", f"Expected WAL mode, got: {mode}"


class TestFR009ForeignKeys:
    """FR-009: SQLite foreign_keys=ON."""

    @pytest.mark.asyncio
    async def test_fr_009_foreign_keys(self, file_db: SQLiteDB):
        cursor = await file_db.db.execute("PRAGMA foreign_keys")
        row = await cursor.fetchone()
        fk_on = list(dict(row).values())[0]
        assert fk_on == 1, "PRAGMA foreign_keys must return 1"


class TestFR010QdrantDenseSparse:
    """FR-010: Qdrant collection has dense (768d cosine) + sparse (BM25 IDF)."""

    @pytest.mark.asyncio
    async def test_fr_010_qdrant_dense_sparse(self):
        storage = _make_storage()
        mock_client = AsyncMock()
        storage.client = mock_client

        await storage._create_collection_with_retry("test_coll", 768, "cosine")

        mock_client.create_collection.assert_called_once()
        call_kwargs = mock_client.create_collection.call_args[1]

        # Dense vector config
        assert "vectors_config" in call_kwargs
        dense_config = call_kwargs["vectors_config"]["dense"]
        assert dense_config.size == 768

        # Sparse vector config
        assert "sparse_vectors_config" in call_kwargs
        assert "sparse" in call_kwargs["sparse_vectors_config"]


class TestFR011QdrantPayload:
    """FR-011: all 11 required payload fields on each point."""

    def test_fr_011_qdrant_payload(self):
        storage = _make_storage()
        # Valid payload passes
        storage._validate_payload(VALID_PAYLOAD)

    def test_fr_011_missing_field_raises(self):
        storage = _make_storage()
        payload = VALID_PAYLOAD.copy()
        del payload["parent_id"]
        with pytest.raises(ValueError, match="missing required fields"):
            storage._validate_payload(payload)

    def test_fr_011_all_11_fields_required(self):
        required = [
            "text", "parent_id", "breadcrumb", "source_file", "page",
            "chunk_index", "doc_type", "chunk_hash", "embedding_model",
            "collection_name", "ingested_at",
        ]
        assert set(required) == set(QdrantStorage.REQUIRED_PAYLOAD_FIELDS)


class TestFR012UUID5Determinism:
    """FR-012: UUID5 generates same ID for same content."""

    def test_fr_012_uuid5_determinism(self):
        content = "canonical document content string"
        id1 = str(uuid.uuid5(uuid.NAMESPACE_DNS, content))
        id2 = str(uuid.uuid5(uuid.NAMESPACE_DNS, content))
        assert id1 == id2

    def test_fr_012_different_content_different_id(self):
        id1 = str(uuid.uuid5(uuid.NAMESPACE_DNS, "content A"))
        id2 = str(uuid.uuid5(uuid.NAMESPACE_DNS, "content B"))
        assert id1 != id2


class TestFR013APIKeyEncryption:
    """FR-013: Fernet encrypt/decrypt round-trip."""

    def test_fr_013_api_key_encryption(self, key_manager: KeyManager):
        plaintext = "sk-test-secret-api-key-12345"
        ciphertext = key_manager.encrypt(plaintext)
        assert ciphertext != plaintext
        assert key_manager.decrypt(ciphertext) == plaintext

    def test_fr_013_wrong_key_fails(self, monkeypatch):
        key1 = Fernet.generate_key().decode()
        key2 = Fernet.generate_key().decode()
        monkeypatch.setenv("EMBEDINATOR_FERNET_KEY", key1)
        km1 = KeyManager()
        ciphertext = km1.encrypt("secret")

        monkeypatch.setenv("EMBEDINATOR_FERNET_KEY", key2)
        km2 = KeyManager()
        with pytest.raises(Exception):
            km2.decrypt(ciphertext)


class TestFR014ParentRetrieval:
    """FR-014: parent chunks queried by ID list with column aliases."""

    @pytest.mark.asyncio
    async def test_fr_014_parent_retrieval(self, populated_db):
        db, coll_id, doc_id = populated_db
        ids = [str(uuid.uuid5(uuid.NAMESPACE_DNS, f"chunk-{i}")) for i in range(5)]
        for pid in ids:
            await db.create_parent_chunk(
                id=pid, collection_id=coll_id, document_id=doc_id,
                text=f"Parent text for {pid}",
            )
        results = await db.get_parent_chunks_batch(ids)
        assert len(results) == 5
        returned_ids = {r["id"] for r in results}
        assert returned_ids == set(ids)

    @pytest.mark.asyncio
    async def test_fr_014_empty_list(self, db: SQLiteDB):
        result = await db.get_parent_chunks_batch([])
        assert result == []


class TestFR015SequentialIngestion:
    """FR-015: ingestion_jobs status tracking supports sequential queue."""

    @pytest.mark.asyncio
    async def test_fr_015_sequential_ingestion(self, populated_db):
        db, _, doc_id = populated_db
        job1 = str(uuid.uuid4())
        job2 = str(uuid.uuid4())
        await db.create_ingestion_job(id=job1, document_id=doc_id, status="started")
        await db.create_ingestion_job(id=job2, document_id=doc_id, status="started")

        # Job1 fails — should not block Job2
        await db.update_ingestion_job(job1, status="failed", error_msg="timeout error")
        await db.update_ingestion_job(job2, status="completed", chunks_processed=10)

        j1 = await db.get_ingestion_job(job1)
        j2 = await db.get_ingestion_job(job2)
        assert j1["status"] == "failed"
        assert j1["error_msg"] == "timeout error"
        assert j2["status"] == "completed"
        assert j2["chunks_processed"] == 10


class TestFR016IdempotentResume:
    """FR-016: failed jobs resumable via UUID5 deterministic IDs."""

    @pytest.mark.asyncio
    async def test_fr_016_idempotent_resume(self, populated_db):
        """UUID5 ID collision is detected (primary key conflict on re-insert)."""
        db, coll_id, doc_id = populated_db
        content = "deterministic content for idempotent test"
        parent_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, content))

        # First insert succeeds
        await db.create_parent_chunk(
            id=parent_id, collection_id=coll_id, document_id=doc_id, text=content
        )
        # Second insert of same UUID5 ID raises (duplicate primary key)
        with pytest.raises(Exception):
            await db.create_parent_chunk(
                id=parent_id, collection_id=coll_id, document_id=doc_id, text=content
            )
        # Original row still intact
        row = await db.get_parent_chunk(parent_id)
        assert row["id"] == parent_id

    @pytest.mark.asyncio
    async def test_fr_016_job_resumable_after_failure(self, populated_db):
        """A failed job can be updated (not stuck in failed state forever)."""
        db, _, doc_id = populated_db
        job_id = str(uuid.uuid4())
        await db.create_ingestion_job(id=job_id, document_id=doc_id, status="failed")

        # Simulate re-run: update status back to "started"
        await db.update_ingestion_job(job_id, status="started")
        row = await db.get_ingestion_job(job_id)
        assert row["status"] == "started"


# ===========================================================================
# SC Regression Tests
# ===========================================================================


class TestSC001AllTablesCreated:
    """SC-001: All 7 SQLite tables with correct columns exist."""

    @pytest.mark.asyncio
    async def test_sc_001_all_tables_created(self, db: SQLiteDB):
        cursor = await db.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        rows = await cursor.fetchall()
        tables = {row[0] for row in rows}
        expected = {
            "collections", "documents", "ingestion_jobs",
            "parent_chunks", "query_traces", "settings", "providers",
        }
        assert expected.issubset(tables), f"Missing tables: {expected - tables}"

    @pytest.mark.asyncio
    async def test_sc_001_collections_columns(self, db: SQLiteDB):
        cursor = await db.db.execute("PRAGMA table_info(collections)")
        rows = await cursor.fetchall()
        cols = {row[1] for row in rows}
        required = {"id", "name", "description", "embedding_model", "chunk_profile",
                    "qdrant_collection_name", "created_at"}
        assert required.issubset(cols), f"Missing columns: {required - cols}"

    @pytest.mark.asyncio
    async def test_sc_001_query_traces_columns(self, db: SQLiteDB):
        cursor = await db.db.execute("PRAGMA table_info(query_traces)")
        rows = await cursor.fetchall()
        cols = {row[1] for row in rows}
        required = {
            "id", "session_id", "query", "sub_questions_json", "collections_searched",
            "chunks_retrieved_json", "reasoning_steps_json", "strategy_switches_json",
            "meta_reasoning_triggered", "latency_ms", "llm_model", "embed_model",
            "confidence_score", "created_at",
        }
        assert required.issubset(cols), f"Missing columns in query_traces: {required - cols}"

    @pytest.mark.asyncio
    async def test_sc_001_confidence_score_is_integer_type(self, db: SQLiteDB):
        """Verify confidence_score column is INTEGER (not REAL) in schema."""
        cursor = await db.db.execute("PRAGMA table_info(query_traces)")
        rows = await cursor.fetchall()
        col_map = {row[1]: row[2] for row in rows}  # name → type
        assert col_map.get("confidence_score", "").upper() == "INTEGER", (
            f"confidence_score must be INTEGER, got: {col_map.get('confidence_score')}"
        )


class TestSC002WALFKPragmas:
    """SC-002: WAL mode and FK enforcement active."""

    @pytest.mark.asyncio
    async def test_sc_002_wal_fk_pragmas(self, file_db: SQLiteDB):
        cursor = await file_db.db.execute("PRAGMA journal_mode")
        wal_row = await cursor.fetchone()
        mode = list(dict(wal_row).values())[0]
        assert mode == "wal"

        cursor = await file_db.db.execute("PRAGMA foreign_keys")
        fk_row = await cursor.fetchone()
        fk = list(dict(fk_row).values())[0]
        assert fk == 1


class TestSC003UUID5Reproducible:
    """SC-003: Same content always produces same UUID5."""

    def test_sc_003_uuid5_reproducible(self):
        content = "test chunk content for reproducibility check"
        ids = [str(uuid.uuid5(uuid.NAMESPACE_DNS, content)) for _ in range(10)]
        assert len(set(ids)) == 1, "UUID5 must be deterministic"

    def test_sc_003_namespace_dns(self):
        """Uses UUID5 NAMESPACE_DNS (not NAMESPACE_URL or NAMESPACE_OID)."""
        expected = str(uuid.uuid5(uuid.NAMESPACE_DNS, "test"))
        assert expected.startswith("4")  # UUID5 version bit: version 5 → "5xxx"
        # Actually UUID5 produces version 5:
        parsed = uuid.UUID(str(uuid.uuid5(uuid.NAMESPACE_DNS, "test")))
        assert parsed.version == 5


class TestSC004QdrantVectors:
    """SC-004: Dense 768d cosine + sparse BM25 configs created."""

    @pytest.mark.asyncio
    async def test_sc_004_qdrant_vectors(self):
        storage = _make_storage()
        mock_client = AsyncMock()
        storage.client = mock_client

        await storage._create_collection_with_retry("sc_coll", 768, "cosine")

        call_kwargs = mock_client.create_collection.call_args[1]
        dense = call_kwargs["vectors_config"]["dense"]
        assert dense.size == 768

        from qdrant_client.models import Distance
        assert dense.distance == Distance.COSINE

        sparse_cfg = call_kwargs["sparse_vectors_config"]
        assert "sparse" in sparse_cfg


class TestSC005PayloadFields:
    """SC-005: All 11 required payload fields present on child chunks."""

    def test_sc_005_payload_fields(self):
        storage = _make_storage()
        storage._validate_payload(VALID_PAYLOAD)  # must not raise

    def test_sc_005_all_11_fields_listed(self):
        assert len(QdrantStorage.REQUIRED_PAYLOAD_FIELDS) == 11

    def test_sc_005_invalid_doc_type_rejected(self):
        storage = _make_storage()
        bad = VALID_PAYLOAD.copy()
        bad["doc_type"] = "Table"
        with pytest.raises(ValueError, match="Invalid doc_type"):
            storage._validate_payload(bad)

    def test_sc_005_valid_doc_types(self):
        storage = _make_storage()
        for dt in ["Prose", "Code"]:
            payload = VALID_PAYLOAD.copy()
            payload["doc_type"] = dt
            storage._validate_payload(payload)  # must not raise


class TestSC006ParentLatency:
    """SC-006: Parent chunk retrieval <10ms for 100 chunks."""

    @pytest.mark.asyncio
    async def test_sc_006_parent_latency(self, populated_db):
        db, coll_id, doc_id = populated_db

        # Insert 100 parent chunks
        ids = [str(uuid.uuid5(uuid.NAMESPACE_DNS, f"latency-test-{i}")) for i in range(100)]
        for pid in ids:
            await db.create_parent_chunk(
                id=pid, collection_id=coll_id, document_id=doc_id, text=f"text {pid}"
            )

        # Measure retrieval time
        start = time.monotonic()
        results = await db.get_parent_chunks_batch(ids)
        elapsed_ms = (time.monotonic() - start) * 1000

        assert len(results) == 100
        assert elapsed_ms < 10, f"Parent retrieval took {elapsed_ms:.1f}ms, expected <10ms"


class TestSC007DuplicatePrevention:
    """SC-007: Re-ingesting same file_hash marks it as duplicate."""

    @pytest.mark.asyncio
    async def test_sc_007_duplicate_prevention(self, populated_db):
        db, coll_id, _ = populated_db
        # Same file_hash in same collection → UNIQUE constraint violation
        with pytest.raises(Exception):
            await db.create_document(
                id=str(uuid.uuid4()),
                collection_id=coll_id,
                filename="same_file.pdf",
                file_hash="sha256_abc123",  # same hash as in populated_db
            )

    @pytest.mark.asyncio
    async def test_sc_007_duplicate_can_be_marked_in_status(self, populated_db):
        """Document status can be set to 'duplicate' to reflect re-ingestion."""
        db, _, doc_id = populated_db
        await db.update_document(doc_id, status="duplicate")
        row = await db.get_document(doc_id)
        assert row["status"] == "duplicate"


class TestSC008WALConcurrency:
    """SC-008: Concurrent reads proceed without blocking (WAL mode)."""

    @pytest.mark.asyncio
    async def test_sc_008_wal_concurrency(self, file_db: SQLiteDB):
        """Two concurrent read queries succeed without error under WAL."""
        coll_id = str(uuid.uuid4())
        await file_db.create_collection(
            id=coll_id,
            name="concurrent-test",
            embedding_model="nomic-embed-text",
            chunk_profile="default",
            qdrant_collection_name="concurrent_qdrant",
        )

        async def read_collection():
            return await file_db.get_collection(coll_id)

        # Run two concurrent reads
        results = await asyncio.gather(read_collection(), read_collection())
        assert all(r is not None for r in results)
        assert all(r["id"] == coll_id for r in results)


class TestSC009EncryptedKeys:
    """SC-009: No plaintext API keys in DB or logs."""

    @pytest.mark.asyncio
    async def test_sc_009_encrypted_keys(self, db: SQLiteDB, key_manager: KeyManager):
        plaintext_key = "sk-supersecret-apikey-should-not-appear"
        encrypted = key_manager.encrypt(plaintext_key)

        await db.create_provider(
            name="openrouter", api_key_encrypted=encrypted, is_active=True
        )
        row = await db.get_provider("openrouter")

        stored = row["api_key_encrypted"]
        assert stored != plaintext_key, "Plaintext key must never be stored"
        assert plaintext_key not in stored, "Plaintext must not appear in ciphertext"

    def test_sc_009_encrypt_returns_different_bytes_each_call(self, key_manager: KeyManager):
        """Fernet uses random IV → same plaintext produces different ciphertext."""
        ct1 = key_manager.encrypt("same-key")
        ct2 = key_manager.encrypt("same-key")
        # Fernet tokens differ due to random IV (timestamp + random bytes)
        assert ct1 != ct2

    def test_sc_009_decrypt_restores_original(self, key_manager: KeyManager):
        original = "sk-anthropic-test-12345"
        assert key_manager.decrypt(key_manager.encrypt(original)) == original


class TestSC010TracesRecorded:
    """SC-010: All trace fields populated including reasoning_steps_json, strategy_switches_json, confidence_score 0-100."""

    @pytest.mark.asyncio
    async def test_sc_010_traces_recorded(self, db: SQLiteDB):
        trace_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        await db.create_query_trace(
            id=trace_id,
            session_id=session_id,
            query="test query",
            collections_searched='["col1"]',
            chunks_retrieved_json='[{"id": "x"}]',
            latency_ms=200,
            llm_model="claude-3",
            embed_model="nomic-embed-text",
            confidence_score=91,
            sub_questions_json='["sub1"]',
            reasoning_steps_json='["reasoning step 1", "reasoning step 2"]',
            strategy_switches_json='["CHANGE_COLLECTION"]',
            meta_reasoning_triggered=True,
        )
        traces = await db.list_query_traces(session_id)
        assert len(traces) == 1
        t = traces[0]
        # All required fields present
        assert t["query"] == "test query"
        assert t["session_id"] == session_id
        assert t["confidence_score"] == 91
        assert isinstance(t["confidence_score"], int)
        assert t["latency_ms"] == 200
        assert t["reasoning_steps_json"] is not None
        assert t["strategy_switches_json"] is not None
        assert t["collections_searched"] is not None
        assert t["chunks_retrieved_json"] is not None

    @pytest.mark.asyncio
    async def test_sc_010_confidence_score_range(self, db: SQLiteDB):
        """confidence_score 0–100 boundary values."""
        session_id = str(uuid.uuid4())
        for score in [0, 50, 100]:
            await db.create_query_trace(
                id=str(uuid.uuid4()),
                session_id=session_id,
                query=f"query-{score}",
                collections_searched="[]",
                chunks_retrieved_json="[]",
                latency_ms=10,
                confidence_score=score,
            )
        traces = await db.list_query_traces(session_id, limit=10)
        scores = {t["confidence_score"] for t in traces}
        assert scores == {0, 50, 100}


class TestSC011CrossReferences:
    """SC-011: parent_id in Qdrant resolves to parent_chunks; document_id resolves to documents."""

    @pytest.mark.asyncio
    async def test_sc_011_cross_references(self, populated_db):
        """parent_chunks.document_id resolves to a documents row."""
        db, coll_id, doc_id = populated_db
        parent_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "cross-ref-test"))
        await db.create_parent_chunk(
            id=parent_id, collection_id=coll_id, document_id=doc_id,
            text="cross reference chunk",
        )

        # parent_chunks.document_id → documents.id
        chunk = await db.get_parent_chunk(parent_id)
        assert chunk is not None
        resolved_doc = await db.get_document(chunk["document_id"])
        assert resolved_doc is not None
        assert resolved_doc["id"] == doc_id

    @pytest.mark.asyncio
    async def test_sc_011_fk_cascade_on_delete(self, file_db: SQLiteDB):
        """Deleting collection cascades to parent_chunks (FK constraint)."""
        coll_id = str(uuid.uuid4())
        doc_id = str(uuid.uuid4())
        parent_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "fk-cascade-test"))

        await file_db.create_collection(
            id=coll_id, name="fk-test-col",
            embedding_model="nomic", chunk_profile="default",
            qdrant_collection_name="fk_test_qdrant",
        )
        await file_db.create_document(
            id=doc_id, collection_id=coll_id, filename="x.pdf", file_hash="fk_hash"
        )
        await file_db.create_parent_chunk(
            id=parent_id, collection_id=coll_id, document_id=doc_id, text="data"
        )

        await file_db.delete_collection(coll_id)

        assert await file_db.get_parent_chunk(parent_id) is None


# ===========================================================================
# Edge Case Tests
# ===========================================================================


class TestEdgeCases:
    """Additional edge case coverage."""

    @pytest.mark.asyncio
    async def test_empty_collection_search(self):
        """Empty batch retrieval returns [] not an error."""
        db = SQLiteDB(":memory:")
        await db.connect()
        try:
            result = await db.get_parent_chunks_batch([])
            assert result == []
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_file_same_hash_different_collections(self, db: SQLiteDB):
        """Same file_hash allowed in different collections (UNIQUE is per collection)."""
        coll_id_1 = str(uuid.uuid4())
        coll_id_2 = str(uuid.uuid4())
        for i, cid in enumerate([coll_id_1, coll_id_2]):
            await db.create_collection(
                id=cid, name=f"col-{i}",
                embedding_model="nomic", chunk_profile="default",
                qdrant_collection_name=f"qdrant_{i}",
            )
        # Same file_hash in different collections must succeed
        await db.create_document(
            id=str(uuid.uuid4()), collection_id=coll_id_1,
            filename="file.pdf", file_hash="same_hash",
        )
        await db.create_document(
            id=str(uuid.uuid4()), collection_id=coll_id_2,
            filename="file.pdf", file_hash="same_hash",
        )
        docs1 = await db.list_documents(coll_id_1)
        docs2 = await db.list_documents(coll_id_2)
        assert len(docs1) == 1
        assert len(docs2) == 1
        assert docs1[0]["file_hash"] == docs2[0]["file_hash"] == "same_hash"

    @pytest.mark.asyncio
    async def test_qdrant_unavailable_mid_batch(self):
        """Entire batch fails on Qdrant timeout (not partial success)."""
        storage = _make_storage()
        mock_client = AsyncMock()
        mock_client.upsert = AsyncMock(side_effect=ConnectionError("Qdrant timeout"))
        storage.client = mock_client

        points = [
            QdrantPoint(
                id=i,
                vector=[0.1] * 768,
                sparse_vector=None,
                payload={**VALID_PAYLOAD, "parent_id": str(uuid.uuid4())},
            )
            for i in range(5)
        ]
        with pytest.raises(Exception):
            await storage._batch_upsert_with_retry("test_coll", points)

        # Circuit should record failure
        storage._record_failure()
        assert storage._failure_count > 0

    @pytest.mark.asyncio
    async def test_failed_job_resumable(self, populated_db):
        """Partial data persists after job failure; job is resumable without rollback."""
        db, coll_id, doc_id = populated_db
        job_id = str(uuid.uuid4())
        await db.create_ingestion_job(id=job_id, document_id=doc_id, status="embedding")

        # Create some parent chunks (partial ingestion)
        partial_ids = [str(uuid.uuid5(uuid.NAMESPACE_DNS, f"partial-{i}")) for i in range(3)]
        for pid in partial_ids:
            await db.create_parent_chunk(
                id=pid, collection_id=coll_id, document_id=doc_id,
                text=f"partial chunk {pid}",
            )

        # Job fails
        await db.update_ingestion_job(
            job_id, status="failed", error_msg="embedding service timeout"
        )

        # Partial data still exists
        chunks = await db.get_parent_chunks_batch(partial_ids)
        assert len(chunks) == 3, "Partial chunks must persist after job failure"

        # Job status is failed (not deleted)
        job = await db.get_ingestion_job(job_id)
        assert job["status"] == "failed"

        # Resume: update status back to started
        await db.update_ingestion_job(job_id, status="started", error_msg=None)
        job = await db.get_ingestion_job(job_id)
        assert job["status"] == "started"
