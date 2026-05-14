"""Unit tests for ingest API endpoint — spec-06 ingestion pipeline.

Updated for spec-08: ingest endpoint moved from documents.py to ingest.py,
error format changed to {error: {code, message, details}, trace_id}.
"""

import io
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.ingest import router, ALLOWED_EXTENSIONS as SUPPORTED_FORMATS


@contextmanager
def _mock_ingest_deps():
    """Patch all imports used by the ingest endpoint.

    The endpoint imports IncrementalChecker and IngestionPipeline at module level.
    We mock them so tests can reach the 202 response without real file I/O.
    """
    mock_checker_cls = MagicMock()
    mock_checker_inst = MagicMock()
    mock_checker_cls.return_value = mock_checker_inst
    mock_checker_cls.compute_file_hash = MagicMock(return_value="abc123fakehash")
    mock_checker_inst.check_duplicate = AsyncMock(return_value=(False, None))
    mock_checker_inst.check_change = AsyncMock(return_value=(False, None))

    mock_pipeline_cls = MagicMock()
    mock_pipeline_inst = MagicMock()
    mock_pipeline_cls.return_value = mock_pipeline_inst
    mock_pipeline_inst.ingest_file = AsyncMock()

    with (
        patch("asyncio.create_task", side_effect=lambda coro: coro.close()),
        patch("backend.api.ingest.IncrementalChecker", mock_checker_cls),
        patch("backend.api.ingest.IngestionPipeline", mock_pipeline_cls),
        patch("backend.api.ingest.Path.mkdir"),
        patch("builtins.open", MagicMock()),
    ):
        yield mock_checker_inst, mock_pipeline_inst


@pytest.fixture
def app():
    """Create a test FastAPI app with mocked state."""
    app = FastAPI()
    app.include_router(router)

    # Mock app state
    mock_db = AsyncMock()
    mock_db.get_collection = AsyncMock(
        return_value={"id": "col-test", "name": "Test", "qdrant_collection_name": "qdrant_col_test"}
    )
    mock_db.create_document = AsyncMock()
    mock_db.create_ingestion_job = AsyncMock()
    mock_db.update_document = AsyncMock()

    mock_qdrant = AsyncMock()

    app.state.db = mock_db
    app.state.qdrant = mock_qdrant

    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_db(app):
    """Access mock db from app state."""
    return app.state.db


