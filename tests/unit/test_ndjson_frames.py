"""NDJSON frame-schema validation — T049.

Validates all 4 NDJSON frame types against specs/002-conversation-graph/contracts/chat-api.md.
"""

from __future__ import annotations

import json

import pytest


# ---------------------------------------------------------------------------
# Schema validators
# ---------------------------------------------------------------------------

_VALID_ERROR_CODES = {
    "NO_COLLECTIONS",
    "EMPTY_COLLECTIONS",
    "EMPTY_MESSAGE",
    "MESSAGE_TOO_LONG",
    "INTERNAL_ERROR",
}


def validate_chunk_frame(frame: dict) -> None:
    """Validate a chunk frame against the contract schema."""
    assert frame["type"] == "chunk"
    assert "text" in frame, "Chunk frame must have 'text' field"
    assert isinstance(frame["text"], str), "Chunk 'text' must be a string"


def validate_clarification_frame(frame: dict) -> None:
    """Validate a clarification frame against the contract schema."""
    assert frame["type"] == "clarification"
    assert "question" in frame, "Clarification frame must have 'question' field"
    assert isinstance(frame["question"], str), "Clarification 'question' must be a string"


def validate_metadata_frame(frame: dict) -> None:
    """Validate a metadata frame against the contract schema."""
    assert frame["type"] == "metadata"

    # Required top-level fields
    assert "trace_id" in frame, "Metadata must have 'trace_id'"
    assert isinstance(frame["trace_id"], str), "trace_id must be a string"

    assert "confidence" in frame, "Metadata must have 'confidence'"
    assert isinstance(frame["confidence"], int), "confidence must be an int"
    assert 0 <= frame["confidence"] <= 100, "confidence must be 0-100"

    assert "citations" in frame, "Metadata must have 'citations'"
    assert isinstance(frame["citations"], list), "citations must be a list"

    assert "latency_ms" in frame, "Metadata must have 'latency_ms'"
    assert isinstance(frame["latency_ms"], int), "latency_ms must be an int"

    # Validate each citation in the list
    for citation in frame["citations"]:
        _validate_citation(citation)


def _validate_citation(citation: dict) -> None:
    """Validate a single citation object within a metadata frame."""
    required_fields = {
        "passage_id": str,
        "document_id": str,
        "document_name": str,
        "text": str,
        "relevance_score": (int, float),
        "source_removed": bool,
    }
    for field, expected_type in required_fields.items():
        assert field in citation, f"Citation must have '{field}'"
        assert isinstance(citation[field], expected_type), (
            f"Citation '{field}' must be {expected_type}, got {type(citation[field])}"
        )


def validate_error_frame(frame: dict) -> None:
    """Validate an error frame against the contract schema."""
    assert frame["type"] == "error"
    assert "message" in frame, "Error frame must have 'message' field"
    assert isinstance(frame["message"], str), "Error 'message' must be a string"
    assert "code" in frame, "Error frame must have 'code' field"
    assert isinstance(frame["code"], str), "Error 'code' must be a string"
    assert frame["code"] in _VALID_ERROR_CODES, f"Error code '{frame['code']}' not in valid codes: {_VALID_ERROR_CODES}"


def validate_frame(frame: dict) -> None:
    """Validate any NDJSON frame by dispatching to the correct type validator."""
    assert "type" in frame, "Frame must have 'type' field"
    validators = {
        "chunk": validate_chunk_frame,
        "clarification": validate_clarification_frame,
        "metadata": validate_metadata_frame,
        "error": validate_error_frame,
    }
    assert frame["type"] in validators, f"Unknown frame type: {frame['type']}"
    validators[frame["type"]](frame)


# ---------------------------------------------------------------------------
# Chunk frame tests
# ---------------------------------------------------------------------------


class TestChunkFrame:
    def test_valid_chunk(self):
        frame = {"type": "chunk", "text": "The key finding is..."}
        validate_chunk_frame(frame)

    def test_chunk_missing_text_fails(self):
        with pytest.raises(AssertionError, match="text"):
            validate_chunk_frame({"type": "chunk"})

    def test_chunk_non_string_text_fails(self):
        with pytest.raises(AssertionError, match="string"):
            validate_chunk_frame({"type": "chunk", "text": 42})

    def test_chunk_empty_text_is_valid(self):
        """Empty string is technically valid (stream may emit partial tokens)."""
        validate_chunk_frame({"type": "chunk", "text": ""})

    def test_chunk_roundtrip_json(self):
        """Chunk frame should survive JSON serialization."""
        frame = {"type": "chunk", "text": "Paris is the capital."}
        restored = json.loads(json.dumps(frame))
        validate_chunk_frame(restored)


# ---------------------------------------------------------------------------
# Clarification frame tests
# ---------------------------------------------------------------------------


class TestClarificationFrame:
    def test_valid_clarification(self):
        frame = {"type": "clarification", "question": "Which collection?"}
        validate_clarification_frame(frame)

    def test_clarification_missing_question_fails(self):
        with pytest.raises(AssertionError, match="question"):
            validate_clarification_frame({"type": "clarification"})

    def test_clarification_non_string_question_fails(self):
        with pytest.raises(AssertionError, match="string"):
            validate_clarification_frame({"type": "clarification", "question": 123})

    def test_clarification_roundtrip_json(self):
        frame = {"type": "clarification", "question": "Can you be more specific?"}
        restored = json.loads(json.dumps(frame))
        validate_clarification_frame(restored)


