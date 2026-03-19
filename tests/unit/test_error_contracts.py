"""
Contract tests for spec-12 error handling.

These tests perform static introspection -- they verify the error hierarchy,
Pydantic models, and config field contracts WITHOUT starting a server.
Tests must remain green after any refactor of error handling code.
"""
from __future__ import annotations

import inspect
import pathlib

import pytest

from backend.errors import EmbeddinatorError
from backend.providers.base import ProviderRateLimitError
from backend.agent.schemas import ErrorDetail, ErrorResponse
from backend.config import Settings


class TestErrorHierarchy:
    """Verify the exception hierarchy matches the spec-12 contract."""

    REQUIRED_SUBCLASS_NAMES = {
        "QdrantConnectionError",
        "OllamaConnectionError",
        "SQLiteError",
        "LLMCallError",
        "EmbeddingError",
        "IngestionError",
        "SessionLoadError",
        "StructuredOutputParseError",
        "RerankerError",
        "CircuitOpenError",
    }

    def test_all_required_classes_exist(self):
        import backend.errors as errors_module
        for name in self.REQUIRED_SUBCLASS_NAMES:
            assert hasattr(errors_module, name), f"Missing class: {name}"

    def test_no_extra_classes_in_errors_module(self):
        import backend.errors as errors_module
        members = inspect.getmembers(errors_module, inspect.isclass)
        exception_classes = [
            cls for _, cls in members
            if issubclass(cls, Exception) and cls.__module__ == errors_module.__name__
        ]
        assert len(exception_classes) == 11, (
            f"Expected 11 exception classes (1 base + 10 subclasses), "
            f"found {len(exception_classes)}: {[c.__name__ for c in exception_classes]}"
        )

    def test_root_base_is_exception(self):
        assert issubclass(EmbeddinatorError, Exception)

    def test_all_subclasses_extend_embedinator_error_directly(self):
        """No intermediate base classes -- flat hierarchy."""
        import backend.errors as errors_module
        for name in self.REQUIRED_SUBCLASS_NAMES:
            cls = getattr(errors_module, name)
            assert EmbeddinatorError in cls.__bases__, (
                f"{name} does not directly extend EmbeddinatorError "
                f"(bases: {cls.__bases__})"
            )

    def test_embedinator_error_has_no_custom_init(self):
        """EmbeddinatorError.__init__ must not be overridden."""
        assert EmbeddinatorError.__init__ is Exception.__init__, (
            "EmbeddinatorError must not override __init__"
        )

    def test_exception_classes_are_instantiable_with_string(self):
        """All subclasses can be created with a plain string message."""
        import backend.errors as errors_module
        for name in self.REQUIRED_SUBCLASS_NAMES:
            cls = getattr(errors_module, name)
            exc = cls("test message")
            assert isinstance(exc, cls)


class TestProviderRateLimitError:
    """ProviderRateLimitError is separate from the EmbeddinatorError hierarchy."""

    def test_lives_in_providers_base(self):
        import backend.providers.base as providers_base
        assert hasattr(providers_base, "ProviderRateLimitError")

    def test_extends_exception_not_embedinator_error(self):
        assert Exception in ProviderRateLimitError.__bases__
        assert EmbeddinatorError not in ProviderRateLimitError.__mro__

    def test_requires_provider_argument(self):
        sig = inspect.signature(ProviderRateLimitError.__init__)
        assert "provider" in sig.parameters

    def test_has_provider_attribute(self):
        exc = ProviderRateLimitError("openai")
        assert exc.provider == "openai"

    def test_str_message_contains_provider_name(self):
        exc = ProviderRateLimitError("anthropic")
        assert "anthropic" in str(exc)