class TestIngestEndpoint:
    """Tests for POST /api/collections/{collection_id}/ingest endpoint."""

    def test_valid_pdf_returns_202(self, client, mock_db):
        """Valid PDF file upload returns 202 with document_id and job_id."""
        file_content = b"%PDF-1.4 test content"
        with _mock_ingest_deps():
            response = client.post(
                "/api/collections/col-test/ingest",
                files={"file": ("report.pdf", io.BytesIO(file_content), "application/pdf")},
            )

        assert response.status_code == 202
        data = response.json()
        assert "document_id" in data
        assert "job_id" in data
        assert data["status"] == "started"

    def test_valid_markdown_returns_202(self, client, mock_db):
        """Valid markdown file returns 202."""
        file_content = b"# Test Document\n\nSome content."
        with _mock_ingest_deps():
            response = client.post(
                "/api/collections/col-test/ingest",
                files={"file": ("readme.md", io.BytesIO(file_content), "text/markdown")},
            )

        assert response.status_code == 202

    def test_valid_python_file_returns_202(self, client, mock_db):
        """Valid Python file returns 202."""
        file_content = b"def hello():\n    print('hello')\n"
        with _mock_ingest_deps():
            response = client.post(
                "/api/collections/col-test/ingest",
                files={"file": ("main.py", io.BytesIO(file_content), "text/x-python")},
            )

        assert response.status_code == 202

    def test_unsupported_extension_returns_400(self, client):
        """Unsupported file type (.exe) returns 400 FILE_FORMAT_NOT_SUPPORTED."""
        file_content = b"binary content"
        response = client.post(
            "/api/collections/col-test/ingest",
            files={"file": ("malware.exe", io.BytesIO(file_content), "application/octet-stream")},
        )

        assert response.status_code == 400
        data = response.json()["detail"]
        assert data["error"]["code"] == "FILE_FORMAT_NOT_SUPPORTED"
        assert ".exe" in data["error"]["message"]

    def test_unsupported_docx_returns_400(self, client):
        """Unsupported .docx returns 400 FILE_FORMAT_NOT_SUPPORTED."""
        file_content = b"PK\x03\x04 fake docx"
        response = client.post(
            "/api/collections/col-test/ingest",
            files={"file": ("doc.docx", io.BytesIO(file_content), "application/vnd.openxmlformats")},
        )

        assert response.status_code == 400
        data = response.json()["detail"]
        assert data["error"]["code"] == "FILE_FORMAT_NOT_SUPPORTED"

    def test_oversized_file_returns_413(self, client, mock_db):
        """File exceeding max_upload_size_mb returns 413."""
        with patch("backend.api.ingest.settings") as mock_settings:
            mock_settings.max_upload_size_mb = 1  # 1MB limit for test speed
            mock_settings.upload_dir = "/tmp/test-uploads"
            file_content = b"x" * (2 * 1024 * 1024)  # 2MB
            response = client.post(
                "/api/collections/col-test/ingest",
                files={"file": ("big.pdf", io.BytesIO(file_content), "application/pdf")},
            )

        assert response.status_code == 413
        data = response.json()["detail"]
        assert data["error"]["code"] == "FILE_TOO_LARGE"

    def test_missing_collection_returns_404(self, client, mock_db):
        """Non-existent collection returns 404 COLLECTION_NOT_FOUND."""
        mock_db.get_collection = AsyncMock(return_value=None)

        file_content = b"test content"
        response = client.post(
            "/api/collections/col-nonexistent/ingest",
            files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        )

        assert response.status_code == 404
        data = response.json()["detail"]
        assert data["error"]["code"] == "COLLECTION_NOT_FOUND"
        assert "col-nonexistent" in data["error"]["message"]

    def test_response_body_matches_contract(self, client, mock_db):
        """Response body matches IngestionJobResponse contract schema."""
        file_content = b"test content"
        with _mock_ingest_deps():
            response = client.post(
                "/api/collections/col-test/ingest",
                files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
            )

        assert response.status_code == 202
        data = response.json()
        # IngestionJobResponse fields
        required_fields = {"document_id", "job_id", "status"}
        assert required_fields.issubset(data.keys())
        assert data["status"] == "started"
        assert isinstance(data["document_id"], str)
        assert isinstance(data["job_id"], str)

    def test_supported_formats_has_12_types(self):
        """SUPPORTED_FORMATS contains exactly 12 file types."""
        expected = {
            ".pdf",
            ".md",
            ".txt",
            ".py",
            ".js",
            ".ts",
            ".rs",
            ".go",
            ".java",
            ".c",
            ".cpp",
            ".h",
        }
        assert SUPPORTED_FORMATS == expected
        assert len(SUPPORTED_FORMATS) == 12

    def test_all_supported_extensions_accepted(self, client, mock_db):
        """All 12 supported file types return 202."""
        for ext in SUPPORTED_FORMATS:
            mock_db.get_collection = AsyncMock(
        return_value={"id": "col-test", "name": "Test", "qdrant_collection_name": "qdrant_col_test"}
    )
            mock_db.create_document = AsyncMock()
            mock_db.create_ingestion_job = AsyncMock()

            file_content = b"%PDF-1.4 test content" if ext == ".pdf" else b"test content for " + ext.encode()
            mime = "application/pdf" if ext == ".pdf" else "application/octet-stream"
            with _mock_ingest_deps():
                response = client.post(
                    "/api/collections/col-test/ingest",
                    files={"file": (f"test{ext}", io.BytesIO(file_content), mime)},
                )

            assert response.status_code == 202, f"Extension {ext} should be accepted but got {response.status_code}"


