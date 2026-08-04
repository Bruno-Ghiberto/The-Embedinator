"""Tests for the NDJSON stream reader and its ``eof_reason`` classification.

``eof_reason`` is a contract, not a convenience. BUG-074 (the frontend swallows
a stream that ends with no terminal event) and BUG-123 (the proxy holds the
socket open after the backend is gone) are *different* defects that a later
batch forks on. A reader that reported one "stream failed" outcome would make
them indistinguishable and would itself be the harness defect.

Each of the three outcomes is produced here by a real cause, over a real socket:

============  ==========================================================
``clean_eof``   the backend finished the turn and closed the body
``still_open``  the backend is wedged inside the LLM call; we gave up
``peer_closed`` the backend process was killed mid-stream
============  ==========================================================
"""

from __future__ import annotations

import signal

import pytest

from tests.e2e_real.fake_ollama import Mode
from tests.e2e_real.ndjson import EOF_REASONS, read_ndjson_stream

pytestmark = pytest.mark.require_server

_CHAT_BODY = {"message": "what does the harness return?", "collection_ids": ["harness"]}


async def test_completed_turn_is_clean_eof_with_a_terminal_event(backend_server):
    result = await read_ndjson_stream(backend_server.base_url, "/api/chat", json=_CHAT_BODY)

    assert result.eof_reason == "clean_eof"
    assert result.saw_terminal is True
    assert result.terminal_type in {"done", "error"}
    assert result.events[0]["type"] == "session"


async def test_reported_reason_is_always_from_the_contract_vocabulary(backend_server):
    result = await read_ndjson_stream(backend_server.base_url, "/api/chat", json=_CHAT_BODY)

    assert result.eof_reason in EOF_REASONS


async def test_a_wedged_turn_is_still_open_not_clean_eof(backend_server, fake_ollama):
    """The server never ended the body — we did. That is NOT an EOF.

    Calling this ``clean_eof`` would let a hung backend masquerade as a
    completed one, which is exactly the confusion BUG-074 lives in.
    """
    fake_ollama.set_mode(Mode.STALL_FOREVER)

    result = await read_ndjson_stream(
        backend_server.base_url, "/api/chat", json=_CHAT_BODY, idle_timeout=6.0
    )

    assert result.eof_reason == "still_open"
    assert result.saw_terminal is False
    assert result.terminal_type is None

    # Release the wedged turn so the backend frees its _chat_semaphore permit.
    fake_ollama.drain_chat_semaphore()


async def test_a_killed_backend_is_peer_closed_not_clean_eof(spawn_backend, fake_ollama):
    """A truncated body is a different defect from a body that ended properly.

    This is the BUG-123 probe shape: the distinction between "the peer went
    away" and "the peer said it was done" decides which fix branch ships.
    """
    server = spawn_backend("peer-closed")
    fake_ollama.set_mode(Mode.STALL_AFTER_FIRST_CHUNK)

    async def _kill() -> None:
        server.proc.send_signal(signal.SIGKILL)

    result = await read_ndjson_stream(
        server.base_url,
        "/api/chat",
        json=_CHAT_BODY,
        idle_timeout=30.0,
        on_first_event=_kill,
    )

    assert result.eof_reason == "peer_closed"
    assert result.saw_terminal is False


async def test_terminal_detection_ignores_non_terminal_events(backend_server):
    """``session``, ``status``, ``chunk``, ``citation``, ``confidence`` must not
    count as terminal — only done/error/clarification end a stream."""
    result = await read_ndjson_stream(backend_server.base_url, "/api/chat", json=_CHAT_BODY)

    non_terminal = [e for e in result.events[:-1] if e.get("type") in {"done", "error", "clarification"}]
    assert non_terminal == [], f"a terminal event appeared before the end: {non_terminal}"
