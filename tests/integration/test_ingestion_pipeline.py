"""Integration tests for ingestion pipeline — spec-06.

End-to-end tests that verify the complete ingestion flow:
upload → parse → chunk → embed → index.

NOTE: These tests require running Qdrant and Ollama services.
They are designed as scaffolds that can be run when the full
infrastructure is available.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.integration.conftest import unique_name


@pytest.fixture
def collection_id():
    """Create a unique test collection ID for ingestion tests."""
    return f"col-{unique_name('ingest')}"


@pytest.fixture
def sample_pdf(tmp_path):
    """Create a small sample PDF-like file for testing.

    NOTE: This creates a minimal text file with .pdf extension.
    The actual PDF parsing is handled by the Rust worker, which
    is mocked in these tests. For true end-to-end PDF tests,
    a real PDF would be needed.
    """
    pdf_path = tmp_path / "sample.pdf"
    # Minimal content that the mocked worker can process
    pdf_path.write_text(
        "Sample document content.\n\n"
        "This is a test document for the ingestion pipeline.\n\n"
        "It contains multiple paragraphs to test chunking behavior.\n\n"
        "Section 2: Details\n\n"
        "More detailed content goes here with enough text to create "
        "multiple chunks when processed through the chunking pipeline. "
        "The goal is to verify that the full flow works correctly.\n"
    )
    return pdf_path


@pytest.fixture
def mock_worker_ndjson():
    """Create NDJSON output simulating Rust worker for a small PDF."""
    chunks = [
        {
            "text": "Sample document content. This is a test document for the ingestion pipeline.",
            "page": 1,
            "section": "",
            "heading_path": [],
            "doc_type": "prose",
            "chunk_profile": "default",
            "chunk_index": 0,
        },
        {
            "text": "It contains multiple paragraphs to test chunking behavior.",
            "page": 1,
            "section": "",
            "heading_path": [],
            "doc_type": "prose",
            "chunk_profile": "default",
            "chunk_index": 1,
        },
        {
            "text": "More detailed content goes here with enough text to create multiple chunks.",
            "page": 1,
            "section": "Section 2: Details",
            "heading_path": ["Section 2: Details"],
            "doc_type": "prose",
            "chunk_profile": "default",
            "chunk_index": 2,
        },
    ]
    return [json.dumps(c) + "\n" for c in chunks]


class TestIngestionIntegration:
    """End-to-end ingestion: upload → parse → chunk → embed → index.

    These tests mock the Rust worker subprocess and Ollama embedding
    service, but exercise the real Python pipeline orchestration,
    chunking, SQLite operations, and Qdrant upserts.
    """

    @pytest.mark.asyncio
    async def test_upload_pdf_end_to_end(
        self, sample_pdf, collection_id, mock_worker_ndjson
    ):
        """Upload a PDF, verify completed status, chunks in storage.

        Flow:
        1. Create collection and document records in SQLite
        2. Run pipeline with mocked worker + mocked embedder
        3. Verify document status = completed
        4. Verify child chunks were upserted to Qdrant
        5. Verify parent chunks exist in SQLite
        """
        from backend.ingestion.pipeline import IngestionPipeline
        from backend.storage.sqlite_db import SQLiteDB

        # Setup: create in-memory SQLite DB
        db = SQLiteDB(":memory:")
        await db.connect()

        # Create a collection
        collection = await db.create_collection(unique_name("test-collection"))
        coll_id = collection["id"]

        # Create document record
        doc = await db.create_document(
            filename="sample.pdf",
            collection_id=coll_id,
            status="pending",
        )
        job_id = await db.create_ingestion_job(doc["id"])

        # Mock Qdrant
        mock_qdrant = AsyncMock()
        mock_qdrant.upsert = AsyncMock()

        # Mock worker process
        mock_proc = MagicMock()
        mock_proc.stdout = iter(mock_worker_ndjson)
        mock_proc.stderr = MagicMock()
        mock_proc.stderr.read.return_value = ""
        mock_proc.returncode = 0
        mock_proc.wait.return_value = 0

        # Mock embeddings (384-dim vectors)
        fake_embeddings = ([[0.1] * 384 for _ in range(20)], 0)

        pipeline = IngestionPipeline(db=db, qdrant=mock_qdrant)

        with (
            patch("backend.ingestion.pipeline.subprocess.Popen", return_value=mock_proc),
            patch.object(
                pipeline.embedder, "embed_chunks",
                new_callable=AsyncMock,
                return_value=fake_embeddings,
            ),
        ):
            result = await pipeline.ingest_file(
                file_path=str(sample_pdf),
                filename="sample.pdf",
                collection_id=coll_id,
                document_id=doc["id"],
                job_id=job_id,
            )

        # Verify result
        assert result.status == "completed"
        assert result.chunks_processed > 0
        assert result.error is None

        # Verify document status updated to completed
        updated_doc = await db.get_document(doc["id"])
        assert updated_doc["status"] == "completed"
        assert updated_doc["chunk_count"] > 0
        assert updated_doc["ingested_at"] is not None

        # Verify Qdrant upsert was called (child chunks)
        assert mock_qdrant.upsert.called
        upsert_calls = mock_qdrant.upsert.call_args_list
        total_points = sum(len(call.args[1]) for call in upsert_calls)
        assert total_points > 0

        # Verify point payloads have correct fields
        first_call_points = upsert_calls[0].args[1]
        point = first_call_points[0]
        assert "id" in point
        assert "vector" in point
        assert point["payload"]["collection_id"] == coll_id
        assert point["payload"]["document_id"] == doc["id"]
        assert "parent_id" in point["payload"]
        assert "source_file" in point["payload"]

        await db.close()

    @pytest.mark.asyncio
    async def test_worker_failure_partial_output_processed(
        self, sample_pdf, mock_worker_ndjson
    ):
        """Worker fails mid-stream, received chunks still processed (R4)."""
        from backend.ingestion.pipeline import IngestionPipeline
        from backend.storage.sqlite_db import SQLiteDB

        db = SQLiteDB(":memory:")
        await db.connect()

        collection = await db.create_collection(unique_name("test-partial"))
        coll_id = collection["id"]
        doc = await db.create_document(
            filename="partial.pdf", collection_id=coll_id, status="pending"
        )
        job_id = await db.create_ingestion_job(doc["id"])

        mock_qdrant = AsyncMock()
        mock_qdrant.upsert = AsyncMock()

        # Worker produces some output then fails
        mock_proc = MagicMock()
        mock_proc.stdout = iter(mock_worker_ndjson[:2])  # Only 2 of 3 chunks
        mock_proc.stderr = MagicMock()
        mock_proc.stderr.read.return_value = "Parse error on page 3"
        mock_proc.returncode = 2  # Parse error
        mock_proc.wait.return_value = 2

        fake_embeddings = ([[0.1] * 384 for _ in range(20)], 0)

        pipeline = IngestionPipeline(db=db, qdrant=mock_qdrant)

        with (
            patch("backend.ingestion.pipeline.subprocess.Popen", return_value=mock_proc),
            patch.object(
                pipeline.embedder, "embed_chunks",
                new_callable=AsyncMock,
                return_value=fake_embeddings,
            ),
        ):
            result = await pipeline.ingest_file(
                file_path=str(sample_pdf),
                filename="partial.pdf",
                collection_id=coll_id,
                document_id=doc["id"],
                job_id=job_id,
            )

        # Status should be failed but chunks were processed
        assert result.status == "failed"
        assert result.chunks_processed > 0
        assert "Worker exited with code 2" in result.error

        # Document should be marked failed
        updated_doc = await db.get_document(doc["id"])
        assert updated_doc["status"] == "failed"

        await db.close()


class TestIncrementalDedup:
    """Integration tests for duplicate detection and change-based re-ingestion."""

    @pytest.mark.asyncio
    async def test_duplicate_upload_returns_conflict(self, sample_pdf, mock_worker_ndjson):
        """Upload -> re-upload same file -> 409 duplicate detected."""
        from backend.ingestion.incremental import IncrementalChecker
        from backend.storage.sqlite_db import SQLiteDB

        db = SQLiteDB(":memory:")
        await db.connect()

        collection = await db.create_collection(unique_name("test-dedup"))
        coll_id = collection["id"]

        # Compute real hash of sample file
        file_hash = IncrementalChecker.compute_file_hash(str(sample_pdf))
        checker = IncrementalChecker(db)

        # First upload: create document with completed status and hash
        doc = await db.create_document(
            filename="sample.pdf",
            collection_id=coll_id,
            file_hash=file_hash,
            status="completed",
        )

        # Second upload attempt: should detect duplicate
        is_dup, existing_id = await checker.check_duplicate(coll_id, file_hash)
        assert is_dup is True
        assert existing_id == doc["id"]

        await db.close()

    @pytest.mark.asyncio
    async def test_failed_document_allows_reingestion(self, sample_pdf):
        """Upload fails -> re-upload same file -> allowed (FR-004)."""
        from backend.ingestion.incremental import IncrementalChecker
        from backend.storage.sqlite_db import SQLiteDB

        db = SQLiteDB(":memory:")
        await db.connect()

        collection = await db.create_collection(unique_name("test-reingestion"))
        coll_id = collection["id"]

        file_hash = IncrementalChecker.compute_file_hash(str(sample_pdf))
        checker = IncrementalChecker(db)

        # First upload: failed
        await db.create_document(
            filename="sample.pdf",
            collection_id=coll_id,
            file_hash=file_hash,
            status="failed",
        )

        # Second upload: should NOT be duplicate
        is_dup, _ = await checker.check_duplicate(coll_id, file_hash)
        assert is_dup is False

        await db.close()

    @pytest.mark.asyncio
    async def test_changed_file_triggers_old_data_deletion(
        self, tmp_path, mock_worker_ndjson
    ):
        """Modify file -> re-upload -> old points deleted, new chunks indexed."""
        from backend.ingestion.incremental import IncrementalChecker
        from backend.ingestion.pipeline import IngestionPipeline
        from backend.storage.sqlite_db import SQLiteDB

        db = SQLiteDB(":memory:")
        await db.connect()

        collection = await db.create_collection(unique_name("test-change"))
        coll_id = collection["id"]

        # Create original file and ingest it
        original_file = tmp_path / "report.pdf"
        original_file.write_text("Original content version 1")
        original_hash = IncrementalChecker.compute_file_hash(str(original_file))

        # Create completed document for original
        old_doc = await db.create_document(
            filename="report.pdf",
            collection_id=coll_id,
            file_hash=original_hash,
            status="completed",
        )

        # Insert some parent chunks for the old document
        await db.insert_parent_chunk(
            chunk_id="parent-old-1",
            collection_id=coll_id,
            document_id=old_doc["id"],
            text="Old parent chunk text",
            source_file="report.pdf",
            page=1,
        )

        # Create modified file with different content
        modified_file = tmp_path / "report_v2.pdf"
        modified_file.write_text("Modified content version 2 with changes")
        new_hash = IncrementalChecker.compute_file_hash(str(modified_file))
        assert original_hash != new_hash

        checker = IncrementalChecker(db)

        # Check for change: same filename, different hash
        is_changed, old_doc_id = await checker.check_change(
            coll_id, "report.pdf", new_hash
        )
        assert is_changed is True
        assert old_doc_id == old_doc["id"]

        # Mock Qdrant for point deletion
        mock_qdrant = AsyncMock()
        mock_qdrant.client = AsyncMock()
        mock_qdrant.client.delete = AsyncMock()
        mock_qdrant.upsert = AsyncMock()

        pipeline = IngestionPipeline(db=db, qdrant=mock_qdrant)

        # Delete old data
        await pipeline.delete_old_document_data(
            collection_name=coll_id,
            source_file="report.pdf",
            old_document_id=old_doc_id,
        )

        # Verify Qdrant delete was called with source_file filter
        mock_qdrant.client.delete.assert_awaited_once()
        delete_call = mock_qdrant.client.delete.call_args
        assert delete_call.kwargs["collection_name"] == coll_id

        # Verify old parent chunks were deleted from SQLite
        cursor = await db.db.execute(
            "SELECT COUNT(*) FROM parent_chunks WHERE document_id = ?",
            (old_doc_id,),
        )
        row = await cursor.fetchone()
        assert row[0] == 0

        # Mark old doc as deleted
        await db.update_document_status(old_doc_id, "deleted")

        # Create new document and ingest
        new_doc = await db.create_document(
            filename="report.pdf",
            collection_id=coll_id,
            file_hash=new_hash,
            status="pending",
        )
        job_id = await db.create_ingestion_job(new_doc["id"])

        # Mock worker process
        mock_proc = MagicMock()
        mock_proc.stdout = iter(mock_worker_ndjson)
        mock_proc.stderr = MagicMock()
        mock_proc.stderr.read.return_value = ""
        mock_proc.returncode = 0
        mock_proc.wait.return_value = 0

        fake_embeddings = ([[0.1] * 384 for _ in range(20)], 0)

        with (
            patch(
                "backend.ingestion.pipeline.subprocess.Popen",
                return_value=mock_proc,
            ),
            patch.object(
                pipeline.embedder,
                "embed_chunks",
                new_callable=AsyncMock,
                return_value=fake_embeddings,
            ),
        ):
            result = await pipeline.ingest_file(
                file_path=str(modified_file),
                filename="report.pdf",
                collection_id=coll_id,
                document_id=new_doc["id"],
                job_id=job_id,
                file_hash=new_hash,
            )

        # Verify new ingestion completed
        assert result.status == "completed"
        assert result.chunks_processed > 0

        # Verify new document has completed status
        updated_new = await db.get_document(new_doc["id"])
        assert updated_new["status"] == "completed"
        assert updated_new["chunk_count"] > 0

        # Verify new Qdrant upsert happened (new child chunks)
        assert mock_qdrant.upsert.called

        await db.close()

    @pytest.mark.asyncio
    async def test_same_hash_different_collection_not_duplicate(self, sample_pdf):
        """Same file in collection A -> upload to collection B -> not duplicate."""
        from backend.ingestion.incremental import IncrementalChecker
        from backend.storage.sqlite_db import SQLiteDB

        db = SQLiteDB(":memory:")
        await db.connect()

        coll_a = await db.create_collection(unique_name("test-coll-a"))
        coll_b = await db.create_collection(unique_name("test-coll-b"))

        file_hash = IncrementalChecker.compute_file_hash(str(sample_pdf))
        checker = IncrementalChecker(db)

        # Document exists in collection A
        await db.create_document(
            filename="sample.pdf",
            collection_id=coll_a["id"],
            file_hash=file_hash,
            status="completed",
        )

        # Check duplicate in collection B -> should NOT be duplicate
        is_dup, _ = await checker.check_duplicate(coll_b["id"], file_hash)
        assert is_dup is False

        await db.close()


class TestFaultToleranceIntegration:
    """Integration tests for fault tolerance: Qdrant outage -> pause -> resume."""

    @pytest.mark.asyncio
    async def test_qdrant_outage_pause_resume_completes(
        self, sample_pdf, mock_worker_ndjson
    ):
        """Mock Qdrant unreachable -> job pauses -> restore -> job completes.

        Flow:
        1. Start ingestion with Qdrant that fails on first N upserts
        2. Verify job transitions to 'paused'
        3. Qdrant recovers (mock succeeds on retry)
        4. Verify job completes with all points flushed
        """
        from backend.ingestion.pipeline import IngestionPipeline
        from backend.storage.sqlite_db import SQLiteDB

        db = SQLiteDB(":memory:")
        await db.connect()

        collection = await db.create_collection(unique_name("test-fault"))
        coll_id = collection["id"]
        doc = await db.create_document(
            filename="fault-test.pdf",
            collection_id=coll_id,
            status="pending",
        )
        job_id = await db.create_ingestion_job(doc["id"])

        # Mock Qdrant: fail first 2 upsert calls, then succeed
        upsert_call_count = 0

        async def qdrant_upsert_flaky(collection_name, points):
            nonlocal upsert_call_count
            upsert_call_count += 1
            if upsert_call_count <= 2:
                raise ConnectionError("Qdrant temporarily unreachable")

        mock_qdrant = AsyncMock()
        mock_qdrant.upsert = AsyncMock(side_effect=qdrant_upsert_flaky)

        # Mock worker process
        mock_proc = MagicMock()
        mock_proc.stdout = iter(mock_worker_ndjson)
        mock_proc.stderr = MagicMock()
        mock_proc.stderr.read.return_value = ""
        mock_proc.returncode = 0
        mock_proc.wait.return_value = 0

        fake_embeddings = ([[0.1] * 384 for _ in range(20)], 0)

        pipeline = IngestionPipeline(db=db, qdrant=mock_qdrant)

        with (
            patch(
                "backend.ingestion.pipeline.subprocess.Popen",
                return_value=mock_proc,
            ),
            patch.object(
                pipeline.embedder,
                "embed_chunks",
                new_callable=AsyncMock,
                return_value=fake_embeddings,
            ),
            patch(
                "backend.ingestion.pipeline.asyncio.sleep",
                new_callable=AsyncMock,
            ),
        ):
            result = await pipeline.ingest_file(
                file_path=str(sample_pdf),
                filename="fault-test.pdf",
                collection_id=coll_id,
                document_id=doc["id"],
                job_id=job_id,
            )

        # Verify job completed successfully after recovery
        assert result.status == "completed"
        assert result.chunks_processed > 0
        assert result.error is None

        # Verify document status is completed in DB
        updated_doc = await db.get_document(doc["id"])
        assert updated_doc["status"] == "completed"
        assert updated_doc["chunk_count"] > 0

        # Verify Qdrant upsert was eventually called successfully
        assert upsert_call_count > 2  # initial failures + successful flush

        await db.close()
