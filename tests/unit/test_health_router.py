"""Unit tests for health router — T023.

Tests:
- 200 when all services ok (status: "healthy")
- 503 when one service errors (status: "degraded")
- latency_ms is float in each service entry when healthy
- error_message is null when ok, string when error
- Three services present: sqlite, qdrant, ollama
Mock db, qdrant, ollama (httpx) probes.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.health import router


def _make_app(db=None, qdrant=None):
    """Create a test FastAPI app with mocked services."""
    app = FastAPI()
    app.include_router(router)
    app.state.db = db or AsyncMock()
    app.state.qdrant = qdrant or AsyncMock()
    return app


def _mock_httpx_success():
    """Mock httpx.AsyncClient returning 200 for Ollama."""
    mock_response = MagicMock()
    mock_response.status_code = 200

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


def _mock_httpx_failure(error=None):
    """Mock httpx.AsyncClient raising connection error for Ollama."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=error or httpx.ConnectError("Connection refused")
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


def _healthy_db():
    """SQLite mock that responds to SELECT 1."""
    db = AsyncMock()
    db.db = AsyncMock()
    db.db.execute = AsyncMock()
    return db


def _healthy_qdrant():
    """Qdrant mock that passes health check."""
    qdrant = AsyncMock()
    qdrant.health_check = AsyncMock(return_value=True)
    return qdrant


# ── All Healthy ──────────────────────────────────────────────────


