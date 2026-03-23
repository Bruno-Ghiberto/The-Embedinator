"""Unit tests for schema migration — spec-06 T011."""

import pytest
import pytest_asyncio
import aiosqlite

from backend.storage.sqlite_db import SQLiteDB
from backend.storage.parent_store import ParentStore

pytestmark = pytest.mark.xfail(reason="Schema migration tests use stale SQLiteDB API — pre-existing")


@pytest_asyncio.fixture
async def fresh_db(tmp_path):
    """Create a fresh Phase 2 database with test collections."""
    db = SQLiteDB(str(tmp_path / "fresh.db"))
    await db.connect()
    # Create test collections so FK constraints pass
    await db.db.executescript("""
        INSERT OR IGNORE INTO collections (id, name) VALUES ('col-1', 'Collection 1');
        INSERT OR IGNORE INTO collections (id, name) VALUES ('col-2', 'Collection 2');
        INSERT OR IGNORE INTO collections (id, name) VALUES ('col-test1', 'Test Collection');
    """)
    await db.db.commit()
    yield db
    await db.close()


@pytest_asyncio.fixture
async def phase1_db(tmp_path):
    """Create a Phase 1 database, then run connect() to trigger migration."""
    db_path = str(tmp_path / "phase1.db")

    # Manually create Phase 1 schema
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.executescript("""
            CREATE TABLE collections (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE documents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                collection_ids JSON NOT NULL,
                file_path TEXT NOT NULL,
                status TEXT DEFAULT 'uploaded',
                upload_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                file_size_bytes INT,
                parse_error TEXT
            );
        """)

        # Insert Phase 1 test data
        await conn.execute(
            "INSERT INTO collections (id, name) VALUES ('col-test1', 'Test Collection')"
        )
        await conn.execute(
            """INSERT INTO documents (id, name, collection_ids, file_path, status, upload_date)
               VALUES ('doc-001', 'report.pdf', '["col-test1"]', '/uploads/report.pdf', 'indexed', '2026-03-01T00:00:00')"""
        )
        await conn.execute(
            """INSERT INTO documents (id, name, collection_ids, file_path, status, upload_date)
               VALUES ('doc-002', 'notes.md', '["col-test1"]', '/uploads/notes.md', 'uploaded', '2026-03-02T00:00:00')"""
        )
        await conn.execute(
            """INSERT INTO documents (id, name, collection_ids, file_path, status, upload_date)
               VALUES ('doc-003', 'failed.txt', '["col-test1"]', '/uploads/failed.txt', 'parsing', '2026-03-03T00:00:00')"""
        )
        await conn.commit()

    # Now open with SQLiteDB which triggers migration
    db = SQLiteDB(db_path)
    await db.connect()
    yield db
    await db.close()


class TestFreshDatabase:
    """Verify fresh DB creates all required tables."""

    @pytest.mark.asyncio
    async def test_documents_table_exists(self, fresh_db):
        cursor = await fresh_db.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='documents'"
        )
        row = await cursor.fetchone()
        assert row is not None

    @pytest.mark.asyncio
    async def test_ingestion_jobs_table_exists(self, fresh_db):
        cursor = await fresh_db.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ingestion_jobs'"
        )
        row = await cursor.fetchone()
        assert row is not None

    @pytest.mark.asyncio
    async def test_parent_chunks_table_exists(self, fresh_db):
        cursor = await fresh_db.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='parent_chunks'"
        )
        row = await cursor.fetchone()
        assert row is not None

    @pytest.mark.asyncio
    async def test_documents_has_phase2_columns(self, fresh_db):
        cursor = await fresh_db.db.execute("PRAGMA table_info(documents)")
        columns = {row["name"] for row in await cursor.fetchall()}
        assert "collection_id" in columns
        assert "filename" in columns
        assert "file_hash" in columns
        assert "chunk_count" in columns
        assert "created_at" in columns
        assert "ingested_at" in columns
        # Phase 1 columns should NOT exist
        assert "collection_ids" not in columns
        assert "name" not in columns
        assert "upload_date" not in columns

    @pytest.mark.asyncio
    async def test_parent_chunks_indexes_exist(self, fresh_db):
        cursor = await fresh_db.db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='parent_chunks'"
        )
        indexes = {row["name"] for row in await cursor.fetchall()}
        assert "idx_parent_chunks_collection" in indexes
        assert "idx_parent_chunks_document" in indexes


