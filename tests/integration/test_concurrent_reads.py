"""Integration tests for WAL-mode concurrent reads (Spec-07 SC-009).

Validates that SQLite WAL mode allows multiple simultaneous readers
without blocking and that writers don't starve readers.

All tests use file-based SQLite (WAL mode requires a real file).
"""
from __future__ import annotations

import asyncio
import uuid

import pytest
import pytest_asyncio

from backend.storage.sqlite_db import SQLiteDB
from tests.integration.conftest import unique_name


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def file_db(tmp_path):
    """File-based SQLiteDB with WAL mode enabled (required for concurrent tests)."""
    db_path = str(tmp_path / "concurrent_test.db")
    async with SQLiteDB(db_path) as database:
        # Seed one collection and document for reads
        coll_id = str(uuid.uuid4())
        doc_id = str(uuid.uuid4())
        await database.create_collection(
            id=coll_id,
            name=unique_name("concurrent"),
            embedding_model="all-MiniLM-L6-v2",
            chunk_profile="default",
            qdrant_collection_name=f"qdrant_{coll_id[:8]}",
        )
        await database.create_document(
            id=doc_id,
            collection_id=coll_id,
            filename="concurrent.pdf",
            file_hash="hash_concurrent",
        )
        for i in range(10):
            pid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"concurrent-chunk-{i}"))
            await database.create_parent_chunk(
                id=pid,
                collection_id=coll_id,
                document_id=doc_id,
                text=f"Concurrent chunk {i}.",
            )
        yield database, coll_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_reads_no_blocking(file_db):
    """10 async readers all complete successfully without blocking each other."""
    database, coll_id = file_db

    async def read_collection():
        docs = await database.list_documents(coll_id)
        assert len(docs) >= 1
        return len(docs)

    results = await asyncio.gather(*[read_collection() for _ in range(10)])

    assert len(results) == 10
    assert all(r >= 1 for r in results), "All readers should see at least 1 document"


@pytest.mark.asyncio
async def test_writer_during_reads(file_db, tmp_path):
    """Concurrent writer + readers: readers complete without exception."""
    database, coll_id = file_db

    read_results: list[int] = []
    write_done = asyncio.Event()

    async def reader(reader_id: int):
        docs = await database.list_documents(coll_id)
        read_results.append(len(docs))

    async def writer():
        new_doc_id = str(uuid.uuid4())
        await database.create_document(
            id=new_doc_id,
            collection_id=coll_id,
            filename="new_concurrent.pdf",
            file_hash=f"hash_{new_doc_id[:8]}",
        )
        write_done.set()

    # Launch 5 readers and 1 writer concurrently
    await asyncio.gather(
        writer(),
        *[reader(i) for i in range(5)],
    )

    # All readers completed (any count is valid; writer may or may not have committed)
    assert len(read_results) == 5
    assert write_done.is_set()


@pytest.mark.asyncio
async def test_wal_checkpoint_during_reads(file_db):
    """Reads continue successfully across WAL checkpoint boundary."""
    database, coll_id = file_db

    async def read_once():
        return await database.list_documents(coll_id)

    # First batch of reads
    before_results = await asyncio.gather(*[read_once() for _ in range(3)])

    # Trigger WAL checkpoint explicitly
    await database.db.execute("PRAGMA wal_checkpoint(PASSIVE)")

    # Second batch of reads after checkpoint — should still succeed
    after_results = await asyncio.gather(*[read_once() for _ in range(3)])

    assert all(r is not None for r in before_results)
    assert all(r is not None for r in after_results)
    # Data must be consistent after checkpoint
    assert len(before_results[0]) == len(after_results[0])
