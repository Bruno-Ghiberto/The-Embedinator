"""Fixtures for the real-socket E2E harness.

Scope note — why this file is NOT ``tests/e2e/conftest.py``
----------------------------------------------------------
``tests/e2e/`` holds four files that drive the app through
``httpx.ASGITransport`` (``tests/e2e/test_chat_e2e.py:80``) — in-process ASGI, no
socket. ``pytest.ini`` documents the ``e2e`` marker as exactly that. Those tests
are the blind spot this harness exists to distrust: they let 11 CRITICAL bugs
through a full hunt. Putting a uvicorn fixture next to them would apply it to the
very tests it is meant to replace. The two worlds stay separate.

Opt-in
------
Everything here is marked ``require_server`` and is **skipped unless
``E2E_REAL=1``**. The backend suite baseline is a 1500-test run that must not
start spawning servers by accident::

    E2E_REAL=1 zsh scripts/run-tests-external.sh -n <name> --no-cov tests/e2e_real/
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from tests.e2e_real.fake_ollama import (
    DEFAULT_EMBED_DIMENSION,
    DEFAULT_EMBED_MODEL,
    DEFAULT_LLM_MODEL,
    FakeOllamaHandle,
)
from tests.e2e_real.process import ServerProcess, spawn_uvicorn

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Readiness deadline. The cross-encoder reranker (``backend/main.py:610`` ->
#: ``backend/retrieval/reranker.py:30``) is constructed eagerly inside the
#: lifespan and takes ~7.2s warm; a cold start is worse.
BACKEND_READY_TIMEOUT = 180.0
FAKE_OLLAMA_READY_TIMEOUT = 60.0


def _e2e_real_enabled() -> bool:
    return os.environ.get("E2E_REAL", "").strip().lower() in {"1", "true", "yes", "on"}


def pytest_runtest_setup(item: pytest.Item) -> None:
    if item.get_closest_marker("require_server") and not _e2e_real_enabled():
        pytest.skip("real-socket harness is opt-in — set E2E_REAL=1 to run")


@pytest.fixture(scope="session")
def harness_log_dir() -> Path:
    """Where spawned servers write stdout/stderr.

    Files, never pipes — see ``process.spawn_uvicorn``.
    """
    path = REPO_ROOT / "Docs" / "Tests" / "e2e_real_logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture(scope="session")
def fake_ollama(tmp_path_factory, harness_log_dir) -> FakeOllamaHandle:
    """The deterministic LLM stub, on its own uvicorn subprocess.

    SYNC, not async, and deliberately so: ``pytest.ini`` sets no
    ``asyncio_default_fixture_loop_scope``, so a session-scoped *async* fixture
    would run on a session loop while tests run on function loops. They would not
    share state and the symptom would look like an unrelated hang.

    A subprocess rather than a thread because ``stall_forever`` would starve a
    worker thread and take the harness with it.
    """
    cwd = tmp_path_factory.mktemp("fake-ollama-cwd")

    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONPATH": str(REPO_ROOT),
        "PYTHONUNBUFFERED": "1",
        "HOME": os.environ.get("HOME", str(cwd)),
        "FAKE_OLLAMA_LLM_MODEL": DEFAULT_LLM_MODEL,
        "FAKE_OLLAMA_EMBED_MODEL": DEFAULT_EMBED_MODEL,
        "FAKE_OLLAMA_EMBED_DIM": str(DEFAULT_EMBED_DIMENSION),
    }

    server: ServerProcess = spawn_uvicorn(
        name="fake-ollama",
        app_target="tests.e2e_real.fake_ollama:app",
        env=env,
        cwd=cwd,
        log_dir=harness_log_dir,
        ready_timeout=FAKE_OLLAMA_READY_TIMEOUT,
        python=sys.executable,
    )

    handle = FakeOllamaHandle(server.base_url)
    handle._server = server  # type: ignore[attr-defined]  # kept for orphan assertions
    try:
        yield handle
    finally:
        handle.drain_chat_semaphore()
        handle.close()
        server.terminate()


@pytest.fixture(autouse=True)
def _reset_fake_ollama(request) -> None:
    """Return the stub to ``normal`` around every test.

    Draining on the way OUT matters more than on the way in: a stalled stream
    left behind holds a ``_chat_semaphore`` permit (``backend/api/chat.py:31``)
    and the NEXT test hangs for reasons that look unrelated.
    """
    if "fake_ollama" not in request.fixturenames:
        yield
        return

    handle: FakeOllamaHandle = request.getfixturevalue("fake_ollama")
    handle.reset()
    try:
        yield
    finally:
        handle.drain_chat_semaphore()
        handle.wait_until_idle(timeout=15.0)
        handle.reset()
