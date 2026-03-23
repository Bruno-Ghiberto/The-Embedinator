"""Tests for spec-08 API schemas and NDJSON event TypedDicts.

Validates Pydantic model constraints, regex patterns, type boundaries,
and importability of all new models added in T003.
"""

import pytest
from pydantic import ValidationError

from backend.agent.schemas import (
    # Modified existing models
    ChatRequest,
    CollectionCreateRequest,
    CollectionResponse,
    DocumentResponse,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    HealthServiceStatus,
    # New spec-08 models
    IngestionJobResponse,
    ModelInfo,
    ProviderDetailResponse,
    ProviderKeyRequest,
    QueryTraceDetailResponse,
    QueryTraceResponse,
    SettingsResponse,
    SettingsUpdateRequest,
    StatsResponse,
    # NDJSON event TypedDicts
    ClarificationEvent,
    ChunkEvent,
    CitationEvent,
    ConfidenceEvent,
    DoneEvent,
    ErrorEvent,
    GroundednessEvent,
    MetaReasoningEvent,
    SessionEvent,
    StatusEvent,
)
from backend.config import Settings


# --- CollectionCreateRequest regex validation ---


class TestCollectionCreateRequest:
    def test_rejects_uppercase_name(self):
        with pytest.raises(ValidationError):
            CollectionCreateRequest(name="MyCollection")

    def test_rejects_spaces_in_name(self):
        with pytest.raises(ValidationError):
            CollectionCreateRequest(name="my collection")

    def test_rejects_name_starting_with_dash(self):
        with pytest.raises(ValidationError):
            CollectionCreateRequest(name="-bad-start")

    def test_rejects_name_starting_with_underscore(self):
        with pytest.raises(ValidationError):
            CollectionCreateRequest(name="_bad-start")

    def test_rejects_empty_name(self):
        with pytest.raises(ValidationError):
            CollectionCreateRequest(name="")

    def test_rejects_name_over_100_chars(self):
        with pytest.raises(ValidationError):
            CollectionCreateRequest(name="a" * 101)

    def test_accepts_valid_lowercase_name(self):
        req = CollectionCreateRequest(name="my-docs")
        assert req.name == "my-docs"

    def test_accepts_name_with_numbers(self):
        req = CollectionCreateRequest(name="docs123")
        assert req.name == "docs123"

    def test_accepts_name_with_underscores_and_dashes(self):
        req = CollectionCreateRequest(name="my_docs-v2")
        assert req.name == "my_docs-v2"

    def test_accepts_single_char_name(self):
        req = CollectionCreateRequest(name="a")
        assert req.name == "a"

    def test_accepts_name_starting_with_digit(self):
        req = CollectionCreateRequest(name="0docs")
        assert req.name == "0docs"

    def test_optional_fields_default_none(self):
        req = CollectionCreateRequest(name="test")
        assert req.description is None
        assert req.embedding_model is None
        assert req.chunk_profile is None

    def test_optional_fields_set(self):
        req = CollectionCreateRequest(
            name="test",
            description="A test collection",
            embedding_model="nomic-embed-text",
            chunk_profile="compact",
        )
        assert req.description == "A test collection"
        assert req.embedding_model == "nomic-embed-text"
        assert req.chunk_profile == "compact"


# --- CollectionResponse ---


class TestCollectionResponse:
    def test_has_seven_fields(self):
        resp = CollectionResponse(
            id="uuid", name="test", created_at="2026-01-01T00:00:00Z"
        )
        assert resp.id == "uuid"
        assert resp.name == "test"
        assert resp.description is None
        assert resp.embedding_model == "nomic-embed-text"
        assert resp.chunk_profile == "default"
        assert resp.document_count == 0
        assert resp.created_at == "2026-01-01T00:00:00Z"

    def test_description_optional(self):
        resp = CollectionResponse(
            id="uuid", name="test",
            description="Custom desc",
            created_at="2026-01-01T00:00:00Z",
        )
        assert resp.description == "Custom desc"


# --- DocumentResponse ---


