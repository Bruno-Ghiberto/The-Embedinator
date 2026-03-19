"""Unit tests for models router — T019.

Tests:
- GET /models/llm returns ModelInfo list with model_type="llm"
- GET /models/embed returns only embedding models
- 503 when Ollama unreachable
- Empty response when no models
- Embedding model detection patterns
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.models import router, _is_embed_model


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


# Sample Ollama /api/tags response
_OLLAMA_RESPONSE = {
    "models": [
        {
            "name": "qwen2.5:7b",
            "size": 5044912345,
            "details": {"quantization_level": "Q4_K_M"},
        },
        {
            "name": "llama3.2:3b",
            "size": 2015678901,
            "details": {"quantization_level": "Q4_0"},
        },
        {
            "name": "nomic-embed-text",
            "size": 274123456,
            "details": {},
        },
        {
            "name": "mxbai-embed-large",
            "size": 670123456,
            "details": {},
        },
        {
            "name": "custom-model:embed",
            "size": 100000000,
            "details": {},
        },
    ]
}


def _mock_httpx_success(response_json: dict):
    """Return a mock that patches httpx.AsyncClient for success."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = response_json
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


def _mock_httpx_failure():
    """Return a mock that patches httpx.AsyncClient for connection failure."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


# ── _is_embed_model() ──────────────────────────────────────────────


class TestIsEmbedModel:
    """Test embedding model name detection."""

    def test_nomic_embed_text(self):
        assert _is_embed_model("nomic-embed-text") is True

    def test_mxbai_embed_large(self):
        assert _is_embed_model("mxbai-embed-large") is True

    def test_model_with_embed_tag(self):
        assert _is_embed_model("custom:embed") is True

    def test_model_with_embedding_tag(self):
        assert _is_embed_model("custom:embedding") is True

    def test_nomic_with_tag(self):
        assert _is_embed_model("nomic-embed-text:latest") is True

    def test_regular_llm(self):
        assert _is_embed_model("qwen2.5:7b") is False

    def test_llama_model(self):
        assert _is_embed_model("llama3.2:3b") is False


# ── GET /api/models/llm ────────────────────────────────────────────


class TestListLLMModels:
    """GET /api/models/llm tests."""

    def test_returns_llm_models_only(self):
        """Should return only LLM models, not embedding models."""
        app = _make_app()
        mock_client = _mock_httpx_success(_OLLAMA_RESPONSE)

        with patch("backend.api.models.httpx.AsyncClient", return_value=mock_client):
            client = TestClient(app)
            resp = client.get("/api/models/llm")

        assert resp.status_code == 200
        data = resp.json()
        models = data["models"]
        # Only qwen2.5:7b and llama3.2:3b should be returned (not embed models)
        assert len(models) == 2
        names = {m["name"] for m in models}
        assert "qwen2.5:7b" in names
        assert "llama3.2:3b" in names
        # All should have model_type=llm
        for m in models:
            assert m["model_type"] == "llm"
            assert m["provider"] == "ollama"

    def test_llm_model_fields(self):
        """Verify ModelInfo fields are populated correctly."""
        app = _make_app()
        mock_client = _mock_httpx_success(_OLLAMA_RESPONSE)

        with patch("backend.api.models.httpx.AsyncClient", return_value=mock_client):
            client = TestClient(app)
            resp = client.get("/api/models/llm")

        models = resp.json()["models"]
        qwen = next(m for m in models if m["name"] == "qwen2.5:7b")
        assert qwen["provider"] == "ollama"
        assert qwen["model_type"] == "llm"
        assert qwen["size_gb"] is not None
        assert qwen["size_gb"] > 0
        assert qwen["quantization"] == "Q4_K_M"

    def test_503_when_ollama_unreachable(self):
        """Should return 503 SERVICE_UNAVAILABLE when Ollama is down."""
        app = _make_app()
        mock_client = _mock_httpx_failure()

        with patch("backend.api.models.httpx.AsyncClient", return_value=mock_client):
            client = TestClient(app)
            resp = client.get("/api/models/llm")

        assert resp.status_code == 503
        detail = resp.json()["detail"]
        assert detail["error"]["code"] == "SERVICE_UNAVAILABLE"

    def test_empty_list_when_no_models(self):
        """Should return empty list, not error, when Ollama has no models."""
        app = _make_app()
        mock_client = _mock_httpx_success({"models": []})

        with patch("backend.api.models.httpx.AsyncClient", return_value=mock_client):
            client = TestClient(app)
            resp = client.get("/api/models/llm")

        assert resp.status_code == 200
        assert resp.json()["models"] == []


# ── GET /api/models/embed ──────────────────────────────────────────


class TestListEmbedModels:
    """GET /api/models/embed tests."""

    def test_returns_embed_models_only(self):
        """Should return only embedding models."""
        app = _make_app()
        mock_client = _mock_httpx_success(_OLLAMA_RESPONSE)

        with patch("backend.api.models.httpx.AsyncClient", return_value=mock_client):
            client = TestClient(app)
            resp = client.get("/api/models/embed")

        assert resp.status_code == 200
        models = resp.json()["models"]
        # nomic-embed-text, mxbai-embed-large, custom-model:embed
        assert len(models) == 3
        for m in models:
            assert m["model_type"] == "embed"
            assert m["provider"] == "ollama"
        names = {m["name"] for m in models}
        assert "nomic-embed-text" in names
        assert "mxbai-embed-large" in names
        assert "custom-model:embed" in names

    def test_503_when_ollama_unreachable(self):
        """Should return 503 when Ollama is down for embed too."""
        app = _make_app()
        mock_client = _mock_httpx_failure()

        with patch("backend.api.models.httpx.AsyncClient", return_value=mock_client):
            client = TestClient(app)
            resp = client.get("/api/models/embed")

        assert resp.status_code == 503

    def test_empty_when_no_embed_models(self):
        """Return empty list when no embedding models available."""
        app = _make_app()
        only_llm = {"models": [{"name": "qwen2.5:7b", "size": 5000000000, "details": {}}]}
        mock_client = _mock_httpx_success(only_llm)

        with patch("backend.api.models.httpx.AsyncClient", return_value=mock_client):
            client = TestClient(app)
            resp = client.get("/api/models/embed")

        assert resp.status_code == 200
        assert resp.json()["models"] == []
