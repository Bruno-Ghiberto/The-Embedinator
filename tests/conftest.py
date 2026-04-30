"""Shared test fixtures for The Embedinator backend tests."""

import os
import socket
import sqlite3
from pathlib import Path

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from langchain_core.messages import AIMessage

from backend.storage.sqlite_db import SQLiteDB
from backend.agent.schemas import RetrievedChunk


def _is_docker_qdrant_available() -> bool:
    """Check if Qdrant is reachable on localhost:6333 via socket."""
    try:
        with socket.create_connection(("127.0.0.1", 6333), timeout=1):
            return True
    except OSError:
        return False


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: backend Python E2E tests using in-process ASGI")
    config.addinivalue_line("markers", "require_docker: tests requiring Qdrant on localhost:6333")


def pytest_runtest_setup(item):
    if item.get_closest_marker("require_docker") and not _is_docker_qdrant_available():
        pytest.skip("Qdrant not available on localhost:6333")


@pytest_asyncio.fixture
async def db():
    """Isolated in-memory SQLiteDB. MUST use connect(), not initialize()."""
    instance = SQLiteDB(":memory:")
    await instance.connect()
    yield instance
    await instance.close()


@pytest.fixture
def sample_chunks() -> list[RetrievedChunk]:
    """Pre-built list[RetrievedChunk] with 3 items, scores [0.92, 0.78, 0.65]."""
    return [
        RetrievedChunk(
            chunk_id="chunk-001",
            text="Authentication requires a valid certificate from the WSAA service.",
            source_file="test-document.pdf",
            page=1,
            breadcrumb="Section 1 > Authentication",
            parent_id="parent-001",
            collection="test-collection",
            dense_score=0.92,
            sparse_score=0.75,
            rerank_score=None,
        ),
        RetrievedChunk(
            chunk_id="chunk-002",
            text="Token validation uses SAML 2.0 assertions for authorization.",
            source_file="test-document.pdf",
            page=2,
            breadcrumb="Section 1 > Tokens",
            parent_id="parent-001",
            collection="test-collection",
            dense_score=0.78,
            sparse_score=0.60,
            rerank_score=None,
        ),
        RetrievedChunk(
            chunk_id="chunk-003",
            text="Digital signatures require X.509 certificates for electronic invoicing.",
            source_file="test-document.pdf",
            page=5,
            breadcrumb="Section 2 > Invoicing",
            parent_id="parent-002",
            collection="test-collection",
            dense_score=0.65,
            sparse_score=0.48,
            rerank_score=None,
        ),
    ]


@pytest.fixture
def mock_llm():
    """MagicMock satisfying BaseChatModel interface.

    ainvoke returns AIMessage("This is a test answer.").
    with_structured_output returns self (supports chaining).
    """
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content="This is a test answer."))
    llm.with_structured_output = MagicMock(return_value=llm)
    llm.astream = AsyncMock()
    return llm


