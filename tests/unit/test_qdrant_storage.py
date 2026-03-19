"""Unit tests for QdrantStorage (Spec-07). All Qdrant calls are mocked."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.storage.qdrant_client import (
    QdrantPoint,
    QdrantStorage,
    SearchResult,
    SparseVector,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_PAYLOAD: dict[str, Any] = {
    "text": "child chunk text (~500 chars of content)",
    "parent_id": "550e8400-e29b-41d4-a716-446655440000",
    "breadcrumb": "My Collection > Document > Section 1",
    "source_file": "report.pdf",
    "page": 3,
    "chunk_index": 5,
    "doc_type": "Prose",
    "chunk_hash": "abc123sha256",
    "embedding_model": "all-MiniLM-L6-v2",
    "collection_name": "my_collection_qdrant",
    "ingested_at": "2026-03-13T10:00:00Z",
}

DENSE_VECTOR: list[float] = [0.1] * 768
SPARSE_VEC = SparseVector(indices=[1, 5, 42], values=[0.8, 0.3, 0.5])


def make_storage(
    failure_threshold: int = 5,
    cooldown_secs: int = 30,
) -> QdrantStorage:
    """Return a QdrantStorage with mocked settings (no real Qdrant)."""
    with patch("backend.storage.qdrant_client.AsyncQdrantClient"):
        with patch("backend.config.settings") as mock_settings:
            mock_settings.circuit_breaker_failure_threshold = failure_threshold
            mock_settings.circuit_breaker_cooldown_secs = cooldown_secs
            storage = QdrantStorage.__new__(QdrantStorage)
            storage.host = "localhost"
            storage.port = 6333
            storage.client = None
            storage._circuit_open = False
            storage._failure_count = 0
            storage._last_failure_time = None
            storage._max_failures = failure_threshold
            storage._cooldown_secs = cooldown_secs
    return storage


def attach_mock_client(storage: QdrantStorage) -> AsyncMock:
    """Attach an AsyncMock as the storage client and return it."""
    mock_client = AsyncMock()
    storage.client = mock_client
    return mock_client


def make_scored_point(id: int, score: float, payload: dict | None = None) -> MagicMock:
    hit = MagicMock()
    hit.id = id
    hit.score = score
    hit.payload = payload or {}
    return hit


def make_query_response(points: list) -> MagicMock:
    """Wrap scored points in a query_points response object."""
    resp = MagicMock()
    resp.points = points
    return resp


def make_record(id: int, vector: Any = None, payload: dict | None = None) -> MagicMock:
    rec = MagicMock()
    rec.id = id
    rec.vector = vector or [0.1] * 768
    rec.payload = payload or {}
    return rec


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def storage() -> QdrantStorage:
    return make_storage()


@pytest.fixture
def client(storage: QdrantStorage) -> AsyncMock:
    return attach_mock_client(storage)


# ---------------------------------------------------------------------------
# T038: Collection management tests
# ---------------------------------------------------------------------------


class TestCreateCollection:
    @pytest.mark.asyncio
    async def test_create_collection_calls_qdrant(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        """create_collection() delegates to qdrant client."""
        client.create_collection = AsyncMock()
        await storage.create_collection("test_col", vector_size=768, distance="cosine")
        client.create_collection.assert_called_once()
        call_kwargs = client.create_collection.call_args.kwargs
        assert call_kwargs["collection_name"] == "test_col"

    @pytest.mark.asyncio
    async def test_create_collection_dense_and_sparse_config(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        """create_collection() passes both vectors_config and sparse_vectors_config."""
        client.create_collection = AsyncMock()
        await storage.create_collection("col", vector_size=768, distance="cosine")
        call_kwargs = client.create_collection.call_args.kwargs
        assert "vectors_config" in call_kwargs
        assert "sparse_vectors_config" in call_kwargs
        assert "dense" in call_kwargs["vectors_config"]
        assert "sparse" in call_kwargs["sparse_vectors_config"]

    @pytest.mark.asyncio
    async def test_create_collection_resets_circuit_on_success(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        storage._failure_count = 2
        client.create_collection = AsyncMock()
        await storage.create_collection("col")
        assert storage._failure_count == 0

    @pytest.mark.asyncio
    async def test_create_collection_records_failure_on_error(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        client.create_collection = AsyncMock(side_effect=Exception("conn refused"))
        with pytest.raises(Exception, match="conn refused"):
            await storage.create_collection("col")
        assert storage._failure_count > 0

    @pytest.mark.asyncio
    async def test_create_collection_raises_circuit_open(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        storage._circuit_open = True
        storage._last_failure_time = None  # cooldown never elapsed
        from backend.errors import CircuitOpenError

        with pytest.raises(CircuitOpenError):
            await storage.create_collection("col")


class TestCollectionExists:
    @pytest.mark.asyncio
    async def test_collection_exists_true(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        client.collection_exists = AsyncMock(return_value=True)
        assert await storage.collection_exists("col") is True

    @pytest.mark.asyncio
    async def test_collection_exists_false(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        client.collection_exists = AsyncMock(return_value=False)
        assert await storage.collection_exists("missing") is False

    @pytest.mark.asyncio
    async def test_collection_exists_propagates_exception(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        client.collection_exists = AsyncMock(side_effect=ConnectionError("timeout"))
        with pytest.raises(ConnectionError):
            await storage.collection_exists("col")
        assert storage._failure_count > 0


class TestDeleteCollection:
    @pytest.mark.asyncio
    async def test_delete_collection(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        client.delete_collection = AsyncMock()
        await storage.delete_collection("col")
        client.delete_collection.assert_called_once_with("col")


class TestGetCollectionInfo:
    @pytest.mark.asyncio
    async def test_get_collection_info_returns_dict(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        mock_info = MagicMock()
        mock_info.points_count = 42
        mock_info.status = MagicMock(__str__=lambda s: "green")
        dense_param = MagicMock()
        dense_param.size = 768
        mock_info.config.params.vectors = {"dense": dense_param}
        client.get_collection = AsyncMock(return_value=mock_info)

        result = await storage.get_collection_info("col")

        assert result["name"] == "col"
        assert result["points_count"] == 42
        assert result["vector_size"] == 768
        assert "status" in result


# ---------------------------------------------------------------------------
# T039: Batch upsert tests
# ---------------------------------------------------------------------------


class TestBatchUpsert:
    def _make_point(self, id: int = 1, payload: dict | None = None) -> QdrantPoint:
        return QdrantPoint(
            id=id,
            vector=DENSE_VECTOR,
            sparse_vector=SPARSE_VEC,
            payload=payload or VALID_PAYLOAD.copy(),
        )

    @pytest.mark.asyncio
    async def test_batch_upsert_returns_count(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        client.upsert = AsyncMock()
        points = [self._make_point(i) for i in range(5)]
        count = await storage.batch_upsert("col", points)
        assert count == 5

    @pytest.mark.asyncio
    async def test_batch_upsert_empty_list_returns_zero(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        count = await storage.batch_upsert("col", [])
        assert count == 0
        client.upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_batch_upsert_calls_qdrant_upsert(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        client.upsert = AsyncMock()
        await storage.batch_upsert("col", [self._make_point()])
        client.upsert.assert_called_once()
        call_kwargs = client.upsert.call_args.kwargs
        assert call_kwargs["collection_name"] == "col"
        assert len(call_kwargs["points"]) == 1

    @pytest.mark.asyncio
    async def test_batch_upsert_idempotent_same_id(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        """Same point ID can be upserted multiple times (idempotent via Qdrant)."""
        client.upsert = AsyncMock()
        point = self._make_point(id=99)
        await storage.batch_upsert("col", [point])
        await storage.batch_upsert("col", [point])
        assert client.upsert.call_count == 2

    @pytest.mark.asyncio
    async def test_batch_upsert_timeout_fails_entire_batch(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        """On Qdrant timeout, the entire batch fails (no partial tracking)."""
        client.upsert = AsyncMock(side_effect=TimeoutError("qdrant timeout"))
        with pytest.raises(TimeoutError):
            await storage.batch_upsert("col", [self._make_point()])
        assert storage._failure_count > 0

    @pytest.mark.asyncio
    async def test_batch_upsert_with_sparse_vector(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        """Points with sparse vectors are included in the upsert call."""
        client.upsert = AsyncMock()
        point = self._make_point()
        point.sparse_vector = SparseVector(indices=[1, 3], values=[0.5, 0.2])
        await storage.batch_upsert("col", [point])
        call_kwargs = client.upsert.call_args.kwargs
        upserted = call_kwargs["points"][0]
        # The PointStruct should have a "sparse" key in its vector dict
        assert "sparse" in upserted.vector

    @pytest.mark.asyncio
    async def test_batch_upsert_without_sparse_vector(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        """Points without sparse vectors only include the dense vector."""
        client.upsert = AsyncMock()
        point = QdrantPoint(
            id=1, vector=DENSE_VECTOR, sparse_vector=None, payload=VALID_PAYLOAD.copy()
        )
        await storage.batch_upsert("col", [point])
        call_kwargs = client.upsert.call_args.kwargs
        upserted = call_kwargs["points"][0]
        assert "dense" in upserted.vector
        assert "sparse" not in upserted.vector


# ---------------------------------------------------------------------------
# T040: Payload validation tests
# ---------------------------------------------------------------------------


class TestPayloadValidation:
    def test_valid_payload_passes(self, storage: QdrantStorage) -> None:
        storage._validate_payload(VALID_PAYLOAD)  # should not raise

    def test_missing_field_raises(self, storage: QdrantStorage) -> None:
        bad = VALID_PAYLOAD.copy()
        del bad["parent_id"]
        with pytest.raises(ValueError, match="parent_id"):
            storage._validate_payload(bad)

    def test_all_11_fields_required(self, storage: QdrantStorage) -> None:
        for field in QdrantStorage.REQUIRED_PAYLOAD_FIELDS:
            bad = VALID_PAYLOAD.copy()
            del bad[field]
            with pytest.raises(ValueError):
                storage._validate_payload(bad)

    def test_invalid_doc_type_raises(self, storage: QdrantStorage) -> None:
        bad = VALID_PAYLOAD.copy()
        bad["doc_type"] = "Table"
        with pytest.raises(ValueError, match="doc_type"):
            storage._validate_payload(bad)

    def test_valid_doc_types(self, storage: QdrantStorage) -> None:
        for valid in ("Prose", "Code"):
            payload = VALID_PAYLOAD.copy()
            payload["doc_type"] = valid
            storage._validate_payload(payload)  # should not raise

    @pytest.mark.asyncio
    async def test_batch_upsert_rejects_invalid_payload(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        bad_payload = VALID_PAYLOAD.copy()
        del bad_payload["chunk_hash"]
        point = QdrantPoint(
            id=1, vector=DENSE_VECTOR, sparse_vector=None, payload=bad_payload
        )
        with pytest.raises(ValueError, match="chunk_hash"):
            await storage.batch_upsert("col", [point])
        client.upsert.assert_not_called()


# ---------------------------------------------------------------------------
# T041: Hybrid search tests
# ---------------------------------------------------------------------------


class TestSearchHybrid:
    @pytest.mark.asyncio
    async def test_search_dense_only(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        """With no sparse vector, only dense search is executed."""
        client.query_points = AsyncMock(
            return_value=make_query_response([make_scored_point(1, 0.9, VALID_PAYLOAD)])
        )
        results = await storage.search_hybrid(
            "col", DENSE_VECTOR, None, top_k=5
        )
        assert len(results) == 1
        assert results[0].id == 1
        # query_points called once (only dense)
        assert client.query_points.call_count == 1

    @pytest.mark.asyncio
    async def test_search_with_sparse_vector(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        """With sparse vector, two searches are performed (dense + sparse)."""
        client.query_points = AsyncMock(
            return_value=make_query_response([make_scored_point(1, 0.8, VALID_PAYLOAD)])
        )
        results = await storage.search_hybrid(
            "col", DENSE_VECTOR, SPARSE_VEC, top_k=5
        )
        # query_points called twice: dense + sparse
        assert client.query_points.call_count == 2
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_search_returns_top_k(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        """Results are limited to top_k after fusion."""
        hits = [make_scored_point(i, 1.0 - i * 0.05, VALID_PAYLOAD) for i in range(20)]
        client.query_points = AsyncMock(return_value=make_query_response(hits))
        results = await storage.search_hybrid(
            "col", DENSE_VECTOR, None, top_k=5
        )
        assert len(results) <= 5

    @pytest.mark.asyncio
    async def test_search_applies_score_threshold(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        """Results below score_threshold are filtered out."""
        hits = [
            make_scored_point(1, 0.9, VALID_PAYLOAD),
            make_scored_point(2, 0.1, VALID_PAYLOAD),
        ]
        client.query_points = AsyncMock(return_value=make_query_response(hits))
        results = await storage.search_hybrid(
            "col", DENSE_VECTOR, None, top_k=10, score_threshold=0.5
        )
        # Only the 0.9 score should pass threshold (dense_weight=0.6 * 0.9 = 0.54)
        for r in results:
            assert r.score >= 0.5

    @pytest.mark.asyncio
    async def test_search_weighted_fusion(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        """Dense and sparse scores are fused by their respective weights."""
        dense_hit = make_scored_point(1, 1.0, VALID_PAYLOAD)
        sparse_hit = make_scored_point(1, 0.5, VALID_PAYLOAD)
        call_count = 0

        async def query_side_effect(*args: Any, **kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            pts = [dense_hit] if call_count == 1 else [sparse_hit]
            return make_query_response(pts)

        client.query_points = query_side_effect
        results = await storage.search_hybrid(
            "col", DENSE_VECTOR, SPARSE_VEC, dense_weight=0.6, sparse_weight=0.4
        )
        assert len(results) == 1
        expected = 0.6 * 1.0 + 0.4 * 0.5
        assert abs(results[0].score - expected) < 1e-6

    @pytest.mark.asyncio
    async def test_search_results_sorted_descending(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        hits = [
            make_scored_point(3, 0.3, VALID_PAYLOAD),
            make_scored_point(1, 0.9, VALID_PAYLOAD),
            make_scored_point(2, 0.6, VALID_PAYLOAD),
        ]
        client.query_points = AsyncMock(return_value=make_query_response(hits))
        results = await storage.search_hybrid("col", DENSE_VECTOR, None, top_k=10)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_search_returns_search_result_objects(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        client.query_points = AsyncMock(
            return_value=make_query_response([make_scored_point(7, 0.75, VALID_PAYLOAD)])
        )
        results = await storage.search_hybrid("col", DENSE_VECTOR, None, top_k=5)
        assert all(isinstance(r, SearchResult) for r in results)

    @pytest.mark.asyncio
    async def test_search_propagates_qdrant_error(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        client.query_points = AsyncMock(side_effect=ConnectionError("qdrant down"))
        with pytest.raises(ConnectionError):
            await storage.search_hybrid("col", DENSE_VECTOR, None)
        assert storage._failure_count > 0


# ---------------------------------------------------------------------------
# T042: Point deletion tests
# ---------------------------------------------------------------------------


class TestDeletePoints:
    @pytest.mark.asyncio
    async def test_delete_points_by_ids(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        client.delete = AsyncMock()
        count = await storage.delete_points("col", [1, 2, 3])
        assert count == 3
        client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_points_empty_list_returns_zero(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        count = await storage.delete_points("col", [])
        assert count == 0
        client.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_points_nonexistent_ids_graceful(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        """Qdrant silently ignores non-existent IDs; we should not raise."""
        client.delete = AsyncMock()  # No exception raised
        count = await storage.delete_points("col", [9999])
        assert count == 1  # We report the count of submitted IDs

    @pytest.mark.asyncio
    async def test_delete_points_by_filter(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        client.delete = AsyncMock()
        count = await storage.delete_points_by_filter("col", {"doc_type": "Prose"})
        assert isinstance(count, int)
        client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_points_propagates_error(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        client.delete = AsyncMock(side_effect=Exception("collection not found"))
        with pytest.raises(Exception, match="collection not found"):
            await storage.delete_points("col", [1])
        assert storage._failure_count > 0


# ---------------------------------------------------------------------------
# T043: Point retrieval tests
# ---------------------------------------------------------------------------


class TestPointRetrieval:
    @pytest.mark.asyncio
    async def test_get_point_returns_dict(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        rec = make_record(id=42, payload=VALID_PAYLOAD)
        client.retrieve = AsyncMock(return_value=[rec])
        result = await storage.get_point("col", 42)
        assert result is not None
        assert result["id"] == 42
        assert result["payload"] == VALID_PAYLOAD

    @pytest.mark.asyncio
    async def test_get_point_not_found_returns_none(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        client.retrieve = AsyncMock(return_value=[])
        result = await storage.get_point("col", 9999)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_points_by_ids_batch(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        records = [make_record(i, payload=VALID_PAYLOAD) for i in range(3)]
        client.retrieve = AsyncMock(return_value=records)
        results = await storage.get_points_by_ids("col", [0, 1, 2])
        assert len(results) == 3
        assert all("id" in r and "payload" in r for r in results)

    @pytest.mark.asyncio
    async def test_get_points_by_ids_empty(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        results = await storage.get_points_by_ids("col", [])
        assert results == []
        client.retrieve.assert_not_called()

    @pytest.mark.asyncio
    async def test_scroll_points_returns_tuple(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        records = [make_record(i) for i in range(10)]
        client.scroll = AsyncMock(return_value=(records, 10))
        points, next_offset = await storage.scroll_points("col", limit=10, offset=0)
        assert len(points) == 10
        assert next_offset == 10

    @pytest.mark.asyncio
    async def test_scroll_points_end_of_collection(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        records = [make_record(i) for i in range(3)]
        client.scroll = AsyncMock(return_value=(records, None))
        points, next_offset = await storage.scroll_points("col", limit=100)
        assert next_offset is None

    @pytest.mark.asyncio
    async def test_scroll_points_pagination(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        first_page = [make_record(i) for i in range(5)]
        second_page = [make_record(i + 5) for i in range(3)]

        async def scroll_side_effect(
            *args: Any, **kwargs: Any
        ) -> tuple[list, int | None]:
            offset = kwargs.get("offset")
            if offset is None or offset == 0:
                return (first_page, 5)
            return (second_page, None)

        client.scroll = scroll_side_effect

        p1, next1 = await storage.scroll_points("col", limit=5, offset=0)
        assert len(p1) == 5
        assert next1 == 5

        p2, next2 = await storage.scroll_points("col", limit=5, offset=next1)
        assert len(p2) == 3
        assert next2 is None


# ---------------------------------------------------------------------------
# T044: Health check and error handling tests
# ---------------------------------------------------------------------------


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_returns_true(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        client.get_collections = AsyncMock(return_value=MagicMock(collections=[]))
        assert await storage.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_error(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        client.get_collections = AsyncMock(side_effect=ConnectionError("refused"))
        assert await storage.health_check() is False
        assert storage._failure_count > 0

    @pytest.mark.asyncio
    async def test_health_check_resets_circuit_on_success(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        storage._failure_count = 3
        client.get_collections = AsyncMock(return_value=MagicMock(collections=[]))
        await storage.health_check()
        assert storage._failure_count == 0
        assert storage._circuit_open is False


class TestCircuitBreaker:
    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        """Circuit opens once failure_count >= max_failures."""
        storage._max_failures = 3
        client.get_collections = AsyncMock(side_effect=ConnectionError("fail"))
        for _ in range(3):
            await storage.health_check()
        assert storage._circuit_open is True

    @pytest.mark.asyncio
    async def test_circuit_open_blocks_requests(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        from backend.errors import CircuitOpenError

        storage._circuit_open = True
        storage._last_failure_time = None  # cooldown never elapses
        with pytest.raises(CircuitOpenError):
            await storage.collection_exists("col")

    @pytest.mark.asyncio
    async def test_circuit_half_open_after_cooldown(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        """After cooldown, circuit resets to closed and probes through."""
        import time

        storage._circuit_open = True
        storage._last_failure_time = time.monotonic() - 9999  # cooldown elapsed
        client.collection_exists = AsyncMock(return_value=True)
        result = await storage.collection_exists("col")
        assert result is True
        assert storage._circuit_open is False

    def test_record_failure_increments_count(self, storage: QdrantStorage) -> None:
        storage._record_failure()
        assert storage._failure_count == 1

    def test_record_success_resets_count(self, storage: QdrantStorage) -> None:
        storage._failure_count = 4
        storage._record_success()
        assert storage._failure_count == 0
        assert storage._circuit_open is False


class TestRetryBehavior:
    @pytest.mark.asyncio
    async def test_batch_upsert_retries_on_transient_error(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        """Tenacity retries up to 3 times on transient errors."""
        call_count = 0

        async def flaky_upsert(*args: Any, **kwargs: Any) -> None:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("transient")

        client.upsert = flaky_upsert
        point = QdrantPoint(
            id=1, vector=DENSE_VECTOR, sparse_vector=None, payload=VALID_PAYLOAD.copy()
        )
        count = await storage.batch_upsert("col", [point])
        assert count == 1
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_create_collection_retries_on_transient_error(
        self, storage: QdrantStorage, client: AsyncMock
    ) -> None:
        call_count = 0

        async def flaky_create(*args: Any, **kwargs: Any) -> None:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("transient")

        client.create_collection = flaky_create
        await storage.create_collection("col")
        assert call_count == 2


# ---------------------------------------------------------------------------
# T038: Data class structure tests
# ---------------------------------------------------------------------------


class TestDataClasses:
    def test_sparse_vector_fields(self) -> None:
        sv = SparseVector(indices=[1, 2], values=[0.5, 0.3])
        assert sv.indices == [1, 2]
        assert sv.values == [0.5, 0.3]

    def test_qdrant_point_fields(self) -> None:
        point = QdrantPoint(
            id=99,
            vector=DENSE_VECTOR,
            sparse_vector=SPARSE_VEC,
            payload=VALID_PAYLOAD,
        )
        assert point.id == 99
        assert point.sparse_vector is SPARSE_VEC

    def test_search_result_fields(self) -> None:
        sr = SearchResult(id=1, score=0.88, payload={"text": "hello"})
        assert sr.id == 1
        assert sr.score == 0.88

    def test_qdrant_point_without_sparse(self) -> None:
        point = QdrantPoint(
            id=5, vector=DENSE_VECTOR, sparse_vector=None, payload=VALID_PAYLOAD
        )
        assert point.sparse_vector is None


# ---------------------------------------------------------------------------
# T038: Importability smoke test
# ---------------------------------------------------------------------------


def test_importable() -> None:
    """QdrantStorage, QdrantPoint, SparseVector, SearchResult are all importable."""
    from backend.storage.qdrant_client import (
        QdrantPoint,
        QdrantStorage,
        SearchResult,
        SparseVector,
    )

    assert QdrantStorage is not None
    assert QdrantPoint is not None
    assert SparseVector is not None
    assert SearchResult is not None


def test_required_payload_fields_count() -> None:
    """Exactly 11 required payload fields per FR-011."""
    assert len(QdrantStorage.REQUIRED_PAYLOAD_FIELDS) == 11


def test_valid_doc_types() -> None:
    """Only 'Prose' and 'Code' are valid doc_type values."""
    assert "Prose" in QdrantStorage.VALID_DOC_TYPES
    assert "Code" in QdrantStorage.VALID_DOC_TYPES
    assert "Table" not in QdrantStorage.VALID_DOC_TYPES
    assert "Mixed" not in QdrantStorage.VALID_DOC_TYPES
