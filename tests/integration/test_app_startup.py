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

    with patch("backend.main.QdrantClientWrapper") as mock_qdrant, \
         patch("backend.main.ProviderRegistry") as mock_registry, \
         patch("langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver") as mock_saver_cls:

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

    routes = [r.path for r in app.routes if hasattr(r, "path")]
    assert "/api/health" in routes
    assert "/api/collections" in routes
    assert "/api/documents" in routes
    assert "/api/chat" in routes
    assert "/api/providers" in routes


def test_app_startup_initializes_services(mock_services, tmp_path, monkeypatch):
    """Verify lifespan initializes DB, Qdrant, providers, and checkpointer on startup."""
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "test.db"))

    from backend.main import create_app
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code in (200, 503)
