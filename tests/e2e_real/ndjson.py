"""NDJSON stream reader with ``eof_reason`` classification.

``backend/api/chat.py`` streams ten event types as ``application/x-ndjson``. The
interesting question is almost never "what did it send" but **how did it stop**,
and there are three genuinely different ways:

``clean_eof``
    The server ended the body at a frame boundary. It said it was finished —
    whether or not it actually emitted a terminal event. ``clean_eof`` with
    ``saw_terminal is False`` is the BUG-074 signature: the stream is over and
    the client was never told.

``peer_closed``
    The body was truncated. The connection went away mid-frame — a reset, a
    killed process, a proxy dropping the socket. The server never said anything.

``still_open``
    Nobody ended it. Our own deadline expired while the server still held the
    stream. This is the BUG-123 signature when it happens through the Next.js
    proxy but not against the backend directly.

Collapsing these into a single "the stream failed" outcome would make BUG-074
and BUG-123 indistinguishable, and a later batch forks on exactly that
distinction. Keeping them apart is the contract.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import httpx

from tests.e2e_real.fake_ollama import EOF_REASONS, TERMINAL_EVENT_TYPES

__all__ = ["EOF_REASONS", "TERMINAL_EVENT_TYPES", "StreamResult", "read_ndjson_stream"]

#: Exceptions that mean the body was truncated rather than finished.
_PEER_CLOSED_ERRORS = (
    httpx.RemoteProtocolError,
    httpx.ReadError,
    httpx.NetworkError,
    ConnectionResetError,
)


@dataclass
class StreamResult:
    """Everything an assertion might need about how a stream behaved."""

    events: list[dict[str, Any]] = field(default_factory=list)
    raw_lines: list[str] = field(default_factory=list)
    eof_reason: str = "still_open"
    status_code: int | None = None
    content_type: str | None = None
    elapsed_s: float = 0.0
    first_byte_s: float | None = None
    error: BaseException | None = None

    @property
    def saw_terminal(self) -> bool:
        """Did any event legitimately end the stream?

        ``clarification`` counts. ``backend/api/chat.py:204-218`` emits it on the
        LangGraph interrupt path and returns — treating that as a truncation
        would flag correct behaviour as a bug.
        """
        return any(e.get("type") in TERMINAL_EVENT_TYPES for e in self.events)

    @property
    def terminal_type(self) -> str | None:
        for event in reversed(self.events):
            if event.get("type") in TERMINAL_EVENT_TYPES:
                return str(event["type"])
        return None

    @property
    def ended_without_terminal(self) -> bool:
        """The BUG-074 signature: the body finished but nothing closed the turn."""
        return self.eof_reason in {"clean_eof", "peer_closed"} and not self.saw_terminal

    def types(self) -> list[str]:
        return [str(e.get("type")) for e in self.events]

    def text(self) -> str:
        """Concatenated ``chunk`` text, i.e. what the user would have seen."""
        return "".join(str(e.get("text", "")) for e in self.events if e.get("type") == "chunk")


async def read_ndjson_stream(
    base_url: str,
    path: str,
    *,
    json: dict[str, Any] | None = None,
    method: str = "POST",
    idle_timeout: float = 120.0,
    total_timeout: float = 600.0,
    connect_timeout: float = 10.0,
    on_first_event: Callable[[], Awaitable[None]] | None = None,
) -> StreamResult:
    """Consume an NDJSON stream and classify how it ended.

    Args:
        idle_timeout: Seconds without a new frame before declaring ``still_open``.
            This is an *idle* budget, matching how the Next.js proxy's
            ``proxyTimeout`` behaves — a slow-but-alive stream is not a stall.
        total_timeout: Absolute ceiling regardless of activity.
        on_first_event: Awaited once, right after the first frame arrives. Lets a
            test kill the server mid-stream to produce a genuine ``peer_closed``.

    Returns:
        A :class:`StreamResult` whose ``eof_reason`` is always in
        :data:`EOF_REASONS`.
    """
    body = json
    result = StreamResult()
    started = time.monotonic()
    timeout = httpx.Timeout(total_timeout, connect=connect_timeout, read=idle_timeout)

    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
            async with client.stream(method, path, json=body) as response:
                result.status_code = response.status_code
                result.content_type = response.headers.get("content-type")

                deadline = started + total_timeout
                fired_hook = False

                line_iter = response.aiter_lines()
                while True:
                    remaining = min(idle_timeout, max(0.0, deadline - time.monotonic()))
                    if remaining <= 0:
                        result.eof_reason = "still_open"
                        return _finish(result, started)

                    try:
                        line = await asyncio.wait_for(anext(line_iter), timeout=remaining)
                    except StopAsyncIteration:
                        # Body ended at a frame boundary — the server is done.
                        result.eof_reason = "clean_eof"
                        return _finish(result, started)
                    except (asyncio.TimeoutError, httpx.ReadTimeout):
                        # Nobody ended it; we gave up. Not an EOF.
                        result.eof_reason = "still_open"
                        return _finish(result, started)

                    if not line.strip():
                        continue

                    if result.first_byte_s is None:
                        result.first_byte_s = time.monotonic() - started

                    result.raw_lines.append(line)
                    try:
                        result.events.append(_loads(line))
                    except ValueError:
                        # Malformed frame: keep the raw line, do not invent an event.
                        pass

                    if on_first_event is not None and not fired_hook:
                        fired_hook = True
                        await on_first_event()

    except _PEER_CLOSED_ERRORS as exc:
        result.error = exc
        result.eof_reason = "peer_closed"
        return _finish(result, started)
    except httpx.ReadTimeout as exc:  # connect-phase or non-iteration timeout
        result.error = exc
        result.eof_reason = "still_open"
        return _finish(result, started)

    result.eof_reason = "clean_eof"  # pragma: no cover - loop always returns
    return _finish(result, started)


def _loads(line: str) -> dict[str, Any]:
    import json as _json

    parsed = _json.loads(line)
    if not isinstance(parsed, dict):
        raise ValueError("NDJSON frame was not an object")
    return parsed


def _finish(result: StreamResult, started: float) -> StreamResult:
    result.elapsed_s = time.monotonic() - started
    assert result.eof_reason in EOF_REASONS, f"unclassifiable eof_reason {result.eof_reason!r}"
    return result
