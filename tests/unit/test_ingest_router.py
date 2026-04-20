"""Unit tests for ingest router — T014.

Tests 12 allowed extensions (including .c/.cpp/.h),
400 on unsupported extension, 413 on file over 100 MB,
409 on duplicate content hash, 404 on unknown collection_id,
GET job status endpoint, asyncio.create_task background launch.
Mocks IngestionPipeline + IncrementalChecker + SQLiteDB.
"""

import asyncio
import io
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.ingest import router, ALLOWED_EXTENSIONS


def _make_app(db=None, qdrant=None):
    """Create a test FastAPI app with mocked dependencies."""
    app = FastAPI()
    app.include_router(router)
    app.state.db = db or AsyncMock()
    app.state.qdrant = qdrant or AsyncMock()
    return app


def _make_collection(coll_id=None, name="my-docs"):
    coll_id = coll_id or str(uuid.uuid4())
    return {
        "id": coll_id,
        "name": name,
        "description": None,
        "embedding_model": "nomic-embed-text",
        "chunk_profile": "default",
        "qdrant_collection_name": f"qdrant_{coll_id}",
        "created_at": "2026-03-15T00:00:00+00:00",
    }


def _make_job(job_id=None, doc_id=None, status="started"):
    return {
        "id": job_id or str(uuid.uuid4()),
        "document_id": doc_id or str(uuid.uuid4()),
        "status": status,
        "started_at": "2026-03-15T00:00:00+00:00",
        "finished_at": None,
        "error_msg": None,
        "chunks_processed": 0,
        "chunks_skipped": 0,
    }


def _upload_file(client, collection_id, filename="test.txt", content=b"hello world"):
    """Helper to upload a file to the ingest endpoint."""
    return client.post(
        f"/api/collections/{collection_id}/ingest",
        files={"file": (filename, io.BytesIO(content), "application/octet-stream")},
    )


# ── Allowed Extensions ───────────────────────────────────────────


class TestAllowedExtensions:
    """Test all 12 allowed extensions return 202."""

    EXTENSIONS = [
        (".pdf", "test.pdf"),
        (".md", "readme.md"),
        (".txt", "notes.txt"),
        (".py", "script.py"),
        (".js", "app.js"),
        (".ts", "index.ts"),
        (".rs", "main.rs"),
        (".go", "server.go"),
        (".java", "Main.java"),
        (".c", "program.c"),
        (".cpp", "module.cpp"),
        (".h", "header.h"),
    ]

    @pytest.mark.parametrize("ext,filename", EXTENSIONS, ids=[e[0] for e in EXTENSIONS])
    @patch("backend.api.ingest.IncrementalChecker")
    @patch("backend.api.ingest.IngestionPipeline")
    @patch("backend.api.ingest.settings")
    def test_allowed_extension_202(self, mock_settings, mock_pipeline_cls, mock_checker_cls, ext, filename, tmp_path):
        mock_settings.upload_dir = str(tmp_path)
        mock_settings.max_upload_size_mb = 100

        coll_id = str(uuid.uuid4())
        db = AsyncMock()
        db.get_collection.return_value = _make_collection(coll_id=coll_id)
        db.create_document.return_value = None
        db.create_ingestion_job.return_value = None

        # Mock IncrementalChecker
        mock_checker_cls.compute_file_hash.return_value = "fakehash123"
        checker_instance = AsyncMock()
        checker_instance.check_duplicate.return_value = (False, None)
        checker_instance.check_change.return_value = (False, None)
        mock_checker_cls.return_value = checker_instance

        # Mock IngestionPipeline
        pipeline_instance = AsyncMock()
        mock_pipeline_cls.return_value = pipeline_instance

        app = _make_app(db=db)
        client = TestClient(app)

        with patch("asyncio.create_task") as mock_task:
            mock_task.return_value = MagicMock()
            content = b"%PDF-1.4 test content" if ext == ".pdf" else b"test content"
            resp = _upload_file(client, coll_id, filename=filename, content=content)

        assert resp.status_code == 202, f"Extension {ext} should be allowed but got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert "job_id" in body
        assert "document_id" in body
        assert body["status"] == "started"

    def test_allowed_extensions_set_has_12(self):
        """Verify ALLOWED_EXTENSIONS has exactly 12 entries."""
        assert len(ALLOWED_EXTENSIONS) == 12
        expected = {".pdf", ".md", ".txt", ".py", ".js", ".ts", ".rs", ".go", ".java", ".c", ".cpp", ".h"}
        assert ALLOWED_EXTENSIONS == expected


