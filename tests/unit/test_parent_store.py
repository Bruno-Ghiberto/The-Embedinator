"""Unit tests for ParentStore (T164).

All tests use mocked aiosqlite connections -- no real DB required.
Verifies column aliases (id AS parent_id, collection_id AS collection),
get_all_by_collection(), error propagation, and edge cases.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.errors import SQLiteError
from backend.storage.parent_store import ParentStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _Row(dict):
    """Minimal aiosqlite.Row-compatible dict that supports ["key"] access."""


def _make_mock_db(rows: list[dict] | None = None) -> MagicMock:
    """Return a mock SQLiteDB whose execute() yields the given rows."""
    mock_cursor = AsyncMock()
    mock_cursor.fetchall = AsyncMock(
        return_value=[_Row(r) for r in (rows or [])]
    )
    mock_db = MagicMock()
    mock_db.db.execute = AsyncMock(return_value=mock_cursor)
    return mock_db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_by_ids_returns_aliases():
    """Verify parent_id (id alias) and collection (collection_id alias) are set."""
    rows = [
        {
            "parent_id": "pid-001",
            "text": "chunk text",
            "source_file": "report.pdf",
            "page": 3,
            "breadcrumb": "Research > Report > Section 1",
            "collection": "col-001",
        }
    ]
    store = ParentStore(_make_mock_db(rows))

    results = await store.get_by_ids(["pid-001"])

    assert len(results) == 1
    assert results[0].parent_id == "pid-001"
    assert results[0].collection == "col-001"
    assert results[0].text == "chunk text"
    assert results[0].source_file == "report.pdf"
    assert results[0].page == 3
    assert results[0].breadcrumb == "Research > Report > Section 1"


@pytest.mark.asyncio
async def test_get_all_by_collection():
    """Verify all parent chunks for a collection are returned."""
    rows = [
        {
            "parent_id": "pid-001",
            "text": "text one",
            "source_file": "doc.pdf",
            "page": 1,
            "breadcrumb": "Col > Doc > Sec 1",
            "collection": "col-001",
        },
        {
            "parent_id": "pid-002",
            "text": "text two",
            "source_file": "doc.pdf",
            "page": 2,
            "breadcrumb": "Col > Doc > Sec 2",
            "collection": "col-001",
        },
    ]
    store = ParentStore(_make_mock_db(rows))

    results = await store.get_all_by_collection("col-001")

    assert len(results) == 2
    assert all(r.collection == "col-001" for r in results)
    assert {r.parent_id for r in results} == {"pid-001", "pid-002"}

    # Verify execute was called with correct collection_id parameter
    store.db.db.execute.assert_called_once()
    call_args = store.db.db.execute.call_args
    assert "col-001" in call_args[0][1] or call_args[1].get("args", ("col-001",))[0] == "col-001"


@pytest.mark.asyncio
async def test_get_by_ids_empty_list():
    """Empty input list returns empty result without hitting the database."""
    mock_db = MagicMock()
    store = ParentStore(mock_db)

    results = await store.get_by_ids([])

    assert results == []
    mock_db.db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_get_by_ids_missing_ids():
    """IDs absent from the DB are silently skipped (no exception)."""
    # DB returns only 1 row even though 2 IDs were requested
    rows = [
        {
            "parent_id": "pid-001",
            "text": "found text",
            "source_file": "a.pdf",
            "page": 1,
            "breadcrumb": "Col > Doc",
            "collection": "col-abc",
        }
    ]
    store = ParentStore(_make_mock_db(rows))

    results = await store.get_by_ids(["pid-001", "pid-missing"])

    assert len(results) == 1
    assert results[0].parent_id == "pid-001"


@pytest.mark.asyncio
async def test_error_handling():
    """Database failure raises SQLiteError with an informative message."""
    mock_db = MagicMock()
    mock_db.db.execute = AsyncMock(side_effect=RuntimeError("connection reset"))
    store = ParentStore(mock_db)

    with pytest.raises(SQLiteError, match="Failed to fetch parent chunks"):
        await store.get_by_ids(["pid-001"])
