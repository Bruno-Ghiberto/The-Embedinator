"""Tests for ingest security hardening (FR-003, FR-004, FR-005, FR-008)."""

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.api.ingest import _sanitize_filename, router


def _make_app():
    """Create minimal FastAPI app with ingest router and mock state."""
    app = FastAPI()
    app.include_router(router)

    # Mock middleware trace_id
    @app.middleware("http")
    async def add_trace_id(request, call_next):
        request.state.trace_id = "test-trace"
        return await call_next(request)

    app.state.db = AsyncMock()
    app.state.qdrant = AsyncMock()
    app.state.registry = None
    return app


# --- FR-003: Filename sanitization (unit tests on _sanitize_filename) ---


class TestSanitizeFilename:
    def test_path_traversal_stripped(self):
        """AC-3: ../../etc/passwd.txt → passwd.txt"""
        assert _sanitize_filename("../../etc/passwd.txt") == "passwd.txt"

    def test_pure_traversal_fallback(self):
        """Pure traversal with no real filename returns 'upload'."""
        assert _sanitize_filename("../../") == "upload"

    def test_backslash_traversal(self):
        """Windows-style path traversal handled."""
        assert _sanitize_filename("..\\..\\etc\\passwd.txt") == "passwd.txt"

    def test_normal_filename_preserved(self):
        """Clean filenames pass through with only unsafe chars replaced."""
        assert _sanitize_filename("my-doc_v2.pdf") == "my-doc_v2.pdf"

    def test_spaces_replaced(self):
        """Spaces and special chars replaced with underscore."""
        assert _sanitize_filename("my file (1).pdf") == "my_file__1_.pdf"

    def test_empty_after_sanitize_returns_upload(self):
        """If nothing remains after sanitization, return 'upload'."""
        assert _sanitize_filename("..") == "upload"


# --- FR-004: PDF magic byte check ---


@pytest.mark.asyncio
async def test_forged_pdf_rejected():
    """AC-4: .pdf file with non-PDF content → 400 FILE_CONTENT_MISMATCH."""
    app = _make_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        fake_pdf = io.BytesIO(b"AAAA not a real PDF")
        response = await client.post(
            "/api/collections/col1/ingest",
            files={"file": ("test.pdf", fake_pdf, "application/pdf")},
        )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "FILE_CONTENT_MISMATCH"


@pytest.mark.asyncio
async def test_short_pdf_rejected():
    """PDF with <4 bytes fails magic check."""
    app = _make_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        short = io.BytesIO(b"AB")
        response = await client.post(
            "/api/collections/col1/ingest",
            files={"file": ("tiny.pdf", short, "application/pdf")},
        )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "FILE_CONTENT_MISMATCH"


# --- FR-005: Non-PDF skips magic check ---


@pytest.mark.asyncio
async def test_non_pdf_skips_magic_check():
    """AC-5: .md file with any content passes (no magic check)."""
    app = _make_app()
    # Mock DB so collection exists and rest of pipeline works
    app.state.db.get_collection = AsyncMock(return_value={"id": "col1", "name": "test"})
    app.state.db.create_document = AsyncMock()
    app.state.db.create_ingestion_job = AsyncMock()

    checker_mock = MagicMock()
    checker_mock.check_duplicate = AsyncMock(return_value=(False, None))
    checker_mock.check_change = AsyncMock(return_value=(False, None))

    transport = ASGITransport(app=app)
    with (
        patch("backend.api.ingest.IncrementalChecker", return_value=checker_mock),
        patch("backend.api.ingest.IncrementalChecker.compute_file_hash", return_value="abc123"),
        patch("backend.api.ingest.IngestionPipeline"),
        patch("asyncio.create_task"),
    ):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            md_file = io.BytesIO(b"AAAA random bytes in a markdown file")
            response = await client.post(
                "/api/collections/col1/ingest",
                files={"file": ("notes.md", md_file, "text/markdown")},
            )
    assert response.status_code == 202


# --- FR-008: Existing extension check preserved ---


@pytest.mark.asyncio
async def test_extension_check_preserved():
    """AC-8: .exe file → 400 FILE_FORMAT_NOT_SUPPORTED."""
    app = _make_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        exe = io.BytesIO(b"MZ fake exe content")
        response = await client.post(
            "/api/collections/col1/ingest",
            files={"file": ("malware.exe", exe, "application/octet-stream")},
        )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "FILE_FORMAT_NOT_SUPPORTED"
