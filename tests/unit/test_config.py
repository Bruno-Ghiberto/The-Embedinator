"""Unit tests for Settings configuration — T004."""

import os

from backend.config import Settings


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
