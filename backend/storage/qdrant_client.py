"""Qdrant vector database client wrapper with circuit breaker and retry."""

import time
from dataclasses import dataclass

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_random,
)

from backend.errors import CircuitOpenError

logger = structlog.get_logger().bind(component=__name__)


class QdrantClientWrapper:
    def __init__(self, host: str, port: int):
        from backend.config import settings

        self.host = host
        self.port = port
        self.client: AsyncQdrantClient | None = None
        self._circuit_open = False
        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._max_failures = settings.circuit_breaker_failure_threshold
        self._cooldown_secs = settings.circuit_breaker_cooldown_secs

    def _check_circuit(self) -> None:
        """Check circuit breaker state. Raises CircuitOpenError if open."""
        if self._circuit_open:
            if (
                self._last_failure_time is not None
                and time.monotonic() - self._last_failure_time >= self._cooldown_secs
            ):
                # Half-open: allow one probe request through
                self._circuit_open = False
                logger.info("circuit_qdrant_half_open")
            else:
                logger.warning("circuit_qdrant_open", failure_count=self._failure_count)
                raise CircuitOpenError("Qdrant circuit breaker is open")

    def _record_success(self) -> None:
        """Reset circuit breaker on success."""
        self._failure_count = 0
        self._circuit_open = False

    def _record_failure(self) -> None:
        """Increment failure count, open circuit if threshold reached."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self._max_failures:
            self._circuit_open = True
            logger.error("circuit_qdrant_opened", failure_count=self._failure_count)

    async def connect(self):
        """Initialize async Qdrant client."""
        try:
            self.client = AsyncQdrantClient(host=self.host, port=self.port)
            await self.health_check()
            logger.info("storage_qdrant_connected", host=self.host, port=self.port)
        except Exception as e:
            logger.warning("storage_qdrant_connection_failed", error=type(e).__name__, detail=str(e))
            # Allow backend to start without Qdrant (degraded mode)

    async def close(self):
        if self.client:
            await self.client.close()

    async def health_check(self) -> bool:
        """Check if Qdrant is reachable."""
        self._check_circuit()
        try:
            await self.client.get_collections()
            self._record_success()
            return True
        except Exception:
            self._record_failure()
            return False

    async def ensure_collection(self, collection_name: str, vector_size: int = 384):
        """Create collection if it doesn't exist."""
        self._check_circuit()
        try:
            result = await self._ensure_collection_with_retry(collection_name, vector_size)
            self._record_success()
            return result
        except Exception:
            self._record_failure()
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10) + wait_random(0, 1),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def _ensure_collection_with_retry(self, collection_name: str, vector_size: int):
        collections = await self.client.get_collections()
        existing = [c.name for c in collections.collections]
        if collection_name not in existing:
            await self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
            logger.info("storage_qdrant_collection_created", name=collection_name)

    async def search(self, collection_name: str, query_vector: list[float], limit: int = 20) -> list[dict]:
        """Search for similar vectors with circuit breaker protection."""
        self._check_circuit()
        try:
            result = await self._search_with_retry(collection_name, query_vector, limit)
            self._record_success()
            return result
        except Exception:
            self._record_failure()
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10) + wait_random(0, 1),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def _search_with_retry(self, collection_name: str, query_vector: list[float], limit: int) -> list[dict]:
        results = await self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
        )
        return [
            {
                "id": str(hit.id),
                "score": hit.score,
                "payload": hit.payload,
            }
            for hit in results
        ]

    async def upsert(self, collection_name: str, points: list[dict]):
        """Insert or update vectors."""
        self._check_circuit()
        try:
            await self._upsert_with_retry(collection_name, points)
            self._record_success()
        except Exception:
            self._record_failure()
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10) + wait_random(0, 1),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def _upsert_with_retry(self, collection_name: str, points: list[dict]):
        from qdrant_client.models import PointStruct

        qdrant_points = [
            PointStruct(
                id=p["id"],
                vector=p["vector"],
                payload=p.get("payload", {}),
            )
            for p in points
        ]
        await self.client.upsert(collection_name=collection_name, points=qdrant_points)


# ---------------------------------------------------------------------------
# New Spec-07 classes: SparseVector, QdrantPoint, SearchResult, QdrantStorage
# The existing QdrantClientWrapper above is NOT modified.
# ---------------------------------------------------------------------------


@dataclass
class SparseVector:
    """Sparse vector with token indices and BM25 weights."""

    indices: list[int]
    values: list[float]


