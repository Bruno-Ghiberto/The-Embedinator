"""Schema validation tests for Spec-07 Storage Architecture (T064-T071).

Verifies that SQLiteDB creates the correct 7 tables, indexes, WAL mode,
and FK enforcement. All tests use file-based SQLite (WAL requires a real file).
"""

from __future__ import annotations

import sqlite3
import uuid

import pytest
import pytest_asyncio

from backend.storage.sqlite_db import SQLiteDB
from tests.integration.conftest import unique_name


EXPECTED_TABLES = {
    "collections",
    "documents",
    "ingestion_jobs",
    "parent_chunks",
    "query_traces",
    "settings",
    "providers",
}

EXPECTED_INDEXES = {
    "idx_parent_chunks_collection",
    "idx_parent_chunks_document",
    "idx_traces_session",
    "idx_traces_created",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db(tmp_path):
    """File-based SQLiteDB so we can inspect WAL mode via PRAGMA."""
    db_path = str(tmp_path / "schema_test.db")
    async with SQLiteDB(db_path) as database:
        yield database, db_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_tables_exist(db):
    """Verify all 7 required tables are created by init_schema."""
    database, _ = db

    cursor = await database.db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    rows = await cursor.fetchall()
    table_names = {row["name"] for row in rows}

    missing = EXPECTED_TABLES - table_names
    assert not missing, f"Missing tables: {missing}"


@pytest.mark.asyncio
async def test_all_indexes_present(db):
    """Verify required indexes are created for query performance."""
    database, _ = db

    cursor = await database.db.execute("SELECT name FROM sqlite_master WHERE type='index'")
    rows = await cursor.fetchall()
    index_names = {row["name"] for row in rows}

    missing = EXPECTED_INDEXES - index_names
    assert not missing, f"Missing indexes: {missing}"


@pytest.mark.asyncio
async def test_fk_cascades_working(db):
    """Collection deletion cascades to documents and parent_chunks."""
    database, _ = db
    coll_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    parent_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "cascade-schema-test"))

    await database.create_collection(
        id=coll_id,
        name=unique_name("cas"),
        embedding_model="all-MiniLM-L6-v2",
        chunk_profile="default",
        qdrant_collection_name=f"qdrant_{coll_id[:8]}",
    )
    await database.create_document(id=doc_id, collection_id=coll_id, filename="test.pdf", file_hash="fk_hash")
    await database.create_parent_chunk(id=parent_id, collection_id=coll_id, document_id=doc_id, text="cascade chunk")

    # Cascade via collection deletion
    await database.delete_collection(coll_id)

    assert await database.get_collection(coll_id) is None
    assert await database.get_document(doc_id) is None
    chunks = await database.get_parent_chunks_batch([parent_id])
    assert chunks == []


@pytest.mark.asyncio
async def test_wal_mode_persisted(db):
    """PRAGMA journal_mode returns 'wal' (not 'delete' or 'memory')."""
    database, _ = db

    cursor = await database.db.execute("PRAGMA journal_mode")
    row = await cursor.fetchone()
    mode = list(dict(row).values())[0]

    assert mode == "wal", f"Expected WAL mode, got: {mode}"


@pytest.mark.asyncio
async def test_foreign_keys_enforced(db):
    """PRAGMA foreign_keys returns 1 (enforced at the connection level)."""
    database, _ = db

    cursor = await database.db.execute("PRAGMA foreign_keys")
    row = await cursor.fetchone()
    fk_enabled = list(dict(row).values())[0]

    assert fk_enabled == 1, "Foreign keys must be enforced (PRAGMA foreign_keys=ON)"
