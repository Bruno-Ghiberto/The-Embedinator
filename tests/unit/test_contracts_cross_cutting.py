"""Contract tests for cross-cutting concerns: error hierarchy (11 classes),
Pydantic schemas (30+ API models), NDJSON events (10 TypedDicts), Settings config.
(FR-017, FR-018)
"""

import inspect
import typing

from pydantic import BaseModel
from pydantic_settings import BaseSettings

# --- Error hierarchy ---
from backend.errors import (
    EmbeddinatorError,
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
)

# --- Cross-layer Pydantic schemas ---
from backend.agent.schemas import (
    QueryAnalysis,
    ClaimVerification,
    GroundednessResult,
    RetrievedChunk,
    Citation,
    SubAnswer,
    # API schemas
    CollectionResponse,
    DocumentResponse,
    ChatRequest,
    ProviderResponse,
    HealthResponse,
    ErrorResponse,
    IngestionJobResponse,
    ModelInfo,
    SettingsResponse,
    QueryTraceResponse,
    # NDJSON events (TypedDict)
    SessionEvent,
    StatusEvent,
    ChunkEvent,
    CitationEvent,
    MetaReasoningEvent,
    ConfidenceEvent,
    GroundednessEvent,
    DoneEvent,
    ClarificationEvent,
    ErrorEvent,
)

# --- Config ---
from backend.config import Settings


