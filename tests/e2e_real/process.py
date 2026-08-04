"""Uvicorn subprocess management for the real-socket harness.

Shared by both servers the harness spawns: the fake Ollama stub and the real
backend. Everything here is **synchronous** on purpose.

Why sync (this is load-bearing)
-------------------------------
``pytest.ini`` sets ``asyncio_mode = auto`` but no
``asyncio_default_fixture_loop_scope``. A session-scoped *async* fixture would
therefore get a session-scoped event loop while the tests that consume it run on
function-scoped loops. The two never share state, and the failure looks like an
unrelated hang. Process supervision needs no event loop, so it does not get one.

Why the port comes out of the log line
--------------------------------------
``uvicorn/server.py:105`` awaits ``lifespan.startup()`` *before* binding the
socket, and ``_log_started_message`` (``:189``) runs *after* the bind. With
``--port 0``, ``server.py:217-219`` substitutes the real bound port into that
message. So the "Uvicorn running on ..." line is simultaneously the port
announcement and the readiness signal — there is no TOCTOU window between
"port is known" and "server accepts connections".
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Sequence

# Matches: "Uvicorn running on http://127.0.0.1:38273 (Press CTRL+C to quit)"
_RUNNING_RE = re.compile(r"Uvicorn running on https?://(?:\[[^\]]+\]|[^:\s]+):(\d+)")

# Emitted when the socket cannot be bound; surfacing it beats waiting out the deadline.
_FATAL_MARKERS = (
    "Address already in use",
    "Error loading ASGI app",
    "Traceback (most recent call last)",
)


class ServerStartupError(RuntimeError):
    """Raised when a spawned uvicorn never announced a bound port."""


def process_group_pids(pgid: int) -> list[int]:
    """Return every live PID in ``pgid`` by reading ``/proc/<pid>/stat``.

    Used by the zero-orphan teardown assertion. Reading ``/proc`` directly avoids
    depending on ``pgrep`` being installed and avoids the shell entirely.
    """
    pids: list[int] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text()
        except (OSError, ValueError):
            continue  # process exited between listdir and read — not an orphan
        # comm may contain spaces and parentheses, so split after the final ')'.
        close_paren = stat.rfind(")")
        if close_paren == -1:
            continue
        fields = stat[close_paren + 2 :].split()
        # After comm, fields are: state ppid pgrp ... -> pgrp is index 2.
        if len(fields) > 2 and fields[2].isdigit() and int(fields[2]) == pgid:
            pids.append(int(entry.name))
    return sorted(pids)


@dataclass
class ServerProcess:
    """A running uvicorn subprocess in its own process group."""

    name: str
    proc: subprocess.Popen
    port: int
    stdout_path: Path
    stderr_path: Path
    pgid: int
    _handles: list[IO[bytes]] = field(default_factory=list, repr=False)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def is_running(self) -> bool:
        return self.proc.poll() is None

    def orphan_pids(self) -> list[int]:
        """PIDs still alive in this server's process group.

        After :meth:`terminate` this MUST be empty. A non-empty list means the
        harness leaked a process — the exact failure ``--timeout-graceful-shutdown``
        and ``killpg`` exist to prevent.
        """
        return process_group_pids(self.pgid)

    def read_stderr(self) -> str:
        try:
            return self.stderr_path.read_text(errors="replace")
        except OSError:
            return ""

    def terminate(self, timeout: float = 15.0) -> None:
        """SIGTERM the whole group, escalate to SIGKILL, then close log handles.

        The group (not the single PID) is signalled because uvicorn may have
        spawned children. ``--timeout-graceful-shutdown`` bounds how long the
        server may sit on an in-flight request before it drops it; without that
        flag a stalled turn makes SIGTERM block forever.
        """
        if self.proc.poll() is None:
            self._signal_group(signal.SIGTERM)
            try:
                self.proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self._signal_group(signal.SIGKILL)
                try:
                    self.proc.wait(timeout=10.0)
                except subprocess.TimeoutExpired:  # pragma: no cover - defensive
                    pass

        # Sweep any child that outlived its parent.
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if not self.orphan_pids():
                break
            self._signal_group(signal.SIGKILL)
            time.sleep(0.1)

        for handle in self._handles:
            try:
                handle.close()
            except OSError:  # pragma: no cover - defensive
                pass
        self._handles.clear()

    def _signal_group(self, sig: int) -> None:
        try:
            os.killpg(self.pgid, sig)
        except (ProcessLookupError, PermissionError):
            pass


def spawn_uvicorn(
    *,
    name: str,
    app_target: str,
    env: dict[str, str],
    cwd: Path,
    log_dir: Path,
    ready_timeout: float,
    graceful_shutdown: int = 5,
    python: str | None = None,
    extra_args: Sequence[str] = (),
) -> ServerProcess:
    """Start ``app_target`` under uvicorn on an ephemeral port and wait for readiness.

    Args:
        name: Short label; names the log files.
        app_target: ``module:attribute`` ASGI target.
        env: The COMPLETE environment for the child. Built as an allowlist by the
            caller — never ``os.environ.copy()``, which would leak the developer's
            real Qdrant, Ollama, and database settings into the harness.
        cwd: Working directory for the child. Point this at a tmp root so the
            repository ``.env`` (``backend/config.py`` ``env_file=".env"``) is not
            picked up and relative defaults land in the sandbox.
        log_dir: Directory for the stdout/stderr files.
        ready_timeout: Seconds to wait for the port announcement.
        graceful_shutdown: ``--timeout-graceful-shutdown``. Essential, not cosmetic.

    Raises:
        ServerStartupError: If no port was announced before the deadline.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / f"{name}.stdout.log"
    stderr_path = log_dir / f"{name}.stderr.log"

    # Files, never subprocess.PIPE: an undrained pipe wedges at the 64 KB buffer
    # and the server freezes mid-test with no visible cause.
    stdout_handle = stdout_path.open("wb")
    stderr_handle = stderr_path.open("wb")

    cmd = [
        python or sys.executable,
        "-m",
        "uvicorn",
        app_target,
        "--host",
        "127.0.0.1",
        "--port",
        "0",
        "--no-access-log",
        "--timeout-graceful-shutdown",
        str(graceful_shutdown),
        *extra_args,
    ]

    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=stdout_handle,
        stderr=stderr_handle,
        stdin=subprocess.DEVNULL,
        start_new_session=True,  # own process group, so killpg cannot hit pytest
    )

    try:
        port = _await_port(proc, stderr_path, stdout_path, ready_timeout)
    except BaseException:
        _emergency_kill(proc)
        stdout_handle.close()
        stderr_handle.close()
        raise

    return ServerProcess(
        name=name,
        proc=proc,
        port=port,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        pgid=os.getpgid(proc.pid),
        _handles=[stdout_handle, stderr_handle],
    )


