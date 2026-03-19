"""Unit tests for backend.errors — all 11 exception classes.

NOTE: ProviderRateLimitError lives in backend.providers.base, NOT here.
Do not import it from backend.errors.
"""
import importlib

import pytest

from backend.errors import (
    CircuitOpenError,
    EmbeddingError,
    EmbeddinatorError,
    IngestionError,
    LLMCallError,
    OllamaConnectionError,
    QdrantConnectionError,
    RerankerError,
    SessionLoadError,
    SQLiteError,
    StructuredOutputParseError,
)

ALL_SUBCLASSES = [
    QdrantConnectionError,
    OllamaConnectionError,
    SQLiteError,
    LLMCallError,
    EmbeddingError,
    IngestionError,
    SessionLoadError,
    StructuredOutputParseError,
    RerankerError,
    CircuitOpenError,
]


def test_embedinator_error_is_exception():
    """EmbeddinatorError must be a direct subclass of the built-in Exception."""
    assert issubclass(EmbeddinatorError, Exception)


def test_all_subclasses_inherit_from_embedinator_error():
    """All 10 subclasses must inherit from EmbeddinatorError."""
    for cls in ALL_SUBCLASSES:
        assert issubclass(cls, EmbeddinatorError), (
            f"{cls.__name__} does not inherit from EmbeddinatorError"
        )


def test_each_subclass_caught_as_base():
    """Every subclass instance must be catchable via except EmbeddinatorError."""
    for cls in ALL_SUBCLASSES:
        with pytest.raises(EmbeddinatorError):
            raise cls("test message")


def test_each_exception_has_string_representation():
    """Constructing any class with a message string must embed it in str(exc)."""
    for cls in ALL_SUBCLASSES + [EmbeddinatorError]:
        exc = cls("meaningful error message")
        assert "meaningful error message" in str(exc), (
            f"{cls.__name__} did not include message in str()"
        )


def test_circuit_open_error_raised_without_arguments():
    """CircuitOpenError must be raise-able with zero arguments (no required message)."""
    with pytest.raises(CircuitOpenError):
        raise CircuitOpenError()


def test_all_classes_importable_from_backend_errors():
    """All 11 classes must be present on the backend.errors module."""
    module = importlib.import_module("backend.errors")
    expected_names = [
        "EmbeddinatorError",
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
    ]
    for name in expected_names:
        assert hasattr(module, name), f"backend.errors is missing: {name}"


def test_subclass_is_not_base_class():
    """Each subclass must be distinct from EmbeddinatorError (not the same object)."""
    for cls in ALL_SUBCLASSES:
        assert cls is not EmbeddinatorError, (
            f"{cls.__name__} appears to be the same object as EmbeddinatorError"
        )