# ---------------------------------------------------------------------------
# Metadata frame tests
# ---------------------------------------------------------------------------


class TestMetadataFrame:
    def _valid_metadata(self, **overrides):
        base = {
            "type": "metadata",
            "trace_id": "7f3a1c2d-abcd-4321-9876-fedcba987654",
            "confidence": 87,
            "citations": [],
            "latency_ms": 1240,
        }
        base.update(overrides)
        return base

    def test_valid_metadata_no_citations(self):
        validate_metadata_frame(self._valid_metadata())

    def test_valid_metadata_with_citation(self):
        citation = {
            "passage_id": "p-001",
            "document_id": "doc-abc",
            "document_name": "report.pdf",
            "text": "The key finding...",
            "relevance_score": 0.94,
            "source_removed": False,
        }
        validate_metadata_frame(self._valid_metadata(citations=[citation]))

    def test_metadata_missing_trace_id_fails(self):
        frame = self._valid_metadata()
        del frame["trace_id"]
        with pytest.raises(AssertionError, match="trace_id"):
            validate_metadata_frame(frame)

    def test_metadata_missing_confidence_fails(self):
        frame = self._valid_metadata()
        del frame["confidence"]
        with pytest.raises(AssertionError, match="confidence"):
            validate_metadata_frame(frame)

    def test_metadata_confidence_out_of_range_fails(self):
        with pytest.raises(AssertionError, match="0-100"):
            validate_metadata_frame(self._valid_metadata(confidence=150))

    def test_metadata_missing_citations_fails(self):
        frame = self._valid_metadata()
        del frame["citations"]
        with pytest.raises(AssertionError, match="citations"):
            validate_metadata_frame(frame)

    def test_metadata_missing_latency_ms_fails(self):
        frame = self._valid_metadata()
        del frame["latency_ms"]
        with pytest.raises(AssertionError, match="latency_ms"):
            validate_metadata_frame(frame)

    def test_citation_missing_source_removed_fails(self):
        citation = {
            "passage_id": "p-001",
            "document_id": "doc-abc",
            "document_name": "report.pdf",
            "text": "Some text",
            "relevance_score": 0.8,
            # source_removed missing
        }
        with pytest.raises(AssertionError, match="source_removed"):
            validate_metadata_frame(self._valid_metadata(citations=[citation]))

    def test_citation_missing_passage_id_fails(self):
        citation = {
            "document_id": "doc-abc",
            "document_name": "report.pdf",
            "text": "Some text",
            "relevance_score": 0.8,
            "source_removed": False,
        }
        with pytest.raises(AssertionError, match="passage_id"):
            validate_metadata_frame(self._valid_metadata(citations=[citation]))

    def test_metadata_roundtrip_json(self):
        citation = {
            "passage_id": "p-001",
            "document_id": "doc-abc",
            "document_name": "report.pdf",
            "text": "Finding text.",
            "relevance_score": 0.92,
            "source_removed": True,
        }
        frame = self._valid_metadata(citations=[citation])
        restored = json.loads(json.dumps(frame))
        validate_metadata_frame(restored)


# ---------------------------------------------------------------------------
# Error frame tests
# ---------------------------------------------------------------------------


class TestErrorFrame:
    def test_valid_error(self):
        frame = {"type": "error", "message": "No collections", "code": "NO_COLLECTIONS"}
        validate_error_frame(frame)

    def test_all_valid_error_codes(self):
        for code in _VALID_ERROR_CODES:
            validate_error_frame({"type": "error", "message": "msg", "code": code})

    def test_error_missing_message_fails(self):
        with pytest.raises(AssertionError, match="message"):
            validate_error_frame({"type": "error", "code": "INTERNAL_ERROR"})

    def test_error_missing_code_fails(self):
        with pytest.raises(AssertionError, match="code"):
            validate_error_frame({"type": "error", "message": "Something went wrong"})

    def test_error_invalid_code_fails(self):
        with pytest.raises(AssertionError, match="not in valid codes"):
            validate_error_frame({"type": "error", "message": "Bad", "code": "INVALID_CODE"})

    def test_error_roundtrip_json(self):
        frame = {"type": "error", "message": "Empty message", "code": "EMPTY_MESSAGE"}
        restored = json.loads(json.dumps(frame))
        validate_error_frame(restored)


# ---------------------------------------------------------------------------
# Generic frame dispatcher tests
# ---------------------------------------------------------------------------


class TestGenericFrameValidator:
    def test_dispatches_to_chunk(self):
        validate_frame({"type": "chunk", "text": "Hello"})

    def test_dispatches_to_clarification(self):
        validate_frame({"type": "clarification", "question": "Which one?"})

    def test_dispatches_to_metadata(self):
        validate_frame(
            {
                "type": "metadata",
                "trace_id": "abc-123",
                "confidence": 75,
                "citations": [],
                "latency_ms": 500,
            }
        )

    def test_dispatches_to_error(self):
        validate_frame({"type": "error", "message": "err", "code": "INTERNAL_ERROR"})

    def test_unknown_type_fails(self):
        with pytest.raises(AssertionError, match="Unknown frame type"):
            validate_frame({"type": "unknown"})

    def test_missing_type_fails(self):
        with pytest.raises(AssertionError, match="type"):
            validate_frame({"text": "no type field"})
