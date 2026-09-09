"""BUG-088 — a stalled turn must end honestly and leak nothing.

The observable contract, end to end through `/api/chat`:

* the stream ends with exactly one terminal frame, and it is an `error` whose
  code is `LLM_TIMEOUT`;
* it ends inside the deadline, not when the client gives up;
* the `_chat_semaphore` permit is released (five stalled turns must not take the
  service down while it still reports itself healthy);
* the in-flight LLM coroutine is cancelled, not abandoned.

RED on the unmodified tree: `backend.agent.llm_deadline` does not exist, so the
graph node raises ImportError and chat.py answers `SERVICE_UNAVAILABLE`.

Production change that makes it pass: the `invoke_with_deadline` helper plus
chat.py catching `LLMDeadlineExceeded` before its generic `except Exception`.

The fixture below mirrors `tests/integration/test_us3_streaming.py:77-147`.
"""

import json
import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from backend.agent.state import ConversationState
from tests.integration.conftest import unique_name


class _FakeCursor:
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
    """A `conn` stand-in for MemorySaver — see test_us3_streaming.py:60-74."""
    conn = AsyncMock()
    conn.execute = lambda sql, *args, **kwargs: _FakeConnContext([("ok",)] if "integrity_check" in sql else [])
    return conn


class _HangingLLM:
    """An LLM whose ainvoke never resolves; records whether it was cancelled."""

    def __init__(self) -> None:
        self.cancelled = False
        self.started = False

    async def ainvoke(self, *_args, **_kwargs):
        import asyncio

        self.started = True
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise


def _build_stalling_graph(hung_llm):
    """One node that waits on an LLM which never answers, under the deadline."""

    async def stall(state, config=None):
        from backend.agent.llm_deadline import invoke_with_deadline

        await invoke_with_deadline(hung_llm, "q")
        return {}

    graph = StateGraph(ConversationState)
    graph.add_node("stall", stall)
    graph.add_edge(START, "stall")
    graph.add_edge("stall", END)
    return graph.compile(checkpointer=MemorySaver())


def _build_fast_graph():
    """Guard: an LLM that answers inside the deadline still reaches `done`."""

    async def respond(state, config=None):
        from langchain_core.messages import AIMessage

        text = "The capital of France is Paris."
        return {
            "messages": state["messages"] + [AIMessage(content=text)],
            "final_response": text,
            "citations": [],
            "confidence_score": 85,
            "intent": "rag_query",
        }

    graph = StateGraph(ConversationState)
    graph.add_node("respond", respond)
    graph.add_edge(START, "respond")
    graph.add_edge("respond", END)
    return graph.compile(checkpointer=MemorySaver())


@pytest.fixture
def deadline_app(tmp_path, monkeypatch):
    """A real app whose conversation graph the test replaces.

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
    mock_qdrant.search = AsyncMock(return_value=[])

    # The second Qdrant path — see the fixture docstring.
    mock_storage = AsyncMock()
    mock_storage.create_collection = AsyncMock()
    mock_storage.delete_collection = AsyncMock()
    mock_storage.close = AsyncMock()

    mock_embed = AsyncMock()
    mock_embed.embed_single = AsyncMock(return_value=[0.1] * 768)

    mock_registry = AsyncMock()
    mock_registry.initialize = AsyncMock()
    mock_registry.get_embedding_provider = AsyncMock(return_value=mock_embed)
    mock_registry.get_active_llm = AsyncMock(return_value=AsyncMock())

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
            coll_resp = client.post("/api/collections", json={"name": unique_name("Deadline")})
            assert coll_resp.status_code == 201
            client._coll_id = coll_resp.json()["id"]
            yield client


def _post_chat(client):
    resp = client.post(
        "/api/chat",
        json={"message": "stall probe", "collection_ids": [client._coll_id]},
    )
    assert resp.status_code == 200
    return [json.loads(line) for line in resp.text.strip().split("\n") if line.strip()]


_TERMINAL_TYPES = frozenset({"done", "error", "clarification"})


def test_a_stalled_turn_ends_with_llm_timeout_and_releases_its_permit(deadline_app, monkeypatch):
    """RED today — the helper does not exist, so chat.py answers SERVICE_UNAVAILABLE."""
    # Imported first on purpose: on the unmodified tree this raises ImportError,
    # so the RED names the missing module instead of tripping over the missing
    # setting inside monkeypatch's teardown.
    from backend.agent.llm_deadline import invoke_with_deadline  # noqa: F401
    from backend.api import chat as chat_module
    from backend.config import settings

    monkeypatch.setattr(settings, "llm_call_timeout_seconds", 0.2)

    hung_llm = _HangingLLM()
    deadline_app.app.state.conversation_graph = _build_stalling_graph(hung_llm)

    started = time.monotonic()
    events = _post_chat(deadline_app)
    elapsed = time.monotonic() - started

    terminals = [e for e in events if e["type"] in _TERMINAL_TYPES]
    assert len(terminals) == 1, f"expected exactly one terminal frame, got {[e['type'] for e in events]}"

    terminal = terminals[-1]
    assert terminal["type"] == "error", f"observed terminal frame: {terminal}"
    assert terminal["code"] == "LLM_TIMEOUT", f"observed terminal frame: {terminal}"
    assert terminal.get("trace_id"), "the error frame must carry a trace_id"
    assert elapsed < 2.0, f"the turn took {elapsed:.2f}s — the deadline did not bound it"

    assert chat_module._chat_semaphore._value == 5, (
        "the turn did not release its _chat_semaphore permit; five stalled turns "
        "would take the service down while it still reports healthy"
    )
    assert hung_llm.cancelled is True, "the in-flight LLM coroutine leaked instead of being cancelled"


def test_a_turn_inside_the_deadline_still_reaches_done(deadline_app):
    """Guard — expected PASS today. The deadline must not change the happy path."""
    deadline_app.app.state.conversation_graph = _build_fast_graph()

    events = _post_chat(deadline_app)

    terminals = [e for e in events if e["type"] in _TERMINAL_TYPES]
    assert len(terminals) == 1, f"expected exactly one terminal frame, got {[e['type'] for e in events]}"
    assert terminals[-1]["type"] == "done", f"observed terminal frame: {terminals[-1]}"
