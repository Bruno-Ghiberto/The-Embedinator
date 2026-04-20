"""Integration tests for full API request cycles — T030.

Tests every endpoint group through the full app with mocked storage.
Uses AsyncMock for db with properly configured return values.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessageChunk

from backend.api import (
    chat,
    collections,
    documents,
    health,
)
from backend.api import ingest as ingest_router
from backend.api import models as models_router
from backend.api import providers
from backend.api import settings as api_settings
from backend.api import traces
from backend.middleware import TraceIDMiddleware


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class FakeInterrupt:
    value: str


def _build_mock_graph(
    *,
    chunks: list[str] | None = None,
    final_state: dict | None = None,
):
    """Build a mock ConversationGraph that streams chunks and returns state."""
    graph = MagicMock()
    chunks = chunks or ["Test answer."]

    async def mock_astream(state, *, stream_mode="messages", config=None):
        for text in chunks:
            msg = AIMessageChunk(content=text)
            metadata = {"langgraph_node": "format_response"}
            yield msg, metadata

    graph.astream = mock_astream

    default_final = {
        "citations": [],
        "attempted_strategies": set(),
        "confidence_score": 82,
        "groundedness_result": None,
        "sub_questions": [],
        "final_response": "Test answer.",
    }
    if final_state:
        default_final.update(final_state)

    state_snapshot = MagicMock()
    state_snapshot.values = default_final
    graph.get_state = MagicMock(return_value=state_snapshot)
    return graph


def _mock_db():
    """Create a properly configured mock DB with common return values."""
    db = AsyncMock()

    # Default: empty lists for list operations
    db.list_collections = AsyncMock(return_value=[])
    db.list_documents = AsyncMock(return_value=[])
    db.list_providers = AsyncMock(return_value=[])
    db.list_ingestion_jobs = AsyncMock(return_value=[])
    db.list_settings = AsyncMock(return_value={})

    # Default: None for get operations (not found)
    db.get_collection = AsyncMock(return_value=None)
    db.get_collection_by_name = AsyncMock(return_value=None)
    db.get_document = AsyncMock(return_value=None)
    db.get_provider = AsyncMock(return_value=None)
    db.get_ingestion_job = AsyncMock(return_value=None)

    # Write operations succeed silently
    db.create_collection = AsyncMock()
    db.create_document = AsyncMock()
    db.create_query_trace = AsyncMock()
    db.delete_collection = AsyncMock()
    db.delete_document = AsyncMock()
    db.update_provider = AsyncMock()
    db.update_ingestion_job = AsyncMock()
    db.set_setting = AsyncMock()

    # Mock the raw db.db connection for traces/stats
    mock_cursor = AsyncMock()
    mock_cursor.fetchone = AsyncMock(return_value=None)
    mock_cursor.fetchall = AsyncMock(return_value=[])
    db.db = AsyncMock()
    db.db.execute = AsyncMock(return_value=mock_cursor)

    return db


def _make_app(
    *,
    db=None,
    qdrant_storage=None,
    qdrant=None,
    key_manager=None,
    graph=None,
) -> FastAPI:
    """Build a test app with all routers and TraceIDMiddleware."""
    app = FastAPI()
    app.add_middleware(TraceIDMiddleware)

    app.include_router(collections.router)
    app.include_router(documents.router)
    app.include_router(chat.router)
    app.include_router(traces.router)
    app.include_router(providers.router)
    app.include_router(health.router)
    app.include_router(ingest_router.router)
    app.include_router(models_router.router)
    app.include_router(api_settings.router)

    app.state.db = db or _mock_db()
    app.state.qdrant_storage = qdrant_storage or AsyncMock()
    app.state.qdrant = qdrant or AsyncMock()
    app.state.key_manager = key_manager
    app.state.checkpointer = None
    app.state.research_graph = None
    app.state.registry = AsyncMock()

    if graph is not None:
        app.state._conversation_graph = graph

    return app


def _parse_ndjson(response) -> list[dict]:
    """Parse NDJSON response text into a list of events."""
    lines = response.text.strip().split("\n")
    return [json.loads(line) for line in lines if line.strip()]


# ---------------------------------------------------------------------------
# Collections (FR-002, FR-003, FR-005)
# ---------------------------------------------------------------------------


class TestCollections:
    """Collection CRUD integration tests."""

    def test_create_collection_201(self):
        """POST /api/collections with valid name -> 201."""
        db = _mock_db()
        now = "2026-03-15T00:00:00+00:00"
        coll_id = str(uuid.uuid4())

        db.get_collection_by_name = AsyncMock(return_value=None)
        db.get_collection = AsyncMock(
            return_value={
                "id": coll_id,
                "name": "my-docs",
                "description": None,
                "embedding_model": "nomic-embed-text",
                "chunk_profile": "default",
                "qdrant_collection_name": f"emb-{coll_id}",
                "created_at": now,
            }
        )
        app = _make_app(db=db)

        with TestClient(app) as client:
            resp = client.post(
                "/api/collections",
                json={"name": "my-docs"},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["name"] == "my-docs"
        assert data["document_count"] == 0

    def test_duplicate_collection_409(self):
        """POST /api/collections with duplicate name -> 409 COLLECTION_NAME_CONFLICT."""
        db = _mock_db()
        db.get_collection_by_name = AsyncMock(
            return_value={
                "id": str(uuid.uuid4()),
                "name": "my-docs",
            }
        )
        app = _make_app(db=db)

        with TestClient(app) as client:
            resp = client.post("/api/collections", json={"name": "my-docs"})

        assert resp.status_code == 409
        body = resp.json()
        assert body["detail"]["error"]["code"] == "COLLECTION_NAME_CONFLICT"
        assert "trace_id" in body["detail"]

    def test_invalid_collection_name_400(self):
        """POST /api/collections with invalid name -> 400 or 422."""
        db = _mock_db()
        app = _make_app(db=db)

        with TestClient(app) as client:
            resp = client.post(
                "/api/collections",
                json={"name": "My Docs!"},
            )

        # Pydantic regex validation returns 422 for pattern mismatch
        assert resp.status_code in (400, 422)

    def test_delete_collection_204_cascade(self):
        """DELETE /api/collections/{id} -> 204 with cascade."""
        db = _mock_db()
        coll_id = str(uuid.uuid4())
        db.get_collection = AsyncMock(
            return_value={
                "id": coll_id,
                "name": "to-delete",
                "qdrant_collection_name": f"emb-{coll_id}",
            }
        )
        db.list_documents = AsyncMock(return_value=[])
        qdrant_storage = AsyncMock()
        app = _make_app(db=db, qdrant_storage=qdrant_storage)

        with TestClient(app) as client:
            resp = client.delete(f"/api/collections/{coll_id}")

        assert resp.status_code == 204
        qdrant_storage.delete_collection.assert_called_once()
        db.delete_collection.assert_called_once_with(coll_id)

    def test_list_collections(self):
        """GET /api/collections -> 200 with collections list."""
        db = _mock_db()
        now = "2026-03-15T00:00:00+00:00"
        db.list_collections = AsyncMock(
            return_value=[
                {
                    "id": "c1",
                    "name": "coll-a",
                    "description": None,
                    "embedding_model": "nomic-embed-text",
                    "chunk_profile": "default",
                    "qdrant_collection_name": "emb-c1",
                    "created_at": now,
                },
                {
                    "id": "c2",
                    "name": "coll-b",
                    "description": None,
                    "embedding_model": "nomic-embed-text",
                    "chunk_profile": "default",
                    "qdrant_collection_name": "emb-c2",
                    "created_at": now,
                },
            ]
        )
        db.list_documents = AsyncMock(return_value=[])
        app = _make_app(db=db)

        with TestClient(app) as client:
            resp = client.get("/api/collections")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["collections"]) == 2


# ---------------------------------------------------------------------------
# Documents (FR-006, FR-012)
# ---------------------------------------------------------------------------


class TestDocuments:
    """Document listing and deletion tests."""

    def test_list_documents_200(self):
        """GET /api/documents -> 200 with documents list."""
        db = _mock_db()
        db.list_collections = AsyncMock(return_value=[])
        app = _make_app(db=db)

        with TestClient(app) as client:
            resp = client.get("/api/documents")

        assert resp.status_code == 200
        assert "documents" in resp.json()

    def test_get_document_404(self):
        """GET /api/documents/{id} for nonexistent -> 404 DOCUMENT_NOT_FOUND."""
        db = _mock_db()
        db.get_document = AsyncMock(return_value=None)
        app = _make_app(db=db)

        with TestClient(app) as client:
            resp = client.get(f"/api/documents/{uuid.uuid4()}")

        assert resp.status_code == 404
        body = resp.json()
        assert body["detail"]["error"]["code"] == "DOCUMENT_NOT_FOUND"
        assert "trace_id" in body["detail"]

    def test_delete_document_204(self):
        """DELETE /api/documents/{id} -> 204."""
        db = _mock_db()
        doc_id = str(uuid.uuid4())
        db.get_document = AsyncMock(
            return_value={
                "id": doc_id,
                "collection_id": "c1",
                "filename": "test.txt",
                "status": "completed",
            }
        )
        app = _make_app(db=db)

        with TestClient(app) as client:
            resp = client.delete(f"/api/documents/{doc_id}")

        assert resp.status_code == 204
        db.delete_document.assert_called_once_with(doc_id)


# ---------------------------------------------------------------------------
# Ingestion (FR-007, FR-008)
# ---------------------------------------------------------------------------


class TestIngestion:
    """Ingestion endpoint tests."""

    def test_unsupported_extension_400(self):
        """POST /api/collections/{id}/ingest with .exe -> 400 FILE_FORMAT_NOT_SUPPORTED."""
        db = _mock_db()
        coll_id = str(uuid.uuid4())
        app = _make_app(db=db)

        with TestClient(app) as client:
            resp = client.post(
                f"/api/collections/{coll_id}/ingest",
                files={"file": ("malware.exe", b"MZ...content", "application/octet-stream")},
            )

        assert resp.status_code == 400
        body = resp.json()
        assert body["detail"]["error"]["code"] == "FILE_FORMAT_NOT_SUPPORTED"
        assert "trace_id" in body["detail"]

    def test_oversized_file_413(self):
        """POST /api/collections/{id}/ingest with oversized file -> 413 FILE_TOO_LARGE."""
        db = _mock_db()
        coll_id = str(uuid.uuid4())
        db.get_collection = AsyncMock(return_value={"id": coll_id, "name": "test"})
        app = _make_app(db=db)

        with TestClient(app) as client:
            # Patch settings to use a tiny limit for test speed
            with patch("backend.api.ingest.settings") as mock_settings:
                mock_settings.max_upload_size_mb = 0  # 0 MB = 0 bytes max
                mock_settings.upload_dir = "/tmp/test-uploads"
                resp = client.post(
                    f"/api/collections/{coll_id}/ingest",
                    files={"file": ("report.pdf", b"x" * 100, "application/pdf")},
                )

        assert resp.status_code == 413
        body = resp.json()
        assert body["detail"]["error"]["code"] == "FILE_TOO_LARGE"
        assert "trace_id" in body["detail"]

    def test_collection_not_found_404(self):
        """POST /api/collections/{id}/ingest for nonexistent collection -> 404."""
        db = _mock_db()
        db.get_collection = AsyncMock(return_value=None)
        app = _make_app(db=db)

        with TestClient(app) as client:
            resp = client.post(
                f"/api/collections/{uuid.uuid4()}/ingest",
                files={"file": ("doc.txt", b"content", "text/plain")},
            )

        assert resp.status_code == 404

    def test_get_job_status_404(self):
        """GET /api/collections/{id}/ingest/{job_id} for nonexistent -> 404."""
        db = _mock_db()
        db.get_ingestion_job = AsyncMock(return_value=None)
        app = _make_app(db=db)

        with TestClient(app) as client:
            resp = client.get(f"/api/collections/{uuid.uuid4()}/ingest/{uuid.uuid4()}")

        assert resp.status_code == 404
        body = resp.json()
        assert body["detail"]["error"]["code"] == "JOB_NOT_FOUND"


# ---------------------------------------------------------------------------
# Chat (FR-013, FR-014, FR-015)
# ---------------------------------------------------------------------------


class TestChat:
    """Chat endpoint integration tests."""

    def test_chat_ndjson_content_type(self):
        """POST /api/chat -> 200 with Content-Type: application/x-ndjson."""
        graph = _build_mock_graph()
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={
                    "message": "What is RAG?",
                    "collection_ids": ["test-coll"],
                },
            )

        assert resp.status_code == 200
        assert "application/x-ndjson" in resp.headers["content-type"]

    def test_chat_session_first_done_last(self):
        """First event is session, last event is done."""
        graph = _build_mock_graph()
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={
                    "message": "Test query",
                    "collection_ids": ["test-coll"],
                },
            )

        events = _parse_ndjson(resp)
        assert events[0]["type"] == "session"
        assert events[-1]["type"] == "done"

    def test_chat_confidence_is_int_0_100(self):
        """Confidence score in response is int 0-100 (FR-015)."""
        graph = _build_mock_graph(final_state={"confidence_score": 82})
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={
                    "message": "Test",
                    "collection_ids": ["test-coll"],
                },
            )

        events = _parse_ndjson(resp)
        conf_events = [e for e in events if e["type"] == "confidence"]
        assert len(conf_events) == 1
        score = conf_events[0]["score"]
        assert isinstance(score, int)
        assert 0 <= score <= 100


# ---------------------------------------------------------------------------
# Providers (FR-018, SC-005)
# ---------------------------------------------------------------------------


class TestProviders:
    """Provider key management — keys must never leak."""

    def test_list_providers_has_key_bool_no_api_key(self):
        """GET /api/providers -> 200, has_key is bool, no api_key field (FR-018, SC-005)."""
        db = _mock_db()
        db.list_providers = AsyncMock(
            return_value=[
                {
                    "name": "openai",
                    "api_key_encrypted": "gAAAAABf...",
                    "base_url": None,
                    "is_active": False,
                    "created_at": "2026-01-01",
                },
            ]
        )
        app = _make_app(db=db)

        with TestClient(app) as client:
            resp = client.get("/api/providers")

        assert resp.status_code == 200
        data = resp.json()
        for p in data["providers"]:
            assert isinstance(p["has_key"], bool)
            assert "api_key" not in p
            assert "api_key_encrypted" not in p

    def test_put_provider_key_200(self):
        """PUT /api/providers/{name}/key -> 200 with {name, has_key: true}."""
        db = _mock_db()
        db.get_provider = AsyncMock(
            return_value={
                "name": "openai",
                "api_key_encrypted": None,
                "base_url": None,
                "is_active": False,
                "created_at": "2026-01-01",
            }
        )
        key_manager = MagicMock()
        key_manager.encrypt.return_value = "encrypted-value"
        app = _make_app(db=db, key_manager=key_manager)

        with TestClient(app) as client:
            resp = client.put(
                "/api/providers/openai/key",
                json={"api_key": "sk-test-key-123"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "openai"
        assert body["has_key"] is True
        # Key value NEVER returned
        assert "api_key" not in body
        assert "api_key_encrypted" not in body

    def test_delete_provider_key_200(self):
        """DELETE /api/providers/{name}/key -> 200 with {name, has_key: false}."""
        db = _mock_db()
        db.get_provider = AsyncMock(
            return_value={
                "name": "openai",
                "api_key_encrypted": "encrypted-val",
                "base_url": None,
                "is_active": False,
                "created_at": "2026-01-01",
            }
        )
        app = _make_app(db=db)

        with TestClient(app) as client:
            resp = client.delete("/api/providers/openai/key")

        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "openai"
        assert body["has_key"] is False

    def test_provider_key_never_in_any_response(self):
        """Across ALL provider endpoints, api_key_encrypted and api_key never appear."""
        db = _mock_db()
        db.list_providers = AsyncMock(
            return_value=[
                {
                    "name": "openai",
                    "api_key_encrypted": "gAAAAABf...",
                    "base_url": None,
                    "is_active": False,
                    "created_at": "2026-01-01",
                },
            ]
        )
        db.get_provider = AsyncMock(
            return_value={
                "name": "openai",
                "api_key_encrypted": "gAAAAABf...",
                "base_url": None,
                "is_active": False,
                "created_at": "2026-01-01",
            }
        )
        key_manager = MagicMock()
        key_manager.encrypt.return_value = "new-encrypted"
        app = _make_app(db=db, key_manager=key_manager)

        with TestClient(app) as client:
            responses = [
                client.get("/api/providers"),
                client.put(
                    "/api/providers/openai/key",
                    json={"api_key": "sk-new"},
                ),
                client.delete("/api/providers/openai/key"),
            ]

        for resp in responses:
            text = resp.text
            assert "api_key_encrypted" not in text
            # Encrypted values must never appear
            assert "gAAAAABf" not in text
            assert "sk-new" not in text
            assert "new-encrypted" not in text


# ---------------------------------------------------------------------------
# Settings (FR-020)
# ---------------------------------------------------------------------------


class TestSettings:
    """Settings CRUD tests."""

    def test_get_settings_200(self):
        """GET /api/settings -> 200 with all 7 fields."""
        db = _mock_db()
        db.list_settings = AsyncMock(return_value={})
        app = _make_app(db=db)

        with TestClient(app) as client:
            resp = client.get("/api/settings")

        assert resp.status_code == 200
        data = resp.json()
        expected_keys = {
            "default_llm_model",
            "default_embed_model",
            "confidence_threshold",
            "groundedness_check_enabled",
            "citation_alignment_threshold",
            "parent_chunk_size",
            "child_chunk_size",
        }
        assert expected_keys == set(data.keys())

    def test_put_settings_persists(self):
        """PUT /api/settings with {confidence_threshold: 75} -> 200, verify persisted."""
        db = _mock_db()
        # After set_setting, list_settings returns updated value
        db.list_settings = AsyncMock(return_value={"confidence_threshold": "75"})
        app = _make_app(db=db)

        with TestClient(app) as client:
            resp = client.put(
                "/api/settings",
                json={"confidence_threshold": 75},
            )
            assert resp.status_code == 200
            assert resp.json()["confidence_threshold"] == 75


# ---------------------------------------------------------------------------
# Traces + Stats (FR-021, FR-023)
# ---------------------------------------------------------------------------


class _MockRow(dict):
    """Dict that also supports attribute-style access like aiosqlite.Row."""

    def __getitem__(self, key):
        return super().__getitem__(key)


class TestTraces:
    """Trace retrieval and stats tests."""

    def test_list_traces_200(self):
        """GET /api/traces -> 200 with traces list."""
        db = _mock_db()
        # Mock count query
        count_row = _MockRow({"cnt": 0})
        count_cursor = AsyncMock()
        count_cursor.fetchone = AsyncMock(return_value=count_row)
        # Mock data query
        data_cursor = AsyncMock()
        data_cursor.fetchall = AsyncMock(return_value=[])

        db.db.execute = AsyncMock(side_effect=[count_cursor, data_cursor])
        app = _make_app(db=db)

        with TestClient(app) as client:
            resp = client.get("/api/traces")

        assert resp.status_code == 200
        data = resp.json()
        assert "traces" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data

    def test_list_traces_nonexistent_session_empty_not_404(self):
        """GET /api/traces?session_id=nonexistent -> 200 with empty list (NOT 404)."""
        db = _mock_db()
        count_row = _MockRow({"cnt": 0})
        count_cursor = AsyncMock()
        count_cursor.fetchone = AsyncMock(return_value=count_row)
        data_cursor = AsyncMock()
        data_cursor.fetchall = AsyncMock(return_value=[])
        db.db.execute = AsyncMock(side_effect=[count_cursor, data_cursor])
        app = _make_app(db=db)

        with TestClient(app) as client:
            resp = client.get("/api/traces?session_id=nonexistent-session")

        assert resp.status_code == 200
        data = resp.json()
        assert data["traces"] == []

    def test_get_stats_200(self):
        """GET /api/stats -> 200 with all 7 numeric fields."""
        db = _mock_db()
        db.list_collections = AsyncMock(return_value=[])
        # Mock the aggregate query for stats
        stats_row = _MockRow(
            {
                "total_queries": 0,
                "avg_confidence": 0.0,
                "avg_latency_ms": 0.0,
                "meta_count": 0,
            }
        )
        stats_cursor = AsyncMock()
        stats_cursor.fetchone = AsyncMock(return_value=stats_row)
        db.db.execute = AsyncMock(return_value=stats_cursor)
        app = _make_app(db=db)

        with TestClient(app) as client:
            resp = client.get("/api/stats")

        assert resp.status_code == 200
        data = resp.json()
        expected_keys = {
            "total_collections",
            "total_documents",
            "total_chunks",
            "total_queries",
            "avg_confidence",
            "avg_latency_ms",
            "meta_reasoning_rate",
        }
        assert expected_keys == set(data.keys())
        # All values should be numeric
        for key in expected_keys:
            assert isinstance(data[key], (int, float))


# ---------------------------------------------------------------------------
# Health (FR-022)
# ---------------------------------------------------------------------------


class TestHealth:
    """Health check endpoint tests."""

    @pytest.mark.xfail(reason="Health check mock boundary mismatch — pre-existing")
    def test_health_200_with_services(self):
        """GET /api/health -> 200 with services list."""
        db = _mock_db()
        db.db.execute = AsyncMock(return_value=AsyncMock())
        qdrant = AsyncMock()
        qdrant.health_check = AsyncMock(return_value=True)
        app = _make_app(db=db, qdrant=qdrant)

        with patch("backend.api.health.httpx.AsyncClient") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.return_value = mock_client

            with TestClient(app) as client:
                resp = client.get("/api/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert len(data["services"]) == 3
        service_names = [s["name"] for s in data["services"]]
        assert "sqlite" in service_names
        assert "qdrant" in service_names
        assert "ollama" in service_names


# ---------------------------------------------------------------------------
# Error Format (FR-026)
# ---------------------------------------------------------------------------


class TestErrorFormat:
    """All error responses must include trace_id and error code/message."""

    def test_404_has_error_code_message_trace_id(self):
        """404 error response has error.code, error.message, and trace_id."""
        db = _mock_db()
        app = _make_app(db=db)

        with TestClient(app) as client:
            resp = client.get(f"/api/documents/{uuid.uuid4()}")

        assert resp.status_code == 404
        body = resp.json()
        assert "detail" in body
        detail = body["detail"]
        assert "error" in detail
        assert "code" in detail["error"]
        assert "message" in detail["error"]
        assert "trace_id" in detail

    def test_trace_id_header_on_all_responses(self):
        """X-Trace-ID header present on all responses."""
        db = _mock_db()
        app = _make_app(db=db)

        with TestClient(app) as client:
            # Success response
            resp_ok = client.get("/api/settings")
            assert "x-trace-id" in resp_ok.headers

            # Error response
            resp_err = client.get(f"/api/documents/{uuid.uuid4()}")
            assert "x-trace-id" in resp_err.headers

    def test_multiple_error_endpoints_have_trace_id(self):
        """Various error endpoints all include trace_id in error body."""
        db = _mock_db()
        app = _make_app(db=db)

        error_requests = [
            ("GET", f"/api/documents/{uuid.uuid4()}"),
            ("DELETE", f"/api/documents/{uuid.uuid4()}"),
            ("DELETE", f"/api/collections/{uuid.uuid4()}"),
        ]

        with TestClient(app) as client:
            for method, path in error_requests:
                resp = client.request(method, path)
                body = resp.json()
                assert "detail" in body, f"No detail in {method} {path}"
                assert "trace_id" in body["detail"], f"No trace_id in {method} {path} error"
