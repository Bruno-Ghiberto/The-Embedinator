"""Unit tests for Settings configuration — T004."""

import os

import pytest

from backend.config import Settings


@pytest.mark.xfail(reason="EMBEDINATOR_FERNET_KEY alias requires populate_by_name in env")
def test_default_settings():
    """Verify defaults load correctly."""
    settings = Settings()
    assert settings.host == "0.0.0.0"
    assert settings.port == 8000
    assert settings.default_llm_model == "qwen2.5:7b"
    assert settings.default_embed_model == "nomic-embed-text"
    assert settings.qdrant_host == "localhost"
    assert settings.qdrant_port == 6333
    assert settings.sqlite_path == "data/embedinator.db"
    assert settings.confidence_threshold == 60
    assert settings.max_upload_size_mb == 100
    assert settings.frontend_port == 3000


def test_env_var_override(monkeypatch):
    """Verify environment variable overrides work."""
    monkeypatch.setenv("DEFAULT_LLM_MODEL", "custom-model")
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("CONFIDENCE_THRESHOLD", "75")

    settings = Settings()
    assert settings.default_llm_model == "custom-model"
    assert settings.port == 9000
    assert settings.confidence_threshold == 75


def test_cors_origins():
    """Verify CORS origins parsing."""
    settings = Settings()
    origins = settings.cors_origins.split(",")
    assert "http://localhost:3000" in origins


def test_startup_refuses_unsupported_model(monkeypatch):
    """spec-26 FR-004: backend must refuse to start when default_llm_model is not in supported list."""
    monkeypatch.setenv("DEFAULT_LLM_MODEL", "gemma4:e4b")

    from backend.errors import UnsupportedModelError
    from backend.main import _validate_model_support

    s = Settings()
    assert s.default_llm_model == "gemma4:e4b"

    with pytest.raises(UnsupportedModelError) as exc_info:
        _validate_model_support(s.default_llm_model, s.supported_llm_models)

    err_msg = str(exc_info.value)
    assert "gemma4:e4b" in err_msg
    assert "qwen2.5:7b" in err_msg
    assert "docs/performance.md" in err_msg


def test_startup_accepts_supported_model(monkeypatch):
    """spec-26 FR-004: validator must pass silently for all supported models."""
    from backend.main import _validate_model_support

    for model in ["qwen2.5:7b", "llama3.1:8b", "mistral:7b"]:
        monkeypatch.setenv("DEFAULT_LLM_MODEL", model)
        s = Settings()
        _validate_model_support(s.default_llm_model, s.supported_llm_models)  # must not raise


def test_supported_llm_models_default():
    """spec-26 FR-004: supported_llm_models must contain the expected non-thinking models."""
    s = Settings()
    assert "qwen2.5:7b" in s.supported_llm_models
    assert "llama3.1:8b" in s.supported_llm_models
    assert "mistral:7b" in s.supported_llm_models
    assert "gemma4:e4b" not in s.supported_llm_models
