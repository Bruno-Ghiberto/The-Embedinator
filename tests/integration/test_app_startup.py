"""Integration test for app startup — T026.

Verifies the FastAPI app initializes all services on startup.
"""

import pytest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


@pytest.fixture
def mock_services():
    """Mock external services (Qdrant, Ollama, checkpointer) for startup test."""
    mock_checkpointer = AsyncMock()
    mock_checkpointer.setup = AsyncMock()

    with (
        patch("backend.main.QdrantClientWrapper") as mock_qdrant,
        patch("backend.main.ProviderRegistry") as mock_registry,
        patch("langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver") as mock_saver_cls,
    ):
        mock_qdrant_instance = AsyncMock()
        mock_qdrant_instance.connect = AsyncMock()
        mock_qdrant_instance.close = AsyncMock()
        mock_qdrant.return_value = mock_qdrant_instance

        mock_registry_instance = AsyncMock()
        mock_registry_instance.initialize = AsyncMock()
        mock_registry.return_value = mock_registry_instance

        mock_saver_cls.from_conn_string.return_value = mock_checkpointer

        yield {
            "qdrant": mock_qdrant_instance,
            "registry": mock_registry_instance,
        }


def test_app_creates_successfully(mock_services):
    """Verify the app factory creates a FastAPI app with all routers."""
    from backend.main import create_app

    app = create_app()
    assert app.title == "The Embedinator"

    # Assert on the OpenAPI schema rather than app.routes.
    #
    # FastAPI 0.141 stopped flattening included routers into app.routes: it now
    # appends a single fastapi.routing._IncludedRouter wrapper that has no
    # `.path` attribute. The previous `hasattr(r, "path")` guard silently
    # dropped that wrapper, so this list collapsed to FastAPI's four built-in
    # doc routes and the assertions below failed — while every endpoint kept
    # serving normally. A filter that can discard the very thing under
    # assertion turns a loud failure into a misleading one.
    #
    # The schema is the app's public contract and reports identical paths on
    # both 0.135.x and 0.141.x, so this assertion survives the next such change.
    paths = set(app.openapi()["paths"])
    assert "/api/health" in paths
    assert "/api/collections" in paths
    assert "/api/documents" in paths
    assert "/api/chat" in paths
    assert "/api/providers" in paths


@pytest.mark.xfail(reason="LangGraph strict checkpointer type validation rejects AsyncMock — pre-existing")
def test_app_startup_initializes_services(mock_services, tmp_path, monkeypatch):
    """Verify lifespan initializes DB, Qdrant, providers, and checkpointer on startup."""
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "test.db"))

    from backend.main import create_app

    app = create_app()

    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code in (200, 503)
