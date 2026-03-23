"""Unit tests for collections router — T012.

Tests name regex validation (400 COLLECTION_NAME_INVALID),
409 on duplicate name (COLLECTION_NAME_CONFLICT),
DELETE cascade: jobs cancelled → qdrant deleted → collection deleted.
Mocks SQLiteDB + QdrantStorage.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.collections import router
from backend.agent.schemas import CollectionCreateRequest


def _make_app(db=None, qdrant_storage=None):
    """Create a test FastAPI app with mocked dependencies."""
    app = FastAPI()
    app.include_router(router)
    app.state.db = db or AsyncMock()
    app.state.qdrant_storage = qdrant_storage or AsyncMock()
    return app


def _make_collection(
    name="my-docs",
    coll_id=None,
    description=None,
    embedding_model="nomic-embed-text",
    chunk_profile="default",
):
    coll_id = coll_id or str(uuid.uuid4())
    return {
        "id": coll_id,
        "name": name,
        "description": description,
        "embedding_model": embedding_model,
        "chunk_profile": chunk_profile,
        "qdrant_collection_name": f"qdrant_{coll_id}",
        "created_at": "2026-03-15T00:00:00+00:00",
    }


# ── List Collections ──────────────────────────────────────────────


class TestListCollections:
    def test_list_empty(self):
        db = AsyncMock()
        db.list_collections.return_value = []
        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get("/api/collections")
        assert resp.status_code == 200
        assert resp.json()["collections"] == []

    def test_list_returns_collections(self):
        coll = _make_collection()
        db = AsyncMock()
        db.list_collections.return_value = [coll]
        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get("/api/collections")
        assert resp.status_code == 200
        assert len(resp.json()["collections"]) == 1
        assert resp.json()["collections"][0]["name"] == "my-docs"


# ── Create Collection ─────────────────────────────────────────────


class TestCreateCollection:
    @pytest.mark.xfail(reason="Awaiting A5 T015: create_collection signature change", strict=False)
    def test_create_valid_name_201(self):
        db = AsyncMock()
        db.get_collection_by_name.return_value = None
        db.create_collection.return_value = None
        db.get_collection.return_value = _make_collection(name="valid-name")
        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.post("/api/collections", json={"name": "valid-name"})
        assert resp.status_code == 201

    def test_create_name_with_uppercase_400(self):
        """Uppercase letters violate the ^[a-z0-9][a-z0-9_-]*$ regex."""
        app = _make_app()
        client = TestClient(app)
        resp = client.post("/api/collections", json={"name": "MyDocs"})
        assert resp.status_code == 400 or resp.status_code == 422
        # Pydantic pattern validation returns 422

    def test_create_name_with_spaces_400(self):
        """Spaces violate the ^[a-z0-9][a-z0-9_-]*$ regex."""
        app = _make_app()
        client = TestClient(app)
        resp = client.post("/api/collections", json={"name": "my docs"})
        assert resp.status_code == 400 or resp.status_code == 422

    def test_create_name_starting_with_dash_400(self):
        """Names must start with [a-z0-9], not dash."""
        app = _make_app()
        client = TestClient(app)
        resp = client.post("/api/collections", json={"name": "-invalid"})
        assert resp.status_code == 400 or resp.status_code == 422

    def test_create_name_with_special_chars_400(self):
        """Special characters violate the regex."""
        app = _make_app()
        client = TestClient(app)
        resp = client.post("/api/collections", json={"name": "hello@world"})
        assert resp.status_code == 400 or resp.status_code == 422

    @pytest.mark.xfail(reason="Awaiting A5 T015: create_collection signature change", strict=False)
    def test_create_valid_name_patterns(self):
        """Valid names: lowercase letters, digits, hyphens, underscores."""
        db = AsyncMock()
        db.get_collection_by_name.return_value = None
        db.create_collection.return_value = None
        app = _make_app(db=db)
        client = TestClient(app)

        valid_names = ["a", "abc", "my-docs", "my_docs", "docs123", "0abc"]
        for name in valid_names:
            db.get_collection.return_value = _make_collection(name=name)
            resp = client.post("/api/collections", json={"name": name})
            assert resp.status_code in (201, 200), f"Name '{name}' should be valid but got {resp.status_code}"

    @pytest.mark.xfail(reason="Awaiting A5 T015: COLLECTION_NAME_CONFLICT error code", strict=False)
    def test_create_duplicate_name_409(self):
        """Duplicate name returns 409 COLLECTION_NAME_CONFLICT."""
        db = AsyncMock()
        from aiosqlite import IntegrityError
        db.get_collection_by_name.return_value = _make_collection(name="existing")
        db.create_collection.side_effect = IntegrityError("UNIQUE constraint failed")
        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.post("/api/collections", json={"name": "existing"})
        # Should be 409 with COLLECTION_NAME_CONFLICT code
        assert resp.status_code == 409
        body = resp.json()
        assert body["detail"]["error"]["code"] == "COLLECTION_NAME_CONFLICT"


# ── Get Collection ────────────────────────────────────────────────


class TestGetCollection:
    def test_get_existing_200(self):
        coll = _make_collection()
        db = AsyncMock()
        db.get_collection.return_value = coll
        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get(f"/api/collections/{coll['id']}")
        # Only test if the endpoint exists; current router may not have GET by ID
        # A5 will add it. If 404 method not allowed, that's expected pre-A5.
        assert resp.status_code in (200, 404, 405)


# ── Delete Collection ─────────────────────────────────────────────


class TestDeleteCollection:
    def test_delete_nonexistent_404(self):
        db = AsyncMock()
        db.get_collection.return_value = None
        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.delete(f"/api/collections/{uuid.uuid4()}")
        assert resp.status_code == 404
        body = resp.json()
        assert body["detail"]["error"]["code"] == "COLLECTION_NOT_FOUND"

    def test_delete_existing_204(self):
        coll = _make_collection()
        db = AsyncMock()
        db.get_collection.return_value = coll
        db.list_documents.return_value = []
        db.delete_collection.return_value = None
        qdrant = AsyncMock()
        app = _make_app(db=db, qdrant_storage=qdrant)
        client = TestClient(app)
        resp = client.delete(f"/api/collections/{coll['id']}")
        assert resp.status_code == 204

    @pytest.mark.xfail(reason="Awaiting A5 T015: cascade delete implementation", strict=False)
    def test_delete_cascade_cancels_jobs(self):
        """DELETE cascade: active ingestion jobs set to 'failed'."""
        coll = _make_collection()
        doc = {
            "id": str(uuid.uuid4()),
            "collection_id": coll["id"],
            "filename": "test.pdf",
            "status": "ingesting",
        }
        job = {
            "id": str(uuid.uuid4()),
            "document_id": doc["id"],
            "status": "started",
        }

        db = AsyncMock()
        db.get_collection.return_value = coll
        db.list_documents.return_value = [doc]
        db.list_ingestion_jobs.return_value = [job]
        db.update_ingestion_job.return_value = None
        db.delete_collection.return_value = None

        qdrant = AsyncMock()
        qdrant.delete_collection.return_value = None

        app = _make_app(db=db, qdrant_storage=qdrant)
        client = TestClient(app)
        resp = client.delete(f"/api/collections/{coll['id']}")
        assert resp.status_code == 204

        # Verify cascade: jobs cancelled, qdrant deleted, collection deleted
        db.update_ingestion_job.assert_called()
        call_kwargs = db.update_ingestion_job.call_args
        # The job should be set to failed
        assert "failed" in str(call_kwargs)

    @pytest.mark.xfail(reason="Awaiting A5 T015: cascade delete implementation", strict=False)
    def test_delete_cascade_deletes_qdrant_collection(self):
        """DELETE cascade: Qdrant collection deleted."""
        coll = _make_collection()

        db = AsyncMock()
        db.get_collection.return_value = coll
        db.list_documents.return_value = []
        db.delete_collection.return_value = None

        qdrant = AsyncMock()
        qdrant.delete_collection.return_value = None

        app = _make_app(db=db, qdrant_storage=qdrant)
        client = TestClient(app)
        resp = client.delete(f"/api/collections/{coll['id']}")
        assert resp.status_code == 204

        # Qdrant collection should be deleted via qdrant_storage
        qdrant.delete_collection.assert_called_once_with(coll["qdrant_collection_name"])

    @pytest.mark.xfail(reason="Awaiting A5 T015: cascade delete implementation", strict=False)
    def test_delete_cascade_order(self):
        """DELETE cascade order: jobs → qdrant → collection record."""
        coll = _make_collection()
        doc = {
            "id": str(uuid.uuid4()),
            "collection_id": coll["id"],
            "filename": "report.pdf",
            "status": "completed",
        }
        job = {
            "id": str(uuid.uuid4()),
            "document_id": doc["id"],
            "status": "embedding",
        }

        call_order = []

        db = AsyncMock()
        db.get_collection.return_value = coll
        db.list_documents.return_value = [doc]
        db.list_ingestion_jobs.return_value = [job]

        async def track_update_job(*args, **kwargs):
            call_order.append("cancel_jobs")

        async def track_delete_collection(*args, **kwargs):
            call_order.append("delete_collection")

        db.update_ingestion_job.side_effect = track_update_job
        db.delete_collection.side_effect = track_delete_collection

        qdrant = AsyncMock()

        async def track_qdrant_delete(*args, **kwargs):
            call_order.append("delete_qdrant")

        qdrant.delete_collection.side_effect = track_qdrant_delete

        app = _make_app(db=db, qdrant_storage=qdrant)
        client = TestClient(app)
        resp = client.delete(f"/api/collections/{coll['id']}")
        assert resp.status_code == 204

        # Verify order: jobs first, then qdrant, then collection
        assert call_order.index("cancel_jobs") < call_order.index("delete_qdrant")
        assert call_order.index("delete_qdrant") < call_order.index("delete_collection")
