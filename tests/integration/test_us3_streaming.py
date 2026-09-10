"""Integration test for US3 streaming — T058.

Verifies NDJSON streaming protocol works correctly.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver

from tests.integration.conftest import unique_name


# The NDJSON wire contract: every type `backend/api/chat.py` emits and
# `frontend/lib/api.ts` consumes. Kept explicit so a new frame type cannot be
# added on one side without this test noticing.
STREAM_EVENT_TYPES = frozenset(
    {
        "session",
        "status",
        "chunk",
        "clarification",
        "citation",
        "meta_reasoning",
        "confidence",
        "groundedness",
        "done",
        "error",
    }
)

# Mirrors tests/e2e_real/fake_ollama.py — omitting `clarification` would flag the
# correct backend/api/chat.py path as a bug. BUG-074 forks on this distinction.
TERMINAL_EVENT_TYPES = frozenset({"done", "error", "clarification"})


class _FakeCursor:
    """Minimal async cursor for the checkpointer PRAGMA/SELECT calls in lifespan."""

    def __init__(self, rows):
        self._rows = rows

    async def fetchall(self):
        return self._rows


class _FakeConnContext:
    def __init__(self, rows):
        self._rows = rows

    async def __aenter__(self):
        return _FakeCursor(self._rows)

    async def __aexit__(self, *exc_info):
        return False


def _fake_checkpoint_conn():
    """A `conn` stand-in for MemorySaver.

    `backend/main.py` startup calls `_check_checkpoint_integrity` and
    `_prune_old_checkpoint_threads`, both of which reach for
    `checkpointer.conn` — an attribute only AsyncSqliteSaver has. The prune
    helper does not guard the access, so a bare MemorySaver raises
    AttributeError and every test in this module errors at setup.

    Reports a healthy integrity check and zero stored threads, which is the
    truth for an in-memory checkpointer.
    """
    conn = AsyncMock()
    conn.execute = lambda sql, *args, **kwargs: _FakeConnContext([("ok",)] if "integrity_check" in sql else [])
    return conn


@pytest.fixture
def streaming_app(tmp_path, monkeypatch):
    """Create a test app configured for streaming tests.

    Self-contained on purpose: the lifespan builds TWO Qdrant clients — the
    `QdrantClientWrapper` patched below, and the `QdrantStorage` that
    `backend/main.py` imports inside the lifespan function (main.py:536-540)
    and exposes as `app.state.qdrant_storage`, which is the one
    `POST /api/collections` reaches (backend/api/collections.py:45,81).
    Patching only the first sends the collection created here to whatever
    Qdrant answers on `settings.qdrant_port`: green on a developer box with the
    dev stack up, a setup error in CI where there is none, and an empty
    leftover collection in the live store either way. `settings.sqlite_path` is
    redirected into `tmp_path` for the same reason — the basename must stay
    `embedinator.db`, since main.py:560 derives the checkpoint path from it.
    """
    from backend.config import settings

    monkeypatch.setattr(settings, "sqlite_path", str(tmp_path / "embedinator.db"))

    mock_checkpointer = MemorySaver()
    mock_checkpointer.setup = AsyncMock()
    mock_checkpointer.conn = _fake_checkpoint_conn()

    mock_qdrant = AsyncMock()
    mock_qdrant.connect = AsyncMock()
    mock_qdrant.close = AsyncMock()
    mock_qdrant.search = AsyncMock(
        return_value=[
            {
                "id": "chunk-1",
                "score": 0.85,
                "payload": {
                    "document_id": "doc-test",
                    "text": "Test passage content.",
                    "chunk_index": 0,
                },
            }
        ]
    )

    # The second Qdrant path — see the fixture docstring.
    mock_storage = AsyncMock()
    mock_storage.create_collection = AsyncMock()
    mock_storage.delete_collection = AsyncMock()
    mock_storage.close = AsyncMock()

    mock_embed = AsyncMock()
    mock_embed.embed_single = AsyncMock(return_value=[0.1] * 768)

    mock_llm = AsyncMock()

    async def mock_stream(prompt):
        tokens = ["Word1 ", "Word2 ", "Word3 ", "Word4 ", "Word5."]
        for token in tokens:
            yield token

    mock_llm.generate_stream = mock_stream

    mock_registry = AsyncMock()
    mock_registry.initialize = AsyncMock()
    mock_registry.get_embedding_provider = AsyncMock(return_value=mock_embed)
    mock_registry.get_active_llm = AsyncMock(return_value=mock_llm)

    with (
        patch("backend.main.QdrantClientWrapper", return_value=mock_qdrant),
        patch("backend.storage.qdrant_client.QdrantStorage", return_value=mock_storage),
        patch("backend.main.ProviderRegistry", return_value=mock_registry),
        patch("langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver") as mock_saver_cls,
    ):
        mock_saver_cls.from_conn_string.return_value = mock_checkpointer

        from backend.main import create_app

        app = create_app()

        with TestClient(app) as client:
            # Set up a simple mock graph (no LLM dependencies).
            # Must be `conversation_graph`, NOT `_conversation_graph`:
            # `_get_or_build_graph` (backend/api/chat.py:81) prefers the
            # lifespan-built `conversation_graph` and only falls back to the
            # underscored name, so setting the fallback leaves the real graph
            # running and the mock silently unused.
            from tests.mocks import build_simple_chat_graph

            app.state.conversation_graph = build_simple_chat_graph()

            # Pre-create a collection
            coll_name = unique_name("Stream")
            coll_resp = client.post("/api/collections", json={"name": coll_name})
            assert coll_resp.status_code == 201
            coll_id = coll_resp.json()["id"]

            client._coll_id = coll_id
            yield client


def _read_events(streaming_app):
    resp = streaming_app.post(
        "/api/chat",
        json={
            "message": "Test query",
            "collection_ids": [streaming_app._coll_id],
        },
    )
    assert resp.status_code == 200
    return [json.loads(line) for line in resp.text.strip().split("\n")]


def test_streaming_ndjson_format(streaming_app):
    """Every frame is valid NDJSON carrying a type the wire contract defines."""
    events = _read_events(streaming_app)
    assert events, "the stream produced no frames"

    for event in events:
        assert "type" in event
        assert event["type"] in STREAM_EVENT_TYPES, f"undeclared frame type {event['type']!r}"


def test_streaming_ends_with_exactly_one_terminal_frame(streaming_app):
    """A completed stream carries one terminal frame, and it is last.

    This is the assertion BUG-074 turns on: a stream that ends without a
    terminal frame is indistinguishable from a working one to the client.
    """
    events = _read_events(streaming_app)

    terminals = [e for e in events if e["type"] in TERMINAL_EVENT_TYPES]
    assert len(terminals) == 1, f"expected one terminal frame, got {[e['type'] for e in terminals]}"
    assert events[-1]["type"] in TERMINAL_EVENT_TYPES


def test_streaming_chunks_contain_text(streaming_app):
    """Chunk frames carry non-empty text, and together they form the answer."""
    events = _read_events(streaming_app)
    chunks = [e for e in events if e["type"] == "chunk"]

    assert chunks, "a successful turn must emit at least one chunk frame"
    for chunk in chunks:
        assert "text" in chunk
        assert isinstance(chunk["text"], str)

    assert "".join(c["text"] for c in chunks).strip()


def test_streaming_done_frame_carries_trace_and_latency(streaming_app):
    """The done frame is where trace_id and latency_ms live.

    Renamed from test_streaming_metadata_includes_trace: the NDJSON contract has
    no `metadata` frame. `backend/api/chat.py` emits `done` as the terminal frame
    and reports confidence in its own `confidence` frame.
    """
    events = _read_events(streaming_app)

    done = [e for e in events if e["type"] == "done"]
    assert len(done) == 1
    assert "trace_id" in done[0]
    assert "latency_ms" in done[0]


def test_streaming_confidence_frame_reports_a_bounded_score(streaming_app):
    """Confidence is its own frame with an integer score in 0..100."""
    events = _read_events(streaming_app)

    confidence = [e for e in events if e["type"] == "confidence"]
    assert len(confidence) == 1
    score = confidence[0]["score"]
    assert isinstance(score, int)
    assert 0 <= score <= 100
