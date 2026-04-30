"""Unit tests for spec-28 BUG-014 fix: VACUUM after prune + startup integrity check.

Extended in spec-029 to cover:
- _migrate_checkpoint_auto_vacuum (R1: auto_vacuum=INCREMENTAL startup migration)
- _prune_old_checkpoint_threads incremental_vacuum rename (R1: PRAGMA incremental_vacuum)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import pytest
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from tests.conftest import make_corrupt_sqlite_file

from backend.main import (
    RecoveryResult,
    _check_checkpoint_integrity,
    _migrate_checkpoint_auto_vacuum,
    _prune_old_checkpoint_threads,
    _recover_checkpoint_db,
)


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
    # No vacuum log because pruned == 0 (spec-029 R1: event renamed to incremental_vacuumed)
    info_events = [c.args[0] for c in logger.info.call_args_list]
    assert "storage_checkpoint_incremental_vacuumed" not in info_events


async def test_prune_uses_incremental_vacuum_after_deleting_threads(tmp_path):
    """Layer 1 + spec-029 R1 contract: freelist gets reclaimed via PRAGMA incremental_vacuum.

    Docstring update: incremental_vacuum (no arg) reclaims all freelist pages — same
    end-state as the old VACUUM (freelist_count==0) but skips rewriting non-freelist pages.
    Log event renamed: storage_checkpoint_vacuumed → storage_checkpoint_incremental_vacuumed.

    NOTE: This test uses a file-based DB (not :memory:) because PRAGMA incremental_vacuum
    only reclaims freelist pages when auto_vacuum=INCREMENTAL is active. The in-memory
    SQLite backend does not honour incremental_vacuum (auto_vacuum is always NONE in-memory).
    In production, _migrate_checkpoint_auto_vacuum sets auto_vacuum=INCREMENTAL before the
    checkpointer connects — this test replicates that pre-condition.
    """
    logger = MagicMock()
    db_path = str(tmp_path / "checkpoints.db")

    # Pre-condition: set auto_vacuum=INCREMENTAL before the checkpointer connects.
    # This mirrors what _migrate_checkpoint_auto_vacuum does in production.
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("PRAGMA auto_vacuum = 2")  # INCREMENTAL
        await conn.execute("VACUUM")  # required to persist mode on an existing file
        await conn.commit()

    async with AsyncSqliteSaver.from_conn_string(db_path) as cp:
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

        # Layer 1 contract: incremental_vacuum ran, freelist is empty.
        # This holds because auto_vacuum=INCREMENTAL tracks freed pages.
        async with cp.conn.execute("PRAGMA freelist_count") as cur:
            (freelist_count,) = await cur.fetchone()
        assert freelist_count == 0, (
            f"Expected freelist_count=0 after PRAGMA incremental_vacuum, got {freelist_count}. "
            "BUG-014 layer 1 + spec-029 R1 contract violated: pages still on the freelist."
        )

    info_events = [c.args[0] for c in logger.info.call_args_list]
    assert "storage_checkpoint_incremental_vacuumed" in info_events


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


# ---------------------------------------------------------------------------
# _migrate_checkpoint_auto_vacuum
# ---------------------------------------------------------------------------


async def test_migrate_auto_vacuum_pristine_db(tmp_path):
    """FR-031: pristine path (no file) → creates file, sets auto_vacuum=2, returns True."""
    logger = MagicMock()
    db_path = str(tmp_path / "checkpoints.db")

    result = await _migrate_checkpoint_auto_vacuum(db_path, logger)

    assert result is True
    # Verify auto_vacuum=2 (INCREMENTAL) is set on the resulting file.
    async with aiosqlite.connect(db_path) as conn:
        async with conn.execute("PRAGMA auto_vacuum") as cur:
            (mode,) = await cur.fetchone()
    assert mode == 2, f"Expected auto_vacuum=2 (INCREMENTAL), got {mode}"


async def test_migrate_auto_vacuum_existing_db_migrates_and_preserves_data(tmp_path):
    """FR-032: existing DB with auto_vacuum=0 (NONE) and rows → migrates + preserves data.

    Returns True. After call: auto_vacuum=2, rows intact.
    """
    logger = MagicMock()
    db_path = str(tmp_path / "checkpoints.db")

    # Build a DB with auto_vacuum=NONE and one row.
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("PRAGMA auto_vacuum = 0")
        await conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
        await conn.execute("INSERT INTO t VALUES (1, 'preserved')")
        await conn.commit()

    result = await _migrate_checkpoint_auto_vacuum(db_path, logger)

    assert result is True

    # auto_vacuum must be INCREMENTAL now.
    async with aiosqlite.connect(db_path) as conn:
        async with conn.execute("PRAGMA auto_vacuum") as cur:
            (mode,) = await cur.fetchone()
        async with conn.execute("SELECT val FROM t WHERE id=1") as cur:
            row = await cur.fetchone()

    assert mode == 2, f"Expected auto_vacuum=2 after migration, got {mode}"
    assert row is not None and row[0] == "preserved", "Row data must be preserved after VACUUM"

    # The migration INFO log must include elapsed_ms.
    info_events = {c.args[0]: c.kwargs for c in logger.info.call_args_list}
    assert "storage_checkpoint_auto_vacuum_migrated" in info_events
    elapsed = info_events["storage_checkpoint_auto_vacuum_migrated"].get("elapsed_ms")
    assert isinstance(elapsed, int) and elapsed >= 0, f"elapsed_ms must be a non-negative int, got {elapsed!r}"


async def test_migrate_auto_vacuum_idempotent(tmp_path):
    """FR-033: DB already at auto_vacuum=2 → returns False, no migration log emitted."""
    logger = MagicMock()
    db_path = str(tmp_path / "checkpoints.db")

    # Build a DB already configured as INCREMENTAL.
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("PRAGMA auto_vacuum = 2")
        await conn.execute("VACUUM")  # required to persist auto_vacuum change on an existing file
        await conn.commit()

    result = await _migrate_checkpoint_auto_vacuum(db_path, logger)

    assert result is False

    info_events = [c.args[0] for c in logger.info.call_args_list]
    assert "storage_checkpoint_auto_vacuum_migrated" not in info_events, (
        "No migration log should be emitted when DB is already INCREMENTAL"
    )


async def test_migrate_auto_vacuum_logs_elapsed_ms(tmp_path):
    """FR-032 logging contract: storage_checkpoint_auto_vacuum_migrated contains elapsed_ms (int)."""
    logger = MagicMock()
    db_path = str(tmp_path / "checkpoints.db")

    # DB with auto_vacuum=NONE and content (so VACUUM is triggered).
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("PRAGMA auto_vacuum = 0")
        await conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        await conn.execute("INSERT INTO t VALUES (42)")
        await conn.commit()

    await _migrate_checkpoint_auto_vacuum(db_path, logger)

    info_calls = {c.args[0]: c.kwargs for c in logger.info.call_args_list}
    assert "storage_checkpoint_auto_vacuum_migrated" in info_calls, (
        "storage_checkpoint_auto_vacuum_migrated INFO log must be emitted on migration"
    )
    elapsed = info_calls["storage_checkpoint_auto_vacuum_migrated"].get("elapsed_ms")
    assert isinstance(elapsed, int), f"elapsed_ms must be an int, got {type(elapsed).__name__}"
    assert elapsed >= 0, f"elapsed_ms must be non-negative, got {elapsed}"


# ---------------------------------------------------------------------------
# _recover_checkpoint_db
# ---------------------------------------------------------------------------


async def test_recovery_skipped_clean_db(tmp_path):
    """FR-038: clean DB passes integrity_check → SKIPPED, no files modified.

    _recover_checkpoint_db is settings-agnostic; the lifespan gates the call.
    Calling it on a healthy DB must always return SKIPPED regardless of any
    CHECKPOINT_AUTO_RECOVER flag.
    """
    import aiosqlite as _aio
    import sqlite3 as _sqlite3

    logger = MagicMock()
    db_path = tmp_path / "checkpoints.db"

    # Create a valid (non-corrupt) DB.
    conn = _sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO t VALUES (1)")
    conn.commit()
    conn.close()

    result = await _recover_checkpoint_db(str(db_path), logger)

    assert result == RecoveryResult.SKIPPED
    # DB file is untouched — no archive created.
    archive_files = list(tmp_path.glob("*.corrupt-*"))
    assert len(archive_files) == 0, f"No archive should be created for clean DB, got: {archive_files}"
    # No error log emitted.
    logger.error.assert_not_called()


async def test_recovery_skipped_path_missing(tmp_path):
    """FR: missing path (fresh install) → SKIPPED immediately, no side effects.

    The helper does NOT create the file — that is R1's job.
    """
    logger = MagicMock()
    db_path = tmp_path / "checkpoints.db"
    # Path intentionally does not exist.
    assert not db_path.exists()

    result = await _recover_checkpoint_db(str(db_path), logger)

    assert result == RecoveryResult.SKIPPED
    assert not db_path.exists(), "Helper must not create the file on missing-path path"
    logger.error.assert_not_called()

    info_events = [c.args[0] for c in logger.info.call_args_list]
    assert "storage_checkpoint_recovery_skipped_path_missing" in info_events


async def test_recovery_recovered_archives_original(tmp_path):
    """FR-041/FR-042: corrupt DB, no WAL → RECOVERED; original archived; recovered file passes integrity_check."""
    logger = MagicMock()
    corrupt_path = make_corrupt_sqlite_file(tmp_path)
    assert not (tmp_path / "checkpoints.db-wal").exists(), "with_wal=False must leave no -wal sibling"

    result = await _recover_checkpoint_db(str(corrupt_path), logger)

    assert result == RecoveryResult.RECOVERED, f"Expected RECOVERED, got {result!r}"

    # Original must be archived with .corrupt- prefix.
    archive_files = list(tmp_path.glob("checkpoints.db.corrupt-*"))
    assert len(archive_files) == 1, f"Expected exactly 1 archive, got: {archive_files}"

    # Recovered file at the original path must pass integrity_check.
    import sqlite3 as _sqlite3

    chk = _sqlite3.connect(str(corrupt_path))
    integrity = chk.execute("PRAGMA integrity_check").fetchone()
    chk.close()
    assert integrity == ("ok",), f"Recovered file must pass integrity_check, got {integrity!r}"

    # INFO log with storage_checkpoint_auto_recovered must be emitted.
    info_events = [c.args[0] for c in logger.info.call_args_list]
    assert "storage_checkpoint_auto_recovered" in info_events, (
        f"storage_checkpoint_auto_recovered INFO log not found in: {info_events}"
    )


async def test_recovery_refused_when_wal_present(tmp_path):
    """FR-040: corrupt DB + -wal sibling → REFUSED_WAL; no files modified; ERROR log emitted."""
    logger = MagicMock()
    corrupt_path = make_corrupt_sqlite_file(tmp_path, with_wal=True)
    wal_path = Path(str(corrupt_path) + "-wal")
    assert wal_path.exists(), "with_wal=True must create -wal sibling"

    result = await _recover_checkpoint_db(str(corrupt_path), logger)

    assert result == RecoveryResult.REFUSED_WAL, f"Expected REFUSED_WAL, got {result!r}"

    # No archive created — files must be untouched.
    archive_files = list(tmp_path.glob("*.corrupt-*"))
    assert len(archive_files) == 0, f"No archive should be created for REFUSED_WAL, got: {archive_files}"

    # -wal sibling must still exist (not cleaned up).
    assert wal_path.exists(), "WAL file must remain after REFUSED_WAL"

    # ERROR log with storage_checkpoint_recovery_refused_wal_present must be emitted.
    error_events = [c.args[0] for c in logger.error.call_args_list]
    assert "storage_checkpoint_recovery_refused_wal_present" in error_events, (
        f"storage_checkpoint_recovery_refused_wal_present ERROR log not found in: {error_events}"
    )


async def test_recovery_fresh_fallback_when_salvage_fails(tmp_path):
    """FR-043: corrupt DB, VACUUM INTO raises (salvage failure) → FRESH_FALLBACK.

    The FRESH_FALLBACK path is triggered when VACUUM INTO itself fails (disk full,
    permission denied, etc.) or when the salvage file also fails integrity_check.

    We test the VACUUM-INTO-raises variant using a mock at the aiosqlite.connect
    boundary. The mock is scoped to this test only and documented in the task
    (ADR-29-6 / design §7 FRESH_FALLBACK boundary decision): authentic
    double-corruption (corrupt the already-corrupt salvage) is brittle and
    version-sensitive; mocking VACUUM INTO raises is faster and more deterministic.
    """
    logger = MagicMock()
    corrupt_path = make_corrupt_sqlite_file(tmp_path)
    original_path_str = str(corrupt_path)

    # Patch aiosqlite.connect so that when it is called with the salvage path,
    # the context manager raises sqlite3.OperationalError on VACUUM INTO.
    import sqlite3 as _sqlite3

    _real_connect = aiosqlite.connect

    class _FakeSalvageConn:
        """Fake connection that raises on any execute call (simulates VACUUM INTO failure)."""

        async def execute(self, sql, *args, **kwargs):
            raise _sqlite3.OperationalError("disk I/O error: simulated VACUUM INTO failure")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    def _mock_connect(path, **kwargs):
        """Return real connection for the original corrupt path; fake for the salvage path."""
        if path.endswith(".salvage"):
            return _FakeSalvageConn()
        return _real_connect(path, **kwargs)

    with patch("aiosqlite.connect", side_effect=_mock_connect):
        result = await _recover_checkpoint_db(original_path_str, logger)

    assert result == RecoveryResult.FRESH_FALLBACK, f"Expected FRESH_FALLBACK, got {result!r}"

    # Original must be archived (archive-first guarantee, NFR-002).
    archive_files = list(tmp_path.glob("checkpoints.db.corrupt-*"))
    assert len(archive_files) == 1, f"Expected exactly 1 archive file, got: {archive_files}"

    # The original path must no longer exist (fresh empty DB will be created by R1 + setup()).
    assert not corrupt_path.exists(), "Original path must be absent after FRESH_FALLBACK so R1 can create a fresh DB"

    # ERROR log with storage_checkpoint_fresh_db_fallback must be emitted.
    error_events = [c.args[0] for c in logger.error.call_args_list]
    assert "storage_checkpoint_fresh_db_fallback" in error_events, (
        f"storage_checkpoint_fresh_db_fallback ERROR log not found in: {error_events}"
    )

    # FR-043: ERROR log must contain the literal phrase "data loss" so operators
    # can grep-alert on checkpoint resets. data_loss=True is the machine flag,
    # impact=... carries the human-readable phrase.
    fresh_call = next(c for c in logger.error.call_args_list if c.args[0] == "storage_checkpoint_fresh_db_fallback")
    assert fresh_call.kwargs.get("data_loss") is True, (
        f"FR-043: data_loss=True flag missing from FRESH_FALLBACK log kwargs: {fresh_call.kwargs}"
    )
    assert "data loss" in fresh_call.kwargs.get("impact", ""), (
        f"FR-043: literal phrase 'data loss' missing from impact field: {fresh_call.kwargs.get('impact')!r}"
    )