class TestErrorSchemas:
    """Verify Pydantic model contracts for the error envelope."""

    def test_error_detail_has_code_field(self):
        assert "code" in ErrorDetail.model_fields

    def test_error_detail_has_message_field(self):
        assert "message" in ErrorDetail.model_fields

    def test_error_detail_has_details_field(self):
        assert "details" in ErrorDetail.model_fields

    def test_error_detail_details_defaults_to_empty_dict(self):
        ed = ErrorDetail(code="X", message="y")
        assert ed.details == {}

    def test_error_response_has_error_field(self):
        assert "error" in ErrorResponse.model_fields

    def test_error_response_has_no_trace_id_field(self):
        """trace_id is NOT a Pydantic field -- it is added as a plain dict key in handlers."""
        assert "trace_id" not in ErrorResponse.model_fields, (
            "ErrorResponse must not have a trace_id field. "
            "trace_id is appended as a plain dict key: {'error': {...}, 'trace_id': '...'}"
        )


class TestCircuitBreakerConfig:
    """Verify circuit breaker config field contracts."""

    def test_circuit_breaker_failure_threshold_is_int_5(self):
        s = Settings()
        assert s.circuit_breaker_failure_threshold == 5
        assert isinstance(s.circuit_breaker_failure_threshold, int)

    def test_circuit_breaker_cooldown_secs_is_int_30(self):
        s = Settings()
        assert s.circuit_breaker_cooldown_secs == 30

    def test_retry_max_attempts_exists_reserved(self):
        """retry_max_attempts is dead config -- reserved for future spec. MUST NOT be removed."""
        s = Settings()
        assert hasattr(s, "retry_max_attempts")
        assert isinstance(s.retry_max_attempts, int)

    def test_retry_backoff_initial_secs_exists_reserved(self):
        """retry_backoff_initial_secs is dead config -- reserved for future spec. MUST NOT be removed."""
        s = Settings()
        assert hasattr(s, "retry_backoff_initial_secs")


class TestRateLimitConfig:
    """Verify rate limit config field contracts."""

    def test_rate_limit_chat_per_minute(self):
        s = Settings()
        assert s.rate_limit_chat_per_minute == 30

    def test_rate_limit_ingest_per_minute(self):
        s = Settings()
        assert s.rate_limit_ingest_per_minute == 10

    def test_rate_limit_provider_keys_per_minute(self):
        s = Settings()
        assert s.rate_limit_provider_keys_per_minute == 5

    def test_rate_limit_general_per_minute(self):
        s = Settings()
        assert s.rate_limit_general_per_minute == 120


class TestStreamErrorCodes:
    """Verify NDJSON stream error codes are present in chat.py (static code inspection).

    These tests prevent accidental renaming of stream error codes that would break
    frontend consumers. The NDJSON format {"type": "error", "code": ...} is intentionally
    different from the REST error envelope -- do NOT unify them.
    """

    _chat_source: str = ""

    @classmethod
    def setup_class(cls):
        chat_path = pathlib.Path(__file__).parent.parent.parent / "backend" / "api" / "chat.py"
        cls._chat_source = chat_path.read_text()

    def test_no_collections_code_present(self):
        assert "NO_COLLECTIONS" in self._chat_source

    def test_circuit_open_code_present(self):
        assert "CIRCUIT_OPEN" in self._chat_source

    def test_service_unavailable_code_present(self):
        assert "SERVICE_UNAVAILABLE" in self._chat_source

    def test_stream_errors_use_type_error_format(self):
        assert '"type": "error"' in self._chat_source


class TestProviderKeyErrorCodes:
    """Verify KEY_MANAGER_UNAVAILABLE code is used in providers.py (static code inspection).

    This test prevents accidental removal of the error code that protects
    provider key operations when the Fernet key manager is not configured.
    """

    _providers_source: str = ""

    @classmethod
    def setup_class(cls):
        providers_path = pathlib.Path(__file__).parent.parent.parent / "backend" / "api" / "providers.py"
        cls._providers_source = providers_path.read_text()

    def test_key_manager_unavailable_code_present(self):
        assert "KEY_MANAGER_UNAVAILABLE" in self._providers_source
