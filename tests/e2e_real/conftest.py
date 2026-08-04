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


def build_backend_env(*, sandbox: Path, ollama_base_url: str) -> dict[str, str]:
    """The COMPLETE environment for a backend subprocess — an allowlist, never a copy.

    ``os.environ.copy()`` would hand the child the developer's real Qdrant port,
    real Ollama URL and real database path, and the harness would silently test
    the wrong system.

    Every entry below is pinned to something the source actually requires:

    ``SQLITE_PATH``
        Basename MUST be ``embedinator.db``. ``backend/main.py:560`` derives the
        checkpoint DB with a literal ``str.replace("embedinator.db", ...)``.
    ``EMBEDINATOR_PORT_QDRANT`` / ``EMBEDINATOR_FERNET_KEY``
        These are pydantic *aliases* (``backend/config.py:33,42``). ``QDRANT_PORT``
        is not the env name.
    ``RATE_LIMIT_*_PER_MINUTE``
        Defaults are 30/10/5/120. A 100 ms readiness loop over 60 s is 600
        requests and would trip the general limiter into 429s.
    ``DEFAULT_LLM_MODEL``
        Must stay inside ``settings.supported_llm_models``: ``main.py:508`` calls
        ``_validate_model_support`` and exits the process on a miss.
    ``HF_HUB_OFFLINE`` / ``HF_HOME``
        ``main.py:610`` eagerly builds ``CrossEncoder`` inside the lifespan. Point
        at the shared cache so it is not re-downloaded per run, and forbid network.
    """
    data_dir = sandbox / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    from cryptography.fernet import Fernet

    return {
        # --- process basics ---
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", str(sandbox)),
        "PYTHONPATH": str(REPO_ROOT),
        "PYTHONUNBUFFERED": "1",
        "LANG": "C.UTF-8",
        # --- storage, all inside the sandbox ---
        "SQLITE_PATH": str(data_dir / "embedinator.db"),
        "UPLOAD_DIR": str(data_dir / "uploads"),
        "CHECKPOINT_AUTO_RECOVER": "false",
        # --- the whole point: the graph's LLM is our stub ---
        "OLLAMA_BASE_URL": ollama_base_url,
        "DEFAULT_PROVIDER": "ollama",
        "DEFAULT_LLM_MODEL": DEFAULT_LLM_MODEL,
        "DEFAULT_EMBED_MODEL": DEFAULT_EMBED_MODEL,
        # --- Qdrant deliberately unreachable: connect() swallows and degrades
        #     (backend/storage/qdrant_client.py:68-77), and a closed localhost
        #     port refuses immediately rather than burning the readiness budget.
        "QDRANT_HOST": "127.0.0.1",
        "EMBEDINATOR_PORT_QDRANT": "59999",
        # --- secrets ---
        "EMBEDINATOR_FERNET_KEY": Fernet.generate_key().decode(),
        # --- keep turns short and deterministic ---
        "META_REASONING_MAX_ATTEMPTS": "0",
        "GROUNDEDNESS_CHECK_ENABLED": "false",
        "MAX_ITERATIONS": "1",
        "MAX_TOOL_CALLS": "2",
        "MAX_LOOP_SECONDS": "60",
        # --- readiness polling must not be rate limited ---
        "RATE_LIMIT_GENERAL_PER_MINUTE": "100000",
        "RATE_LIMIT_CHAT_PER_MINUTE": "100000",
        "RATE_LIMIT_INGEST_PER_MINUTE": "100000",
        "RATE_LIMIT_PROVIDER_KEYS_PER_MINUTE": "100000",
        # --- no model downloads mid-test ---
        "HF_HUB_OFFLINE": "1",
        "HF_HOME": os.environ.get("HF_HOME", str(Path.home() / ".cache" / "huggingface")),
        "TRANSFORMERS_OFFLINE": "1",
        "TOKENIZERS_PARALLELISM": "false",
        "LOG_LEVEL": "INFO",
    }


def _start_backend(
    *,
    name: str,
    sandbox: Path,
    log_dir: Path,
    ollama_base_url: str,
) -> ServerProcess:
    return spawn_uvicorn(
        name=name,
        app_target="backend.main:app",
        env=build_backend_env(sandbox=sandbox, ollama_base_url=ollama_base_url),
        # cwd is the sandbox, so backend/config.py's `env_file=".env"` cannot pick
        # up the repository .env and relative defaults land here, not in the repo.
        cwd=sandbox,
        log_dir=log_dir,
        ready_timeout=BACKEND_READY_TIMEOUT,
        graceful_shutdown=5,
        python=sys.executable,
    )


@pytest.fixture(scope="session")
def backend_server(tmp_path_factory, harness_log_dir, fake_ollama) -> ServerProcess:
    """The shared backend under test, on a real socket.

    Session-scoped because the lifespan builds a ``CrossEncoder`` eagerly
    (~7.2s warm, worse cold) and paying that per test would be intolerable.
    Tests that need to kill a server get their own via ``spawn_backend``.
    """
    sandbox = tmp_path_factory.mktemp("backend-session")
    server = _start_backend(
        name="backend-session",
        sandbox=sandbox,
        log_dir=harness_log_dir,
        ollama_base_url=fake_ollama.base_url,
    )
    try:
        yield server
    finally:
        server.terminate()


@pytest.fixture
def spawn_backend(tmp_path_factory, harness_log_dir, fake_ollama):
    """Factory for disposable backends, each in its own sandbox.

    Use this for anything that terminates, kills or corrupts a server — killing
    the session-scoped one would strand every later test. Cleanup is
    unconditional, so a test that forgets to tear down cannot leak a process.
    """
    started: list[ServerProcess] = []

    def _factory(name: str = "backend") -> ServerProcess:
        sandbox = tmp_path_factory.mktemp(f"{name}-sandbox")
        server = _start_backend(
            name=f"{name}-{len(started)}",
            sandbox=sandbox,
            log_dir=harness_log_dir,
            ollama_base_url=fake_ollama.base_url,
        )
        started.append(server)
        return server

    try:
        yield _factory
    finally:
        for server in started:
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