def _await_port(
    proc: subprocess.Popen,
    stderr_path: Path,
    stdout_path: Path,
    timeout: float,
) -> int:
    """Poll the log files until uvicorn announces its bound port."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise ServerStartupError(
                f"uvicorn exited with code {proc.returncode} before binding a port.\n"
                f"--- stderr ---\n{_tail(stderr_path)}\n--- stdout ---\n{_tail(stdout_path)}"
            )

        for path in (stderr_path, stdout_path):
            text = _read(path)
            match = _RUNNING_RE.search(text)
            if match:
                return int(match.group(1))
            for marker in _FATAL_MARKERS:
                if marker in text:
                    raise ServerStartupError(
                        f"uvicorn reported a fatal startup error ({marker!r}).\n"
                        f"--- {path.name} ---\n{_tail(path)}"
                    )

        time.sleep(0.05)

    raise ServerStartupError(
        f"uvicorn did not announce a port within {timeout:.0f}s.\n"
        f"--- stderr ---\n{_tail(stderr_path)}\n--- stdout ---\n{_tail(stdout_path)}"
    )


def _read(path: Path) -> str:
    try:
        return path.read_text(errors="replace")
    except OSError:
        return ""


def _tail(path: Path, limit: int = 4000) -> str:
    return _read(path)[-limit:]


def _emergency_kill(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):  # pragma: no cover - defensive
        pass
    try:
        proc.wait(timeout=5.0)
    except subprocess.TimeoutExpired:  # pragma: no cover - defensive
        pass