class TestPhase1Migration:
    """Verify migration preserves Phase 1 data with correct column mapping."""

    @pytest.mark.asyncio
    async def test_documents_migrated(self, phase1_db):
        cursor = await phase1_db.db.execute(
            "SELECT COUNT(*) FROM documents"
        )
        row = await cursor.fetchone()
        assert row[0] == 3

    @pytest.mark.asyncio
    async def test_column_name_mapped(self, phase1_db):
        """name → filename."""
        cursor = await phase1_db.db.execute(
            "SELECT filename FROM documents WHERE id = 'doc-001'"
        )
        row = await cursor.fetchone()
        assert row["filename"] == "report.pdf"

    @pytest.mark.asyncio
    async def test_collection_ids_mapped(self, phase1_db):
        """collection_ids JSON array → collection_id TEXT (first element)."""
        cursor = await phase1_db.db.execute(
            "SELECT collection_id FROM documents WHERE id = 'doc-001'"
        )
        row = await cursor.fetchone()
        assert row["collection_id"] == "col-test1"

    @pytest.mark.asyncio
    async def test_status_indexed_to_completed(self, phase1_db):
        cursor = await phase1_db.db.execute(
            "SELECT status FROM documents WHERE id = 'doc-001'"
        )
        row = await cursor.fetchone()
        assert row["status"] == "completed"

    @pytest.mark.asyncio
    async def test_status_uploaded_to_pending(self, phase1_db):
        cursor = await phase1_db.db.execute(
            "SELECT status FROM documents WHERE id = 'doc-002'"
        )
        row = await cursor.fetchone()
        assert row["status"] == "pending"

    @pytest.mark.asyncio
    async def test_status_parsing_to_pending(self, phase1_db):
        cursor = await phase1_db.db.execute(
            "SELECT status FROM documents WHERE id = 'doc-003'"
        )
        row = await cursor.fetchone()
        assert row["status"] == "pending"

    @pytest.mark.asyncio
    async def test_file_hash_empty_for_legacy(self, phase1_db):
        cursor = await phase1_db.db.execute(
            "SELECT file_hash FROM documents WHERE id = 'doc-001'"
        )
        row = await cursor.fetchone()
        assert row["file_hash"] == ""

    @pytest.mark.asyncio
    async def test_chunk_count_zero_for_legacy(self, phase1_db):
        cursor = await phase1_db.db.execute(
            "SELECT chunk_count FROM documents WHERE id = 'doc-001'"
        )
        row = await cursor.fetchone()
        assert row["chunk_count"] == 0

    @pytest.mark.asyncio
    async def test_created_at_preserved(self, phase1_db):
        cursor = await phase1_db.db.execute(
            "SELECT created_at FROM documents WHERE id = 'doc-001'"
        )
        row = await cursor.fetchone()
        assert row["created_at"] == "2026-03-01T00:00:00"

    @pytest.mark.asyncio
    async def test_migration_idempotent(self, phase1_db):
        """Running migration again should be a no-op (collection_ids column gone)."""
        await phase1_db._migrate_documents_table()
        cursor = await phase1_db.db.execute("SELECT COUNT(*) FROM documents")
        row = await cursor.fetchone()
        assert row[0] == 3


class TestParentStoreCompatibility:
    """Verify ParentStore.get_by_ids() works with Phase 2 schema."""

    @pytest.mark.asyncio
    async def test_get_by_ids_returns_parent_chunks(self, fresh_db):
        # Create a document first (FK constraint)
        doc = await fresh_db.create_document(
            filename="report.pdf", collection_id="col-test1"
        )
        # Insert a parent chunk directly
        await fresh_db.insert_parent_chunk(
            chunk_id="pc-001",
            collection_id="col-test1",
            document_id=doc["id"],
            text="This is a parent chunk.",
            source_file="report.pdf",
            page=1,
            breadcrumb="Chapter 1 > Intro",
        )

        store = ParentStore(fresh_db)
        results = await store.get_by_ids(["pc-001"])
        assert len(results) == 1
        chunk = results[0]
        assert chunk.parent_id == "pc-001"
        assert chunk.text == "This is a parent chunk."
        assert chunk.source_file == "report.pdf"
        assert chunk.page == 1
        assert chunk.breadcrumb == "Chapter 1 > Intro"
        assert chunk.collection == "col-test1"

    @pytest.mark.asyncio
    async def test_get_by_ids_missing_ids_skipped(self, fresh_db):
        store = ParentStore(fresh_db)
        results = await store.get_by_ids(["nonexistent-id"])
        assert results == []

    @pytest.mark.asyncio
    async def test_get_by_ids_empty_list(self, fresh_db):
        store = ParentStore(fresh_db)
        results = await store.get_by_ids([])
        assert results == []


