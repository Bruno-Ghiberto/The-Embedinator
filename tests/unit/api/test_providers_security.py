"""Tests for provider response security (FR-007: no encrypted keys in responses)."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.api.providers import router


def _make_app(providers_data):
    """Create minimal FastAPI app with providers router and mock DB."""
    app = FastAPI()
    app.include_router(router)

    mock_db = AsyncMock()
    mock_db.list_providers = AsyncMock(return_value=providers_data)
    app.state.db = mock_db
    app.state.key_manager = None
    return app


@pytest.mark.asyncio
async def test_provider_response_includes_has_key():
    """AC-7: Provider response includes has_key boolean."""
    providers = [
        {"name": "openai", "is_active": 1, "api_key_encrypted": "encrypted-value", "base_url": None},
        {"name": "ollama", "is_active": 1, "api_key_encrypted": None, "base_url": None},
    ]
    app = _make_app(providers)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/providers")

    assert response.status_code == 200
    data = response.json()
    provider_list = data["providers"]

    openai_provider = next(p for p in provider_list if p["name"] == "openai")
    assert "has_key" in openai_provider
    assert openai_provider["has_key"] is True

    ollama_provider = next(p for p in provider_list if p["name"] == "ollama")
    assert "has_key" in ollama_provider
    assert ollama_provider["has_key"] is False


@pytest.mark.asyncio
async def test_provider_response_excludes_encrypted_key():
    """AC-7: Provider response does NOT include api_key_encrypted."""
    providers = [
        {"name": "openai", "is_active": 1, "api_key_encrypted": "super-secret-encrypted", "base_url": None},
    ]
    app = _make_app(providers)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/providers")

    assert response.status_code == 200
    data = response.json()
    for provider in data["providers"]:
        assert "api_key_encrypted" not in provider
        assert "api_key" not in provider