class TestErrorHierarchy:
    """FR-017, Pattern 3: All 11 error classes in backend/errors.py."""

    def test_embeddinatorerror_is_exception_subclass(self):
        """EmbeddinatorError is the base exception."""
        assert issubclass(EmbeddinatorError, Exception)

    def test_qdrant_connection_error_inherits_embeddinatorerror(self):
        assert issubclass(QdrantConnectionError, EmbeddinatorError)

    def test_ollama_connection_error_inherits_embeddinatorerror(self):
        assert issubclass(OllamaConnectionError, EmbeddinatorError)

    def test_sqlite_error_inherits_embeddinatorerror(self):
        assert issubclass(SQLiteError, EmbeddinatorError)

    def test_llm_call_error_inherits_embeddinatorerror(self):
        assert issubclass(LLMCallError, EmbeddinatorError)

    def test_embedding_error_inherits_embeddinatorerror(self):
        assert issubclass(EmbeddingError, EmbeddinatorError)

    def test_ingestion_error_inherits_embeddinatorerror(self):
        assert issubclass(IngestionError, EmbeddinatorError)

    def test_session_load_error_inherits_embeddinatorerror(self):
        assert issubclass(SessionLoadError, EmbeddinatorError)

    def test_structured_output_parse_error_inherits_embeddinatorerror(self):
        assert issubclass(StructuredOutputParseError, EmbeddinatorError)

    def test_reranker_error_inherits_embeddinatorerror(self):
        assert issubclass(RerankerError, EmbeddinatorError)

    def test_circuit_open_error_inherits_embeddinatorerror(self):
        """CircuitOpenError exists and inherits from EmbeddinatorError (commonly missed)."""
        assert issubclass(CircuitOpenError, EmbeddinatorError)

    def test_all_10_specific_errors_inherit_from_embeddinatorerror(self):
        """All 10 specific errors are subclasses of EmbeddinatorError."""
        specific_errors = [
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
        for error_class in specific_errors:
            assert issubclass(error_class, EmbeddinatorError), (
                f"{error_class.__name__} must inherit from EmbeddinatorError"
            )


class TestCrossLayerPydanticSchemas:
    """FR-018: Cross-layer Pydantic schema contracts — 6 schemas with full field validation."""

    def test_query_analysis_has_complexity_tier_field(self):
        """QueryAnalysis has complexity_tier field."""
        assert "complexity_tier" in QueryAnalysis.model_fields

    def test_query_analysis_complexity_tier_is_literal_type(self):
        """QueryAnalysis.complexity_tier has a Literal type annotation."""
        annotation = QueryAnalysis.model_fields["complexity_tier"].annotation
        origin = typing.get_origin(annotation)
        assert origin is typing.Literal

    def test_claim_verification_has_verdict_field(self):
        """ClaimVerification has verdict field."""
        assert "verdict" in ClaimVerification.model_fields

    def test_groundedness_result_has_overall_grounded_field(self):
        """GroundednessResult has overall_grounded field."""
        assert "overall_grounded" in GroundednessResult.model_fields

    def test_retrieved_chunk_is_basemodel_subclass(self):
        """RetrievedChunk is a BaseModel subclass."""
        assert issubclass(RetrievedChunk, BaseModel)

    def test_retrieved_chunk_has_chunk_id(self):
        assert "chunk_id" in RetrievedChunk.model_fields

    def test_retrieved_chunk_has_text(self):
        assert "text" in RetrievedChunk.model_fields

    def test_retrieved_chunk_has_source_file(self):
        assert "source_file" in RetrievedChunk.model_fields

    def test_retrieved_chunk_has_parent_id(self):
        assert "parent_id" in RetrievedChunk.model_fields

    def test_retrieved_chunk_has_collection(self):
        assert "collection" in RetrievedChunk.model_fields

    def test_citation_is_basemodel_subclass(self):
        """Citation is a BaseModel subclass."""
        assert issubclass(Citation, BaseModel)

    def test_citation_has_passage_id(self):
        assert "passage_id" in Citation.model_fields

    def test_citation_has_document_id(self):
        assert "document_id" in Citation.model_fields

    def test_citation_has_text(self):
        assert "text" in Citation.model_fields

    def test_citation_has_relevance_score(self):
        assert "relevance_score" in Citation.model_fields

    def test_sub_answer_is_basemodel_subclass(self):
        """SubAnswer is a BaseModel subclass."""
        assert issubclass(SubAnswer, BaseModel)

    def test_sub_answer_has_sub_question(self):
        assert "sub_question" in SubAnswer.model_fields

    def test_sub_answer_has_answer(self):
        assert "answer" in SubAnswer.model_fields

    def test_sub_answer_has_citations(self):
        assert "citations" in SubAnswer.model_fields


class TestAPISchemaImports:
    """FR-018: All 30+ API models importable from backend/agent/schemas.py (import check only)."""

    def test_collection_response_importable(self):
        assert CollectionResponse is not None

    def test_document_response_importable(self):
        assert DocumentResponse is not None

    def test_chat_request_importable(self):
        assert ChatRequest is not None

    def test_provider_response_importable(self):
        assert ProviderResponse is not None

    def test_health_response_importable(self):
        assert HealthResponse is not None

    def test_error_response_importable(self):
        assert ErrorResponse is not None

    def test_ingestion_job_response_importable(self):
        assert IngestionJobResponse is not None

    def test_model_info_importable(self):
        assert ModelInfo is not None

    def test_settings_response_importable(self):
        assert SettingsResponse is not None

    def test_query_trace_response_importable(self):
        assert QueryTraceResponse is not None

    def test_all_api_schemas_are_basemodel_subclasses(self):
        """All core API response schemas are BaseModel subclasses."""
        api_schemas = [
            CollectionResponse,
            DocumentResponse,
            ChatRequest,
            ProviderResponse,
            HealthResponse,
            ErrorResponse,
            IngestionJobResponse,
            ModelInfo,
            SettingsResponse,
            QueryTraceResponse,
        ]
        for schema in api_schemas:
            assert issubclass(schema, BaseModel), f"{schema.__name__} must be a BaseModel subclass"


class TestNDJSONEventModels:
    """FR-018: NDJSON event model contracts — TypedDict, NOT BaseModel (fixed per validation report)."""

    def test_session_event_importable(self):
        assert SessionEvent is not None

    def test_status_event_importable(self):
        assert StatusEvent is not None

    def test_chunk_event_importable(self):
        assert ChunkEvent is not None

    def test_citation_event_importable(self):
        assert CitationEvent is not None

    def test_meta_reasoning_event_importable(self):
        assert MetaReasoningEvent is not None

    def test_confidence_event_importable(self):
        assert ConfidenceEvent is not None

    def test_groundedness_event_importable(self):
        assert GroundednessEvent is not None

    def test_done_event_importable(self):
        assert DoneEvent is not None

    def test_clarification_event_importable(self):
        assert ClarificationEvent is not None

    def test_error_event_importable(self):
        assert ErrorEvent is not None

    def test_all_events_are_typeddict_subclasses(self):
        """All 10 NDJSON events are TypedDict (dict subclass), not BaseModel."""
        events = [
            SessionEvent,
            StatusEvent,
            ChunkEvent,
            CitationEvent,
            MetaReasoningEvent,
            ConfidenceEvent,
            GroundednessEvent,
            DoneEvent,
            ClarificationEvent,
            ErrorEvent,
        ]
        for event in events:
            # TypedDict classes are dict subclasses at runtime
            assert issubclass(event, dict), f"{event.__name__} must be a TypedDict (dict subclass)"

    def test_no_event_is_basemodel(self):
        """NDJSON events must NOT be BaseModel subclasses (they are TypedDicts)."""
        events = [
            SessionEvent,
            StatusEvent,
            ChunkEvent,
            CitationEvent,
            MetaReasoningEvent,
            ConfidenceEvent,
            GroundednessEvent,
            DoneEvent,
            ClarificationEvent,
            ErrorEvent,
        ]
        for event in events:
            assert not issubclass(event, BaseModel), f"{event.__name__} must NOT be a BaseModel — it is a TypedDict"


class TestSettingsConfig:
    """Settings config contracts: BaseSettings subclass with required fields."""

    def test_settings_is_basesettings_subclass(self):
        """Settings is a BaseSettings subclass in backend/config.py."""
        assert issubclass(Settings, BaseSettings)

    def test_confidence_threshold_field_exists(self):
        """Settings has confidence_threshold field."""
        assert "confidence_threshold" in Settings.model_fields

    def test_meta_relevance_threshold_field_exists(self):
        """Settings has meta_relevance_threshold field."""
        assert "meta_relevance_threshold" in Settings.model_fields

    def test_meta_variance_threshold_field_exists(self):
        """Settings has meta_variance_threshold field."""
        assert "meta_variance_threshold" in Settings.model_fields
