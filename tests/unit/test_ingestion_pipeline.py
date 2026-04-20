"""Unit tests for IngestionPipeline — spec-06 ingestion pipeline."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.ingestion.pipeline import IngestionPipeline, IngestionResult, UpsertBuffer


def _make_ndjson_lines(chunks: list[dict]) -> list[str]:
    """Create NDJSON lines from a list of chunk dicts."""
    return [json.dumps(c) + "\n" for c in chunks]


def _sample_raw_chunks(count: int = 3) -> list[dict]:
    """Create sample raw worker output chunks."""
    return [
        {
            "text": f"Sample text content for chunk {i}. " * 10,
            "page": 1,
            "section": "Introduction",
            "heading_path": ["Chapter 1", "Introduction"],
            "doc_type": "prose",
            "chunk_profile": "default",
            "chunk_index": i,
        }
        for i in range(count)
    ]


def _mock_popen(raw_chunks: list[dict], returncode: int = 0, stderr: str = ""):
    """Create a mock Popen object that yields NDJSON lines."""
    lines = _make_ndjson_lines(raw_chunks)
    mock_proc = MagicMock()
    mock_proc.stdout = iter(lines)
    mock_proc.stderr = MagicMock()
    mock_proc.stderr.read.return_value = stderr
    mock_proc.returncode = returncode
    mock_proc.wait.return_value = returncode
    return mock_proc


def _valid_embeddings(count: int) -> tuple[list[list[float]], int]:
    """Return (embeddings, 0) matching new embed_chunks return type."""
    return [[0.1] * 384 for _ in range(count)], 0


class TestIngestionPipeline:
    """Tests for end-to-end pipeline orchestration with mocked dependencies."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock SQLiteDB."""
        db = AsyncMock()
        db.update_ingestion_job = AsyncMock()
        db.update_document_status = AsyncMock()
        db.insert_parent_chunk = AsyncMock()
        db.create_ingestion_job = AsyncMock(return_value="job-test123")
        return db

    @pytest.fixture
    def mock_qdrant(self):
        """Create a mock QdrantClientWrapper."""
        qdrant = AsyncMock()
        qdrant.upsert = AsyncMock()
        return qdrant

    @pytest.fixture
    def pipeline(self, mock_db, mock_qdrant):
        """Create an IngestionPipeline with mocked dependencies."""
        return IngestionPipeline(db=mock_db, qdrant=mock_qdrant)

    @pytest.mark.asyncio
    async def test_happy_path_status_transitions(self, pipeline, mock_db, mock_qdrant):
        """Happy path: worker succeeds, chunks processed, status transitions correct."""
        raw_chunks = _sample_raw_chunks(3)
        mock_proc = _mock_popen(raw_chunks, returncode=0)

        embeddings = _valid_embeddings(10)

        with (
            patch("backend.ingestion.pipeline.subprocess.Popen", return_value=mock_proc),
            patch.object(pipeline.embedder, "embed_chunks", new_callable=AsyncMock, return_value=embeddings),
            patch.object(pipeline.chunker, "split_into_parents") as mock_split,
        ):
            from backend.ingestion.chunker import ParentChunkData

            mock_parents = [
                ParentChunkData(
                    chunk_id="parent-001",
                    text="Parent text content " * 50,
                    source_file="test.pdf",
                    page=1,
                    breadcrumb="Chapter 1 > Introduction",
                    children=[
                        {"text": "Child text 1", "point_id": "pt-001", "chunk_index": 0},
                        {"text": "Child text 2", "point_id": "pt-002", "chunk_index": 1},
                    ],
                ),
            ]
            mock_split.return_value = mock_parents

            result = await pipeline.ingest_file(
                file_path="/tmp/test.pdf",
                filename="test.pdf",
                collection_id="col-test",
                document_id="doc-test",
                job_id="job-test",
                file_hash="test-hash",
            )

        assert result.status == "completed"
        assert result.document_id == "doc-test"
        assert result.job_id == "job-test"
        assert result.chunks_processed > 0
        assert result.error is None

        # Verify status transitions: started -> streaming -> embedding -> completed
        job_calls = mock_db.update_ingestion_job.call_args_list
        job_statuses = []
        for call in job_calls:
            if call.args and len(call.args) > 1:
                job_statuses.append(call.args[1])
            elif "status" in call.kwargs:
                job_statuses.append(call.kwargs["status"])
        assert "started" in job_statuses
        assert "streaming" in job_statuses
        assert "embedding" in job_statuses
        assert "completed" in job_statuses

        # Verify document status transitions
        doc_calls = mock_db.update_document_status.call_args_list
        doc_statuses = []
        for call in doc_calls:
            if call.args and len(call.args) > 1:
                doc_statuses.append(call.args[1])
        assert "ingesting" in doc_statuses
        assert "completed" in doc_statuses

    @pytest.mark.asyncio
    async def test_happy_path_chunk_count_updated(self, pipeline, mock_db, mock_qdrant):
        """Verify document chunk_count is updated on completion."""
        raw_chunks = _sample_raw_chunks(2)
        mock_proc = _mock_popen(raw_chunks, returncode=0)

        embeddings = _valid_embeddings(5)

        with (
            patch("backend.ingestion.pipeline.subprocess.Popen", return_value=mock_proc),
            patch.object(pipeline.embedder, "embed_chunks", new_callable=AsyncMock, return_value=embeddings),
            patch.object(pipeline.chunker, "split_into_parents") as mock_split,
        ):
            from backend.ingestion.chunker import ParentChunkData

            mock_parents = [
                ParentChunkData(
                    chunk_id="parent-001",
                    text="Parent text " * 50,
                    source_file="test.pdf",
                    page=1,
                    breadcrumb="Intro",
                    children=[
                        {"text": "Child 1", "point_id": "pt-001", "chunk_index": 0},
                        {"text": "Child 2", "point_id": "pt-002", "chunk_index": 1},
                        {"text": "Child 3", "point_id": "pt-003", "chunk_index": 2},
                    ],
                ),
            ]
            mock_split.return_value = mock_parents

            result = await pipeline.ingest_file(
                file_path="/tmp/test.pdf",
                filename="test.pdf",
                collection_id="col-test",
                document_id="doc-test",
                job_id="job-test",
                file_hash="test-hash",
            )

        assert result.status == "completed"
        # Verify chunk_count passed to update_document_status
        completed_calls = [
            call
            for call in mock_db.update_document_status.call_args_list
            if len(call.args) > 1 and call.args[1] == "completed"
        ]
        assert len(completed_calls) == 1
        assert completed_calls[0].kwargs.get("chunk_count", 0) > 0

    @pytest.mark.asyncio
    async def test_parent_chunks_stored_in_sqlite(self, pipeline, mock_db, mock_qdrant):
        """Verify parent chunks are stored via db.insert_parent_chunk."""
        raw_chunks = _sample_raw_chunks(2)
        mock_proc = _mock_popen(raw_chunks, returncode=0)

        embeddings = _valid_embeddings(5)

        with (
            patch("backend.ingestion.pipeline.subprocess.Popen", return_value=mock_proc),
            patch.object(pipeline.embedder, "embed_chunks", new_callable=AsyncMock, return_value=embeddings),
            patch.object(pipeline.chunker, "split_into_parents") as mock_split,
        ):
            from backend.ingestion.chunker import ParentChunkData

            mock_parents = [
                ParentChunkData(
                    chunk_id="parent-001",
                    text="Parent text " * 50,
                    source_file="test.pdf",
                    page=1,
                    breadcrumb="Chapter 1",
                    children=[
                        {"text": "Child 1", "point_id": "pt-001", "chunk_index": 0},
                    ],
                ),
                ParentChunkData(
                    chunk_id="parent-002",
                    text="Parent text 2 " * 50,
                    source_file="test.pdf",
                    page=2,
                    breadcrumb="Chapter 2",
                    children=[
                        {"text": "Child 2", "point_id": "pt-002", "chunk_index": 1},
                    ],
                ),
            ]
            mock_split.return_value = mock_parents

            await pipeline.ingest_file(
                file_path="/tmp/test.pdf",
                filename="test.pdf",
                collection_id="col-test",
                document_id="doc-test",
                job_id="job-test",
                file_hash="test-hash",
            )

        assert mock_db.insert_parent_chunk.call_count == 2
        first_call = mock_db.insert_parent_chunk.call_args_list[0]
        assert first_call.kwargs["chunk_id"] == "parent-001"
        assert first_call.kwargs["collection_id"] == "col-test"
        assert first_call.kwargs["document_id"] == "doc-test"

    @pytest.mark.asyncio
    async def test_batch_upsert_called_with_correct_points(self, pipeline, mock_db, mock_qdrant):
        """Verify Qdrant upsert is called with correctly structured points."""
        raw_chunks = _sample_raw_chunks(2)
        mock_proc = _mock_popen(raw_chunks, returncode=0)

        embedding = [0.1] * 384
        embeddings = ([embedding for _ in range(5)], 0)

        with (
            patch("backend.ingestion.pipeline.subprocess.Popen", return_value=mock_proc),
            patch.object(pipeline.embedder, "embed_chunks", new_callable=AsyncMock, return_value=embeddings),
            patch.object(pipeline.chunker, "split_into_parents") as mock_split,
        ):
            from backend.ingestion.chunker import ParentChunkData

            mock_parents = [
                ParentChunkData(
                    chunk_id="parent-001",
                    text="Parent text " * 50,
                    source_file="test.pdf",
                    page=1,
                    breadcrumb="Intro",
                    children=[
                        {"text": "Child 1", "point_id": "pt-001", "chunk_index": 0},
                    ],
                ),
            ]
            mock_split.return_value = mock_parents

            await pipeline.ingest_file(
                file_path="/tmp/test.pdf",
                filename="test.pdf",
                collection_id="col-test",
                document_id="doc-test",
                job_id="job-test",
                file_hash="test-hash",
            )

        # Verify qdrant.upsert was called
        assert mock_qdrant.upsert.called
        call_args = mock_qdrant.upsert.call_args
        assert call_args.args[0] == "col-test"  # collection_id
        points = call_args.args[1]
        assert len(points) > 0
        point = points[0]
        assert "id" in point
        assert "vector" in point
        assert "payload" in point
        assert point["payload"]["collection_id"] == "col-test"
        assert point["payload"]["document_id"] == "doc-test"

    @pytest.mark.asyncio
    async def test_no_chunks_worker_success(self, pipeline, mock_db, mock_qdrant):
        """Worker succeeds but produces no chunks -> completed with chunk_count=0."""
        mock_proc = _mock_popen([], returncode=0)

        with patch("backend.ingestion.pipeline.subprocess.Popen", return_value=mock_proc):
            result = await pipeline.ingest_file(
                file_path="/tmp/empty.pdf",
                filename="empty.pdf",
                collection_id="col-test",
                document_id="doc-test",
                job_id="job-test",
                file_hash="test-hash",
            )

        assert result.status == "completed"
        assert result.chunks_processed == 0

    @pytest.mark.asyncio
    async def test_worker_failure_no_chunks(self, pipeline, mock_db, mock_qdrant):
        """Worker fails with no output -> status=failed."""
        mock_proc = _mock_popen([], returncode=1, stderr="File not found")

        with patch("backend.ingestion.pipeline.subprocess.Popen", return_value=mock_proc):
            result = await pipeline.ingest_file(
                file_path="/tmp/missing.pdf",
                filename="missing.pdf",
                collection_id="col-test",
                document_id="doc-test",
                job_id="job-test",
                file_hash="test-hash",
            )

        assert result.status == "failed"
        assert "Worker exited with code 1" in result.error

    @pytest.mark.asyncio
    async def test_worker_failure_with_partial_output(self, pipeline, mock_db, mock_qdrant):
        """Worker fails but produced chunks -> process chunks then set failed (R4)."""
        raw_chunks = _sample_raw_chunks(2)
        mock_proc = _mock_popen(raw_chunks, returncode=2, stderr="Parse error on page 5")

        embeddings = _valid_embeddings(5)

        with (
            patch("backend.ingestion.pipeline.subprocess.Popen", return_value=mock_proc),
            patch.object(pipeline.embedder, "embed_chunks", new_callable=AsyncMock, return_value=embeddings),
            patch.object(pipeline.chunker, "split_into_parents") as mock_split,
        ):
            from backend.ingestion.chunker import ParentChunkData

            mock_parents = [
                ParentChunkData(
                    chunk_id="parent-001",
                    text="Partial content " * 50,
                    source_file="test.pdf",
                    page=1,
                    breadcrumb="Intro",
                    children=[
                        {"text": "Child 1", "point_id": "pt-001", "chunk_index": 0},
                    ],
                ),
            ]
            mock_split.return_value = mock_parents

            result = await pipeline.ingest_file(
                file_path="/tmp/corrupt.pdf",
                filename="corrupt.pdf",
                collection_id="col-test",
                document_id="doc-test",
                job_id="job-test",
                file_hash="test-hash",
            )

        # R4: process received chunks but still mark as failed
        assert result.status == "failed"
        assert result.chunks_processed > 0
        assert "Worker exited with code 2" in result.error
        # Parent chunks should still have been stored
        assert mock_db.insert_parent_chunk.called

    @pytest.mark.asyncio
    async def test_pipeline_exception_sets_failed(self, pipeline, mock_db, mock_qdrant):
        """Unexpected exception during pipeline -> job and document set to failed."""
        with patch(
            "backend.ingestion.pipeline.subprocess.Popen", side_effect=FileNotFoundError("Worker binary not found")
        ):
            result = await pipeline.ingest_file(
                file_path="/tmp/test.pdf",
                filename="test.pdf",
                collection_id="col-test",
                document_id="doc-test",
                job_id="job-test",
                file_hash="test-hash",
            )

        assert result.status == "failed"
        assert "Worker binary not found" in result.error
        # Verify job marked as failed
        failed_calls = [
            call for call in mock_db.update_ingestion_job.call_args_list if call.kwargs.get("status") == "failed"
        ]
        assert len(failed_calls) >= 1
        # Verify document marked as failed
        doc_failed = [
            call
            for call in mock_db.update_document_status.call_args_list
            if len(call.args) > 1 and call.args[1] == "failed"
        ]
        assert len(doc_failed) >= 1

    @pytest.mark.asyncio
    async def test_ingestion_result_dataclass(self):
        """IngestionResult fields have correct defaults."""
        result = IngestionResult(
            document_id="doc-1",
            job_id="job-1",
            status="completed",
        )
        assert result.chunks_processed == 0
        assert result.chunks_skipped == 0
        assert result.error is None


