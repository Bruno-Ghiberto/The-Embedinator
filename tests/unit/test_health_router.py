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

import backend.api.health as health_module
from backend.api.health import router
from backend.config import settings


@pytest.fixture(autouse=True)
def _consume_first_probe():
    """Neutralise the ``_first_probe`` module global (health.py:22) for every test.

    ``/api/health`` short-circuits to ``{"status": "starting"}`` on the very first
    call of the process and never probes dependencies. Nothing in this module reset
    that flag, so these tests only passed because ``tests/integration/`` sorts before
    ``tests/unit/`` and burned it first. Run this file as its own target — which is
    how the external runner invokes it — and the first test received "starting".
    Reset it explicitly so each test is order-independent.
    """
    original = health_module._first_probe
    health_module._first_probe = False
    yield
    health_module._first_probe = original


def _make_app(db=None, qdrant=None):
    """Create a test FastAPI app with mocked services."""
    app = FastAPI()
    app.include_router(router)
    app.state.db = db or AsyncMock()
    app.state.qdrant = qdrant or AsyncMock()
    return app


def _mock_httpx_success():
    """Mock httpx.AsyncClient returning 200 for Ollama with both defaults installed.

    This previously left ``json()`` as a bare MagicMock. ``data.get("models", [])``
    then returned a MagicMock that iterates empty, so every "all healthy" test below
    actually ran with BOTH model flags ``False`` and still asserted 200 "healthy" —
    they were asserting BUG-026's behaviour, not health. Supplying the configured
    models makes the fixture mean what its name claims.
    """
    return _mock_httpx_with_models(settings.default_llm_model, settings.default_embed_model)


def _mock_httpx_failure(error=None):
    """Mock httpx.AsyncClient raising connection error for Ollama."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=error or httpx.ConnectError("Connection refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


def _mock_httpx_with_models(*installed: str):
    """Mock Ollama ``/api/tags`` returning exactly ``installed`` as the model list.

    Unlike ``_mock_httpx_success``, this supplies a real JSON payload, so the
    model-availability flags computed in ``_probe_ollama`` reflect the argument
    rather than an empty set.
    """
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value={"models": [{"name": n} for n in installed]})

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


def _get_health(mock_client):
    """Drive GET /api/health against healthy sqlite+qdrant and the given Ollama mock."""
    app = _make_app(db=_healthy_db(), qdrant=_healthy_qdrant())
    with patch("backend.api.health.httpx.AsyncClient", return_value=mock_client):
        return TestClient(app).get("/api/health")


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


# ── Model availability — BUG-026 / BUG-025 ───────────────────────


def _ollama_entry(resp):
    """Extract the ollama service entry from a health response."""
    return next(s for s in resp.json()["services"] if s["name"] == "ollama")


class TestAggregateReflectsModelAvailability:
    """BUG-026: a false model flag MUST degrade the aggregate status.

    Ollama being reachable is not the same as Ollama being usable. The aggregation
    at health.py only tested ``status == "error"``, so a missing required model
    returned 200 "healthy" — the capability was invisible end-to-end.
    """

    def test_503_degraded_when_a_required_model_is_missing(self):
        """Embed model absent from /api/tags MUST yield 503 + 'degraded'."""
        resp = _get_health(_mock_httpx_with_models(settings.default_llm_model))

        assert resp.status_code == 503
        assert resp.json()["status"] == "degraded"

    def test_missing_model_is_named_in_the_flags(self):
        """The degraded response identifies WHICH model is unavailable."""
        resp = _get_health(_mock_httpx_with_models(settings.default_llm_model))

        models = _ollama_entry(resp)["models"]
        assert models[settings.default_embed_model] is False
        assert models[settings.default_llm_model] is True

    def test_ollama_entry_stays_ok_when_only_a_model_is_missing(self):
        """Reachable Ollama MUST NOT be reported as an errored service.

        Degrading the aggregate is correct; claiming the service is down is a
        second lie in the opposite direction.
        """
        resp = _get_health(_mock_httpx_with_models(settings.default_llm_model))

        ollama = _ollama_entry(resp)
        assert ollama["status"] == "ok"
        assert ollama["error_message"] is None
        assert ollama["latency_ms"] is not None

    def test_200_healthy_when_every_required_model_is_present(self):
        """The degradation must be specific — all models present stays healthy."""
        resp = _get_health(_mock_httpx_with_models(settings.default_llm_model, settings.default_embed_model))

        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"
        assert all(_ollama_entry(resp)["models"].values())

    def test_unreachable_ollama_still_wins_over_model_flags(self):
        """A connection failure remains an errored service, not a flag problem."""
        resp = _get_health(_mock_httpx_failure())

        assert resp.status_code == 503
        assert _ollama_entry(resp)["status"] == "error"


class TestModelNameTagNormalization:
    """BUG-025: ``:latest`` suffix must not defeat the availability match.

    Ollama reports bare-named models as ``<name>:latest`` in /api/tags. The
    configured default (``nomic-embed-text``) carries no tag, so exact string
    comparison reported it missing on every boot of a correct install. That false
    flag is the input BUG-026's aggregation consumes — the two must land together
    or a correctly installed stack reports itself degraded forever.
    """

    def test_latest_suffix_matches_an_untagged_configured_model(self):
        """/api/tags 'nomic-embed-text:latest' satisfies config 'nomic-embed-text'."""
        resp = _get_health(
            _mock_httpx_with_models(settings.default_llm_model, f"{settings.default_embed_model}:latest")
        )

        assert _ollama_entry(resp)["models"][settings.default_embed_model] is True
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_explicit_tag_still_matches_exactly(self):
        """A configured model that already carries a tag keeps matching."""
        resp = _get_health(_mock_httpx_with_models(settings.default_llm_model, settings.default_embed_model))

        assert _ollama_entry(resp)["models"][settings.default_llm_model] is True

    def test_a_different_tag_is_not_a_match(self):
        """Normalisation must not collapse distinct tags of the same model."""
        base = settings.default_llm_model.split(":")[0]
        resp = _get_health(_mock_httpx_with_models(f"{base}:some-other-tag", settings.default_embed_model))

        assert _ollama_entry(resp)["models"][settings.default_llm_model] is False
        assert resp.status_code == 503
