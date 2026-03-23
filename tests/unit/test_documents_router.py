"""Unit tests for documents router — T013.

Tests GET /documents (list + collection_id filter),
GET /documents/{id} (200 and 404),
DELETE /documents/{id} (204 and 404).
Mocks SQLiteDB.
"""

import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.documents import router


def _make_app(db=None):
    """Create a test FastAPI app with mocked dependencies."""
    app = FastAPI()
    app.include_router(router)
    app.state.db = db or AsyncMock()
    return app


def _make_document(
    doc_id=None,
    collection_id=None,
    filename="report.pdf",
    status="completed",
    chunk_count=42,
):
    return {
        "id": doc_id or str(uuid.uuid4()),
        "collection_id": collection_id or str(uuid.uuid4()),
        "filename": filename,
        "file_path": f"/uploads/{filename}",
        "file_hash": "abc123def456",
        "status": status,
        "chunk_count": chunk_count,
        "created_at": "2026-03-15T00:00:00+00:00",
        "ingested_at": "2026-03-15T00:05:00+00:00",
    }


# ── List Documents ────────────────────────────────────────────────


class TestListDocuments:
    def test_list_documents_200(self):
        doc = _make_document()
        db = AsyncMock()
        db.list_documents.return_value = [doc]
        db.list_collections.return_value = [{"id": doc["collection_id"]}]
        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get("/api/documents")
        assert resp.status_code == 200
        body = resp.json()
        assert "documents" in body
        assert len(body["documents"]) >= 1

    def test_list_documents_with_collection_filter(self):
        coll_id = str(uuid.uuid4())
        doc = _make_document(collection_id=coll_id)
        db = AsyncMock()
        db.list_documents.return_value = [doc]
        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get(f"/api/documents?collection_id={coll_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert "documents" in body
        docs = body["documents"]
        assert len(docs) == 1
        assert docs[0]["collection_id"] == coll_id

    def test_list_documents_empty(self):
        db = AsyncMock()
        db.list_documents.return_value = []
        db.list_collections.return_value = []
        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get("/api/documents")
        assert resp.status_code == 200
        assert resp.json()["documents"] == []

    def test_list_documents_without_filter_returns_all(self):
        coll1 = str(uuid.uuid4())
        coll2 = str(uuid.uuid4())
        doc1 = _make_document(collection_id=coll1, filename="a.pdf")
        doc2 = _make_document(collection_id=coll2, filename="b.md")
        db = AsyncMock()
        db.list_collections.return_value = [{"id": coll1}, {"id": coll2}]
        db.list_documents.side_effect = [[doc1], [doc2]]
        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get("/api/documents")
        assert resp.status_code == 200
        body = resp.json()
        assert "documents" in body


# ── Get Document ──────────────────────────────────────────────────


class TestGetDocument:
    def test_get_existing_200(self):
        doc = _make_document()
        db = AsyncMock()
        db.get_document.return_value = doc
        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get(f"/api/documents/{doc['id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == doc["id"]
        assert body["filename"] == doc["filename"]

    def test_get_nonexistent_404(self):
        db = AsyncMock()
        db.get_document.return_value = None
        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get(f"/api/documents/{uuid.uuid4()}")
        assert resp.status_code == 404
        body = resp.json()
        assert body["detail"]["error"]["code"] == "DOCUMENT_NOT_FOUND"

    def test_get_returns_document_fields(self):
        doc = _make_document(
            filename="analysis.md",
            status="ingesting",
            chunk_count=None,
        )
        db = AsyncMock()
        db.get_document.return_value = doc
        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get(f"/api/documents/{doc['id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["filename"] == "analysis.md"
        assert body["status"] == "ingesting"


# ── Delete Document ───────────────────────────────────────────────


class TestDeleteDocument:
    def test_delete_existing_204(self):
        doc_id = str(uuid.uuid4())
        db = AsyncMock()
        db.delete_document.return_value = True
        db.get_document.return_value = _make_document(doc_id=doc_id)
        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.delete(f"/api/documents/{doc_id}")
        assert resp.status_code == 204

    def test_delete_nonexistent_404(self):
        db = AsyncMock()
        db.delete_document.return_value = False
        db.get_document.return_value = None
        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.delete(f"/api/documents/{uuid.uuid4()}")
        assert resp.status_code == 404
        body = resp.json()
        assert body["detail"]["error"]["code"] == "DOCUMENT_NOT_FOUND"

    def test_delete_returns_no_content(self):
        doc_id = str(uuid.uuid4())
        db = AsyncMock()
        db.delete_document.return_value = True
        db.get_document.return_value = _make_document(doc_id=doc_id)
        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.delete(f"/api/documents/{doc_id}")
        assert resp.status_code == 204
        assert resp.content == b""
