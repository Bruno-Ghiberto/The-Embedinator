"""
Contract tests for storage layer — T023-T028 (spec-11, US2, FR-008, FR-009).

These tests enforce interface contracts for SQLiteDB, QdrantStorage, and
ParentStore using introspection. No database connections are made.
"""

import inspect

import pytest

from backend.storage.sqlite_db import SQLiteDB
from backend.storage.qdrant_client import (
    QdrantClientWrapper,
    QdrantStorage,
    SparseVector,
    QdrantPoint,
    SearchResult,
)
from backend.storage.parent_store import ParentStore


# ---------------------------------------------------------------------------
# T024 — SQLiteDB method existence tests (FR-008)
# ---------------------------------------------------------------------------


class TestSQLiteDBMethodExistence:
    """Verify all 35+ methods exist on SQLiteDB, organised by category."""

    # --- Collections ---

    def test_create_collection_exists(self):
        assert hasattr(SQLiteDB, "create_collection")
        assert callable(getattr(SQLiteDB, "create_collection"))

    def test_get_collection_exists(self):
        assert hasattr(SQLiteDB, "get_collection")
        assert callable(getattr(SQLiteDB, "get_collection"))

    def test_get_collection_by_name_exists(self):
        assert hasattr(SQLiteDB, "get_collection_by_name")
        assert callable(getattr(SQLiteDB, "get_collection_by_name"))

    def test_list_collections_exists(self):
        assert hasattr(SQLiteDB, "list_collections")
        assert callable(getattr(SQLiteDB, "list_collections"))

    def test_update_collection_exists(self):
        assert hasattr(SQLiteDB, "update_collection")
        assert callable(getattr(SQLiteDB, "update_collection"))

    def test_delete_collection_exists(self):
        assert hasattr(SQLiteDB, "delete_collection")
        assert callable(getattr(SQLiteDB, "delete_collection"))

    # --- Documents ---

    def test_create_document_exists(self):
        assert hasattr(SQLiteDB, "create_document")
        assert callable(getattr(SQLiteDB, "create_document"))

    def test_get_document_exists(self):
        assert hasattr(SQLiteDB, "get_document")
        assert callable(getattr(SQLiteDB, "get_document"))

    def test_get_document_by_hash_exists(self):
        assert hasattr(SQLiteDB, "get_document_by_hash")
        assert callable(getattr(SQLiteDB, "get_document_by_hash"))

    def test_list_documents_exists(self):
        assert hasattr(SQLiteDB, "list_documents")
        assert callable(getattr(SQLiteDB, "list_documents"))

    def test_update_document_exists(self):
        assert hasattr(SQLiteDB, "update_document")
        assert callable(getattr(SQLiteDB, "update_document"))

    def test_delete_document_exists(self):
        assert hasattr(SQLiteDB, "delete_document")
        assert callable(getattr(SQLiteDB, "delete_document"))

    # --- Ingestion Jobs ---

    def test_create_ingestion_job_exists(self):
        assert hasattr(SQLiteDB, "create_ingestion_job")
        assert callable(getattr(SQLiteDB, "create_ingestion_job"))

    def test_get_ingestion_job_exists(self):
        assert hasattr(SQLiteDB, "get_ingestion_job")
        assert callable(getattr(SQLiteDB, "get_ingestion_job"))

    def test_update_ingestion_job_exists(self):
        assert hasattr(SQLiteDB, "update_ingestion_job")
        assert callable(getattr(SQLiteDB, "update_ingestion_job"))

    def test_list_ingestion_jobs_exists(self):
        assert hasattr(SQLiteDB, "list_ingestion_jobs")
        assert callable(getattr(SQLiteDB, "list_ingestion_jobs"))

    # --- Parent Chunks ---

    def test_create_parent_chunk_exists(self):
        assert hasattr(SQLiteDB, "create_parent_chunk")
        assert callable(getattr(SQLiteDB, "create_parent_chunk"))

    def test_get_parent_chunk_exists(self):
        assert hasattr(SQLiteDB, "get_parent_chunk")
        assert callable(getattr(SQLiteDB, "get_parent_chunk"))

    def test_get_parent_chunks_batch_exists(self):
        assert hasattr(SQLiteDB, "get_parent_chunks_batch")
        assert callable(getattr(SQLiteDB, "get_parent_chunks_batch"))

    def test_list_parent_chunks_exists(self):
        assert hasattr(SQLiteDB, "list_parent_chunks")
        assert callable(getattr(SQLiteDB, "list_parent_chunks"))

    def test_delete_parent_chunks_exists(self):
        assert hasattr(SQLiteDB, "delete_parent_chunks")
        assert callable(getattr(SQLiteDB, "delete_parent_chunks"))

    # --- Query Traces ---

    def test_create_query_trace_exists(self):
        assert hasattr(SQLiteDB, "create_query_trace")
        assert callable(getattr(SQLiteDB, "create_query_trace"))

    def test_list_query_traces_exists(self):
        assert hasattr(SQLiteDB, "list_query_traces")
        assert callable(getattr(SQLiteDB, "list_query_traces"))

    def test_list_traces_exists(self):
        assert hasattr(SQLiteDB, "list_traces")
        assert callable(getattr(SQLiteDB, "list_traces"))

    def test_get_trace_exists(self):
        assert hasattr(SQLiteDB, "get_trace")
        assert callable(getattr(SQLiteDB, "get_trace"))

    # --- Settings ---

    def test_get_setting_exists(self):
        assert hasattr(SQLiteDB, "get_setting")
        assert callable(getattr(SQLiteDB, "get_setting"))

    def test_set_setting_exists(self):
        assert hasattr(SQLiteDB, "set_setting")
        assert callable(getattr(SQLiteDB, "set_setting"))

    def test_list_settings_exists(self):
        assert hasattr(SQLiteDB, "list_settings")
        assert callable(getattr(SQLiteDB, "list_settings"))

    def test_delete_setting_exists(self):
        assert hasattr(SQLiteDB, "delete_setting")
        assert callable(getattr(SQLiteDB, "delete_setting"))

    # --- Providers ---

    def test_create_provider_exists(self):
        assert hasattr(SQLiteDB, "create_provider")
        assert callable(getattr(SQLiteDB, "create_provider"))

    def test_get_provider_exists(self):
        assert hasattr(SQLiteDB, "get_provider")
        assert callable(getattr(SQLiteDB, "get_provider"))

    def test_list_providers_exists(self):
        assert hasattr(SQLiteDB, "list_providers")
        assert callable(getattr(SQLiteDB, "list_providers"))

    def test_update_provider_exists(self):
        assert hasattr(SQLiteDB, "update_provider")
        assert callable(getattr(SQLiteDB, "update_provider"))

    def test_delete_provider_exists(self):
        assert hasattr(SQLiteDB, "delete_provider")
        assert callable(getattr(SQLiteDB, "delete_provider"))

    def test_get_active_provider_exists(self):
        assert hasattr(SQLiteDB, "get_active_provider")
        assert callable(getattr(SQLiteDB, "get_active_provider"))

    def test_upsert_provider_exists(self):
        assert hasattr(SQLiteDB, "upsert_provider")
        assert callable(getattr(SQLiteDB, "upsert_provider"))

    # --- Context Manager ---

    def test_connect_exists(self):
        assert hasattr(SQLiteDB, "connect")
        assert callable(getattr(SQLiteDB, "connect"))

    def test_close_exists(self):
        assert hasattr(SQLiteDB, "close")
        assert callable(getattr(SQLiteDB, "close"))


