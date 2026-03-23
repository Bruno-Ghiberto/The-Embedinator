"""Unit tests for providers router — T018, T029, T030.

Tests:
- GET /api/providers returns list with has_key indicator
- API key value NEVER appears in any response
- PUT /key encrypts via KeyManager and stores
- DELETE /key clears key
- 503 KEY_MANAGER_UNAVAILABLE when key_manager is None
- 404 for unknown provider
- Ollama always listed even if not in DB
- GET /api/providers/health — Ollama reachable/unreachable, cloud no-key, exception → False
- GET /api/models/llm — cloud model visible only when key stored
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.providers import router


def _make_app(
    providers: list[dict] | None = None,
    key_manager: MagicMock | None = "default",
    get_provider_result: dict | None | str = "auto",
) -> FastAPI:
    """Create a test app with mocked db and key_manager on app.state."""
    app = FastAPI()
    app.include_router(router)

    db = AsyncMock()

    if providers is None:
        providers = []
    db.list_providers = AsyncMock(return_value=providers)

    # get_provider: "auto" means derive from providers list
    if get_provider_result == "auto":
        async def _get_provider(name: str) -> dict | None:
            for p in providers:
                if p["name"] == name:
                    return p
            return None
        db.get_provider = _get_provider
    elif get_provider_result is None:
        db.get_provider = AsyncMock(return_value=None)
    else:
        db.get_provider = AsyncMock(return_value=get_provider_result)

    db.update_provider = AsyncMock()

    if key_manager == "default":
        km = MagicMock()
        km.encrypt = MagicMock(return_value="encrypted_token_abc")
        km.decrypt = MagicMock(return_value="sk-test-key")
        app.state.key_manager = km
    else:
        app.state.key_manager = key_manager

    app.state.db = db
    return app


# ── GET /api/providers ──────────────────────────────────────────────


class TestListProviders:
    """GET /api/providers tests."""

    def test_has_key_true_when_encrypted_key_present(self):
        """Provider with api_key_encrypted shows has_key=True."""
        app = _make_app(providers=[
            {"name": "openai", "is_active": False, "api_key_encrypted": "enc123", "base_url": None},
        ])
        client = TestClient(app)
        resp = client.get("/api/providers")
        assert resp.status_code == 200
        data = resp.json()
        providers = data["providers"]
        openai_p = next(p for p in providers if p["name"] == "openai")
        assert openai_p["has_key"] is True

    def test_has_key_false_when_no_encrypted_key(self):
        """Provider without api_key_encrypted shows has_key=False."""
        app = _make_app(providers=[
            {"name": "openai", "is_active": True, "api_key_encrypted": None, "base_url": None},
        ])
        client = TestClient(app)
        resp = client.get("/api/providers")
        assert resp.status_code == 200
        providers = resp.json()["providers"]
        openai_p = next(p for p in providers if p["name"] == "openai")
        assert openai_p["has_key"] is False

    def test_has_key_false_when_empty_string(self):
        """Provider with empty string api_key_encrypted shows has_key=False."""
        app = _make_app(providers=[
            {"name": "openai", "is_active": True, "api_key_encrypted": "", "base_url": None},
        ])
        client = TestClient(app)
        resp = client.get("/api/providers")
        providers = resp.json()["providers"]
        openai_p = next(p for p in providers if p["name"] == "openai")
        assert openai_p["has_key"] is False

    def test_api_key_never_returned_in_list(self):
        """Response NEVER contains api_key_encrypted or api_key fields."""
        app = _make_app(providers=[
            {"name": "openai", "is_active": True, "api_key_encrypted": "secret_enc", "base_url": None},
        ])
        client = TestClient(app)
        resp = client.get("/api/providers")
        body_str = resp.text
        assert "api_key_encrypted" not in body_str
        assert "secret_enc" not in body_str
        # api_key should not appear as a field (ProviderKeyRequest is input only)
        for p in resp.json()["providers"]:
            assert "api_key_encrypted" not in p
            assert "api_key" not in p

    def test_ollama_always_listed(self):
        """Ollama appears even when not in DB."""
        app = _make_app(providers=[])
        client = TestClient(app)
        resp = client.get("/api/providers")
        providers = resp.json()["providers"]
        assert len(providers) >= 1
        ollama = next(p for p in providers if p["name"] == "ollama")
        assert ollama["is_active"] is True
        assert ollama["has_key"] is False

    def test_ollama_not_duplicated_if_in_db(self):
        """If Ollama is already in DB, it should not be duplicated."""
        app = _make_app(providers=[
            {"name": "ollama", "is_active": True, "api_key_encrypted": None, "base_url": "http://ollama:11434"},
        ])
        client = TestClient(app)
        resp = client.get("/api/providers")
        providers = resp.json()["providers"]
        ollama_count = sum(1 for p in providers if p["name"] == "ollama")
        assert ollama_count == 1

    def test_multiple_providers_listed(self):
        """Multiple providers returned correctly."""
        app = _make_app(providers=[
            {"name": "ollama", "is_active": True, "api_key_encrypted": None, "base_url": None},
            {"name": "openai", "is_active": False, "api_key_encrypted": "enc_key", "base_url": None},
            {"name": "anthropic", "is_active": False, "api_key_encrypted": None, "base_url": None},
        ])
        client = TestClient(app)
        resp = client.get("/api/providers")
        providers = resp.json()["providers"]
        assert len(providers) == 3
        names = {p["name"] for p in providers}
        assert names == {"ollama", "openai", "anthropic"}


# ── PUT /api/providers/{name}/key ───────────────────────────────────


class TestSaveProviderKey:
    """PUT /api/providers/{name}/key tests."""

    def test_put_key_encrypts_and_stores(self):
        """PUT encrypts key via KeyManager and returns has_key=True."""
        providers = [
            {"name": "openai", "is_active": False, "api_key_encrypted": None, "base_url": None},
        ]
        app = _make_app(providers=providers)
        client = TestClient(app)
        resp = client.put("/api/providers/openai/key", json={"api_key": "sk-test-123"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "openai"
        assert data["has_key"] is True

        # Verify KeyManager.encrypt was called
        app.state.key_manager.encrypt.assert_called_once_with("sk-test-123")
        # Verify db.update_provider was called with encrypted value
        app.state.db.update_provider.assert_called_once_with(
            "openai", api_key_encrypted="encrypted_token_abc"
        )

    def test_put_key_response_never_contains_key_value(self):
        """PUT response NEVER includes the actual key or encrypted value."""
        providers = [
            {"name": "openai", "is_active": False, "api_key_encrypted": None, "base_url": None},
        ]
        app = _make_app(providers=providers)
        client = TestClient(app)
        resp = client.put("/api/providers/openai/key", json={"api_key": "sk-secret"})
        body_str = resp.text
        assert "sk-secret" not in body_str
        assert "encrypted_token_abc" not in body_str
        assert "api_key" not in body_str

    def test_put_key_503_when_key_manager_none(self):
        """PUT returns 503 KEY_MANAGER_UNAVAILABLE when key_manager is None."""
        providers = [
            {"name": "openai", "is_active": False, "api_key_encrypted": None, "base_url": None},
        ]
        app = _make_app(providers=providers, key_manager=None)
        client = TestClient(app)

        # Add trace_id middleware simulation
        @app.middleware("http")
        async def _trace_middleware(request, call_next):
            request.state.trace_id = "test-trace-id"
            return await call_next(request)

        client = TestClient(app)
        resp = client.put("/api/providers/openai/key", json={"api_key": "sk-test"})
        assert resp.status_code == 503
        detail = resp.json()["detail"]
        assert detail["error"]["code"] == "KEY_MANAGER_UNAVAILABLE"

    def test_put_key_404_unknown_provider(self):
        """PUT returns 404 PROVIDER_NOT_FOUND for unknown provider."""
        app = _make_app(providers=[], get_provider_result=None)
        client = TestClient(app)
        resp = client.put("/api/providers/unknown/key", json={"api_key": "sk-test"})
        assert resp.status_code == 404
        detail = resp.json()["detail"]
        assert detail["error"]["code"] == "PROVIDER_NOT_FOUND"


# ── DELETE /api/providers/{name}/key ────────────────────────────────


class TestDeleteProviderKey:
    """DELETE /api/providers/{name}/key tests."""

    def test_delete_key_clears_and_returns_has_key_false(self):
        """DELETE clears key and returns has_key=False."""
        providers = [
            {"name": "openai", "is_active": True, "api_key_encrypted": "enc_key", "base_url": None},
        ]
        app = _make_app(providers=providers)
        client = TestClient(app)
        resp = client.delete("/api/providers/openai/key")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "openai"
        assert data["has_key"] is False

        # Verify db.update_provider was called with empty string to clear
        app.state.db.update_provider.assert_called_once_with(
            "openai", api_key_encrypted=""
        )

    def test_delete_key_404_unknown_provider(self):
        """DELETE returns 404 for unknown provider."""
        app = _make_app(providers=[], get_provider_result=None)
        client = TestClient(app)
        resp = client.delete("/api/providers/unknown/key")
        assert resp.status_code == 404
        detail = resp.json()["detail"]
        assert detail["error"]["code"] == "PROVIDER_NOT_FOUND"

    def test_delete_key_response_never_contains_key(self):
        """DELETE response never contains key values."""
        providers = [
            {"name": "openai", "is_active": True, "api_key_encrypted": "secret_enc", "base_url": None},
        ]
        app = _make_app(providers=providers)
        client = TestClient(app)
        resp = client.delete("/api/providers/openai/key")
        body_str = resp.text
        assert "secret_enc" not in body_str
        assert "api_key_encrypted" not in body_str
        assert "api_key" not in body_str


# ── Helpers for health + models tests ────────────────────────────


def _make_health_app(
    providers: list[dict] | None = None,
    key_manager: MagicMock | None = "default",
) -> FastAPI:
    """Create a test app with the providers router and mocked db/key_manager."""
    app = FastAPI()
    app.include_router(router)

    db = AsyncMock()
    db.list_providers = AsyncMock(return_value=providers or [])
    app.state.db = db

    if key_manager == "default":
        km = MagicMock()
        km.decrypt = MagicMock(return_value="sk-decrypted-key")
        app.state.key_manager = km
    else:
        app.state.key_manager = key_manager

    return app


def _make_models_app(providers: list[dict] | None = None) -> FastAPI:
    """Create a test app with the models router and mocked db."""
    from backend.api.models import router as models_router

    app = FastAPI()
    app.include_router(models_router)

    db = AsyncMock()
    db.list_providers = AsyncMock(return_value=providers or [])
    app.state.db = db

    return app


# ── T029: GET /api/providers/health ──────────────────────────────


class TestProviderHealth:
    """T029: Health endpoint reachability checks."""

    def test_ollama_reachable_returns_reachable_true(self):
        """Ollama health_check() → True is reflected as reachable=True; HTTP 200."""
        app = _make_health_app(providers=[])
        with patch("backend.providers.ollama.OllamaLLMProvider") as MockOllama:
            MockOllama.return_value.health_check = AsyncMock(return_value=True)
            client = TestClient(app)
            resp = client.get("/api/providers/health")

        assert resp.status_code == 200
        health = resp.json()["health"]
        ollama_entry = next(h for h in health if h["provider"] == "ollama")
        assert ollama_entry["reachable"] is True

    def test_cloud_provider_no_key_returns_reachable_false_without_health_check(self):
        """Cloud provider with null api_key_encrypted → reachable=False, no health_check call."""
        providers = [
            {"name": "openai", "api_key_encrypted": None, "config_json": "{}", "is_active": False},
        ]
        app = _make_health_app(providers=providers)
        with patch("backend.providers.openai.OpenAILLMProvider") as MockOpenAI:
            client = TestClient(app)
            resp = client.get("/api/providers/health")
            # health_check should NOT have been called since no key
            MockOpenAI.return_value.health_check.assert_not_called()

        assert resp.status_code == 200
        health = resp.json()["health"]
        openai_entry = next((h for h in health if h["provider"] == "openai"), None)
        assert openai_entry is not None
        assert openai_entry["reachable"] is False

    def test_cloud_provider_health_check_raises_returns_reachable_false_not_500(self):
        """If health_check() raises, endpoint returns reachable=False (no HTTP 500)."""
        providers = [
            {
                "name": "openrouter",
                "api_key_encrypted": "enc_key",
                "config_json": '{"model": "openai/gpt-4o-mini"}',
                "is_active": True,
            },
        ]
        km = MagicMock()
        km.decrypt = MagicMock(return_value="sk-test")
        app = _make_health_app(providers=providers, key_manager=km)

        with patch("backend.providers.openrouter.OpenRouterLLMProvider") as MockOpenRouter:
            MockOpenRouter.return_value.health_check = AsyncMock(
                side_effect=Exception("network unreachable")
            )
            client = TestClient(app)
            resp = client.get("/api/providers/health")

        assert resp.status_code == 200
        health = resp.json()["health"]
        or_entry = next((h for h in health if h["provider"] == "openrouter"), None)
        assert or_entry is not None
        assert or_entry["reachable"] is False

    def test_health_endpoint_always_returns_200(self):
        """Health endpoint is always HTTP 200 even when all providers are unreachable."""
        providers = [
            {"name": "openai", "api_key_encrypted": None, "config_json": "{}", "is_active": False},
            {"name": "anthropic", "api_key_encrypted": None, "config_json": "{}", "is_active": False},
        ]
        app = _make_health_app(providers=providers)
        with patch("backend.providers.ollama.OllamaLLMProvider") as MockOllama:
            MockOllama.return_value.health_check = AsyncMock(return_value=False)
            client = TestClient(app)
            resp = client.get("/api/providers/health")

        assert resp.status_code == 200
        health = resp.json()["health"]
        # All entries exist with reachable=False
        assert all(h["reachable"] is False for h in health)


# ── T030: GET /api/models/llm enriched with cloud provider models ─


class TestEnrichedLLMModels:
    """T030: /api/models/llm includes cloud models only when key is stored."""

    def test_cloud_provider_with_key_model_appears_in_response(self):
        """Cloud provider with non-null api_key_encrypted: its model name appears."""
        from backend.agent.schemas import ModelInfo

        providers = [
            {
                "name": "openrouter",
                "api_key_encrypted": "enc_key",
                "config_json": '{"model": "openai/gpt-4o"}',
                "is_active": True,
            },
        ]
        app = _make_models_app(providers=providers)
        ollama_models = [
            ModelInfo(name="qwen2.5:7b", provider="ollama", model_type="llm"),
        ]
        with patch("backend.api.models._fetch_ollama_models", AsyncMock(return_value=ollama_models)):
            client = TestClient(app)
            resp = client.get("/api/models/llm")

        assert resp.status_code == 200
        models = resp.json()["models"]
        names = [m["name"] for m in models]
        assert "openai/gpt-4o" in names

    def test_cloud_provider_without_key_model_absent_from_response(self):
        """Cloud provider with null api_key_encrypted: its model does NOT appear."""
        from backend.agent.schemas import ModelInfo

        providers = [
            {
                "name": "openrouter",
                "api_key_encrypted": None,
                "config_json": '{"model": "openai/gpt-4o"}',
                "is_active": False,
            },
        ]
        app = _make_models_app(providers=providers)
        ollama_models = [
            ModelInfo(name="qwen2.5:7b", provider="ollama", model_type="llm"),
        ]
        with patch("backend.api.models._fetch_ollama_models", AsyncMock(return_value=ollama_models)):
            client = TestClient(app)
            resp = client.get("/api/models/llm")

        assert resp.status_code == 200
        models = resp.json()["models"]
        names = [m["name"] for m in models]
        assert "openai/gpt-4o" not in names

    def test_ollama_models_appear_regardless_of_cloud_providers(self):
        """Ollama models always appear, independent of cloud provider key status."""
        from backend.agent.schemas import ModelInfo

        providers = [
            {"name": "openai", "api_key_encrypted": None, "config_json": "{}", "is_active": False},
        ]
        app = _make_models_app(providers=providers)
        ollama_models = [
            ModelInfo(name="qwen2.5:7b", provider="ollama", model_type="llm"),
            ModelInfo(name="llama3.2:3b", provider="ollama", model_type="llm"),
        ]
        with patch("backend.api.models._fetch_ollama_models", AsyncMock(return_value=ollama_models)):
            client = TestClient(app)
            resp = client.get("/api/models/llm")

        assert resp.status_code == 200
        models = resp.json()["models"]
        ollama_names = [m["name"] for m in models if m["provider"] == "ollama"]
        assert "qwen2.5:7b" in ollama_names
        assert "llama3.2:3b" in ollama_names

    def test_multiple_cloud_providers_only_keyed_ones_appear(self):
        """With multiple cloud providers, only those with api_key_encrypted appear."""
        from backend.agent.schemas import ModelInfo

        providers = [
            {
                "name": "openrouter",
                "api_key_encrypted": "enc_or_key",
                "config_json": '{"model": "openai/gpt-4o-mini"}',
                "is_active": True,
            },
            {
                "name": "anthropic",
                "api_key_encrypted": None,
                "config_json": '{"model": "claude-sonnet-4-20250514"}',
                "is_active": False,
            },
        ]
        app = _make_models_app(providers=providers)
        with patch("backend.api.models._fetch_ollama_models", AsyncMock(return_value=[])):
            client = TestClient(app)
            resp = client.get("/api/models/llm")

        models = resp.json()["models"]
        names = [m["name"] for m in models]
        assert "openai/gpt-4o-mini" in names          # openrouter has key
        assert "claude-sonnet-4-20250514" not in names  # anthropic has no key
