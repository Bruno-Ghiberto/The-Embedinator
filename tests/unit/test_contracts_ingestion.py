"""Contract tests for ingestion pipeline layer: IngestionPipeline, BatchEmbedder,
ChunkSplitter, IncrementalChecker, UpsertBuffer, IngestionResult (FR-012–FR-015).
"""

import dataclasses
import inspect

import pytest
from pydantic import BaseModel

from backend.ingestion.pipeline import (
    IngestionPipeline,
    IngestionResult,
    UpsertBuffer,
)
from backend.ingestion.embedder import BatchEmbedder, validate_embedding
from backend.ingestion.chunker import ChunkSplitter
from backend.ingestion.incremental import IncrementalChecker
from backend.storage.qdrant_client import QdrantClientWrapper


class TestIngestionPipelineConstructor:
    """FR-013: IngestionPipeline constructor contracts."""

    def test_constructor_takes_exactly_3_non_self_params(self):
        """Constructor takes exactly 3 params: db, qdrant, embedding_provider."""
        sig = inspect.signature(IngestionPipeline.__init__)
        non_self_params = [p for p in sig.parameters if p != "self"]
        assert len(non_self_params) == 3

    def test_constructor_has_db_param(self):
        """Constructor has db parameter."""
        sig = inspect.signature(IngestionPipeline.__init__)
        assert "db" in sig.parameters

    def test_constructor_has_qdrant_param(self):
        """Constructor has qdrant parameter."""
        sig = inspect.signature(IngestionPipeline.__init__)
        assert "qdrant" in sig.parameters

    def test_constructor_has_embedding_provider_param(self):
        """Constructor has embedding_provider parameter."""
        sig = inspect.signature(IngestionPipeline.__init__)
        assert "embedding_provider" in sig.parameters

    def test_qdrant_param_references_qdranclientwrapper_not_qdrantstorage(self):
        """qdrant param annotation is QdrantClientWrapper (NOT QdrantStorage)."""
        sig = inspect.signature(IngestionPipeline.__init__)
        qdrant_param = sig.parameters.get("qdrant")
        assert qdrant_param is not None
        annotation = qdrant_param.annotation
        if annotation is not inspect.Parameter.empty:
            # Get the class name from annotation (handles class or string annotation)
            ann_name = (
                annotation.__name__
                if hasattr(annotation, "__name__")
                else str(annotation)
            )
            assert "QdrantClientWrapper" in ann_name
            assert "QdrantStorage" not in ann_name

    def test_check_duplicate_does_not_exist_on_ingestion_pipeline(self):
        """check_duplicate does NOT exist on IngestionPipeline (Pattern 7)."""
        assert not hasattr(IngestionPipeline, "check_duplicate"), (
            "check_duplicate must NOT be on IngestionPipeline — "
            "it belongs on IncrementalChecker"
        )


class TestIngestionResult:
    """FR-014, Pattern 4: IngestionResult dataclass contracts."""

    def test_is_dataclass_not_basemodel(self):
        """IngestionResult is a @dataclass, NOT a BaseModel."""
        assert dataclasses.is_dataclass(IngestionResult)
        assert not issubclass(IngestionResult, BaseModel)

    def test_has_document_id_field(self):
        """IngestionResult has document_id field."""
        field_names = {f.name for f in dataclasses.fields(IngestionResult)}
        assert "document_id" in field_names

    def test_has_job_id_field(self):
        """IngestionResult has job_id field."""
        field_names = {f.name for f in dataclasses.fields(IngestionResult)}
        assert "job_id" in field_names

    def test_has_status_field(self):
        """IngestionResult has status field."""
        field_names = {f.name for f in dataclasses.fields(IngestionResult)}
        assert "status" in field_names

    def test_has_chunks_processed_field(self):
        """IngestionResult has chunks_processed field."""
        field_names = {f.name for f in dataclasses.fields(IngestionResult)}
        assert "chunks_processed" in field_names

    def test_has_chunks_skipped_field(self):
        """IngestionResult has chunks_skipped field."""
        field_names = {f.name for f in dataclasses.fields(IngestionResult)}
        assert "chunks_skipped" in field_names

    def test_has_error_field(self):
        """IngestionResult has error field."""
        field_names = {f.name for f in dataclasses.fields(IngestionResult)}
        assert "error" in field_names

    def test_error_msg_does_not_exist(self):
        """IngestionResult does NOT have error_msg (common wrong name)."""
        field_names = {f.name for f in dataclasses.fields(IngestionResult)}
        assert "error_msg" not in field_names

    def test_elapsed_ms_does_not_exist(self):
        """IngestionResult does NOT have elapsed_ms."""
        field_names = {f.name for f in dataclasses.fields(IngestionResult)}
        assert "elapsed_ms" not in field_names


