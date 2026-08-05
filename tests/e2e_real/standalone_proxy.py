"""Spawn the Next **standalone** server, which is the one BUG-054 was measured on.

WHY THIS EXISTS RATHER THAN ``next_proxy.py``
    ``next_proxy.py`` runs ``next dev``. Empirically (2026-08-04) ``next dev``
    applies no ~30s idle cut at all: a chat turn that completed in 109s against
    the backend directly produced only a ``session`` frame and then nothing for
    90s through ``next dev``. So it reproduces neither BUG-054 nor BUG-123.

    ``frontend/next.config.ts:4`` sets ``output: "standalone"``, and the hunt
    measured BUG-054 through the Docker stack — the standalone server. BUG-054's
    own record says so: *"best-evidence conclusion is a Next.js standalone-server
    / Node http / undici BUILT-IN default inside the rewrites()-based proxy
    path"*. Reproducing it therefore requires this server, not the dev server.

THE BUILD-TIME CONSTRAINT THAT SHAPES EVERYTHING HERE
    ``next.config.ts`` interpolates ``process.env.BACKEND_URL`` inside
    ``rewrites()``, and Next resolves that **at build time** into
    ``routes-manifest.json``, ``required-server-files.json`` and ``server.js``.
    Setting ``BACKEND_URL`` when starting the server does nothing.

    Verified two ways: grepping a fresh build for the baked literal, and
    ``frontend/Dockerfile:14`` (``ARG BACKEND_URL``) plus ``docker-compose.yml:88``
    passing it under ``args:`` — the project already treats it as a build arg.

    Consequence: the backend cannot use an ephemeral port. The build and the
    backend must agree on a number in advance, which is why
    :data:`HARNESS_BACKEND_PORT` exists and why the backend fixture passes
    ``port=`` to ``spawn_uvicorn``.

    A relay hop from a fixed port to an ephemeral one was rejected: it inserts
    another buffering layer into the exact measurement the fixture exists to make.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import tempfile
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import httpx

from tests.e2e_real.next_proxy import (
    READINESS_PATH,
    NextProxyError,
    frontend_dir,
    reserve_port,
    terminate_process_group,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The port the harness backend must bind, and the port the standalone build must
#: have been built against. Deliberately unusual so it does not collide with the
#: developer's own stack (backend 8000, frontend 3000, Qdrant 6333).
HARNESS_BACKEND_PORT = 8931
HARNESS_BACKEND_URL = f"http://127.0.0.1:{HARNESS_BACKEND_PORT}"

#: A production server has nothing to compile on demand, so readiness is quick.
DEFAULT_READINESS_TIMEOUT = 90.0
DEFAULT_SHUTDOWN_GRACE = 10.0

ENV_PASSTHROUGH = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR")


def standalone_dir() -> Path:
    return frontend_dir() / ".next" / "standalone"


def standalone_server_js() -> Path:
    return standalone_dir() / "server.js"


@dataclass(frozen=True)
class StandaloneProxy:
    """A running Next standalone server."""

    base_url: str
    port: int
    backend_url: str
    pid: int
    log_path: Path


def baked_backend_destination() -> str | None:
    """The proxy destination compiled into the current build, or ``None``.

    Read from the manifest rather than inferred, because this value is the whole
    reason the fixture needs a fixed port and a stale build would silently send
    every request to the developer's real backend on :8000.
    """
    manifest = standalone_dir() / ".next" / "routes-manifest.json"
    if not manifest.is_file():
        return None

    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return None

    rewrites = data.get("rewrites")
    if isinstance(rewrites, dict):
        entries = rewrites.get("beforeFiles", []) + rewrites.get("afterFiles", [])
    else:
        entries = rewrites or []

    for entry in entries:
        if entry.get("source") == "/api/:path*":
            return str(entry.get("destination", "")) or None
    return None


def build_command() -> str:
    """The exact command that produces a build this fixture can use."""
    return (
        f"cd {frontend_dir()} && BACKEND_URL={HARNESS_BACKEND_URL} "
        f"NEXT_TELEMETRY_DISABLED=1 ./node_modules/.bin/next build"
    )


def assert_build_is_usable() -> None:
    """Fail loudly unless a standalone build exists AND targets the harness backend.

    A build baked against the wrong origin is worse than no build: the server
    starts, ``/healthz`` answers 200, and every ``/api/*`` request quietly goes to
    whatever backend that origin names. The test would then measure the
    developer's running stack while appearing to measure the harness.
    """
    if not standalone_server_js().is_file():
        raise NextProxyError(f"no standalone build at {standalone_server_js()}.\nBuild it with:\n  {build_command()}")

    destination = baked_backend_destination()
    if destination is None:
        raise NextProxyError(
            f"could not read the /api/:path* rewrite from the standalone build at "
            f"{standalone_dir()}.\nRebuild with:\n  {build_command()}"
        )

    if not destination.startswith(HARNESS_BACKEND_URL):
        raise NextProxyError(
            f"the standalone build proxies /api/* to {destination!r}, not to the "
            f"harness backend at {HARNESS_BACKEND_URL}. BACKEND_URL is baked at BUILD "
            f"time, so this cannot be corrected by setting an environment variable.\n"
            f"Rebuild with:\n  {build_command()}"
        )


@contextlib.contextmanager
def standalone_proxy(
    *,
    host: str = "127.0.0.1",
    port: int | None = None,
    readiness_timeout: float = DEFAULT_READINESS_TIMEOUT,
    shutdown_grace: float = DEFAULT_SHUTDOWN_GRACE,
    log_dir: Path | None = None,
) -> Iterator[StandaloneProxy]:
    """Run the built standalone server for the block's duration.

    Unlike ``next dev`` there is no per-directory lock here, so this can run
    alongside the developer's own dev server.

    Args:
        host: Interface to bind. Loopback only.
        port: Explicit port, or ``None`` to reserve an ephemeral one. Unlike the
            *backend* port this one is free to be ephemeral — nothing is compiled
            against it.
        readiness_timeout: Seconds to wait for ``/healthz`` to answer 200.
        shutdown_grace: Seconds the process group gets on SIGTERM before SIGKILL.
        log_dir: Where to write the server log.

    Raises:
        NextProxyError: No usable build, or the server never became ready.
    """
    assert_build_is_usable()

    chosen_port = reserve_port(host) if port is None else port
    base_url = f"http://{host}:{chosen_port}"

    log_root = Path(log_dir) if log_dir else Path(tempfile.mkdtemp(prefix="e2e-real-standalone-"))
    log_root.mkdir(parents=True, exist_ok=True)
    log_path = log_root / f"next-standalone-{chosen_port}.log"

    env = {name: os.environ[name] for name in ENV_PASSTHROUGH if name in os.environ}
    env["NODE_ENV"] = "production"
    env["PORT"] = str(chosen_port)
    env["HOSTNAME"] = host
    env["NEXT_TELEMETRY_DISABLED"] = "1"
    env["NO_COLOR"] = "1"
    # Set for completeness and explicitly NOT relied upon — the destination is
    # already compiled in. assert_build_is_usable() is what actually guarantees it.
    env["BACKEND_URL"] = HARNESS_BACKEND_URL

    process: subprocess.Popen[bytes] | None = None
    with log_path.open("wb") as log_handle:
        try:
            process = subprocess.Popen(
                ["node", "server.js"],
                cwd=str(standalone_dir()),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )

            _await_readiness(
                process=process,
                base_url=base_url,
                timeout=readiness_timeout,
                log_path=log_path,
            )

            yield StandaloneProxy(
                base_url=base_url,
                port=chosen_port,
                backend_url=HARNESS_BACKEND_URL,
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
    readiness_url = f"{base_url}{READINESS_PATH}"
    deadline = time.monotonic() + timeout

    with httpx.Client(timeout=5.0) as client:
        while time.monotonic() < deadline:
            exit_code = process.poll()
            if exit_code is not None:
                raise NextProxyError(
                    f"the standalone server exited with code {exit_code} before becoming ready.\n{_log_tail(log_path)}"
                )

            try:
                response = client.get(readiness_url)
            except httpx.HTTPError:
                pass
            else:
                if response.status_code == 200:
                    return

            time.sleep(0.25)

    raise NextProxyError(
        f"the standalone server did not answer {readiness_url} with 200 within {timeout:.0f}s.\n{_log_tail(log_path)}"
    )


def _log_tail(log_path: Path, limit: int = 4000) -> str:
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"--- standalone log unavailable ({exc}) ---"
    if len(text) > limit:
        text = text[-limit:]
    return f"--- standalone log ({log_path}) ---\n{text}"


def kill_process_group(process: subprocess.Popen[bytes]) -> None:
    """Re-exported for symmetry with ``next_proxy``; see that module."""
    with contextlib.suppress(ProcessLookupError):
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