# ---------------------------------------------------------------------------
# T025 — SQLiteDB key method signature tests (FR-008)
# ---------------------------------------------------------------------------


class TestSQLiteDBSignatures:
    """Verify parameter names and counts for critical SQLiteDB methods."""

    def test_create_query_trace_param_names(self):
        """create_query_trace must include provider_name and all trace fields."""
        sig = inspect.signature(SQLiteDB.create_query_trace)
        params = list(sig.parameters.keys())
        expected_params = [
            "self",
            "id",
            "session_id",
            "query",
            "collections_searched",
            "chunks_retrieved_json",
            "latency_ms",
            "llm_model",
            "embed_model",
            "confidence_score",
            "sub_questions_json",
            "reasoning_steps_json",
            "strategy_switches_json",
            "meta_reasoning_triggered",
            "provider_name",
            "stage_timings_json",
        ]
        assert params == expected_params, (
            f"create_query_trace params mismatch.\nExpected: {expected_params}\nGot:      {params}"
        )

    def test_create_query_trace_has_provider_name(self):
        """provider_name param must be present (spec-10 FR integration)."""
        sig = inspect.signature(SQLiteDB.create_query_trace)
        assert "provider_name" in sig.parameters

    def test_create_query_trace_param_count(self):
        """Verify the exact number of parameters (16 including self, spec-14 adds stage_timings_json)."""
        sig = inspect.signature(SQLiteDB.create_query_trace)
        assert len(sig.parameters) == 16

    def test_create_document_uses_individual_params(self):
        """create_document must accept individual primitive params, not a model type."""
        sig = inspect.signature(SQLiteDB.create_document)
        params = list(sig.parameters.keys())
        # Must have individual field params
        assert "id" in params
        assert "collection_id" in params
        assert "filename" in params
        assert "file_hash" in params
        # Must NOT accept a single positional Pydantic model as first real arg
        # (i.e. no param named 'document' or 'model' or 'data')
        assert "document" not in params
        assert "model" not in params
        assert "data" not in params

    def test_list_traces_has_all_filter_params(self):
        """list_traces must accept session_id, collection_id, confidence range, pagination."""
        sig = inspect.signature(SQLiteDB.list_traces)
        params = list(sig.parameters.keys())
        required = [
            "session_id",
            "collection_id",
            "min_confidence",
            "max_confidence",
            "limit",
            "offset",
        ]
        for p in required:
            assert p in params, f"list_traces is missing param: {p}"

    def test_list_traces_param_defaults(self):
        """limit and offset must have sensible defaults."""
        sig = inspect.signature(SQLiteDB.list_traces)
        assert sig.parameters["limit"].default == 20
        assert sig.parameters["offset"].default == 0


