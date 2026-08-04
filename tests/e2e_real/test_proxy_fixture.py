"""Behaviour tests for the real ``next dev`` proxy fixture.

WHY THIS FILE EXISTS
    ``tests/e2e/`` is not end-to-end: ``tests/e2e/test_chat_e2e.py:80`` drives the
    app through ``httpx.ASGITransport``, in-process, no socket. That blind spot let
    eleven CRITICAL bugs survive a full hunt, and one of them — a Next.js proxy idle
    timeout — is invisible unless a request genuinely traverses a real ``next dev``
    server.

    So the fixture under test spawns a real Next server and this file proves the
    traversal actually happens, rather than assuming it.

HOW THE TRAVERSAL PROOF WORKS
    The test stands up a stub backend on its own ephemeral port that records every
    request it receives, points the Next server at it via ``BACKEND_URL``, and then
    issues requests to the *Next* port. The stub and the Next server are on different
    ports, so a request the stub records could only have arrived through the Next
    rewrite. Nothing here mocks or intercepts anything.

ANTI-CRITERION
    Playwright ``page.route()`` is forbidden in this fixture. It intercepts inside the
    browser and never reaches the Next server, so a fixture built on it cannot observe
    a proxy timeout at all. ``test_fixture_does_not_intercept_in_the_browser`` keeps a
    future rewrite from quietly reintroducing it.
"""

from __future__ import annotations

import ast
import json
import socket
import threading
import uuid
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import pytest

from tests.e2e_real.next_proxy import (
    NEXT_BIN,
    NextProxy,
    frontend_dir,
    next_dev_proxy,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

# The whole module needs a real Next install. Skipping is honest; a green run that
# silently never started a server would be exactly the kind of false evidence this
# harness exists to eliminate.
pytestmark = pytest.mark.skipif(
    not NEXT_BIN.exists(),
    reason=(
        f"next binary not found at {NEXT_BIN} — run `npm ci` in {frontend_dir()} to exercise the real proxy fixture"
    ),
)


class _RecordingBackend:
    """A stub backend that records what the proxy forwards to it.

    Deliberately stdlib-only and deliberately not the real FastAPI app: this test
    asks one question — did the request cross the Next server — and a real backend
    would drag in Qdrant, Ollama and a database to answer it.
    """

    def __init__(self) -> None:
        self.token = uuid.uuid4().hex
        self.requests: list[tuple[str, str]] = []
        self._lock = threading.Lock()

        recorder = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self) -> None:  # noqa: N802 - stdlib callback name
                with recorder._lock:
                    recorder.requests.append(("GET", self.path))
                body = json.dumps({"token": recorder.token, "path": self.path}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args: object) -> None:
                """Silence the stdlib access log — pytest captures enough already."""

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def recorded_paths(self) -> list[str]:
        with self._lock:
            return [path for _method, path in self.requests]

    def __enter__(self) -> _RecordingBackend:
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


@pytest.fixture
def recording_backend() -> Iterator[_RecordingBackend]:
    with _RecordingBackend() as backend:
        yield backend


@pytest.fixture
def proxy(recording_backend: _RecordingBackend) -> Iterator[NextProxy]:
    with next_dev_proxy(backend_url=recording_backend.base_url) as running:
        yield running


def test_readiness_uses_a_route_the_proxy_does_not_serve(
    proxy: NextProxy, recording_backend: _RecordingBackend
) -> None:
    """``/healthz`` must be served by Next itself, never forwarded to the backend.

    Readiness has to be independent of the thing under measurement. If the fixture
    polled ``/api/*`` it would be waiting on the proxy path whose timeout behaviour
    the harness exists to measure, and a proxy fault would read as "server not up".
    """
    response = httpx.get(f"{proxy.base_url}/healthz", timeout=30.0)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert recording_backend.recorded_paths() == [], (
        "/healthz reached the backend, so it is not a proxy-independent readiness "
        f"signal. Backend saw: {recording_backend.recorded_paths()}"
    )


def test_request_at_the_proxy_port_reaches_the_backend(proxy: NextProxy, recording_backend: _RecordingBackend) -> None:
    """The load-bearing assertion: ``:proxy_port/api/*`` genuinely traverses Next."""
    probe_path = f"/api/harness-probe/{uuid.uuid4().hex}"

    response = httpx.get(f"{proxy.base_url}{probe_path}", timeout=60.0)

    assert response.status_code == 200

    payload = response.json()
    assert payload["token"] == recording_backend.token, (
        "the response did not come from the stub backend, so the request never crossed the proxy"
    )
    assert payload["path"] == probe_path, "the proxy rewrote the path unexpectedly"
    assert probe_path in recording_backend.recorded_paths(), (
        "the backend never recorded the request; it was answered by Next itself "
        f"instead of being forwarded. Backend saw: {recording_backend.recorded_paths()}"
    )


def test_proxy_port_is_distinct_from_the_backend_port(proxy: NextProxy, recording_backend: _RecordingBackend) -> None:
    """Two ports, or the traversal proof above proves nothing."""
    backend_port = int(recording_backend.base_url.rsplit(":", 1)[1])

    assert proxy.port != backend_port
    assert proxy.backend_url == recording_backend.base_url


def test_teardown_closes_the_port_and_leaves_no_process(
    recording_backend: _RecordingBackend,
) -> None:
    """A leaked ``next dev`` holds its port and poisons every later run.

    Next spawns its own children, so teardown has to take down the whole process
    group; killing only the parent leaves compiler processes alive.
    """
    with next_dev_proxy(backend_url=recording_backend.base_url) as running:
        port = running.port
        pid = running.pid
        assert httpx.get(f"{running.base_url}/healthz", timeout=30.0).status_code == 200

    assert not _pid_alive(pid), f"next dev pid {pid} survived teardown"

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(("127.0.0.1", port))


def test_fixture_does_not_intercept_in_the_browser() -> None:
    """Anti-criterion guard for the acceptance gate.

    ``page.route()`` intercepts in the browser and never reaches the Next server, so
    a fixture that used it could not observe a proxy timeout. A fixture built that
    way fails the gate outright — this keeps a future rewrite from reintroducing it
    without anyone noticing.

    The check walks the parsed module rather than grepping the text, so that the
    fixture stays free to *document* why interception is forbidden. A substring
    search cannot tell an explanation apart from a call, and would be satisfied only
    by deleting the very warning that keeps the rule alive.
    """
    tree = ast.parse((Path(__file__).parent / "next_proxy.py").read_text(encoding="utf-8"))

    imported: list[str] = []
    routed: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
        elif isinstance(node, ast.Attribute) and node.attr == "route":
            routed.append(ast.unparse(node))

    assert not [name for name in imported if name.split(".")[0] == "playwright"], (
        f"the proxy fixture imports playwright: {imported}"
    )
    assert routed == [], f"the proxy fixture calls a .route() interceptor: {routed}"


def _pid_alive(pid: int) -> bool:
    """True while the process exists and has not been reaped."""
    try:
        status = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except FileNotFoundError, ProcessLookupError, PermissionError:
        return False
    # A zombie has exited; its entry lingers only until the parent reaps it.
    return status.rsplit(") ", 1)[-1].split(" ", 1)[0] != "Z"