class TestHealthAllOk:
    """Tests when all services are healthy."""

    def test_200_status_healthy(self):
        """All services ok returns 200 with status='healthy'."""
        db = _healthy_db()
        qdrant = _healthy_qdrant()
        mock_client = _mock_httpx_success()

        app = _make_app(db=db, qdrant=qdrant)
        with patch("backend.api.health.httpx.AsyncClient", return_value=mock_client):
            client = TestClient(app)
            resp = client.get("/api/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    def test_three_services_present(self):
        """Response contains sqlite, qdrant, ollama entries."""
        db = _healthy_db()
        qdrant = _healthy_qdrant()
        mock_client = _mock_httpx_success()

        app = _make_app(db=db, qdrant=qdrant)
        with patch("backend.api.health.httpx.AsyncClient", return_value=mock_client):
            client = TestClient(app)
            resp = client.get("/api/health")

        data = resp.json()
        assert len(data["services"]) == 3
        names = [s["name"] for s in data["services"]]
        assert "sqlite" in names
        assert "qdrant" in names
        assert "ollama" in names

    def test_all_services_status_ok(self):
        """All services report status 'ok'."""
        db = _healthy_db()
        qdrant = _healthy_qdrant()
        mock_client = _mock_httpx_success()

        app = _make_app(db=db, qdrant=qdrant)
        with patch("backend.api.health.httpx.AsyncClient", return_value=mock_client):
            client = TestClient(app)
            resp = client.get("/api/health")

        data = resp.json()
        for svc in data["services"]:
            assert svc["status"] == "ok"

    def test_latency_ms_is_float_when_healthy(self):
        """latency_ms is a float (not int, not None) when service is ok."""
        db = _healthy_db()
        qdrant = _healthy_qdrant()
        mock_client = _mock_httpx_success()

        app = _make_app(db=db, qdrant=qdrant)
        with patch("backend.api.health.httpx.AsyncClient", return_value=mock_client):
            client = TestClient(app)
            resp = client.get("/api/health")

        data = resp.json()
        for svc in data["services"]:
            assert svc["status"] == "ok"
            assert isinstance(svc["latency_ms"], (int, float))
            assert svc["latency_ms"] is not None
            assert svc["latency_ms"] >= 0

    def test_error_message_null_when_ok(self):
        """error_message is None when service is ok."""
        db = _healthy_db()
        qdrant = _healthy_qdrant()
        mock_client = _mock_httpx_success()

        app = _make_app(db=db, qdrant=qdrant)
        with patch("backend.api.health.httpx.AsyncClient", return_value=mock_client):
            client = TestClient(app)
            resp = client.get("/api/health")

        data = resp.json()
        for svc in data["services"]:
            assert svc["error_message"] is None


# ── Degraded ─────────────────────────────────────────────────────


class TestHealthDegraded:
    """Tests when one or more services are down."""

    def test_503_when_qdrant_errors(self):
        """Qdrant failure returns 503 with status='degraded'."""
        db = _healthy_db()
        qdrant = AsyncMock()
        qdrant.health_check = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client = _mock_httpx_success()

        app = _make_app(db=db, qdrant=qdrant)
        with patch("backend.api.health.httpx.AsyncClient", return_value=mock_client):
            client = TestClient(app)
            resp = client.get("/api/health")

        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "degraded"

    def test_503_when_ollama_errors(self):
        """Ollama failure returns 503 degraded."""
        db = _healthy_db()
        qdrant = _healthy_qdrant()
        mock_client = _mock_httpx_failure()

        app = _make_app(db=db, qdrant=qdrant)
        with patch("backend.api.health.httpx.AsyncClient", return_value=mock_client):
            client = TestClient(app)
            resp = client.get("/api/health")

        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "degraded"

    def test_503_when_sqlite_errors(self):
        """SQLite failure returns 503 degraded."""
        db = AsyncMock()
        db.db = AsyncMock()
        db.db.execute = AsyncMock(side_effect=Exception("disk I/O error"))
        qdrant = _healthy_qdrant()
        mock_client = _mock_httpx_success()

        app = _make_app(db=db, qdrant=qdrant)
        with patch("backend.api.health.httpx.AsyncClient", return_value=mock_client):
            client = TestClient(app)
            resp = client.get("/api/health")

        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "degraded"

    def test_error_service_has_error_message(self):
        """Failed service has error_message string, not None."""
        db = _healthy_db()
        qdrant = AsyncMock()
        qdrant.health_check = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client = _mock_httpx_success()

        app = _make_app(db=db, qdrant=qdrant)
        with patch("backend.api.health.httpx.AsyncClient", return_value=mock_client):
            client = TestClient(app)
            resp = client.get("/api/health")

        data = resp.json()
        qdrant_svc = next(s for s in data["services"] if s["name"] == "qdrant")
        assert qdrant_svc["status"] == "error"
        assert isinstance(qdrant_svc["error_message"], str)
        assert len(qdrant_svc["error_message"]) > 0

    def test_error_service_latency_is_none(self):
        """Failed service has latency_ms=None."""
        db = _healthy_db()
        qdrant = AsyncMock()
        qdrant.health_check = AsyncMock(side_effect=Exception("fail"))
        mock_client = _mock_httpx_success()

        app = _make_app(db=db, qdrant=qdrant)
        with patch("backend.api.health.httpx.AsyncClient", return_value=mock_client):
            client = TestClient(app)
            resp = client.get("/api/health")

        data = resp.json()
        qdrant_svc = next(s for s in data["services"] if s["name"] == "qdrant")
        assert qdrant_svc["latency_ms"] is None

    def test_healthy_services_still_report_ok(self):
        """When one service fails, others still report ok with latency."""
        db = _healthy_db()
        qdrant = AsyncMock()
        qdrant.health_check = AsyncMock(side_effect=Exception("fail"))
        mock_client = _mock_httpx_success()

        app = _make_app(db=db, qdrant=qdrant)
        with patch("backend.api.health.httpx.AsyncClient", return_value=mock_client):
            client = TestClient(app)
            resp = client.get("/api/health")

        data = resp.json()
        sqlite_svc = next(s for s in data["services"] if s["name"] == "sqlite")
        ollama_svc = next(s for s in data["services"] if s["name"] == "ollama")
        assert sqlite_svc["status"] == "ok"
        assert ollama_svc["status"] == "ok"
        assert sqlite_svc["latency_ms"] is not None
        assert ollama_svc["latency_ms"] is not None

    def test_qdrant_health_check_returns_false(self):
        """Qdrant health_check returning False (not exception) is error."""
        db = _healthy_db()
        qdrant = AsyncMock()
        qdrant.health_check = AsyncMock(return_value=False)
        mock_client = _mock_httpx_success()

        app = _make_app(db=db, qdrant=qdrant)
        with patch("backend.api.health.httpx.AsyncClient", return_value=mock_client):
            client = TestClient(app)
            resp = client.get("/api/health")

        assert resp.status_code == 503
        data = resp.json()
        qdrant_svc = next(s for s in data["services"] if s["name"] == "qdrant")
        assert qdrant_svc["status"] == "error"