class TestDocumentResponse:
    def test_valid_statuses(self):
        for status in ("pending", "ingesting", "completed", "failed", "duplicate"):
            resp = DocumentResponse(
                id="d1", collection_id="c1", filename="f.txt",
                status=status, created_at="2026-01-01T00:00:00Z",
            )
            assert resp.status == status

    def test_rejects_old_status_literals(self):
        for bad_status in ("uploaded", "parsing", "indexing", "indexed", "deleted"):
            with pytest.raises(ValidationError):
                DocumentResponse(
                    id="d1", collection_id="c1", filename="f.txt",
                    status=bad_status, created_at="2026-01-01T00:00:00Z",
                )

    def test_chunk_count_optional(self):
        resp = DocumentResponse(
            id="d1", collection_id="c1", filename="f.txt",
            status="pending", created_at="2026-01-01T00:00:00Z",
        )
        assert resp.chunk_count is None

    def test_updated_at_optional(self):
        resp = DocumentResponse(
            id="d1", collection_id="c1", filename="f.txt",
            status="completed", created_at="2026-01-01T00:00:00Z",
        )
        assert resp.updated_at is None


# --- ChatRequest ---


class TestChatRequest:
    def test_embed_model_defaults_none(self):
        req = ChatRequest(message="hello")
        assert req.embed_model is None

    def test_embed_model_can_be_set(self):
        req = ChatRequest(message="hello", embed_model="nomic-embed-text")
        assert req.embed_model == "nomic-embed-text"

    def test_existing_fields_preserved(self):
        req = ChatRequest(message="hello", llm_model="qwen2.5:7b", session_id="s1")
        assert req.message == "hello"
        assert req.llm_model == "qwen2.5:7b"
        assert req.session_id == "s1"
        assert req.collection_ids == []


# --- SettingsResponse ---


class TestSettingsResponse:
    def test_rejects_confidence_threshold_150(self):
        with pytest.raises(ValidationError):
            SettingsResponse(
                default_llm_model="m", default_embed_model="e",
                confidence_threshold=150,
                groundedness_check_enabled=True,
                citation_alignment_threshold=0.3,
                parent_chunk_size=2000, child_chunk_size=500,
            )

    def test_rejects_confidence_threshold_negative(self):
        with pytest.raises(ValidationError):
            SettingsResponse(
                default_llm_model="m", default_embed_model="e",
                confidence_threshold=-1,
                groundedness_check_enabled=True,
                citation_alignment_threshold=0.3,
                parent_chunk_size=2000, child_chunk_size=500,
            )

    def test_accepts_confidence_threshold_0(self):
        resp = SettingsResponse(
            default_llm_model="m", default_embed_model="e",
            confidence_threshold=0,
            groundedness_check_enabled=True,
            citation_alignment_threshold=0.3,
            parent_chunk_size=2000, child_chunk_size=500,
        )
        assert resp.confidence_threshold == 0

    def test_accepts_confidence_threshold_100(self):
        resp = SettingsResponse(
            default_llm_model="m", default_embed_model="e",
            confidence_threshold=100,
            groundedness_check_enabled=True,
            citation_alignment_threshold=0.3,
            parent_chunk_size=2000, child_chunk_size=500,
        )
        assert resp.confidence_threshold == 100

    def test_has_all_seven_fields(self):
        resp = SettingsResponse(
            default_llm_model="qwen2.5:7b",
            default_embed_model="nomic-embed-text",
            confidence_threshold=60,
            groundedness_check_enabled=True,
            citation_alignment_threshold=0.3,
            parent_chunk_size=2000,
            child_chunk_size=500,
        )
        assert resp.default_llm_model == "qwen2.5:7b"
        assert resp.default_embed_model == "nomic-embed-text"
        assert resp.confidence_threshold == 60
        assert resp.groundedness_check_enabled is True
        assert resp.citation_alignment_threshold == 0.3
        assert resp.parent_chunk_size == 2000
        assert resp.child_chunk_size == 500


# --- SettingsUpdateRequest ---