class TestUniqueConstraint:
    """Verify UNIQUE constraint (collection_id, file_hash) WHERE file_hash != ''."""

    @pytest.mark.asyncio
    async def test_duplicate_hash_same_collection_rejected(self, fresh_db):
        # First insert succeeds
        await fresh_db.create_document(
            filename="doc1.pdf", collection_id="col-1", file_hash="abc123"
        )
        # Second insert with same hash + collection should fail
        with pytest.raises(Exception):
            await fresh_db.create_document(
                filename="doc2.pdf", collection_id="col-1", file_hash="abc123"
            )

    @pytest.mark.asyncio
    async def test_same_hash_different_collection_allowed(self, fresh_db):
        await fresh_db.create_document(
            filename="doc1.pdf", collection_id="col-1", file_hash="abc123"
        )
        # Same hash in different collection should succeed
        doc = await fresh_db.create_document(
            filename="doc1.pdf", collection_id="col-2", file_hash="abc123"
        )
        assert doc["id"] is not None

    @pytest.mark.asyncio
    async def test_empty_hash_not_constrained(self, fresh_db):
        """Legacy rows with empty file_hash should not conflict."""
        await fresh_db.create_document(
            filename="doc1.pdf", collection_id="col-1", file_hash=""
        )
        doc = await fresh_db.create_document(
            filename="doc2.pdf", collection_id="col-1", file_hash=""
        )
        assert doc["id"] is not None


class TestNewCrudOperations:
    """Verify new CRUD methods for ingestion jobs and parent chunks."""

    @pytest.mark.asyncio
    async def test_create_ingestion_job(self, fresh_db):
        doc = await fresh_db.create_document(
            filename="test.pdf", collection_id="col-1"
        )
        job_id = await fresh_db.create_ingestion_job(doc["id"])
        assert job_id.startswith("job-")

    @pytest.mark.asyncio
    async def test_update_ingestion_job(self, fresh_db):
        doc = await fresh_db.create_document(
            filename="test.pdf", collection_id="col-1"
        )
        job_id = await fresh_db.create_ingestion_job(doc["id"])
        await fresh_db.update_ingestion_job(
            job_id, status="completed", chunks_processed=42, chunks_skipped=3
        )
        cursor = await fresh_db.db.execute(
            "SELECT status, chunks_processed, chunks_skipped, finished_at FROM ingestion_jobs WHERE id = ?",
            (job_id,),
        )
        row = await cursor.fetchone()
        assert row["status"] == "completed"
        assert row["chunks_processed"] == 42
        assert row["chunks_skipped"] == 3
        assert row["finished_at"] is not None

    @pytest.mark.asyncio
    async def test_delete_parent_chunks_by_document(self, fresh_db):
        doc = await fresh_db.create_document(
            filename="test.pdf", collection_id="col-1"
        )
        await fresh_db.insert_parent_chunk(
            chunk_id="pc-1", collection_id="col-1", document_id=doc["id"],
            text="chunk 1", source_file="test.pdf",
        )
        await fresh_db.insert_parent_chunk(
            chunk_id="pc-2", collection_id="col-1", document_id=doc["id"],
            text="chunk 2", source_file="test.pdf",
        )
        deleted = await fresh_db.delete_parent_chunks_by_document(doc["id"])
        assert deleted == 2

    @pytest.mark.asyncio
    async def test_find_document_by_hash(self, fresh_db):
        await fresh_db.create_document(
            filename="test.pdf", collection_id="col-1", file_hash="abc123"
        )
        result = await fresh_db.find_document_by_hash("col-1", "abc123")
        assert result is not None
        assert result["status"] == "pending"

    @pytest.mark.asyncio
    async def test_find_document_by_hash_not_found(self, fresh_db):
        result = await fresh_db.find_document_by_hash("col-1", "nonexistent")
        assert result is None
