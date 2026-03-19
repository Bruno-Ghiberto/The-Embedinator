"""Unit tests for Pydantic schemas — T018."""

import pytest
from pydantic import ValidationError

from backend.agent.schemas import (
    ChatRequest,
    Citation,
    CollectionCreateRequest,
    CollectionResponse,
    DocumentResponse,
    HealthResponse,
    Passage,
    ProviderResponse,
    SubAnswer,
    TraceResponse,
    AnswerResponse,
)


def test_collection_create_request_validation():
    """Verify name constraints: lowercase alphanumeric, 1-100 chars, regex pattern."""
    req = CollectionCreateRequest(name="valid-name")
    assert req.name == "valid-name"

    req2 = CollectionCreateRequest(name="my_docs_123")
    assert req2.name == "my_docs_123"

    with pytest.raises(ValidationError):
        CollectionCreateRequest(name="")

    with pytest.raises(ValidationError):
        CollectionCreateRequest(name="x" * 101)

    # Uppercase not allowed
    with pytest.raises(ValidationError):
        CollectionCreateRequest(name="Invalid Name")


def test_chat_request_validation():
    """Verify message and collection_ids constraints."""
    req = ChatRequest(message="What?", collection_ids=["col-1"])
    assert req.llm_model == "qwen2.5:7b"  # Default
    assert req.session_id is None  # Optional, absent by default

    with pytest.raises(ValidationError):
        ChatRequest(message="", collection_ids=["col-1"])

    # Empty collection_ids is now allowed (NO_COLLECTIONS guard handles it in stream)
    req_empty = ChatRequest(message="What?", collection_ids=[])
    assert req_empty.collection_ids == []


def test_confidence_score_bounds():
    """Verify confidence_score is constrained to 0-100."""
    answer = AnswerResponse(
        id="ans-1",
        query_id="q-1",
        answer_text="test",
        citations=[],
        confidence_score=85,
        generated_at="2026-03-10T00:00:00Z",
    )
    assert answer.confidence_score == 85

    with pytest.raises(ValidationError):
        AnswerResponse(
            id="ans-1", query_id="q-1", answer_text="test",
            citations=[], confidence_score=101, generated_at="2026-03-10T00:00:00Z",
        )

    with pytest.raises(ValidationError):
        AnswerResponse(
            id="ans-1", query_id="q-1", answer_text="test",
            citations=[], confidence_score=-1, generated_at="2026-03-10T00:00:00Z",
        )


def test_trace_response_serialization():
    """Verify TraceResponse serializes correctly."""
    trace = TraceResponse(
        id="trace-1",
        query_id="q-1",
        query_text="What is AI?",
        collections_searched=["col-1"],
        passages_retrieved=[
            Passage(
                id="p-1",
                document_id="doc-1",
                document_name="test.pdf",
                text="AI is...",
                relevance_score=0.95,
                chunk_index=0,
            )
        ],
        confidence_score=92,
        created_at="2026-03-10T00:00:00Z",
    )
    data = trace.model_dump()
    assert data["confidence_score"] == 92
    assert len(data["passages_retrieved"]) == 1
    assert data["passages_retrieved"][0]["source_removed"] is False


def test_passage_source_removed_default():
    """Verify source_removed defaults to False."""
    p = Passage(
        id="p-1", document_id="d-1", document_name="test.pdf",
        text="content", relevance_score=0.8, chunk_index=0,
    )
    assert p.source_removed is False


def test_health_response():
    """Verify HealthResponse validates status with service list."""
    from backend.agent.schemas import HealthServiceStatus

    h = HealthResponse(
        status="healthy",
        services=[HealthServiceStatus(name="sqlite", status="ok", latency_ms=0.4)],
    )
    assert h.status == "healthy"
    assert len(h.services) == 1

    h2 = HealthResponse(
        status="degraded",
        services=[
            HealthServiceStatus(name="sqlite", status="ok", latency_ms=0.3),
            HealthServiceStatus(name="qdrant", status="error", error_message="down"),
        ],
    )
    assert h2.status == "degraded"

    with pytest.raises(ValidationError):
        HealthResponse(status="unknown", services=[])