class TestSettingsUpdateRequest:
    def test_accepts_confidence_threshold_none(self):
        req = SettingsUpdateRequest(confidence_threshold=None)
        assert req.confidence_threshold is None

    def test_all_fields_default_none(self):
        req = SettingsUpdateRequest()
        assert req.default_llm_model is None
        assert req.default_embed_model is None
        assert req.confidence_threshold is None
        assert req.groundedness_check_enabled is None
        assert req.citation_alignment_threshold is None
        assert req.parent_chunk_size is None
        assert req.child_chunk_size is None

    def test_rejects_confidence_threshold_over_100(self):
        with pytest.raises(ValidationError):
            SettingsUpdateRequest(confidence_threshold=101)

    def test_accepts_partial_update(self):
        req = SettingsUpdateRequest(confidence_threshold=75, groundedness_check_enabled=False)
        assert req.confidence_threshold == 75
        assert req.groundedness_check_enabled is False
        assert req.default_llm_model is None


# --- HealthServiceStatus + HealthResponse ---


class TestHealthResponse:
    def test_healthy_status(self):
        resp = HealthResponse(
            status="healthy",
            services=[
                HealthServiceStatus(name="sqlite", status="ok", latency_ms=0.4),
                HealthServiceStatus(name="qdrant", status="ok", latency_ms=12.3),
            ],
        )
        assert resp.status == "healthy"
        assert len(resp.services) == 2
        assert resp.services[0].latency_ms == 0.4

    def test_degraded_status(self):
        resp = HealthResponse(
            status="degraded",
            services=[
                HealthServiceStatus(name="qdrant", status="error", error_message="Connection refused"),
            ],
        )
        assert resp.status == "degraded"
        assert resp.services[0].error_message == "Connection refused"
        assert resp.services[0].latency_ms is None

    def test_rejects_invalid_service_status(self):
        with pytest.raises(ValidationError):
            HealthServiceStatus(name="sqlite", status="unknown")


# --- IngestionJobResponse ---


class TestIngestionJobResponse:
    def test_valid_statuses(self):
        for status in ("pending", "started", "streaming", "embedding", "completed", "failed", "paused"):
            resp = IngestionJobResponse(
                job_id="j1", document_id="d1", status=status,
            )
            assert resp.status == status

    def test_defaults(self):
        resp = IngestionJobResponse(job_id="j1", document_id="d1", status="pending")
        assert resp.chunks_processed == 0
        assert resp.chunks_total is None
        assert resp.error_message is None
        assert resp.started_at is None
        assert resp.completed_at is None


# --- ModelInfo ---


class TestModelInfo:
    def test_llm_type(self):
        m = ModelInfo(name="qwen2.5:7b", provider="ollama", model_type="llm")
        assert m.model_type == "llm"

    def test_embed_type(self):
        m = ModelInfo(name="nomic-embed-text", provider="ollama", model_type="embed")
        assert m.model_type == "embed"

    def test_rejects_invalid_type(self):
        with pytest.raises(ValidationError):
            ModelInfo(name="m", provider="p", model_type="unknown")


# --- ProviderKeyRequest ---


class TestProviderKeyRequest:
    def test_accepts_api_key(self):
        req = ProviderKeyRequest(api_key="sk-abc123")
        assert req.api_key == "sk-abc123"

    def test_rejects_missing_key(self):
        with pytest.raises(ValidationError):
            ProviderKeyRequest()


# --- ProviderDetailResponse ---


class TestProviderDetailResponse:
    def test_has_key_bool(self):
        resp = ProviderDetailResponse(name="openai", has_key=True)
        assert resp.has_key is True

    def test_defaults(self):
        resp = ProviderDetailResponse(name="ollama")
        assert resp.is_active is False
        assert resp.has_key is False
        assert resp.base_url is None
        assert resp.model_count == 0


# --- QueryTraceResponse + Detail ---


class TestQueryTraceResponse:
    def test_confidence_score_is_int_or_none(self):
        resp = QueryTraceResponse(
            id="t1", session_id="s1", query="q",
            collections_searched=[], latency_ms=100, created_at="2026-01-01",
        )
        assert resp.confidence_score is None

    def test_confidence_score_int(self):
        resp = QueryTraceResponse(
            id="t1", session_id="s1", query="q",
            collections_searched=[], confidence_score=82,
            latency_ms=100, created_at="2026-01-01",
        )
        assert resp.confidence_score == 82
        assert isinstance(resp.confidence_score, int)


