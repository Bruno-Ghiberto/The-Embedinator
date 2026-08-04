"""Spawn a real ``next dev`` server so requests genuinely traverse the Next proxy.

WHY THIS EXISTS
    ``tests/e2e/`` is not end-to-end. ``tests/e2e/test_chat_e2e.py:80`` drives the app
    through ``httpx.ASGITransport`` — in-process ASGI, no socket, no proxy. That blind
    spot let eleven CRITICAL bugs survive a full hunt.

    One of them is a Next.js proxy **idle** timeout on the ``/api/:path*`` rewrite
    declared in ``frontend/next.config.ts``. It cannot be reproduced by any in-process
    client, because the timeout lives in the Next server that an in-process client
    never touches. Reproducing it requires a real server on a real port, which is what
    this module provides.

TWO CONSTRAINTS THAT LOOK LIKE DETAILS AND ARE NOT
    1. Readiness polls ``/healthz`` and never ``/api/*``. ``/api/*`` is the rewrite
       under measurement; using it as the readiness signal would make the fixture
       depend on the very behaviour it exists to measure, and a proxy fault would
       present as "server not up yet".

    2. Playwright ``page.route()`` is forbidden here. It intercepts inside the browser,
       so the request never reaches the Next server and the proxy timeout can never
       fire. A fixture built on it fails the acceptance gate outright.

PORT HANDLING
    ``next dev`` parses ``--port`` with a positive-integer parser, so ``--port 0`` is
    rejected outright and the usual "let the OS choose" trick is unavailable. The port
    is therefore reserved here by binding an ephemeral socket, reading the number, and
    releasing it.

    This leaves a small race, and Next's behaviour on losing it is worth knowing:
    ``start-server.ts`` only retries the next port up when the port was **not**
    explicitly requested. Because this module always passes ``--port``, a collision
    makes Next log the error and exit 1 rather than drift silently to another port.
    The readiness loop watches for that exit and reports it, so the failure is loud
    and the fixture never reports a URL that some other process owns.

PROCESS HYGIENE
    ``next dev`` spawns its own compiler children. Teardown signals the whole process
    group, so killing the parent alone cannot leave orphans holding the port. Output
    goes to a file rather than a pipe: a pipe nobody drains wedges the child at the
    64 KB buffer, and a chatty dev server reaches that easily.

WIRING (owned by whoever edits ``tests/e2e_real/conftest.py``)
    This module deliberately defines no pytest fixture, so that the file that owns
    fixture wiring stays the only place fixtures are declared::

        @pytest.fixture
        def next_proxy(live_backend):
            with next_dev_proxy(backend_url=live_backend.base_url) as proxy:
                yield proxy
"""

from __future__ import annotations

import contextlib
import os
import signal
import socket
import subprocess
import tempfile
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]

# Served by frontend/app/healthz/route.ts, which returns {"status": "ok"}. It is a
# route handler on the Next server itself, so it proves the server is up without
# touching the rewrite under measurement. Never point this at /api/*.
READINESS_PATH = "/healthz"

# Turbopack compiles routes on demand, and a cold first compile on a loaded machine is
# not fast. A short deadline here shows up later as a flaky harness.
DEFAULT_READINESS_TIMEOUT = 180.0

# Time the process group gets to exit on SIGTERM before SIGKILL.
DEFAULT_SHUTDOWN_GRACE = 10.0

# Environment passed through to the child. This is an allowlist on purpose: inheriting
# the parent environment wholesale would let an ambient BACKEND_URL, PORT or NODE_ENV
# silently redirect the server and make the test lie about what it proved.
ENV_PASSTHROUGH = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR")


def frontend_dir() -> Path:
    """Directory ``next dev`` runs in — the one holding ``next.config.ts``."""
    return REPO_ROOT / "frontend"


NEXT_BIN = frontend_dir() / "node_modules" / ".bin" / "next"


class NextProxyError(RuntimeError):
    """The Next dev server could not be started, or died before becoming ready."""


@dataclass(frozen=True)
class NextProxy:
    """A running ``next dev`` server.

    Attributes:
        base_url: Origin to issue requests against, e.g. ``http://127.0.0.1:41234``.
            Requests to ``/api/*`` here traverse the real proxy.
        port: The port ``base_url`` resolves to.
        backend_url: What the proxy was told to forward ``/api/*`` to.
        pid: Process id of the ``next dev`` parent, and the process group id.
        log_path: Merged stdout/stderr of the server, kept after teardown for
            post-mortem.
    """

    base_url: str
    port: int
    backend_url: str
    pid: int
    log_path: Path