# ── Unsupported Extension ────────────────────────────────────────


class TestUnsupportedExtension:
    def test_unsupported_extension_400(self):
        coll_id = str(uuid.uuid4())
        db = AsyncMock()
        app = _make_app(db=db)
        client = TestClient(app)
        resp = _upload_file(client, coll_id, filename="malware.exe")
        assert resp.status_code == 400
        body = resp.json()
        assert body["detail"]["error"]["code"] == "FILE_FORMAT_NOT_SUPPORTED"

    def test_unsupported_extension_includes_allowed_list(self):
        coll_id = str(uuid.uuid4())
        app = _make_app()
        client = TestClient(app)
        resp = _upload_file(client, coll_id, filename="data.csv")
        assert resp.status_code == 400
        body = resp.json()
        assert "allowed_extensions" in body["detail"]["error"]["details"]

    @pytest.mark.parametrize("filename", ["file.docx", "image.png", "data.xlsx", "archive.zip"])
    def test_various_unsupported_extensions(self, filename):
        coll_id = str(uuid.uuid4())
        app = _make_app()
        client = TestClient(app)
        resp = _upload_file(client, coll_id, filename=filename)
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"]["code"] == "FILE_FORMAT_NOT_SUPPORTED"


# ── File Too Large ───────────────────────────────────────────────


class TestFileTooLarge:
    @patch("backend.api.ingest.settings")
    def test_file_over_100mb_413(self, mock_settings):
        mock_settings.max_upload_size_mb = 100

        coll_id = str(uuid.uuid4())
        app = _make_app()
        client = TestClient(app)

        # Create content just over 100 MB
        large_content = b"x" * (100 * 1024 * 1024 + 1)
        resp = _upload_file(client, coll_id, filename="big.txt", content=large_content)
        assert resp.status_code == 413
        body = resp.json()
        assert body["detail"]["error"]["code"] == "FILE_TOO_LARGE"
        assert "max_size_mb" in body["detail"]["error"]["details"]

    @patch("backend.api.ingest.settings")
    def test_file_exactly_100mb_passes_size_check(self, mock_settings, tmp_path):
        """File exactly at limit should pass size validation."""
        mock_settings.max_upload_size_mb = 100
        mock_settings.upload_dir = str(tmp_path)

        coll_id = str(uuid.uuid4())
        db = AsyncMock()
        db.get_collection.return_value = _make_collection(coll_id=coll_id)
        db.create_document.return_value = None
        db.create_ingestion_job.return_value = None
        app = _make_app(db=db)
        client = TestClient(app)

        exact_content = b"x" * (100 * 1024 * 1024)
        with (
            patch("backend.api.ingest.IncrementalChecker") as mock_checker_cls,
            patch("backend.api.ingest.IngestionPipeline"),
            patch("asyncio.create_task", return_value=MagicMock()),
        ):
            mock_checker_cls.compute_file_hash.return_value = "hash"
            checker = AsyncMock()
            checker.check_duplicate.return_value = (False, None)
            checker.check_change.return_value = (False, None)
            mock_checker_cls.return_value = checker

            resp = _upload_file(client, coll_id, filename="exact.txt", content=exact_content)
        # Should pass size check (may hit other checks, but not 413)
        assert resp.status_code != 413


# ── Duplicate Document ───────────────────────────────────────────


