"""Unit tests for SQLiteDB — Spec 07 Storage Architecture (T017-T026)."""

import json
import sqlite3
import time
import uuid

import pytest
import pytest_asyncio

from backend.storage.sqlite_db import SQLiteDB


# ── Fixtures ──────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db():
    """Create an in-memory SQLite database for test isolation."""
    database = SQLiteDB(":memory:")
    await database.connect()
    yield database
    await database.close()


@pytest_asyncio.fixture
async def collection_id(db: SQLiteDB) -> str:
    """Create a test collection and return its ID."""
    cid = str(uuid.uuid4())
    await db.create_collection(
        id=cid,
        name="test-collection",
        embedding_model="all-MiniLM-L6-v2",
        chunk_profile="default",
        qdrant_collection_name="test_qdrant_coll",
    )
    return cid


@pytest_asyncio.fixture
async def document_id(db: SQLiteDB, collection_id: str) -> str:
    """Create a test document and return its ID."""
    did = str(uuid.uuid4())
    await db.create_document(
        id=did,
        collection_id=collection_id,
        filename="report.pdf",
        file_hash="abc123hash",
    )
    return did


# ── Schema Tests (T017) ──────────────────────────────────────────


class TestSchema:
    @pytest.mark.asyncio
    async def test_init_schema_creates_all_tables(self, db: SQLiteDB):
        cursor = await db.db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        rows = await cursor.fetchall()
        tables = {row[0] for row in rows}
        expected = {
            "collections",
            "documents",
            "ingestion_jobs",
            "parent_chunks",
            "query_traces",
            "settings",
            "providers",
        }
        assert expected.issubset(tables), f"Missing tables: {expected - tables}"

    @pytest.mark.asyncio
    async def test_wal_mode_enabled(self, db: SQLiteDB):
        """WAL mode is set on connect. :memory: DBs report 'memory' instead of 'wal'."""
        cursor = await db.db.execute("PRAGMA journal_mode")
        row = await cursor.fetchone()
        # In-memory databases cannot use WAL; they return 'memory'.
        # WAL is verified with a file-based DB in integration tests.
        assert row[0] in ("wal", "memory")

    @pytest.mark.asyncio
    async def test_foreign_keys_enabled(self, db: SQLiteDB):
        cursor = await db.db.execute("PRAGMA foreign_keys")
        row = await cursor.fetchone()
        assert row[0] == 1

    @pytest.mark.asyncio
    async def test_schema_idempotent(self, db: SQLiteDB):
        """Calling _init_schema() again should not raise."""
        await db._init_schema()
        await db._init_schema()
        cursor = await db.db.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
        row = await cursor.fetchone()
        assert row[0] >= 7


# ── Collections Tests (T018) ─────────────────────────────────────