class TestUpsertBuffer:
    """Tests for UpsertBuffer add/flush/pending_count mechanics."""

    def test_add_returns_true_under_capacity(self):
        """add() returns True when buffer is under MAX_CAPACITY."""
        buf = UpsertBuffer()
        points = [{"id": f"pt-{i}", "vector": [0.1]} for i in range(10)]
        assert buf.add(points) is True
        assert buf.pending_count == 10

    def test_add_returns_false_at_capacity(self):
        """add() returns False when buffer reaches MAX_CAPACITY."""
        buf = UpsertBuffer()
        points = [{"id": f"pt-{i}", "vector": [0.1]} for i in range(1000)]
        assert buf.add(points) is False
        assert buf.pending_count == 1000

    def test_add_returns_false_over_capacity(self):
        """add() returns False when buffer exceeds MAX_CAPACITY."""
        buf = UpsertBuffer()
        buf.add([{"id": f"pt-{i}", "vector": [0.1]} for i in range(900)])
        result = buf.add([{"id": f"pt-{i}", "vector": [0.1]} for i in range(200)])
        assert result is False
        assert buf.pending_count == 1100

    def test_pending_count_starts_at_zero(self):
        """Empty buffer has pending_count == 0."""
        buf = UpsertBuffer()
        assert buf.pending_count == 0

    @pytest.mark.asyncio
    async def test_flush_upserts_all_points(self):
        """flush() calls qdrant.upsert and clears buffer."""
        buf = UpsertBuffer()
        points = [{"id": f"pt-{i}", "vector": [0.1]} for i in range(5)]
        buf.add(points)

        mock_qdrant = AsyncMock()
        mock_qdrant.upsert = AsyncMock()

        flushed = await buf.flush(mock_qdrant, "test-col")

        assert flushed == 5
        assert buf.pending_count == 0
        assert mock_qdrant.upsert.called

    @pytest.mark.asyncio
    async def test_flush_empty_buffer_returns_zero(self):
        """flush() on empty buffer returns 0 without calling qdrant."""
        buf = UpsertBuffer()
        mock_qdrant = AsyncMock()

        flushed = await buf.flush(mock_qdrant, "test-col")

        assert flushed == 0
        assert not mock_qdrant.upsert.called

    @pytest.mark.asyncio
    async def test_flush_batches_by_upsert_batch_size(self):
        """flush() respects settings.qdrant_upsert_batch_size for batching."""
        buf = UpsertBuffer()
        points = [{"id": f"pt-{i}", "vector": [0.1]} for i in range(120)]
        buf.add(points)

        mock_qdrant = AsyncMock()
        mock_qdrant.upsert = AsyncMock()

        # Default qdrant_upsert_batch_size is 50, so 120 points = 3 batches
        flushed = await buf.flush(mock_qdrant, "test-col")

        assert flushed == 120
        assert mock_qdrant.upsert.call_count == 3  # 50 + 50 + 20
        assert buf.pending_count == 0

    def test_max_capacity_is_1000(self):
        """MAX_CAPACITY class constant is 1000."""
        assert UpsertBuffer.MAX_CAPACITY == 1000