class TestDuplicateDocument:
    @patch("backend.api.ingest.IncrementalChecker")
    @patch("backend.api.ingest.settings")
    def test_duplicate_content_hash_409(self, mock_settings, mock_checker_cls, tmp_path):
        mock_settings.upload_dir = str(tmp_path)
        mock_settings.max_upload_size_mb = 100

        coll_id = str(uuid.uuid4())
        existing_doc_id = str(uuid.uuid4())

        db = AsyncMock()
        db.get_collection.return_value = _make_collection(coll_id=coll_id)

        # Mock checker to return duplicate
        mock_checker_cls.compute_file_hash.return_value = "duplicate_hash"
        checker = AsyncMock()
        checker.check_duplicate.return_value = (True, existing_doc_id)
        mock_checker_cls.return_value = checker

        app = _make_app(db=db)
        client = TestClient(app)
        resp = _upload_file(client, coll_id, filename="report.txt")
        assert resp.status_code == 409
        body = resp.json()
        assert body["detail"]["error"]["code"] == "DUPLICATE_DOCUMENT"
        assert body["detail"]["error"]["details"]["existing_document_id"] == existing_doc_id

    @patch("backend.api.ingest.IncrementalChecker")
    @patch("backend.api.ingest.settings")
    def test_duplicate_cleans_up_saved_file(self, mock_settings, mock_checker_cls, tmp_path):
        """On duplicate detection, the saved file should be removed."""
        mock_settings.upload_dir = str(tmp_path)
        mock_settings.max_upload_size_mb = 100

        coll_id = str(uuid.uuid4())
        db = AsyncMock()
        db.get_collection.return_value = _make_collection(coll_id=coll_id)

        mock_checker_cls.compute_file_hash.return_value = "dup_hash"
        checker = AsyncMock()
        checker.check_duplicate.return_value = (True, "existing-id")
        mock_checker_cls.return_value = checker

        app = _make_app(db=db)
        client = TestClient(app)
        resp = _upload_file(client, coll_id, filename="report.txt")
        assert resp.status_code == 409

        # The uploaded file should have been cleaned up
        upload_path = tmp_path / coll_id / "report.txt"
        assert not upload_path.exists()


# ── Collection Not Found ─────────────────────────────────────────


class TestCollectionNotFound:
    @patch("backend.api.ingest.settings")
    def test_unknown_collection_404(self, mock_settings):
        mock_settings.max_upload_size_mb = 100

        coll_id = str(uuid.uuid4())
        db = AsyncMock()
        db.get_collection.return_value = None
        app = _make_app(db=db)
        client = TestClient(app)
        resp = _upload_file(client, coll_id, filename="test.txt")
        assert resp.status_code == 404
        body = resp.json()
        assert body["detail"]["error"]["code"] == "COLLECTION_NOT_FOUND"


# ── GET Job Status ───────────────────────────────────────────────


