"""PR2 — the uvicorn subprocess fixture proves itself.

These tests exist to make one claim checkable: the backend under test is reached
through a **real TCP socket**, not ``httpx.ASGITransport``. Everything the
harness later asserts about streaming, timeouts and disconnects is only
meaningful if that is true.
"""

from __future__ import annotations

import json
import socket

import httpx
import pytest

from tests.e2e_real.fake_ollama import TERMINAL_EVENT_TYPES, Mode

pytestmark = pytest.mark.require_server


# --------------------------------------------------------------------------
# The defining property: a real socket.
# --------------------------------------------------------------------------


def test_backend_listens_on_a_real_tcp_socket(backend_server):
    """A raw ``socket.create_connection`` succeeds — no ASGI shortcut can do this."""
    with socket.create_connection(("127.0.0.1", backend_server.port), timeout=5) as sock:
        assert sock.getpeername()[1] == backend_server.port


def test_backend_process_is_alive_and_in_its_own_process_group(backend_server):
    assert backend_server.is_running()
    assert backend_server.pgid != 0
    assert backend_server.proc.pid in backend_server.orphan_pids()


def test_server_output_goes_to_files_not_pipes(backend_server):
    """An undrained ``subprocess.PIPE`` wedges at 64 KB and freezes the server."""
    assert backend_server.proc.stdout is None
    assert backend_server.proc.stderr is None
    assert backend_server.stderr_path.exists()
    assert "Uvicorn running on" in backend_server.read_stderr()


# --------------------------------------------------------------------------
# Readiness and wiring.
# --------------------------------------------------------------------------


async def test_health_live_is_the_readiness_probe(backend_server):
    """``/api/health/live`` (health.py:26) answers unconditionally with no side effects."""
    async with httpx.AsyncClient(base_url=backend_server.base_url, timeout=10.0) as client:
        resp = await client.get("/api/health/live")

    assert resp.status_code == 200
    assert resp.json() == {"status": "alive"}


async def test_readiness_probe_is_repeatable(backend_server):
    """Contrast with ``/api/health``, whose ``_first_probe`` global (health.py:23)
    returns ``starting`` without probing and burns the flag on the first call.
    Polling that endpoint for readiness would consume the signal it reports."""
    async with httpx.AsyncClient(base_url=backend_server.base_url, timeout=10.0) as client:
        first = await client.get("/api/health/live")
        second = await client.get("/api/health/live")

    assert first.json() == second.json() == {"status": "alive"}


async def test_backend_talks_to_the_fake_ollama_not_a_real_one(backend_server, fake_ollama):
    """Proves the ``OLLAMA_BASE_URL`` -> ``registry.py:86-90`` wiring actually took."""
    before = fake_ollama.stats()["chat_calls"]

    async with httpx.AsyncClient(base_url=backend_server.base_url, timeout=120.0) as client:
        async with client.stream(
            "POST",
            "/api/chat",
            json={"message": "what does the harness return?", "collection_ids": ["harness"]},
        ) as resp:
            async for _line in resp.aiter_lines():
                pass

    assert fake_ollama.stats()["chat_calls"] > before, "the real graph never called the stub"


async def test_child_environment_is_an_allowlist_not_os_environ_copy(backend_server):
    """``os.environ.copy()`` would leak the developer's real Qdrant/Ollama/DB settings."""
    assert "E2E_REAL_LEAK_CANARY" not in backend_server.child_env
    assert backend_server.child_env["SQLITE_PATH"].endswith("embedinator.db"), (
        "main.py:560 does a literal str.replace on the basename 'embedinator.db'"
    )


# --------------------------------------------------------------------------
# The wire contract, over a real socket.
# --------------------------------------------------------------------------


async def test_chat_streams_ndjson_and_reaches_a_terminal_event(backend_server):
    events: list[dict] = []
    async with httpx.AsyncClient(base_url=backend_server.base_url, timeout=120.0) as client:
        async with client.stream(
            "POST",
            "/api/chat",
            json={"message": "what does the harness return?", "collection_ids": ["harness"]},
        ) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("application/x-ndjson")
            async for line in resp.aiter_lines():
                if line.strip():
                    events.append(json.loads(line))

    assert events, "expected at least one NDJSON event"
    assert events[0]["type"] == "session", "chat.py:145 emits the session event first"
    assert events[-1]["type"] in TERMINAL_EVENT_TYPES, f"stream ended on {events[-1]['type']!r}"


# --------------------------------------------------------------------------
# Task 0.12 — the test that proves the process discipline.
# --------------------------------------------------------------------------


async def test_teardown_leaves_zero_orphan_pids_after_a_stall_forever_turn(spawn_backend, fake_ollama):
    """The whole reason for ``--timeout-graceful-shutdown``, ``start_new_session`` and ``killpg``.

    BUG-088's premise is a hung in-flight task. Without
    ``--timeout-graceful-shutdown`` SIGTERM waits on that task forever and
    teardown hangs; without ``start_new_session`` + ``killpg`` a child outlives
    its parent and leaks into the next test.
    """
    server = spawn_backend("orphan-check")
    fake_ollama.set_mode(Mode.STALL_FOREVER)

    # Fire a turn and walk away while it is still hung inside the LLM call.
    with pytest.raises((httpx.ReadTimeout, httpx.RemoteProtocolError)):
        async with httpx.AsyncClient(
            base_url=server.base_url, timeout=httpx.Timeout(30.0, read=8.0)
        ) as client:
            async with client.stream(
                "POST",
                "/api/chat",
                json={"message": "hang please", "collection_ids": ["harness"]},
            ) as resp:
                async for _line in resp.aiter_lines():
                    pass

    assert server.is_running(), "the server should still be up, just stuck on the turn"

    server.terminate(timeout=20.0)

    assert not server.is_running()
    assert server.orphan_pids() == [], f"leaked PIDs after teardown: {server.orphan_pids()}"


def test_spawned_backends_are_torn_down_between_tests(spawn_backend):
    """The factory owns cleanup, so a test that forgets cannot leak a server."""
    server = spawn_backend("cleanup-check")
    assert server.is_running()
    # No explicit terminate — the fixture must do it, and the next test's
    # orphan assertions would fail if it did not.