class TestCollections:
    @pytest.mark.asyncio
    async def test_create_collection(self, db: SQLiteDB):
        cid = str(uuid.uuid4())
        await db.create_collection(
            id=cid,
            name="my-collection",
            embedding_model="all-MiniLM-L6-v2",
            chunk_profile="default",
            qdrant_collection_name="my_qdrant",
            description="A test collection",
        )
        result = await db.get_collection(cid)
        assert result is not None
        assert result["name"] == "my-collection"
        assert result["description"] == "A test collection"
        assert result["embedding_model"] == "all-MiniLM-L6-v2"
        assert result["chunk_profile"] == "default"
        assert result["qdrant_collection_name"] == "my_qdrant"
        assert result["created_at"] is not None

    @pytest.mark.asyncio
    async def test_create_duplicate_name_rejected(self, db: SQLiteDB, collection_id: str):
        with pytest.raises(Exception):
            await db.create_collection(
                id=str(uuid.uuid4()),
                name="test-collection",  # same name as fixture
                embedding_model="all-MiniLM-L6-v2",
                chunk_profile="default",
                qdrant_collection_name="other_qdrant",
            )

    @pytest.mark.asyncio
    async def test_get_collection_not_found(self, db: SQLiteDB):
        result = await db.get_collection("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_collection_by_name(self, db: SQLiteDB, collection_id: str):
        result = await db.get_collection_by_name("test-collection")
        assert result is not None
        assert result["id"] == collection_id

    @pytest.mark.asyncio
    async def test_get_collection_by_name_not_found(self, db: SQLiteDB):
        result = await db.get_collection_by_name("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_collections(self, db: SQLiteDB, collection_id: str):
        collections = await db.list_collections()
        assert len(collections) == 1
        assert collections[0]["id"] == collection_id

    @pytest.mark.asyncio
    async def test_update_collection(self, db: SQLiteDB, collection_id: str):
        await db.update_collection(collection_id, description="Updated description")
        result = await db.get_collection(collection_id)
        assert result["description"] == "Updated description"

    @pytest.mark.asyncio
    async def test_delete_collection(self, db: SQLiteDB, collection_id: str):
        await db.delete_collection(collection_id)
        result = await db.get_collection(collection_id)
        assert result is None


# ── Documents Tests (T019) ───────────────────────────────────────


class TestDocuments:
    @pytest.mark.asyncio
    async def test_create_document(self, db: SQLiteDB, collection_id: str):
        did = str(uuid.uuid4())
        await db.create_document(
            id=did,
            collection_id=collection_id,
            filename="test.pdf",
            file_hash="sha256abc",
            file_path="/tmp/test.pdf",
        )
        result = await db.get_document(did)
        assert result is not None
        assert result["filename"] == "test.pdf"
        assert result["file_hash"] == "sha256abc"
        assert result["file_path"] == "/tmp/test.pdf"
        assert result["status"] == "pending"
        assert result["chunk_count"] == 0

    @pytest.mark.asyncio
    async def test_create_duplicate_hash_rejected(self, db: SQLiteDB, collection_id: str):
        did1 = str(uuid.uuid4())
        await db.create_document(
            id=did1,
            collection_id=collection_id,
            filename="file1.pdf",
            file_hash="same_hash",
        )
        with pytest.raises(Exception):
            await db.create_document(
                id=str(uuid.uuid4()),
                collection_id=collection_id,
                filename="file2.pdf",
                file_hash="same_hash",
            )

    @pytest.mark.asyncio
    async def test_get_document_by_hash(self, db: SQLiteDB, collection_id: str, document_id: str):
        result = await db.get_document_by_hash(collection_id, "abc123hash")
        assert result is not None
        assert result["id"] == document_id

    @pytest.mark.asyncio
    async def test_get_document_by_hash_not_found(self, db: SQLiteDB, collection_id: str):
        result = await db.get_document_by_hash(collection_id, "nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_documents(self, db: SQLiteDB, collection_id: str, document_id: str):
        docs = await db.list_documents(collection_id)
        assert len(docs) == 1
        assert docs[0]["id"] == document_id

    @pytest.mark.asyncio
    async def test_update_document_status(self, db: SQLiteDB, collection_id: str, document_id: str):
        await db.update_document(document_id, status="ingesting")
        result = await db.get_document(document_id)
        assert result["status"] == "ingesting"

    @pytest.mark.asyncio
    async def test_update_document_multiple_fields(self, db: SQLiteDB, collection_id: str, document_id: str):
        await db.update_document(document_id, status="completed", chunk_count=42)
        result = await db.get_document(document_id)
        assert result["status"] == "completed"
        assert result["chunk_count"] == 42

    @pytest.mark.asyncio
    async def test_delete_document(self, db: SQLiteDB, collection_id: str, document_id: str):
        await db.delete_document(document_id)
        result = await db.get_document(document_id)
        assert result is None


# ── Ingestion Jobs Tests (T020) ──────────────────────────────────


class TestIngestionJobs:
    @pytest.mark.asyncio
    async def test_create_ingestion_job(self, db: SQLiteDB, collection_id: str, document_id: str):
        jid = str(uuid.uuid4())
        await db.create_ingestion_job(id=jid, document_id=document_id)
        result = await db.get_ingestion_job(jid)
        assert result is not None
        assert result["status"] == "started"
        assert result["started_at"] is not None
        assert result["chunks_processed"] == 0
        assert result["chunks_skipped"] == 0

    @pytest.mark.asyncio
    async def test_update_ingestion_job_status(self, db: SQLiteDB, collection_id: str, document_id: str):
        jid = str(uuid.uuid4())
        await db.create_ingestion_job(id=jid, document_id=document_id)
        await db.update_ingestion_job(
            jid,
            status="completed",
            chunks_processed=10,
            chunks_skipped=2,
            finished_at="2026-03-14T00:00:00Z",
        )
        result = await db.get_ingestion_job(jid)
        assert result["status"] == "completed"
        assert result["chunks_processed"] == 10
        assert result["chunks_skipped"] == 2
        assert result["finished_at"] == "2026-03-14T00:00:00Z"

    @pytest.mark.asyncio
    async def test_update_ingestion_job_error(self, db: SQLiteDB, collection_id: str, document_id: str):
        jid = str(uuid.uuid4())
        await db.create_ingestion_job(id=jid, document_id=document_id)
        await db.update_ingestion_job(jid, status="failed", error_msg="Qdrant timeout")
        result = await db.get_ingestion_job(jid)
        assert result["status"] == "failed"
        assert result["error_msg"] == "Qdrant timeout"

    @pytest.mark.asyncio
    async def test_list_ingestion_jobs(self, db: SQLiteDB, collection_id: str, document_id: str):
        jid1 = str(uuid.uuid4())
        jid2 = str(uuid.uuid4())
        await db.create_ingestion_job(id=jid1, document_id=document_id)
        await db.create_ingestion_job(id=jid2, document_id=document_id)
        jobs = await db.list_ingestion_jobs(document_id)
        assert len(jobs) == 2


# ── Parent Chunks Tests (T021) ───────────────────────────────────


class TestParentChunks:
    @pytest.mark.asyncio
    async def test_create_parent_chunk_uuid5(self, db: SQLiteDB, collection_id: str, document_id: str):
        pid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{collection_id}:{document_id}:text"))
        await db.create_parent_chunk(
            id=pid,
            collection_id=collection_id,
            document_id=document_id,
            text="This is a parent chunk with substantial content for testing.",
            metadata_json=json.dumps({"page": 1, "section": "intro"}),
        )
        result = await db.get_parent_chunk(pid)
        assert result is not None
        assert result["id"] == pid
        assert result["text"].startswith("This is a parent chunk")
        assert result["metadata_json"] is not None

    @pytest.mark.asyncio
    async def test_duplicate_uuid5_rejected(self, db: SQLiteDB, collection_id: str, document_id: str):
        pid = str(uuid.uuid5(uuid.NAMESPACE_DNS, "unique-content"))
        await db.create_parent_chunk(
            id=pid,
            collection_id=collection_id,
            document_id=document_id,
            text="First version",
        )
        with pytest.raises(Exception):
            await db.create_parent_chunk(
                id=pid,
                collection_id=collection_id,
                document_id=document_id,
                text="Second version",
            )

    @pytest.mark.asyncio
    async def test_batch_retrieval(self, db: SQLiteDB, collection_id: str, document_id: str):
        ids = []
        for i in range(100):
            pid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"chunk-{i}"))
            ids.append(pid)
            await db.create_parent_chunk(
                id=pid,
                collection_id=collection_id,
                document_id=document_id,
                text=f"Parent chunk number {i} with enough content to be meaningful.",
            )

        start = time.monotonic()
        results = await db.get_parent_chunks_batch(ids)
        elapsed_ms = (time.monotonic() - start) * 1000

        assert len(results) == 100
        assert elapsed_ms < 10, f"Batch retrieval took {elapsed_ms:.1f}ms, target <10ms"

    @pytest.mark.asyncio
    async def test_batch_retrieval_empty(self, db: SQLiteDB):
        results = await db.get_parent_chunks_batch([])
        assert results == []

    @pytest.mark.asyncio
    async def test_list_parent_chunks_by_collection(self, db: SQLiteDB, collection_id: str, document_id: str):
        pid = str(uuid.uuid5(uuid.NAMESPACE_DNS, "list-test"))
        await db.create_parent_chunk(
            id=pid,
            collection_id=collection_id,
            document_id=document_id,
            text="Content for listing test.",
        )
        results = await db.list_parent_chunks(collection_id)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_list_parent_chunks_by_document(self, db: SQLiteDB, collection_id: str, document_id: str):
        pid = str(uuid.uuid5(uuid.NAMESPACE_DNS, "doc-list-test"))
        await db.create_parent_chunk(
            id=pid,
            collection_id=collection_id,
            document_id=document_id,
            text="Content for doc listing test.",
        )
        results = await db.list_parent_chunks(collection_id, document_id=document_id)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_delete_parent_chunks(self, db: SQLiteDB, collection_id: str, document_id: str):
        pid = str(uuid.uuid5(uuid.NAMESPACE_DNS, "delete-test"))
        await db.create_parent_chunk(
            id=pid,
            collection_id=collection_id,
            document_id=document_id,
            text="Content to delete.",
        )
        await db.delete_parent_chunks(document_id)
        result = await db.get_parent_chunk(pid)
        assert result is None


# ── Query Traces Tests (T022) ────────────────────────────────────


class TestQueryTraces:
    @pytest.mark.asyncio
    async def test_create_query_trace(self, db: SQLiteDB):
        tid = str(uuid.uuid4())
        await db.create_query_trace(
            id=tid,
            session_id="session-1",
            query="What is AI?",
            collections_searched=json.dumps(["col-1"]),
            chunks_retrieved_json=json.dumps([{"parent_id": "p1", "score": 0.9}]),
            latency_ms=125,
            llm_model="qwen2.5:7b",
            embed_model="all-MiniLM-L6-v2",
            confidence_score=85,
            reasoning_steps_json=json.dumps([{"step": 1, "action": "search"}]),
            strategy_switches_json=json.dumps([]),
            meta_reasoning_triggered=False,
        )
        traces = await db.list_query_traces("session-1")
        assert len(traces) == 1
        trace = traces[0]
        assert trace["id"] == tid
        assert trace["query"] == "What is AI?"
        assert trace["confidence_score"] == 85
        assert trace["reasoning_steps_json"] is not None
        assert trace["strategy_switches_json"] is not None
        assert trace["meta_reasoning_triggered"] == 0
        assert trace["latency_ms"] == 125

    @pytest.mark.asyncio
    async def test_confidence_score_is_integer(self, db: SQLiteDB):
        """confidence_score must be INTEGER (0-100), not REAL/float."""
        tid = str(uuid.uuid4())
        await db.create_query_trace(
            id=tid,
            session_id="session-int",
            query="test",
            collections_searched="[]",
            chunks_retrieved_json="[]",
            latency_ms=10,
            confidence_score=75,
        )
        # Verify via raw SQL that the column type is INTEGER
        cursor = await db.db.execute("PRAGMA table_info(query_traces)")
        columns = await cursor.fetchall()
        conf_col = next(c for c in columns if c["name"] == "confidence_score")
        assert conf_col["type"] == "INTEGER"

    @pytest.mark.asyncio
    async def test_reasoning_steps_json_column_exists(self, db: SQLiteDB):
        """FR-005: reasoning_steps_json must exist in query_traces."""
        cursor = await db.db.execute("PRAGMA table_info(query_traces)")
        columns = await cursor.fetchall()
        col_names = {c["name"] for c in columns}
        assert "reasoning_steps_json" in col_names
        assert "strategy_switches_json" in col_names

    @pytest.mark.asyncio
    async def test_list_query_traces_by_session(self, db: SQLiteDB):
        for i in range(5):
            await db.create_query_trace(
                id=str(uuid.uuid4()),
                session_id="session-list",
                query=f"Query {i}",
                collections_searched="[]",
                chunks_retrieved_json="[]",
                latency_ms=10 + i,
            )
        # Different session
        await db.create_query_trace(
            id=str(uuid.uuid4()),
            session_id="other-session",
            query="Other query",
            collections_searched="[]",
            chunks_retrieved_json="[]",
            latency_ms=10,
        )
        traces = await db.list_query_traces("session-list")
        assert len(traces) == 5

    @pytest.mark.asyncio
    async def test_query_traces_timerange(self, db: SQLiteDB):
        tid = str(uuid.uuid4())
        await db.create_query_trace(
            id=tid,
            session_id="session-time",
            query="Timerange test",
            collections_searched="[]",
            chunks_retrieved_json="[]",
            latency_ms=50,
        )
        # Query with wide range that includes everything
        traces = await db.get_query_traces_by_timerange("2020-01-01", "2030-12-31")
        assert len(traces) >= 1

    @pytest.mark.asyncio
    async def test_meta_reasoning_triggered_flag(self, db: SQLiteDB):
        tid = str(uuid.uuid4())
        await db.create_query_trace(
            id=tid,
            session_id="session-meta",
            query="Meta test",
            collections_searched="[]",
            chunks_retrieved_json="[]",
            latency_ms=200,
            meta_reasoning_triggered=True,
        )
        traces = await db.list_query_traces("session-meta")
        assert traces[0]["meta_reasoning_triggered"] == 1


# ── Settings Tests (T023) ────────────────────────────────────────


class TestSettings:
    @pytest.mark.asyncio
    async def test_set_and_get_setting(self, db: SQLiteDB):
        await db.set_setting("confidence_threshold", "60")
        value = await db.get_setting("confidence_threshold")
        assert value == "60"

    @pytest.mark.asyncio
    async def test_set_setting_upsert(self, db: SQLiteDB):
        await db.set_setting("key1", "value1")
        await db.set_setting("key1", "value2")
        value = await db.get_setting("key1")
        assert value == "value2"

    @pytest.mark.asyncio
    async def test_get_setting_not_found(self, db: SQLiteDB):
        value = await db.get_setting("nonexistent")
        assert value is None

    @pytest.mark.asyncio
    async def test_list_settings(self, db: SQLiteDB):
        await db.set_setting("a", "1")
        await db.set_setting("b", "2")
        settings = await db.list_settings()
        assert settings == {"a": "1", "b": "2"}

    @pytest.mark.asyncio
    async def test_delete_setting(self, db: SQLiteDB):
        await db.set_setting("to_delete", "value")
        await db.delete_setting("to_delete")
        value = await db.get_setting("to_delete")
        assert value is None


# ── Providers Tests (T024) ───────────────────────────────────────


class TestProviders:
    @pytest.mark.asyncio
    async def test_create_provider(self, db: SQLiteDB):
        await db.create_provider(
            name="openai",
            api_key_encrypted="gAAAAA_encrypted_key",
            base_url="https://api.openai.com",
            is_active=True,
        )
        result = await db.get_provider("openai")
        assert result is not None
        assert result["name"] == "openai"
        assert result["api_key_encrypted"] == "gAAAAA_encrypted_key"
        assert result["is_active"] is True
        assert result["created_at"] is not None

    @pytest.mark.asyncio
    async def test_create_provider_null_api_key_ollama(self, db: SQLiteDB):
        await db.create_provider(
            name="ollama",
            base_url="http://localhost:11434",
            is_active=True,
        )
        result = await db.get_provider("ollama")
        assert result is not None
        assert result["api_key_encrypted"] is None
        assert result["base_url"] == "http://localhost:11434"

    @pytest.mark.asyncio
    async def test_create_duplicate_provider_rejected(self, db: SQLiteDB):
        await db.create_provider(name="openai")
        with pytest.raises(Exception):
            await db.create_provider(name="openai")

    @pytest.mark.asyncio
    async def test_list_providers(self, db: SQLiteDB):
        await db.create_provider(name="openai", is_active=True)
        await db.create_provider(name="ollama", is_active=False)
        providers = await db.list_providers()
        assert len(providers) == 2

    @pytest.mark.asyncio
    async def test_update_provider(self, db: SQLiteDB):
        await db.create_provider(name="openai", is_active=True)
        await db.update_provider("openai", is_active=False)
        result = await db.get_provider("openai")
        assert result["is_active"] is False

    @pytest.mark.asyncio
    async def test_delete_provider(self, db: SQLiteDB):
        await db.create_provider(name="to_delete")
        await db.delete_provider("to_delete")
        result = await db.get_provider("to_delete")
        assert result is None


# ── Constraints Tests (T025) ─────────────────────────────────────


class TestConstraints:
    @pytest.mark.asyncio
    async def test_fk_violation_document(self, db: SQLiteDB):
        """Creating a document with nonexistent collection_id should fail."""
        with pytest.raises(Exception):
            await db.create_document(
                id=str(uuid.uuid4()),
                collection_id="nonexistent-collection",
                filename="test.pdf",
                file_hash="hash123",
            )

    @pytest.mark.asyncio
    async def test_fk_violation_ingestion_job(self, db: SQLiteDB):
        """Creating a job with nonexistent document_id should fail."""
        with pytest.raises(Exception):
            await db.create_ingestion_job(
                id=str(uuid.uuid4()),
                document_id="nonexistent-document",
            )

    @pytest.mark.asyncio
    async def test_fk_violation_parent_chunk(self, db: SQLiteDB, collection_id: str):
        """Creating a chunk with nonexistent document_id should fail."""
        with pytest.raises(Exception):
            await db.create_parent_chunk(
                id=str(uuid.uuid5(uuid.NAMESPACE_DNS, "fk-test")),
                collection_id=collection_id,
                document_id="nonexistent-document",
                text="Should fail",
            )

    @pytest.mark.asyncio
    async def test_cascade_delete_collection(self, db: SQLiteDB, collection_id: str, document_id: str):
        """Deleting a collection should cascade to documents, jobs, and chunks."""
        # Create a job and chunk linked to the document
        jid = str(uuid.uuid4())
        await db.create_ingestion_job(id=jid, document_id=document_id)
        pid = str(uuid.uuid5(uuid.NAMESPACE_DNS, "cascade-test"))
        await db.create_parent_chunk(
            id=pid,
            collection_id=collection_id,
            document_id=document_id,
            text="Cascade test chunk",
        )

        # Delete collection — should cascade
        await db.delete_collection(collection_id)

        # All related records gone
        assert await db.get_document(document_id) is None
        assert await db.get_ingestion_job(jid) is None
        assert await db.get_parent_chunk(pid) is None

    @pytest.mark.asyncio
    async def test_cascade_delete_document(self, db: SQLiteDB, collection_id: str, document_id: str):
        """Deleting a document should cascade to jobs and chunks."""
        jid = str(uuid.uuid4())
        await db.create_ingestion_job(id=jid, document_id=document_id)
        pid = str(uuid.uuid5(uuid.NAMESPACE_DNS, "doc-cascade"))
        await db.create_parent_chunk(
            id=pid,
            collection_id=collection_id,
            document_id=document_id,
            text="Document cascade test chunk",
        )

        await db.delete_document(document_id)

        assert await db.get_ingestion_job(jid) is None
        assert await db.get_parent_chunk(pid) is None

    @pytest.mark.asyncio
    async def test_unique_qdrant_collection_name(self, db: SQLiteDB):
        """qdrant_collection_name must be unique."""
        await db.create_collection(
            id=str(uuid.uuid4()),
            name="coll-a",
            embedding_model="model",
            chunk_profile="default",
            qdrant_collection_name="shared_qdrant_name",
        )
        with pytest.raises(Exception):
            await db.create_collection(
                id=str(uuid.uuid4()),
                name="coll-b",
                embedding_model="model",
                chunk_profile="default",
                qdrant_collection_name="shared_qdrant_name",
            )

    @pytest.mark.asyncio
    async def test_unique_collection_file_hash(self, db: SQLiteDB, collection_id: str):
        """UNIQUE(collection_id, file_hash) must be enforced."""
        await db.create_document(
            id=str(uuid.uuid4()),
            collection_id=collection_id,
            filename="a.pdf",
            file_hash="duplicate_hash",
        )
        with pytest.raises(Exception):
            await db.create_document(
                id=str(uuid.uuid4()),
                collection_id=collection_id,
                filename="b.pdf",
                file_hash="duplicate_hash",
            )


# ── Performance Tests (T026) ─────────────────────────────────────


class TestPerformance:
    @pytest.mark.asyncio
    async def test_batch_retrieval_100_chunks_under_10ms(self, db: SQLiteDB, collection_id: str, document_id: str):
        """Batch retrieval of 100 parent chunks must complete in <10ms."""
        ids = []
        for i in range(100):
            pid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"perf-chunk-{i}"))
            ids.append(pid)
            await db.create_parent_chunk(
                id=pid,
                collection_id=collection_id,
                document_id=document_id,
                text=f"Performance test chunk {i} with enough text to be realistic.",
                metadata_json=json.dumps({"page": i, "section": f"Section {i}"}),
            )

        # Warm up
        await db.get_parent_chunks_batch(ids[:10])

        # Timed run
        start = time.monotonic()
        results = await db.get_parent_chunks_batch(ids)
        elapsed_ms = (time.monotonic() - start) * 1000

        assert len(results) == 100
        assert elapsed_ms < 10, f"Batch retrieval took {elapsed_ms:.1f}ms, target <10ms"


