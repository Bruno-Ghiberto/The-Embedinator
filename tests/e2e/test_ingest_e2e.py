"""E2E: Ingest lifecycle — POST file → poll job → verify document in collection.

Uses mock DB (pre-configured) + patched IncrementalChecker + patched IngestionPipeline.
All tests marked @pytest.mark.e2e.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from unittest.mock import AsyncMock, MagicMock, patch

from backend.api import documents, health
from backend.api import ingest as ingest_router
from backend.middleware import TraceIDMiddleware


_COLLECTION_ID = "e2e-ingest-collection-001"
_DOC_ID = str(uuid.uuid4())


def _make_mock_db(collection_id: str, doc_id: str) -> AsyncMock:
    """Mock DB pre-configured for the ingest lifecycle."""
    db = AsyncMock()

    # Collection exists
    db.get_collection = AsyncMock(
        return_value={
            "id": collection_id,
            "name": "e2e-ingest-collection",
            "qdrant_collection_name": f"emb-{collection_id}",
            "embedding_model": "nomic-embed-text",
        }
    )
    db.get_collection_by_name = AsyncMock(return_value=None)

    # Write ops succeed silently
    db.create_document = AsyncMock()
    db.create_ingestion_job = AsyncMock()
    db.update_document = AsyncMock()
    db.update_ingestion_job = AsyncMock()

    # Job always returns "completed" (pipeline is mocked to run instantly)
    db.get_ingestion_job = AsyncMock(
        side_effect=lambda job_id: {
            "id": job_id,
            "document_id": doc_id,
            "status": "completed",
            "chunks_processed": 3,
            "error_msg": None,
            "started_at": None,
            "finished_at": None,
        }
    )

    # Documents endpoint: one document appears after ingestion
    db.list_documents = AsyncMock(
        return_value=[
            {
                "id": doc_id,
                "collection_id": collection_id,
                "filename": "sample.txt",
                "status": "completed",
                "chunk_count": 3,
            }
        ]
    )
    db.list_collections = AsyncMock(return_value=[{"id": collection_id, "name": "e2e-ingest-collection"}])

    return db


def _make_ingest_app(db: AsyncMock) -> "FastAPI":
    """Minimal app with ingest + documents + health routers."""
    app = FastAPI()
    app.add_middleware(TraceIDMiddleware)
    app.include_router(ingest_router.router)
    app.include_router(documents.router)
    app.include_router(health.router)

    app.state.db = db
    app.state.qdrant = AsyncMock()

    # Mock registry → get_embedding_provider returns None (pipeline handles None gracefully)
    registry = AsyncMock()
    registry.get_embedding_provider = AsyncMock(return_value=None)
    app.state.registry = registry

    return app


@pytest.mark.e2e
class TestIngestLifecycle:
    """Ingest file → poll job → verify document appears in collection."""

    @pytest_asyncio.fixture
    async def setup(self, tmp_path):
        """Create test file, mock DB, and patched app."""
        collection_id = _COLLECTION_ID
        doc_id = _DOC_ID

        db = _make_mock_db(collection_id, doc_id)
        app = _make_ingest_app(db)

        # Create a real temp file that the ingest endpoint will save
        test_file = tmp_path / "sample.txt"
        test_file.write_text("Test content for E2E ingestion.\n" * 20)

        yield app, collection_id, doc_id, test_file, tmp_path

    async def test_ingest_poll_verify(self, setup):
        """POST file, poll for completed status, verify document in /api/documents."""
        app, collection_id, doc_id, test_file, tmp_path = setup

        # Patch: settings.upload_dir → tmp_path; IncrementalChecker + IngestionPipeline mocked
        mock_settings = MagicMock()
        mock_settings.upload_dir = str(tmp_path / "uploads")
        mock_settings.max_upload_size_mb = 10

        try:
            with (
                patch("backend.api.ingest.settings", mock_settings),
                patch("backend.api.ingest.IncrementalChecker") as MockChecker,
                patch("backend.api.ingest.IngestionPipeline") as MockPipeline,
            ):
                # Configure IncrementalChecker
                checker_inst = MagicMock()
                checker_inst.check_duplicate = AsyncMock(return_value=(False, None))
                checker_inst.check_change = AsyncMock(return_value=(False, None))
                MockChecker.return_value = checker_inst
                MockChecker.compute_file_hash = MagicMock(return_value="abc123hash")

                # Configure IngestionPipeline — ingest_file is a no-op (returns immediately)
                pipeline_inst = MagicMock()
                pipeline_inst.ingest_file = AsyncMock()
                pipeline_inst.delete_old_document_data = AsyncMock()
                MockPipeline.return_value = pipeline_inst

                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                    # 1. POST file for ingestion
                    with open(test_file, "rb") as f:
                        resp = await client.post(
                            f"/api/collections/{collection_id}/ingest",
                            files={"file": ("sample.txt", f, "text/plain")},
                        )

                    assert resp.status_code == 202, f"Expected 202, got {resp.status_code}: {resp.text}"
                    data = resp.json()
                    assert "job_id" in data, f"Missing job_id in response: {data}"
                    assert data["status"] == "started"
                    job_id = data["job_id"]

                    # 2. Poll job status (mock returns "completed" immediately)
                    resp = await client.get(f"/api/collections/{collection_id}/ingest/{job_id}")
                    assert resp.status_code == 200, f"Job poll failed: {resp.text}"
                    job_data = resp.json()
                    assert job_data["status"] == "completed", f"Expected 'completed', got '{job_data['status']}'"
                    assert job_data["chunks_processed"] == 3

                    # 3. Verify document appears in /api/documents
                    resp = await client.get(
                        "/api/documents",
                        params={"collection_id": collection_id},
                    )
                    assert resp.status_code == 200
                    docs = resp.json()["documents"]
                    assert len(docs) >= 1, f"Expected at least 1 document, got {docs}"
        finally:
            pass  # mock DB, nothing real to clean up

    async def test_ingest_unsupported_extension_returns_400(self, setup, tmp_path):
        """Uploading a .exe file returns 400 FILE_FORMAT_NOT_SUPPORTED."""
        app, collection_id, doc_id, test_file, _ = setup

        bad_file = tmp_path / "malware.exe"
        bad_file.write_bytes(b"\x00\x01\x02\x03")

        mock_settings = MagicMock()
        mock_settings.upload_dir = str(tmp_path / "uploads")
        mock_settings.max_upload_size_mb = 10

        try:
            with patch("backend.api.ingest.settings", mock_settings):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                    with open(bad_file, "rb") as f:
                        resp = await client.post(
                            f"/api/collections/{collection_id}/ingest",
                            files={"file": ("malware.exe", f, "application/octet-stream")},
                        )
                    assert resp.status_code == 400
                    err = resp.json()["detail"]["error"]
                    assert err["code"] == "FILE_FORMAT_NOT_SUPPORTED"
        finally:
            pass