class TestQueryTraceDetailResponse:
    def test_inherits_base_fields(self):
        resp = QueryTraceDetailResponse(
            id="t1", session_id="s1", query="q",
            collections_searched=["c1"], latency_ms=200,
            created_at="2026-01-01", confidence_score=75,
            sub_questions=["sub1"], chunks_retrieved=[{"id": "ch1"}],
            reasoning_steps=[{"step": 1}], strategy_switches=[{"from": "a"}],
        )
        assert resp.id == "t1"
        assert resp.sub_questions == ["sub1"]
        assert resp.chunks_retrieved == [{"id": "ch1"}]

    def test_detail_defaults_empty(self):
        resp = QueryTraceDetailResponse(
            id="t1", session_id="s1", query="q",
            collections_searched=[], latency_ms=100, created_at="2026-01-01",
        )
        assert resp.sub_questions == []
        assert resp.chunks_retrieved == []
        assert resp.reasoning_steps == []
        assert resp.strategy_switches == []


# --- StatsResponse ---


class TestStatsResponse:
    def test_all_numeric_fields(self):
        resp = StatsResponse(
            total_collections=3, total_documents=47, total_chunks=8920,
            total_queries=312, avg_confidence=74.2, avg_latency_ms=1840.5,
            meta_reasoning_rate=0.12,
        )
        assert resp.total_collections == 3
        assert resp.meta_reasoning_rate == 0.12


# --- NDJSON Event TypedDicts importability ---


class TestNDJSONEventTypedDicts:
    def test_session_event_importable(self):
        event: SessionEvent = {"type": "session", "session_id": "s1"}
        assert event["type"] == "session"

    def test_status_event_importable(self):
        event: StatusEvent = {"type": "status", "node": "query_rewrite"}
        assert event["node"] == "query_rewrite"

    def test_chunk_event_importable(self):
        event: ChunkEvent = {"type": "chunk", "text": "hello"}
        assert event["text"] == "hello"

    def test_citation_event_importable(self):
        event: CitationEvent = {"type": "citation", "citations": []}
        assert event["citations"] == []

    def test_meta_reasoning_event_importable(self):
        event: MetaReasoningEvent = {"type": "meta_reasoning", "strategies_attempted": ["WIDEN_SEARCH"]}
        assert event["strategies_attempted"] == ["WIDEN_SEARCH"]

    def test_confidence_event_importable(self):
        event: ConfidenceEvent = {"type": "confidence", "score": 82}
        assert isinstance(event["score"], int)

    def test_groundedness_event_importable(self):
        event: GroundednessEvent = {
            "type": "groundedness", "overall_grounded": True,
            "supported": 3, "unsupported": 0, "contradicted": 0,
        }
        assert event["overall_grounded"] is True

    def test_done_event_importable(self):
        event: DoneEvent = {"type": "done", "latency_ms": 1240, "trace_id": "uuid"}
        assert event["trace_id"] == "uuid"

    def test_clarification_event_importable(self):
        event: ClarificationEvent = {"type": "clarification", "question": "Which Q?"}
        assert event["question"] == "Which Q?"

    def test_error_event_importable(self):
        event: ErrorEvent = {"type": "error", "message": "fail", "code": "CIRCUIT_OPEN", "trace_id": "uuid"}
        assert event["code"] == "CIRCUIT_OPEN"


# --- Config rate limits (T004) ---


class TestConfigRateLimits:
    def test_chat_rate_limit_is_30(self):
        s = Settings()
        assert s.rate_limit_chat_per_minute == 30

    def test_provider_keys_rate_limit_is_5(self):
        s = Settings()
        assert s.rate_limit_provider_keys_per_minute == 5

    def test_general_rate_limit_is_120(self):
        s = Settings()
        assert s.rate_limit_general_per_minute == 120

    def test_ingest_rate_limit_unchanged(self):
        s = Settings()
        assert s.rate_limit_ingest_per_minute == 10


# --- ErrorDetail and ErrorResponse unchanged ---


class TestErrorModelsUnchanged:
    def test_error_detail(self):
        ed = ErrorDetail(code="TEST_CODE", message="Test message")
        assert ed.code == "TEST_CODE"
        assert ed.details == {}

    def test_error_response(self):
        er = ErrorResponse(error=ErrorDetail(code="X", message="Y"))
        assert er.error.code == "X"
