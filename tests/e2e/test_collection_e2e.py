"""E2E: Collection CRUD lifecycle — POST → list → DELETE → verify gone.

Uses real in-memory SQLiteDB + mock QdrantStorage.
All tests marked @pytest.mark.e2e.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from unittest.mock import AsyncMock

from backend.api import collections, health
from backend.middleware import TraceIDMiddleware
from backend.storage.sqlite_db import SQLiteDB


def _make_collection_app(db: SQLiteDB) -> "FastAPI":
    """Minimal app with only collection + health routers and a mock Qdrant."""
    app = FastAPI()
    app.add_middleware(TraceIDMiddleware)
    app.include_router(collections.router)
    app.include_router(health.router)

    app.state.db = db
    # Mock QdrantStorage so vector operations don't need a real Qdrant
    mock_qdrant_storage = AsyncMock()
    mock_qdrant_storage.create_collection = AsyncMock()
    mock_qdrant_storage.delete_collection = AsyncMock()
    app.state.qdrant_storage = mock_qdrant_storage

    return app


@pytest.mark.e2e
class TestCollectionLifecycle:
    """Full collection lifecycle: create → list → delete → verify gone."""

    @pytest_asyncio.fixture
    async def db(self):
        """Isolated in-memory SQLiteDB for each test."""
        instance = SQLiteDB(":memory:")
        await instance.connect()
        yield instance
        await instance.close()

    @pytest_asyncio.fixture
    async def client(self, db):
        """ASGI test client backed by in-process app."""
        app = _make_collection_app(db)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            yield c

    async def test_create_list_delete_lifecycle(self, client):
        """POST creates collection, list returns it, DELETE removes it."""
        # Use a unique name to avoid conflicts across runs
        name = f"e2e-{uuid.uuid4().hex[:8]}"
        collection_id = None

        try:
            # 1. CREATE
            resp = await client.post(
                "/api/collections",
                json={"name": name, "description": "E2E test collection"},
            )
            assert resp.status_code == 201, f"Create failed: {resp.text}"
            data = resp.json()
            assert data["name"] == name
            assert "id" in data
            assert data["document_count"] == 0
            collection_id = data["id"]

            # 2. LIST — verify the collection appears
            resp = await client.get("/api/collections")
            assert resp.status_code == 200
            names = [c["name"] for c in resp.json()["collections"]]
            assert name in names, f"Expected '{name}' in {names}"

            # 3. DELETE
            resp = await client.delete(f"/api/collections/{collection_id}")
            assert resp.status_code == 204

            # 4. LIST again — verify it's gone
            resp = await client.get("/api/collections")
            assert resp.status_code == 200
            names_after = [c["name"] for c in resp.json()["collections"]]
            assert name not in names_after, f"'{name}' should be gone but still in {names_after}"

        finally:
            # Guarantee cleanup even if assertions failed
            if collection_id:
                await client.delete(f"/api/collections/{collection_id}")

    async def test_delete_nonexistent_returns_404(self, client):
        """DELETE on a non-existent collection_id returns 404."""
        fake_id = str(uuid.uuid4())
        try:
            resp = await client.delete(f"/api/collections/{fake_id}")
            assert resp.status_code == 404
            err = resp.json()
            assert err["detail"]["error"]["code"] == "COLLECTION_NOT_FOUND"
        finally:
            pass  # nothing to clean up

    async def test_duplicate_name_returns_409(self, client):
        """POST with a duplicate name returns 409."""
        name = f"dup-{uuid.uuid4().hex[:8]}"
        collection_id = None

        try:
            # First create succeeds
            resp = await client.post("/api/collections", json={"name": name})
            assert resp.status_code == 201
            collection_id = resp.json()["id"]

            # Second create with same name returns 409
            resp = await client.post("/api/collections", json={"name": name})
            assert resp.status_code == 409
            assert resp.json()["detail"]["error"]["code"] == "COLLECTION_NAME_CONFLICT"

        finally:
            if collection_id:
                await client.delete(f"/api/collections/{collection_id}")

    async def test_invalid_name_is_rejected(self, client):
        """POST with an invalid name (uppercase, spaces, special chars) is rejected.

        Pydantic validates the name pattern first (422), so the endpoint's
        own 400 check is only reached for edge cases. Both 400 and 422 are
        correct rejections of an invalid collection name.
        """
        try:
            resp = await client.post(
                "/api/collections",
                json={"name": "Invalid Name!"},
            )
            # Either Pydantic validation (422) or endpoint validation (400) rejects it
            assert resp.status_code in (400, 422), (
                f"Expected 400 or 422 for invalid name, got {resp.status_code}: {resp.text}"
            )
        finally:
            pass  # nothing created, nothing to clean up
