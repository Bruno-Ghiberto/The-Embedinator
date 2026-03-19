"""Tests for log field redaction (FR-006)."""

import structlog

from backend.main import _strip_sensitive_fields, _configure_logging


class TestStripSensitiveFields:
    def test_api_key_redacted(self):
        """AC-6: api_key value replaced with [REDACTED]."""
        event = {"event": "test", "api_key": "sk-real-key-12345"}
        result = _strip_sensitive_fields(None, None, event)
        assert result["api_key"] == "[REDACTED]"
        assert result["event"] == "test"

    def test_other_sensitive_keys_redacted(self):
        """password, secret, token, authorization all redacted."""
        event = {
            "event": "test",
            "password": "hunter2",
            "secret": "my-secret",
            "token": "jwt-abc",
            "authorization": "Bearer xyz",
        }
        result = _strip_sensitive_fields(None, None, event)
        assert result["password"] == "[REDACTED]"
        assert result["secret"] == "[REDACTED]"
        assert result["token"] == "[REDACTED]"
        assert result["authorization"] == "[REDACTED]"

    def test_case_insensitive_match(self):
        """Matching is case-insensitive."""
        event = {"API_KEY": "key123", "Token": "tok456"}
        result = _strip_sensitive_fields(None, None, event)
        assert result["API_KEY"] == "[REDACTED]"
        assert result["Token"] == "[REDACTED]"

    def test_non_sensitive_key_unchanged(self):
        """Non-sensitive keys pass through unchanged."""
        event = {"event": "request", "user_id": "u123", "path": "/api/chat"}
        result = _strip_sensitive_fields(None, None, event)
        assert result == {"event": "request", "user_id": "u123", "path": "/api/chat"}


class TestProcessorChainPosition:
    def test_strip_sensitive_at_position_minus_2(self):
        """AC-11: _strip_sensitive_fields is at index -2 (before JSONRenderer)."""
        _configure_logging("INFO")
        config = structlog.get_config()
        processors = config["processors"]
        assert processors[-2] is _strip_sensitive_fields
        assert isinstance(processors[-1], structlog.processors.JSONRenderer)
        assert len(processors) == 8  # +1 for _filter_by_component (US3, T039)
