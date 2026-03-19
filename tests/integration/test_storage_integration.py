"""Integration tests for Spec-07 Storage Architecture — cross-store consistency.

Tests cover:
  US1: Parent-child linking (SQLite ↔ Qdrant)
  US2: Search retrieval workflow
  US3: Query trace recording
  US4: Provider encryption

Requires:
  - Qdrant running: docker compose up qdrant -d
  - EMBEDINATOR_FERNET_KEY env var for encryption tests
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet

from backend.providers.key_manager import KeyManager
from backend.storage.qdrant_client import QdrantPoint, QdrantStorage
from backend.storage.sqlite_db import SQLiteDB
from tests.integration.conftest import unique_name


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def unique_collection_name() -> str:
    """Generate unique collection name to avoid 409 conflicts on re-runs."""
    return f"test_{uuid.uuid4().hex[:8]}"


def _make_point(
    point_id: int,
    parent_id: str,
    collection_name: str,
    dims: int = 4,
) -> QdrantPoint:
    """Build a minimal-valid QdrantPoint for testing."""
    return QdrantPoint(
        id=point_id,
        vector=[0.1] * dims,
        sparse_vector=None,
        payload={
            "text": f"child chunk for parent {parent_id}",
            "parent_id": parent_id,
            "breadcrumb": "Test > Document > Section",
            "source_file": "test.pdf",
            "page": 1,
            "chunk_index": 0,
            "doc_type": "Prose",
            "chunk_hash": uuid.uuid4().hex,
            "embedding_model": "all-MiniLM-L6-v2",
            "collection_name": collection_name,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        },
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db(tmp_path):
    """File-based SQLiteDB (WAL mode requires a real file)."""
    async with SQLiteDB(str(tmp_path / "test.db")) as database:
        yield database


@pytest_asyncio.fixture
async def qdrant():
    """QdrantStorage pointed at local Qdrant."""
    return QdrantStorage("localhost", 6333)


@pytest.fixture
def fernet_key() -> str:
    """A valid Fernet key for encryption tests."""
    return Fernet.generate_key().decode()


# ---------------------------------------------------------------------------
# US1: Parent-child linking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parent_chunk_to_qdrant_linking(db, qdrant):
    """Create parent in SQLite, child vector in Qdrant; verify cross-store resolve."""
    coll_name = unique_collection_name()
    coll_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    parent_id = str(uuid.uuid4())

    # Setup SQLite side
    await db.create_collection(
        id=coll_id,
        name=unique_name("coll"),
        embedding_model="all-MiniLM-L6-v2",
        chunk_profile="default",
        qdrant_collection_name=coll_name,
    )
    await db.create_document(
        id=doc_id, collection_id=coll_id, filename="doc.pdf", file_hash="abc123"
    )
    await db.create_parent_chunk(
        id=parent_id,
        collection_id=coll_id,
        document_id=doc_id,
        text="Parent chunk content for linking test.",
    )

    # Setup Qdrant side
    await qdrant.create_collection(coll_name, vector_size=4)
    try:
        point = _make_point(1, parent_id, coll_name)
        await qdrant.batch_upsert(coll_name, [point])

        # Search and resolve
        results = await qdrant.search_hybrid(
            collection_name=coll_name,
            dense_vector=[0.1] * 4,
            sparse_vector=None,
            top_k=1,
        )

        assert len(results) == 1
        resolved_parent_id = results[0].payload["parent_id"]
        assert resolved_parent_id == parent_id

        # Verify resolves back to SQLite
        parents = await db.get_parent_chunks_batch([resolved_parent_id])
        assert len(parents) == 1
        assert parents[0]["id"] == parent_id
        assert parents[0]["text"] == "Parent chunk content for linking test."
    finally:
        await qdrant.delete_collection(coll_name)


@pytest.mark.asyncio
async def test_duplicate_document_detection(db):
    """Re-ingesting same file_hash in same collection is detected as duplicate."""
    coll_id = str(uuid.uuid4())
    doc_id_1 = str(uuid.uuid4())
    doc_id_2 = str(uuid.uuid4())
    file_hash = "sha256_deadbeef"

    await db.create_collection(
        id=coll_id,
        name=unique_name("dup"),
        embedding_model="all-MiniLM-L6-v2",
        chunk_profile="default",
        qdrant_collection_name=unique_collection_name(),
    )
    await db.create_document(
        id=doc_id_1, collection_id=coll_id, filename="file.pdf", file_hash=file_hash
    )

    # Detect duplicate via get_document_by_hash
    existing = await db.get_document_by_hash(coll_id, file_hash)
    assert existing is not None
    assert existing["id"] == doc_id_1

    # Mark as duplicate instead of re-creating
    await db.update_document(doc_id_1, status="duplicate")
    doc = await db.get_document(doc_id_1)
    assert doc["status"] == "duplicate"


@pytest.mark.asyncio
async def test_batch_parent_retrieval_performance(db):
    """Batch retrieval of 100 parent chunks must complete in <10ms."""
    coll_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())

    await db.create_collection(
        id=coll_id,
        name=unique_name("perf"),
        embedding_model="all-MiniLM-L6-v2",
        chunk_profile="default",
        qdrant_collection_name=unique_collection_name(),
    )
    await db.create_document(
        id=doc_id, collection_id=coll_id, filename="big.pdf", file_hash="hash_perf"
    )

    # Insert 100 parent chunks
    parent_ids = []
    for i in range(100):
        pid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"perf-chunk-{i}"))
        await db.create_parent_chunk(
            id=pid, collection_id=coll_id, document_id=doc_id,
            text=f"Parent chunk {i} content.",
        )
        parent_ids.append(pid)

    # Measure batch retrieval
    start = time.monotonic()
    chunks = await db.get_parent_chunks_batch(parent_ids)
    elapsed_ms = (time.monotonic() - start) * 1000

    assert len(chunks) == 100
    assert elapsed_ms < 10, f"Batch retrieval took {elapsed_ms:.1f}ms (target <10ms)"


# ---------------------------------------------------------------------------
# US2: Search retrieval workflow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_returns_parent_id(qdrant):
    """Qdrant search result payload includes parent_id."""
    coll_name = unique_collection_name()
    parent_id = str(uuid.uuid4())

    await qdrant.create_collection(coll_name, vector_size=4)
    try:
        await qdrant.batch_upsert(coll_name, [_make_point(1, parent_id, coll_name)])

        results = await qdrant.search_hybrid(
            collection_name=coll_name,
            dense_vector=[0.1] * 4,
            sparse_vector=None,
            top_k=1,
        )

        assert len(results) >= 1
        assert "parent_id" in results[0].payload
        assert results[0].payload["parent_id"] == parent_id
    finally:
        await qdrant.delete_collection(coll_name)


@pytest.mark.asyncio
async def test_search_parent_retrieval_workflow(db, qdrant):
    """Full workflow: search Qdrant → get parent_id → resolve in SQLite."""
    coll_name = unique_collection_name()
    coll_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    parent_id = str(uuid.uuid4())

    await db.create_collection(
        id=coll_id, name=unique_name("srw"),
        embedding_model="all-MiniLM-L6-v2", chunk_profile="default",
        qdrant_collection_name=coll_name,
    )
    await db.create_document(
        id=doc_id, collection_id=coll_id, filename="srw.pdf", file_hash="srw_hash"
    )
    await db.create_parent_chunk(
        id=parent_id, collection_id=coll_id, document_id=doc_id,
        text="Search-workflow parent chunk.",
    )

    await qdrant.create_collection(coll_name, vector_size=4)
    try:
        await qdrant.batch_upsert(coll_name, [_make_point(1, parent_id, coll_name)])

        results = await qdrant.search_hybrid(
            collection_name=coll_name,
            dense_vector=[0.1] * 4,
            sparse_vector=None,
            top_k=5,
        )

        # Extract parent IDs and resolve
        retrieved_parent_ids = [r.payload["parent_id"] for r in results]
        parents = await db.get_parent_chunks_batch(retrieved_parent_ids)

        assert len(parents) >= 1
        assert parents[0]["id"] == parent_id
        assert parents[0]["text"] == "Search-workflow parent chunk."
    finally:
        await qdrant.delete_collection(coll_name)


@pytest.mark.asyncio
async def test_collection_isolation(qdrant):
    """Vectors in collection A are not returned when searching collection B."""
    coll_a = unique_collection_name()
    coll_b = unique_collection_name()
    parent_a = str(uuid.uuid4())
    parent_b = str(uuid.uuid4())

    await qdrant.create_collection(coll_a, vector_size=4)
    await qdrant.create_collection(coll_b, vector_size=4)
    try:
        # Upsert distinct vectors in each collection
        await qdrant.batch_upsert(coll_a, [_make_point(1, parent_a, coll_a)])
        await qdrant.batch_upsert(coll_b, [_make_point(2, parent_b, coll_b)])

        results_a = await qdrant.search_hybrid(
            collection_name=coll_a, dense_vector=[0.1] * 4, sparse_vector=None
        )
        results_b = await qdrant.search_hybrid(
            collection_name=coll_b, dense_vector=[0.1] * 4, sparse_vector=None
        )

        ids_a = {r.payload["parent_id"] for r in results_a}
        ids_b = {r.payload["parent_id"] for r in results_b}

        assert parent_a in ids_a
        assert parent_b in ids_b
        assert parent_b not in ids_a, "Collection B parent leaked into Collection A results"
        assert parent_a not in ids_b, "Collection A parent leaked into Collection B results"
    finally:
        for coll in (coll_a, coll_b):
            try:
                await qdrant.delete_collection(coll)
            except Exception:
                pass


@pytest.mark.asyncio
async def test_parent_id_mismatch_detection(db, qdrant):
    """Orphaned Qdrant vector (parent not in SQLite) is detectable."""
    coll_name = unique_collection_name()
    orphan_parent_id = str(uuid.uuid4())  # Never inserted into SQLite

    await qdrant.create_collection(coll_name, vector_size=4)
    try:
        await qdrant.batch_upsert(
            coll_name, [_make_point(1, orphan_parent_id, coll_name)]
        )

        results = await qdrant.search_hybrid(
            collection_name=coll_name, dense_vector=[0.1] * 4, sparse_vector=None
        )
        assert len(results) >= 1

        # Attempt to resolve in SQLite — should come back empty (orphaned)
        parent_id_from_qdrant = results[0].payload["parent_id"]
        parents = await db.get_parent_chunks_batch([parent_id_from_qdrant])
        assert parents == [], "Orphaned parent_id should not resolve in SQLite"
    finally:
        await qdrant.delete_collection(coll_name)


# ---------------------------------------------------------------------------
# US3: Query trace recording
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_query_trace_full_flow(db):
    """Query trace includes reasoning_steps_json, strategy_switches_json, confidence_score (int)."""
    trace_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    reasoning = json.dumps(["step1: retrieved 5 chunks", "step2: reranked"])
    switches = json.dumps([{"from": "WIDEN", "to": "CHANGE_COLLECTION"}])

    await db.create_query_trace(
        id=trace_id,
        session_id=session_id,
        query="What is the authentication flow?",
        collections_searched=json.dumps(["col-001"]),
        chunks_retrieved_json=json.dumps([{"chunk_id": "c1", "score": 0.9}]),
        latency_ms=145,
        llm_model="qwen2.5:7b",
        embed_model="nomic-embed-text",
        confidence_score=82,
        sub_questions_json=json.dumps(["What is auth?", "Which service?"]),
        reasoning_steps_json=reasoning,
        strategy_switches_json=switches,
        meta_reasoning_triggered=True,
    )

    traces = await db.list_query_traces(session_id)
    assert len(traces) == 1
    t = traces[0]
    assert t["id"] == trace_id
    assert t["confidence_score"] == 82
    assert isinstance(t["confidence_score"], int)
    assert t["reasoning_steps_json"] == reasoning
    assert t["strategy_switches_json"] == switches
    assert t["meta_reasoning_triggered"] == 1  # stored as int


@pytest.mark.asyncio
async def test_query_trace_latency_accuracy(db):
    """latency_ms stored and retrieved accurately."""
    session_id = str(uuid.uuid4())
    await db.create_query_trace(
        id=str(uuid.uuid4()), session_id=session_id, query="latency test",
        collections_searched="[]", chunks_retrieved_json="[]", latency_ms=237,
    )
    traces = await db.list_query_traces(session_id)
    assert traces[0]["latency_ms"] == 237


@pytest.mark.asyncio
async def test_trace_json_field_validation(db):
    """JSON fields stored as strings are parseable after retrieval."""
    session_id = str(uuid.uuid4())
    chunks = [{"chunk_id": "c1", "score": 0.85}]
    sub_qs = ["sub-q1", "sub-q2"]

    await db.create_query_trace(
        id=str(uuid.uuid4()), session_id=session_id, query="json validation",
        collections_searched=json.dumps(["col-a"]),
        chunks_retrieved_json=json.dumps(chunks),
        latency_ms=55,
        sub_questions_json=json.dumps(sub_qs),
    )

    traces = await db.list_query_traces(session_id)
    t = traces[0]
    assert json.loads(t["collections_searched"]) == ["col-a"]
    assert json.loads(t["chunks_retrieved_json"]) == chunks
    assert json.loads(t["sub_questions_json"]) == sub_qs


@pytest.mark.asyncio
async def test_list_traces_by_session(db):
    """Traces are filtered by session_id and returned in DESC order."""
    session_a = str(uuid.uuid4())
    session_b = str(uuid.uuid4())

    for i in range(3):
        await db.create_query_trace(
            id=str(uuid.uuid4()), session_id=session_a, query=f"query {i}",
            collections_searched="[]", chunks_retrieved_json="[]",
            latency_ms=10 + i,
        )

    # Session B gets 1 trace
    await db.create_query_trace(
        id=str(uuid.uuid4()), session_id=session_b, query="other session",
        collections_searched="[]", chunks_retrieved_json="[]", latency_ms=99,
    )

    traces_a = await db.list_query_traces(session_a)
    traces_b = await db.list_query_traces(session_b)

    assert len(traces_a) == 3
    assert len(traces_b) == 1
    # DESC ordering: latest first (last inserted = query 2)
    assert traces_a[0]["query"] == "query 2"


# ---------------------------------------------------------------------------
# US4: Provider encryption
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_provider_with_encrypted_key(db, fernet_key):
    """Encrypt an API key, store in SQLite, retrieve and decrypt — verifies round-trip."""
    with patch.dict(os.environ, {"EMBEDINATOR_FERNET_KEY": fernet_key}):
        km = KeyManager()
        plaintext = "sk-test-api-key-12345"
        encrypted = km.encrypt(plaintext)

        await db.create_provider(
            name="openai-test",
            api_key_encrypted=encrypted,
            base_url="https://api.openai.com",
            is_active=True,
        )

        provider = await db.get_provider("openai-test")
        assert provider is not None
        assert provider["api_key_encrypted"] == encrypted

        decrypted = km.decrypt(provider["api_key_encrypted"])
        assert decrypted == plaintext
        assert provider["api_key_encrypted"] != plaintext


@pytest.mark.asyncio
async def test_provider_update_changes_key(db, fernet_key):
    """Updating a provider re-encrypts with a new ciphertext."""
    with patch.dict(os.environ, {"EMBEDINATOR_FERNET_KEY": fernet_key}):
        km = KeyManager()
        key_v1 = "sk-old-key"
        key_v2 = "sk-new-key"

        await db.create_provider(
            name="anthropic-test", api_key_encrypted=km.encrypt(key_v1)
        )

        encrypted_v2 = km.encrypt(key_v2)
        await db.update_provider("anthropic-test", api_key_encrypted=encrypted_v2)

        provider = await db.get_provider("anthropic-test")
        assert km.decrypt(provider["api_key_encrypted"]) == key_v2


@pytest.mark.asyncio
async def test_provider_key_isolation(db, fernet_key):
    """Multiple providers decrypt to their own distinct keys independently."""
    with patch.dict(os.environ, {"EMBEDINATOR_FERNET_KEY": fernet_key}):
        km = KeyManager()
        keys = {"prov-a": "sk-key-aaa", "prov-b": "sk-key-bbb", "prov-c": "sk-key-ccc"}

        for name, plaintext in keys.items():
            await db.create_provider(name=name, api_key_encrypted=km.encrypt(plaintext))

        for name, expected_plaintext in keys.items():
            provider = await db.get_provider(name)
            assert km.decrypt(provider["api_key_encrypted"]) == expected_plaintext


@pytest.mark.asyncio
async def test_plaintext_never_logged(db, fernet_key):
    """Plaintext API key must not appear in any log output during create_provider."""
    with patch.dict(os.environ, {"EMBEDINATOR_FERNET_KEY": fernet_key}):
        km = KeyManager()
        plaintext = "sk-super-secret-key-xyz"
        encrypted = km.encrypt(plaintext)

        logged_calls: list[str] = []

        def capturing_log(*args, **kwargs):
            logged_calls.append(str(args) + str(kwargs))

        with patch("structlog.get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_logger.info.side_effect = capturing_log
            mock_logger.warning.side_effect = capturing_log
            mock_logger.error.side_effect = capturing_log
            mock_get_logger.return_value = mock_logger

            await db.create_provider(name="secret-test", api_key_encrypted=encrypted)

        # Verify plaintext never appears in any captured log call
        for call_str in logged_calls:
            assert plaintext not in call_str, (
                f"Plaintext API key found in log output: {call_str}"
            )


# ---------------------------------------------------------------------------
# Error recovery
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_document_delete_cascades(db):
    """Deleting a document cascades to its ingestion jobs and parent chunks."""
    coll_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    parent_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "cascade-test"))

    await db.create_collection(
        id=coll_id, name=unique_name("cascade"),
        embedding_model="all-MiniLM-L6-v2", chunk_profile="default",
        qdrant_collection_name=unique_collection_name(),
    )
    await db.create_document(
        id=doc_id, collection_id=coll_id, filename="cascade.pdf", file_hash="cascade_hash"
    )
    await db.create_ingestion_job(id=job_id, document_id=doc_id)
    await db.create_parent_chunk(
        id=parent_id, collection_id=coll_id, document_id=doc_id, text="chunk"
    )

    await db.delete_document(doc_id)

    assert await db.get_document(doc_id) is None
    assert await db.get_ingestion_job(job_id) is None
    chunks = await db.get_parent_chunks_batch([parent_id])
    assert chunks == []


@pytest.mark.asyncio
async def test_qdrant_unavailable_batch_fails():
    """batch_upsert raises when Qdrant is unreachable."""
    bad_qdrant = QdrantStorage(host="localhost", port=9999)
    coll_name = unique_collection_name()
    parent_id = str(uuid.uuid4())

    with pytest.raises(Exception):
        await bad_qdrant.batch_upsert(coll_name, [_make_point(1, parent_id, coll_name)])


@pytest.mark.asyncio
async def test_idempotent_retry_on_failure(db):
    """UUID5 parent chunk IDs are idempotent: second insert raises IntegrityError."""
    coll_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    # UUID5 is deterministic — same inputs always give same ID
    parent_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "idempotent-chunk"))

    await db.create_collection(
        id=coll_id, name=unique_name("idem"),
        embedding_model="all-MiniLM-L6-v2", chunk_profile="default",
        qdrant_collection_name=unique_collection_name(),
    )
    await db.create_document(
        id=doc_id, collection_id=coll_id, filename="idem.pdf", file_hash="idem_hash"
    )
    await db.create_parent_chunk(
        id=parent_id, collection_id=coll_id, document_id=doc_id, text="chunk"
    )

    # Second insert with same UUID5 should raise (duplicate primary key)
    with pytest.raises(Exception):
        await db.create_parent_chunk(
            id=parent_id, collection_id=coll_id, document_id=doc_id, text="chunk again"
        )

    # Original chunk still exists unchanged
    chunks = await db.get_parent_chunks_batch([parent_id])
    assert len(chunks) == 1
    assert chunks[0]["text"] == "chunk"


@pytest.mark.asyncio
async def test_document_status_transitions(db):
    """Document status transitions: pending → ingesting → completed."""
    coll_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())

    await db.create_collection(
        id=coll_id, name=unique_name("status"),
        embedding_model="all-MiniLM-L6-v2", chunk_profile="default",
        qdrant_collection_name=unique_collection_name(),
    )
    await db.create_document(
        id=doc_id, collection_id=coll_id, filename="transitions.pdf",
        file_hash="trans_hash", status="pending",
    )

    doc = await db.get_document(doc_id)
    assert doc["status"] == "pending"

    await db.update_document(doc_id, status="ingesting")
    doc = await db.get_document(doc_id)
    assert doc["status"] == "ingesting"

    await db.update_document(doc_id, status="completed", chunk_count=42)
    doc = await db.get_document(doc_id)
    assert doc["status"] == "completed"
    assert doc["chunk_count"] == 42


# ---------------------------------------------------------------------------
# Constraint validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_foreign_key_constraints_enforced(db):
    """Creating a document with non-existent collection_id raises IntegrityError."""
    with pytest.raises(Exception):  # sqlite3.IntegrityError
        await db.create_document(
            id=str(uuid.uuid4()),
            collection_id="non-existent-collection-id",
            filename="bad.pdf",
            file_hash="bad_hash",
        )


@pytest.mark.asyncio
async def test_unique_constraints_enforced(db):
    """Duplicate collection name raises IntegrityError."""
    shared_name = unique_name("unique")
    await db.create_collection(
        id=str(uuid.uuid4()), name=shared_name,
        embedding_model="all-MiniLM-L6-v2", chunk_profile="default",
        qdrant_collection_name=unique_collection_name(),
    )

    with pytest.raises(Exception):  # sqlite3.IntegrityError
        await db.create_collection(
            id=str(uuid.uuid4()), name=shared_name,
            embedding_model="all-MiniLM-L6-v2", chunk_profile="default",
            qdrant_collection_name=unique_collection_name(),
        )