def reserve_port(host: str = "127.0.0.1") -> int:
    """Reserve an ephemeral port and release it for the child to bind.

    ``next dev`` rejects ``--port 0``, so the port has to be chosen before the server
    starts. See the module docstring for what happens if the reservation is lost.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


@contextlib.contextmanager
def next_dev_proxy(
    *,
    backend_url: str,
    host: str = "127.0.0.1",
    port: int | None = None,
    readiness_timeout: float = DEFAULT_READINESS_TIMEOUT,
    shutdown_grace: float = DEFAULT_SHUTDOWN_GRACE,
    log_dir: Path | None = None,
) -> Iterator[NextProxy]:
    """Run a real ``next dev`` server against ``backend_url`` for the block's duration.

    Args:
        backend_url: Origin the ``/api/:path*`` rewrite forwards to, passed as
            ``BACKEND_URL``. ``frontend/next.config.ts`` reads it when the config
            loads, so it must be set before the process starts — it cannot be
            changed on a running server.
        host: Interface to bind. Loopback by default; the fixture has no business
            listening on the network.
        port: Explicit port, or ``None`` to reserve an ephemeral one.
        readiness_timeout: Seconds to wait for ``/healthz`` to answer 200.
        shutdown_grace: Seconds the process group gets on SIGTERM before SIGKILL.
        log_dir: Where to write the server log. Defaults to a new temp directory,
            which is left behind on purpose so a failed run can be read afterwards.

    Yields:
        A :class:`NextProxy` describing the running server.

    Raises:
        NextProxyError: The ``next`` binary is missing, the server exited before
            becoming ready, or it never answered ``/healthz`` in time.
    """
    if not NEXT_BIN.exists():
        raise NextProxyError(f"next binary not found at {NEXT_BIN}. Run `npm ci` in {frontend_dir()} first.")

    chosen_port = reserve_port(host) if port is None else port
    base_url = f"http://{host}:{chosen_port}"

    log_root = Path(log_dir) if log_dir else Path(tempfile.mkdtemp(prefix="e2e-real-next-"))
    log_root.mkdir(parents=True, exist_ok=True)
    log_path = log_root / f"next-dev-{chosen_port}.log"

    env = {name: os.environ[name] for name in ENV_PASSTHROUGH if name in os.environ}
    env["BACKEND_URL"] = backend_url
    # Keep the log free of telemetry noise and ANSI escapes so it stays greppable.
    env["NEXT_TELEMETRY_DISABLED"] = "1"
    env["NO_COLOR"] = "1"
    env["FORCE_COLOR"] = "0"

    command = [
        str(NEXT_BIN),
        "dev",
        "--hostname",
        host,
        "--port",
        str(chosen_port),
    ]

    process: subprocess.Popen[bytes] | None = None
    with log_path.open("wb") as log_handle:
        try:
            process = subprocess.Popen(
                command,
                cwd=str(frontend_dir()),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                # Merged so the log preserves the real interleaving, and so neither
                # stream is a pipe that nobody drains.
                stderr=subprocess.STDOUT,
                # Own process group, so teardown can signal the compiler children too.
                start_new_session=True,
            )

            _await_readiness(
                process=process,
                base_url=base_url,
                timeout=readiness_timeout,
                log_path=log_path,
            )

            yield NextProxy(
                base_url=base_url,
                port=chosen_port,
                backend_url=backend_url,
                pid=process.pid,
                log_path=log_path,
            )
        finally:
            if process is not None:
                terminate_process_group(process, grace=shutdown_grace)


def _await_readiness(
    *,
    process: subprocess.Popen[bytes],
    base_url: str,
    timeout: float,
    log_path: Path,
) -> None:
    """Block until ``/healthz`` answers 200, the server dies, or the deadline passes."""
    readiness_url = f"{base_url}{READINESS_PATH}"
    deadline = time.monotonic() + timeout

    with httpx.Client(timeout=5.0) as client:
        while time.monotonic() < deadline:
            exit_code = process.poll()
            if exit_code is not None:
                raise NextProxyError(
                    f"next dev exited with code {exit_code} before becoming ready. "
                    f"A port collision reports this way, because an explicitly requested "
                    f"port makes Next fail instead of drifting to another one.\n"
                    f"{_log_tail(log_path)}"
                )

            try:
                response = client.get(readiness_url)
            except httpx.HTTPError:
                # Not listening yet, or still compiling. Both are ordinary here.
                pass
            else:
                if response.status_code == 200:
                    return

            time.sleep(0.25)

    raise NextProxyError(
        f"next dev did not answer {readiness_url} with 200 within {timeout:.0f}s.\n{_log_tail(log_path)}"
    )


def terminate_process_group(process: subprocess.Popen[bytes], *, grace: float = DEFAULT_SHUTDOWN_GRACE) -> None:
    """Stop the server and everything it spawned, then reap it.

    Signals the process group rather than the pid: ``next dev`` starts compiler
    children, and killing only the parent leaves them holding the port. SIGKILL
    follows if the group ignores SIGTERM.
    """
    if process.poll() is not None:
        process.wait()
        return

    try:
        pgid = os.getpgid(process.pid)
    except ProcessLookupError:
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=grace)
        return

    with contextlib.suppress(ProcessLookupError):
        os.killpg(pgid, signal.SIGTERM)

    try:
        process.wait(timeout=grace)
        return
    except subprocess.TimeoutExpired:
        pass

    with contextlib.suppress(ProcessLookupError):
        os.killpg(pgid, signal.SIGKILL)

    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(timeout=grace)


def _log_tail(log_path: Path, limit: int = 4000) -> str:
    """Last few KB of the server log, for failure messages."""
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"--- next dev log unavailable ({exc}) ---"

    if len(text) > limit:
        text = text[-limit:]
    return f"--- next dev log ({log_path}) ---\n{text}"
