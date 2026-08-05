"""BUG-123 isolation probe — spec-31 task 1.6 (read-only, no product code touched).

BUG-123 was registered UNCONFIRMED on two single observations that were never
controlled for the proxy variable: a browser fetch reader saw no EOF for 189s on
the proxied path, while a `curl` client on the direct path terminated promptly.
Different clients, different turn states, one observation each, no re-kill.

This probe holds every variable fixed except the path:

  * identical request body, identical model, identical collection
  * the SAME client and the SAME reader on both runs
  * the kill fires at the SAME point in the turn (after N `chunk` frames), so the
    backend is doing the same work when it dies
  * both runs are re-killed to check reproducibility

The instrument is the live Docker stack, NOT `tests/e2e_real`'s proxy fixtures.
`tests/e2e_real/README.md` records a host-loopback artifact that stalls proxied
requests inside the backend before the graph runs, and says in terms that the
proxy fixtures are not the instrument for the proxy class. Using them here would
reproduce the very defect this probe exists to rule out.

`eof_reason` is imported from the harness rather than redefined, so the taxonomy
that Batch 2's fork reads is the same one this writes.
"""

from __future__ import annotations

import asyncio
import json as _json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

sys.path.insert(0, "/home/brunoghiberto/Documents/Projects/The-Embedinator")
from tests.e2e_real.ndjson import EOF_REASONS, TERMINAL_EVENT_TYPES  # noqa: E402

BACKEND = "embedinator-backend"
DIRECT_URL = "http://localhost:8000"
PROXY_URL = "http://localhost:3000"
CHAT_PATH = "/api/chat"

# Held fixed across every run — the whole point of the probe.
CHAT_BODY = {
    "message": ("Summarise everything you know about this collection in as much detail as you can, step by step."),
    "collection_ids": ["a0c923c1-b8a3-4690-8cd3-d570d77c7d31"],
    "llm_model": "qwen3:14b",
}

#: Kill once the turn is genuinely generating, matching P7-S1d's mid-generation
#: kill. Killing on the first frame would land on `session`, which chat.py:148
#: emits before it even takes the semaphore.
KILL_AFTER_CHUNKS = 3

#: How long we keep reading after the kill before declaring `still_open`.
#: BUG-123 claims >=189s held open; the direct path is claimed to die "promptly".
#: 120s separates those two outcomes decisively without an open-ended wait.
POST_KILL_IDLE_BUDGET_S = 120.0
FIRST_CHUNK_BUDGET_S = 180.0

_PEER_CLOSED_ERRORS = (
    httpx.RemoteProtocolError,
    httpx.ReadError,
    httpx.NetworkError,
    ConnectionResetError,
)


@dataclass
class ProbeRun:
    label: str
    url: str
    eof_reason: str = "still_open"
    events: list[dict[str, Any]] = field(default_factory=list)
    killed_at: float | None = None
    eof_at: float | None = None
    chunks_before_kill: int = 0
    status_code: int | None = None
    error: str | None = None
    backend_state_at_eof: str | None = None

    @property
    def seconds_from_kill_to_eof(self) -> float | None:
        if self.killed_at is None or self.eof_at is None:
            return None
        return self.eof_at - self.killed_at

    @property
    def saw_terminal(self) -> bool:
        return any(e.get("type") in TERMINAL_EVENT_TYPES for e in self.events)

    def summary(self) -> str:
        gap = self.seconds_from_kill_to_eof
        return (
            f"{self.label:<22} eof_reason={self.eof_reason:<12} "
            f"kill->eof={'never' if gap is None else f'{gap:6.1f}s'}  "
            f"terminal={self.saw_terminal!s:<5} "
            f"events={len(self.events):<4} chunks_pre_kill={self.chunks_before_kill} "
            f"backend_at_eof={self.backend_state_at_eof} err={self.error}"
        )


def _docker(*args: str) -> str:
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=False).stdout.strip()


def backend_state() -> str:
    return _docker("inspect", "-f", "{{.State.Status}}", BACKEND) or "unknown"


def kill_backend() -> None:
    subprocess.run(["docker", "kill", BACKEND], capture_output=True, check=False)


def restore_backend(timeout_s: float = 180.0) -> bool:
    subprocess.run(["docker", "start", BACKEND], capture_output=True, check=False)
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{DIRECT_URL}/api/health/live", timeout=3.0)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(2.0)
    return False


async def probe(label: str, base_url: str) -> ProbeRun:
    run = ProbeRun(label=label, url=base_url)
    started = time.monotonic()
    chunks = 0
    killed = False

    timeout = httpx.Timeout(None, connect=10.0, read=POST_KILL_IDLE_BUDGET_S)
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
            async with client.stream("POST", CHAT_PATH, json=CHAT_BODY) as response:
                run.status_code = response.status_code
                line_iter = response.aiter_lines()
                while True:
                    budget = (
                        POST_KILL_IDLE_BUDGET_S
                        if killed
                        else max(1.0, FIRST_CHUNK_BUDGET_S - (time.monotonic() - started))
                    )
                    try:
                        line = await asyncio.wait_for(anext(line_iter), timeout=budget)
                    except StopAsyncIteration:
                        run.eof_reason = "clean_eof"
                        run.eof_at = time.monotonic()
                        break
                    except (asyncio.TimeoutError, httpx.ReadTimeout):
                        run.eof_reason = "still_open"
                        run.eof_at = None
                        break

                    if not line.strip():
                        continue
                    try:
                        event = _json.loads(line)
                    except ValueError:
                        continue
                    run.events.append(event)

                    if event.get("type") == "chunk":
                        chunks += 1
                    if not killed and chunks >= KILL_AFTER_CHUNKS:
                        killed = True
                        run.chunks_before_kill = chunks
                        run.killed_at = time.monotonic()
                        kill_backend()
                        print(
                            f"  [{label}] killed backend after {chunks} chunks at t+{run.killed_at - started:.1f}s",
                            flush=True,
                        )
    except _PEER_CLOSED_ERRORS as exc:
        run.eof_reason = "peer_closed"
        run.eof_at = time.monotonic()
        run.error = type(exc).__name__
    except Exception as exc:  # noqa: BLE001 - probe must record, never raise
        run.eof_reason = "still_open"
        run.error = f"{type(exc).__name__}: {exc}"

    run.backend_state_at_eof = backend_state()
    assert run.eof_reason in EOF_REASONS, f"unclassifiable {run.eof_reason!r}"
    return run


async def main() -> int:
    order = [("PROXIED :3000", PROXY_URL), ("DIRECT :8000", DIRECT_URL)]
    results: list[ProbeRun] = []

    for attempt in (1, 2):  # re-kill: BUG-123 was never checked for reproducibility
        for label, url in order:
            print(f"\n=== {label} (attempt {attempt}) ===", flush=True)
            if not restore_backend():
                print("  ABORT: backend did not come back healthy", flush=True)
                return 1
            # Let the stack settle so run-to-run state is comparable.
            time.sleep(3.0)
            run = await probe(f"{label} #{attempt}", url)
            print("  " + run.summary(), flush=True)
            results.append(run)

    print("\n\n================ BUG-123 PROBE RESULT ================", flush=True)
    for r in results:
        print(r.summary(), flush=True)

    restore_backend()
    print(f"\nbackend restored: {backend_state()}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