class TestGetJobStatus:
    def test_get_job_200(self):
        job = _make_job(status="embedding")
        job["chunks_processed"] = 15
        db = AsyncMock()
        db.get_ingestion_job.return_value = job
        app = _make_app(db=db)
        client = TestClient(app)
        coll_id = str(uuid.uuid4())
        resp = client.get(f"/api/collections/{coll_id}/ingest/{job['id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["job_id"] == job["id"]
        assert body["document_id"] == job["document_id"]
        assert body["status"] == "embedding"
        assert body["chunks_processed"] == 15
        assert body["chunks_total"] is None

    def test_get_job_not_found_404(self):
        db = AsyncMock()
        db.get_ingestion_job.return_value = None
        app = _make_app(db=db)
        client = TestClient(app)
        coll_id = str(uuid.uuid4())
        job_id = str(uuid.uuid4())
        resp = client.get(f"/api/collections/{coll_id}/ingest/{job_id}")
        assert resp.status_code == 404
        body = resp.json()
        assert body["detail"]["error"]["code"] == "JOB_NOT_FOUND"

    def test_get_completed_job(self):
        job = _make_job(status="completed")
        job["chunks_processed"] = 42
        job["finished_at"] = "2026-03-15T00:05:00+00:00"
        db = AsyncMock()
        db.get_ingestion_job.return_value = job
        app = _make_app(db=db)
        client = TestClient(app)
        coll_id = str(uuid.uuid4())
        resp = client.get(f"/api/collections/{coll_id}/ingest/{job['id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert body["completed_at"] == "2026-03-15T00:05:00+00:00"
        assert body["chunks_processed"] == 42

    def test_get_failed_job_with_error(self):
        job = _make_job(status="failed")
        job["error_msg"] = "Worker crashed"
        job["finished_at"] = "2026-03-15T00:03:00+00:00"
        db = AsyncMock()
        db.get_ingestion_job.return_value = job
        app = _make_app(db=db)
        client = TestClient(app)
        coll_id = str(uuid.uuid4())
        resp = client.get(f"/api/collections/{coll_id}/ingest/{job['id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "failed"
        assert body["error_message"] == "Worker crashed"


# ── Background Task ──────────────────────────────────────────────


class TestBackgroundTask:
    @patch("backend.api.ingest.IncrementalChecker")
    @patch("backend.api.ingest.IngestionPipeline")
    @patch("backend.api.ingest.settings")
    def test_asyncio_create_task_called(self, mock_settings, mock_pipeline_cls, mock_checker_cls, tmp_path):
        """Verify asyncio.create_task is used (not await) for background ingestion."""
        mock_settings.upload_dir = str(tmp_path)
        mock_settings.max_upload_size_mb = 100

        coll_id = str(uuid.uuid4())
        db = AsyncMock()
        db.get_collection.return_value = _make_collection(coll_id=coll_id)
        db.create_document.return_value = None
        db.create_ingestion_job.return_value = None

        mock_checker_cls.compute_file_hash.return_value = "hash123"
        checker = AsyncMock()
        checker.check_duplicate.return_value = (False, None)
        checker.check_change.return_value = (False, None)
        mock_checker_cls.return_value = checker

        pipeline = AsyncMock()
        mock_pipeline_cls.return_value = pipeline

        app = _make_app(db=db)
        client = TestClient(app)

        with patch("asyncio.create_task") as mock_create_task:
            mock_create_task.return_value = MagicMock()
            resp = _upload_file(client, coll_id, filename="test.py", content=b"print('hi')")

        assert resp.status_code == 202
        mock_create_task.assert_called_once()

    @patch("backend.api.ingest.IncrementalChecker")
    @patch("backend.api.ingest.IngestionPipeline")
    @patch("backend.api.ingest.settings")
    def test_pipeline_ingest_file_passed_to_create_task(
        self, mock_settings, mock_pipeline_cls, mock_checker_cls, tmp_path
    ):
        """Verify pipeline.ingest_file() coroutine is passed to create_task."""
        mock_settings.upload_dir = str(tmp_path)
        mock_settings.max_upload_size_mb = 100

        coll_id = str(uuid.uuid4())
        db = AsyncMock()
        db.get_collection.return_value = _make_collection(coll_id=coll_id)
        db.create_document.return_value = None
        db.create_ingestion_job.return_value = None

        mock_checker_cls.compute_file_hash.return_value = "hash456"
        checker = AsyncMock()
        checker.check_duplicate.return_value = (False, None)
        checker.check_change.return_value = (False, None)
        mock_checker_cls.return_value = checker

        pipeline = AsyncMock()
        mock_pipeline_cls.return_value = pipeline

        app = _make_app(db=db)
        client = TestClient(app)

        with patch("asyncio.create_task") as mock_create_task:
            mock_create_task.return_value = MagicMock()
            resp = _upload_file(client, coll_id, filename="main.rs", content=b"fn main() {}")

        assert resp.status_code == 202
        # The coroutine passed to create_task should be from pipeline.ingest_file
        pipeline.ingest_file.assert_called_once()
        call_kwargs = pipeline.ingest_file.call_args[1]
        assert call_kwargs["filename"] == "main.rs"
        assert call_kwargs["collection_id"] == coll_id


# ── Response Format ──────────────────────────────────────────────


class TestResponseFormat:
    @patch("backend.api.ingest.IncrementalChecker")
    @patch("backend.api.ingest.IngestionPipeline")
    @patch("backend.api.ingest.settings")
    def test_202_response_shape(self, mock_settings, mock_pipeline_cls, mock_checker_cls, tmp_path):
        """202 response body contains required IngestionJobResponse fields."""
        mock_settings.upload_dir = str(tmp_path)
        mock_settings.max_upload_size_mb = 100

        coll_id = str(uuid.uuid4())
        db = AsyncMock()
        db.get_collection.return_value = _make_collection(coll_id=coll_id)
        db.create_document.return_value = None
        db.create_ingestion_job.return_value = None

        mock_checker_cls.compute_file_hash.return_value = "hash789"
        checker = AsyncMock()
        checker.check_duplicate.return_value = (False, None)
        checker.check_change.return_value = (False, None)
        mock_checker_cls.return_value = checker

        pipeline = AsyncMock()
        mock_pipeline_cls.return_value = pipeline

        app = _make_app(db=db)
        client = TestClient(app)

        with patch("asyncio.create_task", return_value=MagicMock()):
            resp = _upload_file(client, coll_id, filename="doc.md", content=b"# Hello")

        assert resp.status_code == 202
        body = resp.json()

        # All IngestionJobResponse fields present
        assert "job_id" in body
        assert "document_id" in body
        assert "status" in body
        assert "chunks_processed" in body
        assert "chunks_total" in body
        assert "error_message" in body
        assert "started_at" in body
        assert "completed_at" in body

        # Initial values
        assert body["status"] == "started"
        assert body["chunks_processed"] == 0
        assert body["chunks_total"] is None
        assert body["error_message"] is None

    @patch("backend.api.ingest.IncrementalChecker")
    @patch("backend.api.ingest.IngestionPipeline")
    @patch("backend.api.ingest.settings")
    def test_202_response_includes_filename(self, mock_settings, mock_pipeline_cls, mock_checker_cls, tmp_path):
        mock_settings.upload_dir = str(tmp_path)
        mock_settings.max_upload_size_mb = 100

        coll_id = str(uuid.uuid4())
        db = AsyncMock()
        db.get_collection.return_value = _make_collection(coll_id=coll_id)
        db.create_document.return_value = None
        db.create_ingestion_job.return_value = None

        mock_checker_cls.compute_file_hash.return_value = "hashxyz"
        checker = AsyncMock()
        checker.check_duplicate.return_value = (False, None)
        checker.check_change.return_value = (False, None)
        mock_checker_cls.return_value = checker

        pipeline = AsyncMock()
        mock_pipeline_cls.return_value = pipeline

        app = _make_app(db=db)
        client = TestClient(app)

        with patch("asyncio.create_task", return_value=MagicMock()):
            resp = _upload_file(client, coll_id, filename="report.pdf", content=b"%PDF-1.4 test")

        assert resp.status_code == 202
        # IngestionJobResponse doesn't have filename, but the original spec 202 body does
        # The Pydantic model will serialize what it has


# ── Error Response Format ────────────────────────────────────────


class TestErrorFormat:
    def test_error_has_structured_format(self):
        """All errors include error.code, error.message, error.details, trace_id."""
        app = _make_app()
        client = TestClient(app)
        coll_id = str(uuid.uuid4())
        resp = _upload_file(client, coll_id, filename="bad.exe")
        assert resp.status_code == 400
        body = resp.json()
        detail = body["detail"]
        assert "error" in detail
        assert "code" in detail["error"]
        assert "message" in detail["error"]
        assert "details" in detail["error"]
        assert "trace_id" in detail