# ---------------------------------------------------------------------------
# T026 — QdrantStorage tests (FR-009)
# ---------------------------------------------------------------------------


class TestQdrantStorageMethods:
    """Verify QdrantStorage method names, data classes, and coexistence."""

    # --- Method name correctness ---

    def test_batch_upsert_exists_not_upsert_batch(self):
        """Correct method is batch_upsert, NOT upsert_batch."""
        assert hasattr(QdrantStorage, "batch_upsert"), "batch_upsert must exist"
        assert not hasattr(QdrantStorage, "upsert_batch"), "upsert_batch must NOT exist (use batch_upsert)"

    def test_search_hybrid_exists_not_hybrid_search(self):
        """Correct method is search_hybrid, NOT hybrid_search."""
        assert hasattr(QdrantStorage, "search_hybrid"), "search_hybrid must exist"
        assert not hasattr(QdrantStorage, "hybrid_search"), "hybrid_search must NOT exist (use search_hybrid)"

    def test_delete_points_by_filter_exists_not_delete_by_filter(self):
        """Correct method is delete_points_by_filter, NOT delete_by_filter."""
        assert hasattr(QdrantStorage, "delete_points_by_filter"), "delete_points_by_filter must exist"
        assert not hasattr(QdrantStorage, "delete_by_filter"), (
            "delete_by_filter must NOT exist (use delete_points_by_filter)"
        )

    # --- Other required methods ---

    def test_health_check_exists(self):
        assert hasattr(QdrantStorage, "health_check")

    def test_create_collection_exists(self):
        assert hasattr(QdrantStorage, "create_collection")

    def test_collection_exists_exists(self):
        assert hasattr(QdrantStorage, "collection_exists")

    def test_delete_collection_exists(self):
        assert hasattr(QdrantStorage, "delete_collection")

    def test_get_point_exists(self):
        assert hasattr(QdrantStorage, "get_point")

    # --- Data classes ---

    def test_sparse_vector_class_exists(self):
        """SparseVector data class must be importable from qdrant_client module."""
        assert SparseVector is not None
        assert callable(SparseVector)

    def test_qdrant_point_class_exists(self):
        """QdrantPoint data class must be importable from qdrant_client module."""
        assert QdrantPoint is not None
        assert callable(QdrantPoint)

    def test_search_result_class_exists(self):
        """SearchResult data class must be importable from qdrant_client module."""
        assert SearchResult is not None
        assert callable(SearchResult)

    # --- Coexistence ---

    def test_qdrant_client_wrapper_coexists(self):
        """QdrantClientWrapper (legacy Phase 1) must coexist with QdrantStorage."""
        assert QdrantClientWrapper is not None
        assert isinstance(QdrantClientWrapper, type)

    def test_qdrant_storage_is_separate_class(self):
        """QdrantStorage must be a distinct class from QdrantClientWrapper."""
        assert QdrantStorage is not QdrantClientWrapper