class TestUnsupportedFormats:
    """Verify unsupported file types are rejected with 400 FILE_FORMAT_NOT_SUPPORTED."""

    @pytest.mark.parametrize(
        "filename,mime",
        [
            ("archive.zip", "application/zip"),
            ("spreadsheet.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ("binary.exe", "application/octet-stream"),
            ("word.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ],
    )
    def test_unsupported_type_rejected(self, client, filename, mime):
        """Unsupported file types (.zip, .xlsx, .exe, .docx) return 400."""
        response = client.post(
            "/api/collections/col-test/ingest",
            files={"file": (filename, io.BytesIO(b"fake content"), mime)},
        )
        assert response.status_code == 400
        data = response.json()["detail"]
        assert data["error"]["code"] == "FILE_FORMAT_NOT_SUPPORTED"
        ext = Path(filename).suffix
        assert ext in data["error"]["message"]

    def test_no_extension_rejected(self, client):
        """File with no extension is rejected."""
        response = client.post(
            "/api/collections/col-test/ingest",
            files={"file": ("Makefile", io.BytesIO(b"all: build"), "text/plain")},
        )
        assert response.status_code == 400

    def test_oversized_file_returns_413(self, client, mock_db):
        """File exceeding max_upload_size_mb returns 413 FILE_TOO_LARGE."""
        with patch("backend.api.ingest.settings") as mock_settings:
            mock_settings.max_upload_size_mb = 1  # 1MB limit for test speed
            mock_settings.upload_dir = "/tmp/test-uploads"
            file_content = b"x" * (2 * 1024 * 1024)  # 2MB
            response = client.post(
                "/api/collections/col-test/ingest",
                files={"file": ("big.pdf", io.BytesIO(file_content), "application/pdf")},
            )
        assert response.status_code == 413
        data = response.json()["detail"]
        assert data["error"]["code"] == "FILE_TOO_LARGE"


class TestEdgeCases:
    """Edge case tests for ingestion API."""

    def test_zero_content_pdf_completes_via_pipeline(self):
        """Zero-content PDF -> IngestionResult with status=completed, chunks=0."""
        import asyncio

        from backend.ingestion.pipeline import IngestionPipeline

        mock_db = AsyncMock()
        mock_db.update_ingestion_job = AsyncMock()
        mock_db.update_document_status = AsyncMock()

        mock_qdrant = AsyncMock()
        pipeline = IngestionPipeline(db=mock_db, qdrant=mock_qdrant)

        mock_proc = MagicMock()
        mock_proc.stdout = iter([])
        mock_proc.stderr = MagicMock()
        mock_proc.stderr.read.return_value = ""
        mock_proc.wait.return_value = None
        mock_proc.returncode = 0

        with patch.object(pipeline, "_spawn_worker", return_value=mock_proc):
            result = asyncio.run(
                pipeline.ingest_file(
                    file_path="/tmp/empty.pdf",
                    filename="empty.pdf",
                    collection_id="col-test",
                    document_id="doc-empty",
                    job_id="job-empty",
                    file_hash="abc123",
                )
            )

        assert result.status == "completed"
        assert result.chunks_processed == 0
        assert result.error is None

    def test_zero_content_pdf_marks_document_completed(self):
        """Zero-content PDF marks document as completed with chunk_count=0."""
        import asyncio

        from backend.ingestion.pipeline import IngestionPipeline

        mock_db = AsyncMock()
        mock_db.update_ingestion_job = AsyncMock()
        mock_db.update_document_status = AsyncMock()

        mock_qdrant = AsyncMock()
        pipeline = IngestionPipeline(db=mock_db, qdrant=mock_qdrant)

        mock_proc = MagicMock()
        mock_proc.stdout = iter([])
        mock_proc.stderr = MagicMock()
        mock_proc.stderr.read.return_value = ""
        mock_proc.wait.return_value = None
        mock_proc.returncode = 0

        with patch.object(pipeline, "_spawn_worker", return_value=mock_proc):
            asyncio.run(
                pipeline.ingest_file(
                    file_path="/tmp/empty.pdf",
                    filename="empty.pdf",
                    collection_id="col-test",
                    document_id="doc-empty",
                    job_id="job-empty",
                    file_hash="abc123",
                )
            )

        status_calls = mock_db.update_document_status.call_args_list
        final_call = status_calls[-1]
        assert final_call.args[1] == "completed"
        assert final_call.kwargs.get("chunk_count") == 0

    def test_missing_worker_binary_returns_error(self):
        """Missing worker binary raises FileNotFoundError, pipeline sets status=failed."""
        import asyncio

        from backend.ingestion.pipeline import IngestionPipeline

        mock_db = AsyncMock()
        mock_db.update_ingestion_job = AsyncMock()
        mock_db.update_document_status = AsyncMock()

        mock_qdrant = AsyncMock()
        pipeline = IngestionPipeline(db=mock_db, qdrant=mock_qdrant)

        with patch.object(
            pipeline,
            "_spawn_worker",
            side_effect=FileNotFoundError("[Errno 2] No such file or directory: '/nonexistent/worker'"),
        ):
            result = asyncio.run(
                pipeline.ingest_file(
                    file_path="/tmp/test.pdf",
                    filename="test.pdf",
                    collection_id="col-test",
                    document_id="doc-test",
                    job_id="job-test",
                )
            )

        assert result.status == "failed"
        assert "No such file" in result.error
        job_calls = mock_db.update_ingestion_job.call_args_list
        last_job_call = job_calls[-1]
        assert last_job_call.kwargs.get("status") == "failed"
        doc_calls = mock_db.update_document_status.call_args_list
        last_doc_call = doc_calls[-1]
        assert last_doc_call.args[1] == "failed"

    def test_concurrent_upload_same_file_unique_constraint(self, app, mock_db):
        """Second upload of same file to same collection rejected by UNIQUE constraint."""
        import sqlite3

        error_client = TestClient(app, raise_server_exceptions=False)

        mock_db.create_document = AsyncMock(
            side_effect=sqlite3.IntegrityError("UNIQUE constraint failed: documents.collection_id, documents.file_hash")
        )

        with _mock_ingest_deps():
            response = error_client.post(
                "/api/collections/col-test/ingest",
                files={"file": ("test.pdf", io.BytesIO(b"%PDF-1.4 content"), "application/pdf")},
            )

        assert response.status_code == 500
