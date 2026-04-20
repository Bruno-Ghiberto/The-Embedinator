"""
Integration tests for spec-12 exception handlers in backend/main.py.

Uses a minimal FastAPI app with the same 4 handlers registered and
trigger routes for each exception type. Tests verify HTTP status codes
and response body shape WITHOUT needing the full app startup.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from backend.errors import (
    CircuitOpenError,
    EmbeddinatorError,
    LLMCallError,
    OllamaConnectionError,
    QdrantConnectionError,
    SQLiteError,
)
from backend.providers.base import ProviderRateLimitError


def _build_test_app() -> FastAPI:
    """Build a minimal FastAPI app with all 4 spec-12 handlers and trigger routes."""
    app = FastAPI()

    # Register handlers in the same order as backend/main.py
    @app.exception_handler(ProviderRateLimitError)
    async def rate_limit_handler(request, exc: ProviderRateLimitError):
        trace_id = getattr(request.state, "trace_id", "")
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "PROVIDER_RATE_LIMIT",
                    "message": f"Rate limit exceeded for provider: {exc.provider}",
                    "details": {"provider": exc.provider},
                },
                "trace_id": trace_id,
            },
        )

    @app.exception_handler(QdrantConnectionError)
    async def qdrant_handler(request, exc: QdrantConnectionError):
        trace_id = getattr(request.state, "trace_id", "")
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "QDRANT_UNAVAILABLE",
                    "message": "Vector database is temporarily unavailable",
                    "details": {},
                },
                "trace_id": trace_id,
            },
        )

    @app.exception_handler(OllamaConnectionError)
    async def ollama_handler(request, exc: OllamaConnectionError):
        trace_id = getattr(request.state, "trace_id", "")
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "OLLAMA_UNAVAILABLE",
                    "message": "Inference service is temporarily unavailable",
                    "details": {},
                },
                "trace_id": trace_id,
            },
        )

    @app.exception_handler(EmbeddinatorError)
    async def embedinator_error_handler(request, exc: EmbeddinatorError):
        trace_id = getattr(request.state, "trace_id", "")
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An internal error occurred",
                    "details": {},
                },
                "trace_id": trace_id,
            },
        )

    # Trigger routes -- each raises a specific exception
    @app.get("/trigger/rate-limit")
    async def trigger_rate_limit():
        raise ProviderRateLimitError("test-provider")

    @app.get("/trigger/qdrant")
    async def trigger_qdrant():
        raise QdrantConnectionError("qdrant down")

    @app.get("/trigger/ollama")
    async def trigger_ollama():
        raise OllamaConnectionError("ollama down")

    @app.get("/trigger/embedinator")
    async def trigger_embedinator():
        raise EmbeddinatorError("generic error")

    @app.get("/trigger/sqlite")
    async def trigger_sqlite():
        raise SQLiteError("sqlite error")

    @app.get("/trigger/llm")
    async def trigger_llm():
        raise LLMCallError("llm error")

    @app.get("/trigger/circuit")
    async def trigger_circuit():
        raise CircuitOpenError("circuit open")

    return app


@pytest.fixture
def client():
    app = _build_test_app()
    return TestClient(app, raise_server_exceptions=False)


class TestProviderRateLimitHandler:
    def test_returns_429(self, client):
        resp = client.get("/trigger/rate-limit")
        assert resp.status_code == 429

    def test_response_body_uses_nested_envelope(self, client):
        resp = client.get("/trigger/rate-limit")
        body = resp.json()
        assert "error" in body
        assert "code" in body["error"]

    def test_error_code_is_uppercase(self, client):
        resp = client.get("/trigger/rate-limit")
        code = resp.json()["error"]["code"]
        assert code == code.upper(), f"code must be UPPER_SNAKE_CASE, got: {code}"
        assert code == "PROVIDER_RATE_LIMIT"

    def test_response_includes_trace_id(self, client):
        resp = client.get("/trigger/rate-limit")
        assert "trace_id" in resp.json()

    def test_provider_name_in_details(self, client):
        resp = client.get("/trigger/rate-limit")
        details = resp.json()["error"]["details"]
        assert details.get("provider") == "test-provider"

    def test_no_raw_exception_text(self, client):
        resp = client.get("/trigger/rate-limit")
        assert "ProviderRateLimitError" not in resp.json()["error"]["message"]


class TestQdrantConnectionHandler:
    def test_returns_503(self, client):
        resp = client.get("/trigger/qdrant")
        assert resp.status_code == 503

    def test_error_code_is_qdrant_unavailable(self, client):
        resp = client.get("/trigger/qdrant")
        assert resp.json()["error"]["code"] == "QDRANT_UNAVAILABLE"

    def test_uses_nested_envelope(self, client):
        resp = client.get("/trigger/qdrant")
        body = resp.json()
        assert "error" in body
        assert "trace_id" in body

    def test_no_raw_exception_text(self, client):
        resp = client.get("/trigger/qdrant")
        assert "QdrantConnectionError" not in resp.json()["error"]["message"]


class TestOllamaConnectionHandler:
    def test_returns_503(self, client):
        resp = client.get("/trigger/ollama")
        assert resp.status_code == 503

    def test_error_code_is_ollama_unavailable(self, client):
        resp = client.get("/trigger/ollama")
        assert resp.json()["error"]["code"] == "OLLAMA_UNAVAILABLE"

    def test_uses_nested_envelope(self, client):
        resp = client.get("/trigger/ollama")
        body = resp.json()
        assert "error" in body
        assert "trace_id" in body


class TestGlobalEmbeddinatorErrorHandler:
    def test_generic_embedinator_error_returns_500(self, client):
        resp = client.get("/trigger/embedinator")
        assert resp.status_code == 500

    def test_sqlite_error_falls_through_to_global_handler(self, client):
        resp = client.get("/trigger/sqlite")
        assert resp.status_code == 500

    def test_llm_call_error_falls_through_to_global_handler(self, client):
        resp = client.get("/trigger/llm")
        assert resp.status_code == 500

    def test_circuit_open_error_falls_through_to_global_handler(self, client):
        resp = client.get("/trigger/circuit")
        assert resp.status_code == 500

    def test_error_code_is_internal_error(self, client):
        resp = client.get("/trigger/embedinator")
        assert resp.json()["error"]["code"] == "INTERNAL_ERROR"

    def test_response_uses_nested_envelope(self, client):
        resp = client.get("/trigger/embedinator")
        body = resp.json()
        assert "error" in body
        assert "trace_id" in body

    def test_no_raw_exception_text_in_any_handler(self, client):
        class_names = {
            "/trigger/embedinator": "EmbeddinatorError",
            "/trigger/qdrant": "QdrantConnectionError",
            "/trigger/ollama": "OllamaConnectionError",
            "/trigger/rate-limit": "ProviderRateLimitError",
        }
        for route, class_name in class_names.items():
            resp = client.get(route)
            message = resp.json()["error"]["message"]
            assert class_name not in message, (
                f"Raw exception class name '{class_name}' found in message for {route}: {message!r}"
            )