class TestFaultTolerance:
    """Tests for fault tolerance: validation skip, buffer-full pause,
    Ollama outage, worker crash handling."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.update_ingestion_job = AsyncMock()
        db.update_document_status = AsyncMock()
        db.insert_parent_chunk = AsyncMock()
        return db

    @pytest.fixture
    def mock_qdrant(self):
        qdrant = AsyncMock()
        qdrant.upsert = AsyncMock()
        return qdrant

    @pytest.fixture
    def pipeline(self, mock_db, mock_qdrant):
        return IngestionPipeline(db=mock_db, qdrant=mock_qdrant)

    def _make_parent_with_children(self, child_count=2):
        """Helper to create mock parents with N children."""
        from backend.ingestion.chunker import ParentChunkData

        return [
            ParentChunkData(
                chunk_id="parent-001",
                text="Parent text " * 50,
                source_file="test.pdf",
                page=1,
                breadcrumb="Chapter 1",
                children=[
                    {
                        "text": f"Child {i}",
                        "point_id": f"pt-{i:03d}",
                        "chunk_index": i,
                    }
                    for i in range(child_count)
                ],
            ),
        ]

    @pytest.mark.asyncio
    async def test_validation_skip_increments_chunks_skipped(self, pipeline, mock_db, mock_qdrant):
        """When embed_chunks returns None for some vectors, chunks_skipped is incremented."""
        raw_chunks = _sample_raw_chunks(2)
        mock_proc = _mock_popen(raw_chunks, returncode=0)

        # 3 children: 1 valid, 1 None (skipped), 1 valid
        embeddings_with_skip = (
            [[0.1] * 384, None, [0.2] * 384],
            1,  # 1 skipped
        )

        with (
            patch("backend.ingestion.pipeline.subprocess.Popen", return_value=mock_proc),
            patch.object(
                pipeline.embedder,
                "embed_chunks",
                new_callable=AsyncMock,
                return_value=embeddings_with_skip,
            ),
            patch.object(pipeline.chunker, "split_into_parents") as mock_split,
        ):
            mock_split.return_value = self._make_parent_with_children(3)

            result = await pipeline.ingest_file(
                file_path="/tmp/test.pdf",
                filename="test.pdf",
                collection_id="col-test",
                document_id="doc-test",
                job_id="job-test",
                file_hash="test-hash",
            )

        assert result.status == "completed"
        assert result.chunks_skipped == 1
        # Only 2 valid points should be upserted
        assert result.chunks_processed == 2

    @pytest.mark.asyncio
    async def test_qdrant_outage_buffers_and_pauses(self, pipeline, mock_db, mock_qdrant):
        """Qdrant upsert failure buffers points; when buffer is full, job pauses."""
        raw_chunks = _sample_raw_chunks(2)
        mock_proc = _mock_popen(raw_chunks, returncode=0)

        embeddings = _valid_embeddings(2)

        # Make qdrant.upsert fail on first call, succeed on second (flush)
        call_count = 0

        async def upsert_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Qdrant down")
            # Succeed on subsequent calls (flush)

        mock_qdrant.upsert = AsyncMock(side_effect=upsert_side_effect)

        with (
            patch("backend.ingestion.pipeline.subprocess.Popen", return_value=mock_proc),
            patch.object(
                pipeline.embedder,
                "embed_chunks",
                new_callable=AsyncMock,
                return_value=embeddings,
            ),
            patch.object(pipeline.chunker, "split_into_parents") as mock_split,
            patch("backend.ingestion.pipeline.asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_split.return_value = self._make_parent_with_children(2)

            result = await pipeline.ingest_file(
                file_path="/tmp/test.pdf",
                filename="test.pdf",
                collection_id="col-test",
                document_id="doc-test",
                job_id="job-test",
                file_hash="test-hash",
            )

        assert result.status == "completed"
        assert result.chunks_processed > 0

    @pytest.mark.asyncio
    async def test_buffer_full_triggers_pause_status(self, pipeline, mock_db, mock_qdrant):
        """When UpsertBuffer is full, job status transitions to 'paused'."""
        # Create enough points to fill the buffer (MAX_CAPACITY=1000)
        from backend.ingestion.chunker import ParentChunkData

        raw_chunks = _sample_raw_chunks(2)
        mock_proc = _mock_popen(raw_chunks, returncode=0)

        # Create many children to generate >1000 points
        many_children = [{"text": f"Child {i}", "point_id": f"pt-{i:04d}", "chunk_index": i} for i in range(1050)]
        mock_parents = [
            ParentChunkData(
                chunk_id="parent-001",
                text="Parent " * 50,
                source_file="test.pdf",
                page=1,
                breadcrumb="Ch1",
                children=many_children,
            )
        ]

        embeddings = ([[0.1] * 384 for _ in range(1050)], 0)

        # Qdrant fails for all initial upserts, then succeeds on flush
        fail_count = 0

        async def upsert_fail_then_ok(*args, **kwargs):
            nonlocal fail_count
            fail_count += 1
            if fail_count <= 21:  # 1050/50 = 21 batches, all fail initially
                raise ConnectionError("Qdrant down")

        mock_qdrant.upsert = AsyncMock(side_effect=upsert_fail_then_ok)

        with (
            patch("backend.ingestion.pipeline.subprocess.Popen", return_value=mock_proc),
            patch.object(
                pipeline.embedder,
                "embed_chunks",
                new_callable=AsyncMock,
                return_value=embeddings,
            ),
            patch.object(pipeline.chunker, "split_into_parents", return_value=mock_parents),
            patch("backend.ingestion.pipeline.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await pipeline.ingest_file(
                file_path="/tmp/test.pdf",
                filename="test.pdf",
                collection_id="col-test",
                document_id="doc-test",
                job_id="job-test",
                file_hash="test-hash",
            )

        # Verify 'paused' status was set at some point
        job_statuses = [
            call.kwargs.get("status") for call in mock_db.update_ingestion_job.call_args_list if "status" in call.kwargs
        ]
        assert "paused" in job_statuses
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_ollama_outage_pauses_and_retries(self, pipeline, mock_db, mock_qdrant):
        """CircuitOpenError from embed_chunks pauses job, then resumes on retry."""
        from backend.errors import CircuitOpenError

        raw_chunks = _sample_raw_chunks(2)
        mock_proc = _mock_popen(raw_chunks, returncode=0)

        call_count = 0

        async def embed_fail_then_ok(texts):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise CircuitOpenError("Ollama circuit open")
            return _valid_embeddings(len(texts))

        with (
            patch("backend.ingestion.pipeline.subprocess.Popen", return_value=mock_proc),
            patch.object(
                pipeline.embedder,
                "embed_chunks",
                side_effect=embed_fail_then_ok,
            ),
            patch.object(pipeline.chunker, "split_into_parents") as mock_split,
            patch("backend.ingestion.pipeline.asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_split.return_value = self._make_parent_with_children(2)

            result = await pipeline.ingest_file(
                file_path="/tmp/test.pdf",
                filename="test.pdf",
                collection_id="col-test",
                document_id="doc-test",
                job_id="job-test",
                file_hash="test-hash",
            )

        # Verify paused status was set
        job_statuses = [
            call.kwargs.get("status") for call in mock_db.update_ingestion_job.call_args_list if "status" in call.kwargs
        ]
        assert "paused" in job_statuses
        assert result.status == "completed"
        assert result.chunks_processed > 0

    @pytest.mark.asyncio
    async def test_ollama_httpx_connect_error_pauses(self, pipeline, mock_db, mock_qdrant):
        """httpx.ConnectError from embed_chunks also triggers pause."""
        import httpx

        raw_chunks = _sample_raw_chunks(2)
        mock_proc = _mock_popen(raw_chunks, returncode=0)

        call_count = 0

        async def embed_connect_fail(texts):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.ConnectError("Connection refused")
            return _valid_embeddings(len(texts))

        with (
            patch("backend.ingestion.pipeline.subprocess.Popen", return_value=mock_proc),
            patch.object(
                pipeline.embedder,
                "embed_chunks",
                side_effect=embed_connect_fail,
            ),
            patch.object(pipeline.chunker, "split_into_parents") as mock_split,
            patch("backend.ingestion.pipeline.asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_split.return_value = self._make_parent_with_children(2)

            result = await pipeline.ingest_file(
                file_path="/tmp/test.pdf",
                filename="test.pdf",
                collection_id="col-test",
                document_id="doc-test",
                job_id="job-test",
                file_hash="test-hash",
            )

        job_statuses = [
            call.kwargs.get("status") for call in mock_db.update_ingestion_job.call_args_list if "status" in call.kwargs
        ]
        assert "paused" in job_statuses
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_worker_crash_processes_received_chunks(self, pipeline, mock_db, mock_qdrant):
        """Worker exits non-zero but produced chunks -> process them, then set failed."""
        raw_chunks = _sample_raw_chunks(2)
        mock_proc = _mock_popen(raw_chunks, returncode=2, stderr="Crash on page 5")

        embeddings = _valid_embeddings(5)

        with (
            patch("backend.ingestion.pipeline.subprocess.Popen", return_value=mock_proc),
            patch.object(
                pipeline.embedder,
                "embed_chunks",
                new_callable=AsyncMock,
                return_value=embeddings,
            ),
            patch.object(pipeline.chunker, "split_into_parents") as mock_split,
        ):
            mock_split.return_value = self._make_parent_with_children(2)

            result = await pipeline.ingest_file(
                file_path="/tmp/crash.pdf",
                filename="crash.pdf",
                collection_id="col-test",
                document_id="doc-test",
                job_id="job-test",
                file_hash="test-hash",
            )

        assert result.status == "failed"
        assert result.chunks_processed > 0
        assert "Worker exited with code 2" in result.error
        assert "Crash on page 5" in result.error

        # Verify document status set to failed
        doc_statuses = [call.args[1] for call in mock_db.update_document_status.call_args_list if len(call.args) > 1]
        assert "failed" in doc_statuses

        # Verify parent chunks were still stored
        assert mock_db.insert_parent_chunk.called

        # Verify chunks_processed was recorded in job update
        failed_job_calls = [
            call for call in mock_db.update_ingestion_job.call_args_list if call.kwargs.get("status") == "failed"
        ]
        assert len(failed_job_calls) >= 1
        assert failed_job_calls[0].kwargs.get("chunks_processed", 0) > 0

    @pytest.mark.asyncio
    async def test_worker_crash_no_output_sets_failed(self, pipeline, mock_db, mock_qdrant):
        """Worker crashes with no output -> failed status, no chunks processed."""
        mock_proc = _mock_popen([], returncode=1, stderr="File not found")

        with patch("backend.ingestion.pipeline.subprocess.Popen", return_value=mock_proc):
            result = await pipeline.ingest_file(
                file_path="/tmp/missing.pdf",
                filename="missing.pdf",
                collection_id="col-test",
                document_id="doc-test",
                job_id="job-test",
                file_hash="test-hash",
            )

        assert result.status == "failed"
        assert result.chunks_processed == 0
        assert "Worker exited with code 1" in result.error
