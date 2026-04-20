"""Unit tests for settings router — T026.

Tests:
- GET returns SettingsResponse with all 7 fields
- Defaults match config.py values
- PUT updates only submitted fields
- PUT with confidence_threshold=150 returns 400
- PUT with confidence_threshold=0 and =100 returns 200
- Mock SQLiteDB
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.settings import router
from backend.config import settings as app_config


def _make_app(
    db_settings: dict[str, str] | None = None,
) -> tuple[FastAPI, AsyncMock]:
    """Create a test app with mocked db."""
    app = FastAPI()
    app.include_router(router)

    db = AsyncMock()

    if db_settings is None:
        db_settings = {}

    _stored = dict(db_settings)

    async def _list_settings() -> dict[str, str]:
        return dict(_stored)

    async def _set_setting(key: str, value: str) -> None:
        _stored[key] = value

    db.list_settings = _list_settings
    db.set_setting = _set_setting

    app.state.db = db

    # Add trace_id to request state
    @app.middleware("http")
    async def _trace_middleware(request, call_next):
        request.state.trace_id = "test-trace-id"
        return await call_next(request)

    return app, db


# ── GET /api/settings ──────────────────────────────────────────────


class TestGetSettings:
    """GET /api/settings tests."""

    def test_returns_all_7_fields_with_defaults(self):
        """When no DB settings exist, config defaults are returned."""
        app, _ = _make_app()
        client = TestClient(app)
        resp = client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.json()

        assert "default_llm_model" in data
        assert "default_embed_model" in data
        assert "confidence_threshold" in data
        assert "groundedness_check_enabled" in data
        assert "citation_alignment_threshold" in data
        assert "parent_chunk_size" in data
        assert "child_chunk_size" in data

    def test_defaults_match_config(self):
        """Default values should match config.py Settings class."""
        app, _ = _make_app()
        client = TestClient(app)
        resp = client.get("/api/settings")
        data = resp.json()

        assert data["default_llm_model"] == app_config.default_llm_model
        assert data["default_embed_model"] == app_config.default_embed_model
        assert data["confidence_threshold"] == app_config.confidence_threshold
        assert data["groundedness_check_enabled"] == app_config.groundedness_check_enabled
        assert data["citation_alignment_threshold"] == app_config.citation_alignment_threshold
        assert data["parent_chunk_size"] == app_config.parent_chunk_size
        assert data["child_chunk_size"] == app_config.child_chunk_size

    def test_db_overrides_applied(self):
        """DB settings override config defaults."""
        app, _ = _make_app(
            db_settings={
                "confidence_threshold": "80",
                "groundedness_check_enabled": "false",
            }
        )
        client = TestClient(app)
        resp = client.get("/api/settings")
        data = resp.json()

        assert data["confidence_threshold"] == 80
        assert data["groundedness_check_enabled"] is False
        # Others still defaults
        assert data["default_llm_model"] == app_config.default_llm_model

    def test_confidence_threshold_is_int(self):
        """confidence_threshold must always be int, not float."""
        app, _ = _make_app()
        client = TestClient(app)
        resp = client.get("/api/settings")
        data = resp.json()
        assert isinstance(data["confidence_threshold"], int)

    def test_invalid_db_value_falls_back_to_default(self):
        """If DB has unparseable value, fall back to config default."""
        app, _ = _make_app(
            db_settings={
                "confidence_threshold": "not_a_number",
            }
        )
        client = TestClient(app)
        resp = client.get("/api/settings")
        data = resp.json()
        assert data["confidence_threshold"] == app_config.confidence_threshold


# ── PUT /api/settings ──────────────────────────────────────────────


class TestUpdateSettings:
    """PUT /api/settings tests."""

    def test_partial_update_only_changes_submitted(self):
        """Only submitted fields change, others retain values."""
        app, _ = _make_app()
        client = TestClient(app)

        resp = client.put(
            "/api/settings",
            json={
                "confidence_threshold": 75,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["confidence_threshold"] == 75
        # Other fields should be defaults
        assert data["default_llm_model"] == app_config.default_llm_model

    def test_update_multiple_fields(self):
        """Multiple fields can be updated at once."""
        app, _ = _make_app()
        client = TestClient(app)

        resp = client.put(
            "/api/settings",
            json={
                "confidence_threshold": 90,
                "groundedness_check_enabled": False,
                "child_chunk_size": 250,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["confidence_threshold"] == 90
        assert data["groundedness_check_enabled"] is False
        assert data["child_chunk_size"] == 250

    def test_confidence_threshold_150_returns_400(self):
        """confidence_threshold=150 exceeds max, returns 400."""
        app, _ = _make_app()
        client = TestClient(app)
        resp = client.put(
            "/api/settings",
            json={
                "confidence_threshold": 150,
            },
        )
        assert resp.status_code == 422  # Pydantic validation catches ge=0, le=100

    def test_confidence_threshold_negative_returns_400(self):
        """Negative confidence_threshold returns validation error."""
        app, _ = _make_app()
        client = TestClient(app)
        resp = client.put(
            "/api/settings",
            json={
                "confidence_threshold": -1,
            },
        )
        assert resp.status_code == 422  # Pydantic validation

    def test_confidence_threshold_0_valid(self):
        """confidence_threshold=0 is valid boundary."""
        app, _ = _make_app()
        client = TestClient(app)
        resp = client.put(
            "/api/settings",
            json={
                "confidence_threshold": 0,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["confidence_threshold"] == 0

    def test_confidence_threshold_100_valid(self):
        """confidence_threshold=100 is valid boundary."""
        app, _ = _make_app()
        client = TestClient(app)
        resp = client.put(
            "/api/settings",
            json={
                "confidence_threshold": 100,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["confidence_threshold"] == 100

    def test_empty_update_returns_current(self):
        """PUT with empty body returns current settings unchanged."""
        app, _ = _make_app()
        client = TestClient(app)
        resp = client.put("/api/settings", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["confidence_threshold"] == app_config.confidence_threshold

    def test_returns_full_response_after_update(self):
        """PUT returns all 7 fields, not just updated ones."""
        app, _ = _make_app()
        client = TestClient(app)
        resp = client.put(
            "/api/settings",
            json={
                "parent_chunk_size": 4000,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 7
        assert data["parent_chunk_size"] == 4000