# ── Context Manager Tests ────────────────────────────────────────


class TestContextManager:
    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        async with SQLiteDB(":memory:") as db:
            assert db.db is not None
            # Verify schema was initialized
            cursor = await db.db.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
            row = await cursor.fetchone()
            assert row[0] >= 7
        # After exit, connection should be closed
        assert db.db is None

    @pytest.mark.asyncio
    async def test_close_idempotent(self):
        db = SQLiteDB(":memory:")
        await db.connect()
        await db.close()
        await db.close()  # Should not raise


# ── Spec-10 Migration Tests (T028) ───────────────────────────────


class TestSpec10ProviderNameMigration:
    """T028: query_traces.provider_name column migration and create_query_trace()."""

    @pytest.mark.asyncio
    async def test_provider_name_column_exists_after_connect(self):
        """After connect(), PRAGMA table_info shows provider_name on query_traces."""
        db = SQLiteDB(":memory:")
        await db.connect()
        cursor = await db.db.execute("PRAGMA table_info(query_traces)")
        columns = {row[1] for row in await cursor.fetchall()}
        assert "provider_name" in columns
        await db.close()

    @pytest.mark.asyncio
    async def test_create_query_trace_with_provider_name_persists(self):
        """create_query_trace(provider_name='openrouter') stores the value."""
        db = SQLiteDB(":memory:")
        await db.connect()
        tid = str(uuid.uuid4())
        await db.create_query_trace(
            id=tid,
            session_id="s1",
            query="What is RAG?",
            collections_searched="[]",
            chunks_retrieved_json="[]",
            latency_ms=50,
            provider_name="openrouter",
        )
        cursor = await db.db.execute("SELECT provider_name FROM query_traces WHERE id = ?", (tid,))
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == "openrouter"
        await db.close()

    @pytest.mark.asyncio
    async def test_create_query_trace_without_provider_name_stores_null(self):
        """create_query_trace() without provider_name succeeds; NULL is stored."""
        db = SQLiteDB(":memory:")
        await db.connect()
        tid = str(uuid.uuid4())
        await db.create_query_trace(
            id=tid,
            session_id="s2",
            query="backward compat test",
            collections_searched="[]",
            chunks_retrieved_json="[]",
            latency_ms=10,
        )
        cursor = await db.db.execute("SELECT provider_name FROM query_traces WHERE id = ?", (tid,))
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] is None  # NULL stored (backward compatible)
        await db.close()

    @pytest.mark.asyncio
    async def test_migration_idempotent_no_error_on_second_run(self):
        """Running _migrate_query_traces_columns() twice does not raise."""
        db = SQLiteDB(":memory:")
        await db.connect()
        # First run was already done in connect(); run again explicitly
        await db._migrate_query_traces_columns()
        await db._migrate_query_traces_columns()
        # Column still present after idempotent runs
        cursor = await db.db.execute("PRAGMA table_info(query_traces)")
        columns = {row[1] for row in await cursor.fetchall()}
        assert "provider_name" in columns
        await db.close()