# ---------------------------------------------------------------------------
# T027 — ParentStore tests
# ---------------------------------------------------------------------------


class TestParentStoreContract:
    """Verify ParentStore constructor and public method contracts."""

    def test_constructor_takes_db_param(self):
        """ParentStore.__init__ must accept a 'db' parameter."""
        sig = inspect.signature(ParentStore.__init__)
        params = list(sig.parameters.keys())
        assert "db" in params, f"ParentStore.__init__ must have 'db' param, got: {params}"

    def test_constructor_param_count(self):
        """ParentStore.__init__ should take exactly self + db."""
        sig = inspect.signature(ParentStore.__init__)
        assert len(sig.parameters) == 2  # self + db

    def test_get_by_ids_exists(self):
        assert hasattr(ParentStore, "get_by_ids")
        assert callable(getattr(ParentStore, "get_by_ids"))

    def test_get_all_by_collection_exists(self):
        assert hasattr(ParentStore, "get_all_by_collection")
        assert callable(getattr(ParentStore, "get_all_by_collection"))


# ---------------------------------------------------------------------------
# T028 — Negative assertions: phantom methods must NOT exist (SC-006)
# ---------------------------------------------------------------------------


class TestSQLiteDBNegativeAssertions:
    """
    Verify commonly confused phantom method names do NOT exist on SQLiteDB.

    These assertions prevent callers from using wrong method names that
    would raise AttributeError at runtime.
    """

    def test_find_by_hash_does_not_exist(self):
        """Use get_document_by_hash, not find_by_hash."""
        assert not hasattr(SQLiteDB, "find_by_hash"), "find_by_hash must NOT exist — use get_document_by_hash"

    def test_store_parent_chunks_does_not_exist(self):
        """Use create_parent_chunk (singular), not store_parent_chunks."""
        assert not hasattr(SQLiteDB, "store_parent_chunks"), (
            "store_parent_chunks must NOT exist — use create_parent_chunk"
        )

    def test_store_trace_does_not_exist(self):
        """Use create_query_trace, not store_trace."""
        assert not hasattr(SQLiteDB, "store_trace"), "store_trace must NOT exist — use create_query_trace"

    def test_get_all_settings_does_not_exist(self):
        """Use list_settings, not get_all_settings."""
        assert not hasattr(SQLiteDB, "get_all_settings"), "get_all_settings must NOT exist — use list_settings"

    def test_set_provider_key_does_not_exist(self):
        """set_provider_key does not exist as a direct method on SQLiteDB."""
        assert not hasattr(SQLiteDB, "set_provider_key"), "set_provider_key must NOT exist on SQLiteDB"

    def test_delete_provider_key_does_not_exist(self):
        """Use delete_provider, not delete_provider_key."""
        assert not hasattr(SQLiteDB, "delete_provider_key"), "delete_provider_key must NOT exist — use delete_provider"

    def test_update_document_status_does_not_exist(self):
        """Use update_document, not update_document_status."""
        assert not hasattr(SQLiteDB, "update_document_status"), (
            "update_document_status must NOT exist — use update_document"
        )
