"""Unit tests for spec-28 BUG-014 fix: VACUUM after prune + startup integrity check."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from backend.main import _check_checkpoint_integrity, _prune_old_checkpoint_threads


def _seed_checkpoints(conn, num_threads: int, blob_size: int = 8192):
    """Insert num_threads rows directly into the checkpoints table.

    Each checkpoint carries an 8 KB BLOB by default so deletes leave
    measurable pages on the freelist (with auto_vacuum=NONE the freelist
    is not auto-reclaimed — that's exactly the BUG-014 condition).
    """
    payload = b"x" * blob_size
    for i in range(num_threads):
        thread_id = f"thread-{i:04d}"
        # checkpoint_id is lex-sortable per spec-26 DISK-001 (UUIDv6 or simulated here)
        checkpoint_id = f"chk-{i:04d}"
        return_coro = conn.execute(
            "INSERT INTO checkpoints (thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, type, checkpoint, metadata) "
            "VALUES (?, '', ?, NULL, 'msgpack', ?, ?)",
            (thread_id, checkpoint_id, payload, b"{}"),
        )
        yield return_coro


# ---------------------------------------------------------------------------
# _check_checkpoint_integrity
# ---------------------------------------------------------------------------


async def test_check_checkpoint_integrity_clean_db_logs_ok():
    logger = MagicMock()
    async with AsyncSqliteSaver.from_conn_string(":memory:") as cp:
        await cp.setup()
        result = await _check_checkpoint_integrity(cp, logger)

    assert result is True
    logger.info.assert_called_once()
    assert logger.info.call_args.args[0] == "storage_checkpoint_integrity_ok"
    logger.warning.assert_not_called()


async def test_check_checkpoint_integrity_corrupt_logs_warning_with_runbook():
    logger = MagicMock()

    fake_cursor = MagicMock()
    fake_cursor.fetchall = AsyncMock(
        return_value=[
            ("Freelist: 2nd reference to page 8976",),
            ("Tree 4 page 88876 cell 302: 2nd reference to page 74516",),
        ]
    )
    fake_cursor.__aenter__ = AsyncMock(return_value=fake_cursor)
    fake_cursor.__aexit__ = AsyncMock(return_value=None)

    fake_conn = MagicMock()
    fake_conn.execute = MagicMock(return_value=fake_cursor)
    fake_checkpointer = MagicMock(conn=fake_conn)

    result = await _check_checkpoint_integrity(fake_checkpointer, logger)

    assert result is False
    logger.info.assert_not_called()
    logger.warning.assert_called_once()
    event, kwargs = logger.warning.call_args.args[0], logger.warning.call_args.kwargs
    assert event == "storage_checkpoint_integrity_failed"
    assert kwargs["total_issues"] == 2
    assert kwargs["first_issue"] == "Freelist: 2nd reference to page 8976"
    assert "BUG-013" in kwargs["recovery_runbook"]


async def test_check_checkpoint_integrity_pragma_raises_logs_warning():
    logger = MagicMock()

    fake_conn = MagicMock()
    fake_conn.execute = MagicMock(side_effect=RuntimeError("disk I/O error"))
    fake_checkpointer = MagicMock(conn=fake_conn)

    result = await _check_checkpoint_integrity(fake_checkpointer, logger)

    assert result is False
    logger.warning.assert_called_once()
    event = logger.warning.call_args.args[0]
    assert event == "storage_checkpoint_integrity_check_failed"


# ---------------------------------------------------------------------------
# _prune_old_checkpoint_threads
# ---------------------------------------------------------------------------


async def test_prune_disabled_when_max_threads_is_zero():
    logger = MagicMock()
    async with AsyncSqliteSaver.from_conn_string(":memory:") as cp:
        await cp.setup()
        for coro in _seed_checkpoints(cp.conn, num_threads=5):
            await coro
        await cp.conn.commit()

        pruned = await _prune_old_checkpoint_threads(cp, max_threads=0, logger=logger)

    assert pruned == 0
    logger.info.assert_not_called()  # no vacuum log either


async def test_prune_skipped_when_thread_count_under_limit():
    logger = MagicMock()
    async with AsyncSqliteSaver.from_conn_string(":memory:") as cp:
        await cp.setup()
        for coro in _seed_checkpoints(cp.conn, num_threads=3):
            await coro
        await cp.conn.commit()

        pruned = await _prune_old_checkpoint_threads(cp, max_threads=5, logger=logger)

    assert pruned == 0
    # No "storage_checkpoint_vacuumed" log because pruned == 0
    info_events = [c.args[0] for c in logger.info.call_args_list]
    assert "storage_checkpoint_vacuumed" not in info_events


async def test_prune_vacuums_freelist_after_deleting_threads():
    """The core BUG-014 layer 1 contract: freelist gets reclaimed."""
    logger = MagicMock()
    async with AsyncSqliteSaver.from_conn_string(":memory:") as cp:
        await cp.setup()
        # Seed 10 threads with 8 KB BLOBs each. Pages will be allocated.
        for coro in _seed_checkpoints(cp.conn, num_threads=10):
            await coro
        await cp.conn.commit()

        # Sanity: there's real data in the file before prune.
        async with cp.conn.execute("SELECT COUNT(DISTINCT thread_id) FROM checkpoints") as cur:
            (count_before,) = await cur.fetchone()
        assert count_before == 10

        pruned = await _prune_old_checkpoint_threads(cp, max_threads=3, logger=logger)

        # 7 threads deleted, 3 kept (most recent by checkpoint_id lex-sort)
        assert pruned == 7

        async with cp.conn.execute("SELECT COUNT(DISTINCT thread_id) FROM checkpoints") as cur:
            (count_after,) = await cur.fetchone()
        assert count_after == 3

        # Layer 1 contract: VACUUM ran, freelist is empty.
        async with cp.conn.execute("PRAGMA freelist_count") as cur:
            (freelist_count,) = await cur.fetchone()
        assert freelist_count == 0, (
            f"Expected freelist_count=0 after VACUUM, got {freelist_count}. "
            "BUG-014 layer 1 contract violated: pages still on the freelist."
        )

    info_events = [c.args[0] for c in logger.info.call_args_list]
    assert "storage_checkpoint_vacuumed" in info_events


async def test_prune_continues_after_individual_thread_delete_failure():
    """One thread's adelete_thread() raising must not abort the loop."""
    logger = MagicMock()

    async with AsyncSqliteSaver.from_conn_string(":memory:") as cp:
        await cp.setup()
        for coro in _seed_checkpoints(cp.conn, num_threads=5):
            await coro
        await cp.conn.commit()

        original_adelete = cp.adelete_thread
        call_count = {"n": 0}

        async def flaky_adelete(thread_id):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("simulated failure on first delete")
            await original_adelete(thread_id)

        cp.adelete_thread = flaky_adelete  # type: ignore[method-assign]

        pruned = await _prune_old_checkpoint_threads(cp, max_threads=2, logger=logger)

    # 3 should be pruned (5 - 2); 1 failed; net pruned count = 2
    assert pruned == 2
    # Failure was logged
    warn_events = [c.args[0] for c in logger.warning.call_args_list]
    assert "storage_checkpoint_prune_failed" in warn_events