@dataclass
class QdrantPoint:
    """Point to be upserted into Qdrant with dense + optional sparse vectors."""

    id: int | str
    vector: list[float]  # Dense embedding (768 dims)
    sparse_vector: SparseVector | None  # BM25 token sparse vector
    payload: dict  # Metadata (11 required fields per FR-011)


@dataclass
class SearchResult:
    """Result from hybrid search with fused score."""

    id: int | str
    score: float  # Hybrid score after weighted rank fusion
    payload: dict  # Point payload (parent metadata)


class QdrantStorage:
    """Qdrant vector storage: collection management, batch upsert, hybrid search.

    NEW class (Spec-07) that coexists with QdrantClientWrapper in this file.
    Adds hybrid dense+sparse search, full payload validation, and circuit breaker.
    """

    REQUIRED_PAYLOAD_FIELDS: list[str] = [
        "text",
        "parent_id",
        "breadcrumb",
        "source_file",
        "page",
        "chunk_index",
        "doc_type",
        "chunk_hash",
        "embedding_model",
        "collection_name",
        "ingested_at",
    ]
    VALID_DOC_TYPES: frozenset[str] = frozenset({"Prose", "Code"})

    def __init__(self, host: str = "localhost", port: int = 6333) -> None:
        from backend.config import settings

        self.host = host
        self.port = port
        self.client: AsyncQdrantClient | None = None
        self._circuit_open = False
        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._max_failures = settings.circuit_breaker_failure_threshold
        self._cooldown_secs = settings.circuit_breaker_cooldown_secs

    # ------------------------------------------------------------------
    # Circuit breaker helpers (same pattern as QdrantClientWrapper)
    # ------------------------------------------------------------------

    def _check_circuit(self) -> None:
        """Raise CircuitOpenError if the circuit is open and cooldown not elapsed."""
        if self._circuit_open:
            if (
                self._last_failure_time is not None
                and time.monotonic() - self._last_failure_time >= self._cooldown_secs
            ):
                self._circuit_open = False
                logger.info("circuit_qdrant_storage_half_open")
            else:
                logger.warning(
                    "circuit_qdrant_storage_open",
                    failure_count=self._failure_count,
                )
                raise CircuitOpenError("QdrantStorage circuit breaker is open")

    def _record_success(self) -> None:
        self._failure_count = 0
        self._circuit_open = False

    def _record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self._max_failures:
            self._circuit_open = True
            logger.error(
                "circuit_qdrant_storage_opened",
                failure_count=self._failure_count,
            )

    async def _get_client(self) -> AsyncQdrantClient:
        """Return (or lazily create) the async Qdrant client."""
        if self.client is None:
            self.client = AsyncQdrantClient(host=self.host, port=self.port)
        return self.client

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """Return True if Qdrant is reachable, False otherwise."""
        try:
            client = await self._get_client()
            await client.get_collections()
            self._record_success()
            return True
        except Exception:
            self._record_failure()
            return False

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------

    async def create_collection(
        self,
        collection_name: str,
        vector_size: int = 768,
        distance: str = "cosine",
    ) -> None:
        """Create collection with dense (HNSW cosine) + sparse (BM25 IDF) config."""
        self._check_circuit()
        try:
            await self._create_collection_with_retry(collection_name, vector_size, distance)
            self._record_success()
        except Exception:
            self._record_failure()
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10) + wait_random(0, 1),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def _create_collection_with_retry(
        self,
        collection_name: str,
        vector_size: int,
        distance: str,
    ) -> None:
        from qdrant_client.models import (
            HnswConfigDiff,
            Modifier,
            SparseIndexParams,
            SparseVectorParams,
        )

        dist = Distance.COSINE if distance.lower() == "cosine" else Distance.DOT
        client = await self._get_client()
        await client.create_collection(
            collection_name=collection_name,
            vectors_config={
                "dense": VectorParams(
                    size=vector_size,
                    distance=dist,
                    hnsw_config=HnswConfigDiff(m=16, ef_construct=200),
                ),
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams(
                    index=SparseIndexParams(on_disk=True),
                    modifier=Modifier.IDF,
                ),
            },
        )
        logger.info("storage_qdrant_collection_created", name=collection_name)

    async def collection_exists(self, collection_name: str) -> bool:
        """Return True if the collection exists in Qdrant."""
        self._check_circuit()
        try:
            client = await self._get_client()
            result = await client.collection_exists(collection_name)
            self._record_success()
            return result
        except Exception:
            self._record_failure()
            raise

    async def delete_collection(self, collection_name: str) -> None:
        """Remove collection and all its points."""
        self._check_circuit()
        try:
            client = await self._get_client()
            await client.delete_collection(collection_name)
            self._record_success()
            logger.info("storage_qdrant_collection_deleted", name=collection_name)
        except Exception:
            self._record_failure()
            raise

    async def get_collection_info(self, collection_name: str) -> dict:
        """Return {name, points_count, vector_size, status} for the collection."""
        self._check_circuit()
        try:
            client = await self._get_client()
            info = await client.get_collection(collection_name)
            self._record_success()
            vector_size: int | None = None
            vectors = info.config.params.vectors
            if isinstance(vectors, dict) and "dense" in vectors:
                vector_size = vectors["dense"].size
            return {
                "name": collection_name,
                "points_count": info.points_count,
                "vector_size": vector_size,
                "status": str(info.status),
            }
        except Exception:
            self._record_failure()
            raise

    # ------------------------------------------------------------------
    # Payload validation
    # ------------------------------------------------------------------

    def _validate_payload(self, payload: dict) -> None:
        """Validate all 11 required FR-011 payload fields."""
        missing = [f for f in self.REQUIRED_PAYLOAD_FIELDS if f not in payload]
        if missing:
            raise ValueError(f"Payload missing required fields: {missing}")
        doc_type = payload.get("doc_type")
        if doc_type not in self.VALID_DOC_TYPES:
            raise ValueError(f"Invalid doc_type '{doc_type}'. Must be one of {sorted(self.VALID_DOC_TYPES)}")

    # ------------------------------------------------------------------
    # Batch upsert
    # ------------------------------------------------------------------

    async def batch_upsert(self, collection_name: str, points: list[QdrantPoint]) -> int:
        """Idempotent batch upsert. Validates all 11 payload fields. Returns count."""
        if not points:
            return 0
        for point in points:
            self._validate_payload(point.payload)
        self._check_circuit()
        try:
            count = await self._batch_upsert_with_retry(collection_name, points)
            self._record_success()
            return count
        except Exception:
            self._record_failure()
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10) + wait_random(0, 1),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def _batch_upsert_with_retry(self, collection_name: str, points: list[QdrantPoint]) -> int:
        from qdrant_client.models import PointStruct
        from qdrant_client.models import SparseVector as QdrantSparseVec

        qdrant_points = []
        for point in points:
            vectors: dict = {"dense": point.vector}
            if point.sparse_vector is not None:
                vectors["sparse"] = QdrantSparseVec(
                    indices=point.sparse_vector.indices,
                    values=point.sparse_vector.values,
                )
            qdrant_points.append(PointStruct(id=point.id, vector=vectors, payload=point.payload))
        client = await self._get_client()
        await client.upsert(collection_name=collection_name, points=qdrant_points)
        return len(points)

    # ------------------------------------------------------------------
    # Hybrid search
    # ------------------------------------------------------------------

    async def search_hybrid(
        self,
        collection_name: str,
        dense_vector: list[float],
        sparse_vector: SparseVector | None,
        top_k: int = 10,
        dense_weight: float = 0.6,
        sparse_weight: float = 0.4,
        score_threshold: float | None = None,
    ) -> list[SearchResult]:
        """Weighted rank fusion of dense cosine + sparse BM25 search results."""
        self._check_circuit()
        try:
            results = await self._search_hybrid_with_retry(
                collection_name,
                dense_vector,
                sparse_vector,
                top_k,
                dense_weight,
                sparse_weight,
                score_threshold,
            )
            self._record_success()
            return results
        except Exception:
            self._record_failure()
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10) + wait_random(0, 1),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def _search_hybrid_with_retry(
        self,
        collection_name: str,
        dense_vector: list[float],
        sparse_vector: SparseVector | None,
        top_k: int,
        dense_weight: float,
        sparse_weight: float,
        score_threshold: float | None,
    ) -> list[SearchResult]:
        # qdrant-client >= 1.12 replaced client.search() with client.query_points()
        from qdrant_client.models import SparseVector as QdrantSparseVec

        client = await self._get_client()
        fetch_limit = top_k * 3

        # Dense search (named vector "dense") via query_points API
        dense_response = await client.query_points(
            collection_name=collection_name,
            query=dense_vector,
            using="dense",
            limit=fetch_limit,
            with_payload=True,
        )
        dense_hits = dense_response.points

        dense_scores: dict[str, float] = {str(hit.id): hit.score for hit in dense_hits}
        sparse_scores: dict[str, float] = {}
        payload_map: dict[str, dict] = {str(hit.id): (hit.payload or {}) for hit in dense_hits}

        # Sparse search (named vector "sparse"), only if sparse vector provided
        if sparse_vector is not None:
            sparse_response = await client.query_points(
                collection_name=collection_name,
                query=QdrantSparseVec(
                    indices=sparse_vector.indices,
                    values=sparse_vector.values,
                ),
                using="sparse",
                limit=fetch_limit,
                with_payload=True,
            )
            for hit in sparse_response.points:
                key = str(hit.id)
                sparse_scores[key] = hit.score
                if key not in payload_map:
                    payload_map[key] = hit.payload or {}

        # Weighted rank fusion over union of result sets
        all_ids = set(dense_scores) | set(sparse_scores)
        fused: list[SearchResult] = []
        for sid in all_ids:
            hybrid_score = dense_weight * dense_scores.get(sid, 0.0) + sparse_weight * sparse_scores.get(sid, 0.0)
            if score_threshold is not None and hybrid_score < score_threshold:
                continue
            try:
                orig_id: int | str = int(sid)
            except ValueError, TypeError:
                orig_id = sid
            fused.append(
                SearchResult(
                    id=orig_id,
                    score=hybrid_score,
                    payload=payload_map.get(sid, {}),
                )
            )

        fused.sort(key=lambda r: r.score, reverse=True)
        return fused[:top_k]

    # ------------------------------------------------------------------
    # Point deletion
    # ------------------------------------------------------------------

    async def delete_points(self, collection_name: str, point_ids: list[int]) -> int:
        """Delete points by ID list. Returns count of submitted IDs."""
        if not point_ids:
            return 0
        self._check_circuit()
        try:
            from qdrant_client.models import PointIdsList

            client = await self._get_client()
            await client.delete(
                collection_name=collection_name,
                points_selector=PointIdsList(points=point_ids),
            )
            self._record_success()
            return len(point_ids)
        except Exception:
            self._record_failure()
            raise

    async def delete_points_by_filter(self, collection_name: str, filter: dict) -> int:
        """Delete points matching payload filter dict. Returns 0 (count unknown)."""
        self._check_circuit()
        try:
            from qdrant_client.models import FilterSelector

            client = await self._get_client()
            qdrant_filter = self._build_filter(filter)
            await client.delete(
                collection_name=collection_name,
                points_selector=FilterSelector(filter=qdrant_filter),
            )
            self._record_success()
            return 0  # Qdrant delete does not return a count
        except Exception:
            self._record_failure()
            raise

    def _build_filter(self, filter_dict: dict):  # type: ignore[return]
        """Convert a simple key→value dict into a Qdrant Filter."""
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        conditions = [FieldCondition(key=k, match=MatchValue(value=v)) for k, v in filter_dict.items()]
        return Filter(must=conditions)

    # ------------------------------------------------------------------
    # Point retrieval
    # ------------------------------------------------------------------

    async def get_point(self, collection_name: str, point_id: int) -> dict | None:
        """Return {id, vector, payload} for a single point, or None if not found."""
        self._check_circuit()
        try:
            client = await self._get_client()
            results = await client.retrieve(
                collection_name=collection_name,
                ids=[point_id],
                with_payload=True,
                with_vectors=True,
            )
            self._record_success()
            if not results:
                return None
            point = results[0]
            return {"id": point.id, "vector": point.vector, "payload": point.payload or {}}
        except Exception:
            self._record_failure()
            raise

    async def get_points_by_ids(self, collection_name: str, point_ids: list[int]) -> list[dict]:
        """Batch retrieval of points by ID list."""
        if not point_ids:
            return []
        self._check_circuit()
        try:
            client = await self._get_client()
            results = await client.retrieve(
                collection_name=collection_name,
                ids=point_ids,
                with_payload=True,
                with_vectors=True,
            )
            self._record_success()
            return [{"id": p.id, "vector": p.vector, "payload": p.payload or {}} for p in results]
        except Exception:
            self._record_failure()
            raise

    async def scroll_points(
        self,
        collection_name: str,
        limit: int = 100,
        offset: int | None = None,
    ) -> tuple[list[dict], int | None]:
        """Cursor-based iteration through a collection. Returns (points, next_offset)."""
        self._check_circuit()
        try:
            client = await self._get_client()
            points, next_offset = await client.scroll(
                collection_name=collection_name,
                limit=limit,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            self._record_success()
            return (
                [{"id": p.id, "payload": p.payload or {}} for p in points],
                next_offset,
            )
        except Exception:
            self._record_failure()
            raise