class TestBatchEmbedder:
    """FR-012: BatchEmbedder contracts."""

    def test_method_is_embed_chunks_not_embed_batch(self):
        """Method is embed_chunks (NOT embed_batch)."""
        assert hasattr(BatchEmbedder, "embed_chunks")
        assert not hasattr(BatchEmbedder, "embed_batch")

    def test_embed_chunks_is_callable(self):
        """embed_chunks is callable on BatchEmbedder."""
        assert callable(BatchEmbedder.embed_chunks)

    def test_validate_embedding_is_standalone_module_level_function(self):
        """validate_embedding is a standalone module-level function (NOT a method on BatchEmbedder)."""
        assert callable(validate_embedding)
        assert not hasattr(BatchEmbedder, "validate_embedding")

    def test_validate_embedding_can_be_imported_directly(self):
        """validate_embedding can be imported directly from backend.ingestion.embedder."""
        from backend.ingestion.embedder import validate_embedding as ve

        assert ve is validate_embedding


class TestIncrementalChecker:
    """FR-015: IncrementalChecker contracts."""

    def test_check_duplicate_lives_on_incremental_checker(self):
        """check_duplicate lives on IncrementalChecker (NOT IngestionPipeline)."""
        assert hasattr(IncrementalChecker, "check_duplicate")

    def test_check_duplicate_not_on_ingestion_pipeline(self):
        """check_duplicate does NOT exist on IngestionPipeline."""
        assert not hasattr(IngestionPipeline, "check_duplicate")

    def test_compute_file_hash_exists_on_incremental_checker(self):
        """compute_file_hash exists on IncrementalChecker."""
        assert hasattr(IncrementalChecker, "compute_file_hash")

    def test_compute_file_hash_is_callable(self):
        """compute_file_hash is callable."""
        assert callable(IncrementalChecker.compute_file_hash)


class TestChunkSplitter:
    """FR-015: ChunkSplitter method contracts."""

    def test_has_split_into_parents_method(self):
        """ChunkSplitter has split_into_parents method."""
        assert hasattr(ChunkSplitter, "split_into_parents")
        assert callable(ChunkSplitter.split_into_parents)

    def test_has_split_parent_into_children_method(self):
        """ChunkSplitter has split_parent_into_children method."""
        assert hasattr(ChunkSplitter, "split_parent_into_children")
        assert callable(ChunkSplitter.split_parent_into_children)

    def test_has_prepend_breadcrumb_method(self):
        """ChunkSplitter has prepend_breadcrumb method."""
        assert hasattr(ChunkSplitter, "prepend_breadcrumb")
        assert callable(ChunkSplitter.prepend_breadcrumb)

    def test_has_compute_point_id_method(self):
        """ChunkSplitter has compute_point_id method."""
        assert hasattr(ChunkSplitter, "compute_point_id")
        assert callable(ChunkSplitter.compute_point_id)


class TestUpsertBuffer:
    """FR-015: UpsertBuffer contracts."""

    def test_upsertbuffer_class_exists(self):
        """UpsertBuffer class exists."""
        assert UpsertBuffer is not None

    def test_has_add_method(self):
        """UpsertBuffer has add method."""
        assert hasattr(UpsertBuffer, "add")
        assert callable(UpsertBuffer.add)

    def test_has_flush_method(self):
        """UpsertBuffer has flush method."""
        assert hasattr(UpsertBuffer, "flush")
        assert callable(UpsertBuffer.flush)

    def test_has_pending_count(self):
        """UpsertBuffer has pending_count (property or method)."""
        assert hasattr(UpsertBuffer, "pending_count")

    def test_pending_count_is_property(self):
        """pending_count is a @property on UpsertBuffer."""
        # Check it's a property descriptor on the class
        assert isinstance(
            inspect.getattr_static(UpsertBuffer, "pending_count"), property
        )