def make_corrupt_sqlite_file(tmp_path: Path, *, with_wal: bool = False) -> Path:
    """Create a deterministically corrupt SQLite DB file with a valid header.

    Returns the path to the corrupt file. ``PRAGMA integrity_check`` on the
    result will report at least one error. ``PRAGMA quick_check`` will also fail.

    Corruption strategy:
    1. Create a valid SQLite DB with checkpointer-shaped schema (2 tables) using
       stdlib ``sqlite3`` (sync) — same DDL that AsyncSqliteSaver.setup() issues.
    2. Insert ~3 checkpoint rows with 4 KB BLOBs so the B-tree spans 8 pages
       (default page_size=4096; pages 5–8 are overflow/leaf pages that produce
       an "invalid page number" integrity error — the BUG-013 corruption type).
    3. Close cleanly and checkpoint WAL into main DB so no -wal sibling remains
       (``with_wal=False`` default).
    4. Self-validate: PRAGMA integrity_check must return ("ok",) at this stage.
    5. Open file in ``'r+b'`` mode, seek to byte 20480 (start of page 6),
       overwrite 64 bytes with random garbage to corrupt a B-tree cell reference.
       - Why page 6 (offset 20480): the full checkpointer schema (2 tables +
         3 rows × 4 KB BLOBs) produces an 8-page DB (WAL mode, page_size=4096).
         Pages 1–3 (offsets 0–8192) are the critical SQLite root pages —
         corrupting them makes the DB completely unreadable (DatabaseError) AND
         causes VACUUM INTO to fail (no salvage possible). Pages 5–8 (offsets
         16384–28672) are overflow/leaf pages that produce "invalid page number"
         errors in integrity_check while allowing VACUUM INTO to succeed and
         produce a clean salvage file. Offset 20480 (page 6) reliably reproduces
         the BUG-013 "invalid page number in B-tree traversal" pattern.
       - Why 64 bytes: enough to corrupt a B-tree cell offset at fixed positions
         without destroying the page-allocation map.
    6. Self-validate corruption: PRAGMA integrity_check must NOT return ("ok",).
       AssertionError if corruption failed — canary against future SQLite versions
       that change page-6 corruption detection.
    7. If ``with_wal=True``: touch ``<path>-wal`` (size 0 is sufficient; the
       recovery helper only checks ``os.path.exists``).

    Args:
        tmp_path: pytest ``tmp_path`` fixture — base directory for the file.
        with_wal: If True, also create an empty ``<path>-wal`` sibling file.

    Returns:
        Path to the corrupt ``checkpoints.db`` file.
    """
    db_path = tmp_path / "checkpoints.db"

    # Step 1: build a valid checkpointer-shaped DB using stdlib sqlite3 (sync).
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE checkpoints (
            thread_id TEXT,
            checkpoint_ns TEXT,
            checkpoint_id TEXT,
            parent_checkpoint_id TEXT,
            type TEXT,
            checkpoint BLOB,
            metadata BLOB,
            PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE writes (
            thread_id TEXT,
            checkpoint_ns TEXT,
            checkpoint_id TEXT,
            task_id TEXT,
            idx INTEGER,
            channel TEXT,
            type TEXT,
            value BLOB,
            PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
        )
        """
    )
    # Step 2: insert 3 rows with 4 KB BLOBs so the B-tree spans 8 pages.
    blob = os.urandom(4096)
    for i in range(3):
        conn.execute(
            "INSERT INTO checkpoints "
            "(thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, type, checkpoint, metadata) "
            "VALUES (?, '', ?, NULL, 'msgpack', ?, ?)",
            (f"thread-{i:04d}", f"chk-{i:04d}", blob, b"{}"),
        )
    conn.commit()
    # Step 3: close cleanly — WAL is checkpointed on close, no -wal sibling left.
    conn.close()

    # Step 4: self-validate the fresh DB is healthy.
    chk = sqlite3.connect(str(db_path))
    result = chk.execute("PRAGMA integrity_check").fetchone()
    chk.close()
    assert result == ("ok",), f"make_corrupt_sqlite_file: DB should be healthy before corruption, got {result!r}"

    # Step 5: corrupt page 6 (byte offset 20480) with 64 random bytes.
    # Design note: original design specified offset 4096 but in the full
    # checkpointer schema (2 tables + 3×4KB BLOBs = 8 pages WAL mode), pages
    # 1–3 are critical root pages whose corruption causes DatabaseError and
    # makes VACUUM INTO fail. Pages 5–8 (offsets 16384+) produce recoverable
    # "invalid page number" integrity errors; offset 20480 (page 6) is chosen
    # as it reliably reproduces the BUG-013 pattern AND allows VACUUM INTO to
    # produce a clean salvage file.
    with open(db_path, "r+b") as f:
        f.seek(20480)
        f.write(os.urandom(64))

    # Step 6: self-validate corruption took effect.
    chk2 = sqlite3.connect(str(db_path))
    result2 = chk2.execute("PRAGMA integrity_check").fetchone()
    chk2.close()
    assert result2 != ("ok",), (
        "make_corrupt_sqlite_file: Page-6 corruption did not register as a SQLite "
        "integrity issue. SQLite version may have changed corruption detection behavior. "
        f"Got: {result2!r}"
    )

    # Step 7: optionally create a -wal sibling.
    if with_wal:
        Path(str(db_path) + "-wal").touch()

    return db_path


@pytest.fixture
def mock_qdrant_results() -> list[dict]:
    """Raw Qdrant result dicts matching HybridSearcher payload format.

    Payload keys: text, source_file, page, breadcrumb, parent_id, sparse_score.
    Scores: [0.92, 0.78].
    """
    return [
        {
            "id": "chunk-001",
            "score": 0.92,
            "payload": {
                "text": "Authentication requires a valid certificate from the WSAA service.",
                "source_file": "test-document.pdf",
                "page": 1,
                "breadcrumb": "Section 1 > Authentication",
                "parent_id": "parent-001",
                "sparse_score": 0.75,
            },
        },
        {
            "id": "chunk-002",
            "score": 0.78,
            "payload": {
                "text": "Token validation uses SAML 2.0 assertions for authorization.",
                "source_file": "test-document.pdf",
                "page": 2,
                "breadcrumb": "Section 1 > Tokens",
                "parent_id": "parent-001",
                "sparse_score": 0.60,
            },
        },
    ]
