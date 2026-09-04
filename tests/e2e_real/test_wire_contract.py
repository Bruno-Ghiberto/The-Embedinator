"""The backend NDJSON wire contract — what the Python harness can honestly gate.

This file replaces the original Batch 0 exit gate, which asserted that the Next
proxy cuts an idle stream at 30s. That premise was **falsified** on 2026-08-04 by
a three-arm experiment on the live Docker stack:

===========  =================  ==========  ======================================
Size         Path               Duration    Result
===========  =================  ==========  ======================================
12.6 MB      via proxy ``:3000``  63.5s     FAIL (client 500, backend logged 400)
12.6 MB      direct ``:8000``     41.0s     202
**8.0 MB**   **via proxy**        **39.0s** **202**
===========  =================  ==========  ======================================

The third arm is the discriminator: a **39-second** proxied request *succeeded*.
There is no ~30s idle timeout. The trigger is **size** — Next's
``proxyClientMaxBodySize`` 10 MB default. BUG-054 and BUG-040 are one defect, and
the fix is ``proxyClientMaxBodySize``, not ``proxyTimeout``.

Consequently the proxy-timeout assertions were deleted rather than adjusted: they
encoded a hypothesis the evidence refutes, and a gate built on a refuted premise
is worse than no gate. BUG-054's regression cover is task 2.2's static
``next.config.ts`` import assertion; its *behavioural* evidence is the Docker
stack plus the Phase 8.2 operator transcript.

What survives here is the contract this harness genuinely owns: **a backend
stream that ends must say how it ended, and a backend stream that cannot end must
be terminated by the backend itself.**

See ``README.md`` in this directory for the full scope boundary.
"""

from __future__ import annotations

import pytest

from tests.e2e_real.fake_ollama import Mode
from tests.e2e_real.ndjson import StreamResult, read_ndjson_stream

pytestmark = pytest.mark.require_server

CHAT_PATH = "/api/chat"
CHAT_BODY = {"message": "wire contract probe", "collection_ids": ["harness"]}

#: The deadline BUG-088's fix installs must be shorter than this, or the assertion
#: below cannot distinguish "the backend terminated late" from "the backend never
#: terminated". Chosen well above the ~110s a normal cold turn takes so a slow
#: machine does not produce a false red.
DEADLINE_BUDGET_S = 180.0

#: Reader budget for a stream the backend is expected to terminate on its own.
#: Must exceed ``DEADLINE_BUDGET_S`` so the *backend* is always the party that
#: gives up first. If the reader wins the race, the test measures our patience
#: rather than the product — the failure mode that made the first exit-gate run
#: prove nothing.
READER_IDLE_TIMEOUT_S = 240.0
READER_TOTAL_TIMEOUT_S = 300.0


def _signature(result: StreamResult) -> str:
    """Observed stream signature, so a red run is diagnostic rather than merely negative."""
    first_byte = result.first_byte_s
    return (
        f"elapsed={result.elapsed_s:.1f}s "
        f"first_byte={first_byte if first_byte is None else f'{first_byte:.1f}s'} "
        f"eof_reason={result.eof_reason!r} "
        f"saw_terminal={result.saw_terminal} "
        f"terminal_type={result.terminal_type!r} "
        f"status={result.status_code} "
        f"types={result.types()}"
    )


async def test_backend_terminates_a_stream_whose_upstream_died(backend_server, fake_ollama):
    """A body that ends must carry a terminal event.

    ``die_midstream`` closes the upstream Ollama body with no ``done: true``. If
    the backend passed that truncation through, a client would have nothing to
    react to and its streaming state would never clear.

    Asserted against the backend directly — this is the wire contract, and
    routing it through the proxy would conflate it with the upload-size defect.

    Expected **green**. This is a regression lock, not a bug reproduction: it was
    green on 2026-08-04, which is precisely the finding that moved BUG-074 out of
    pytest and into the frontend vitest suite. The defect is entirely in
    ``frontend/lib/api.ts:157-208``, which swallows a truncated body; the backend
    end of the contract already holds and must keep holding.
    """
    fake_ollama.set_mode(Mode.DIE_MIDSTREAM)

    result = await read_ndjson_stream(
        backend_server.base_url,
        CHAT_PATH,
        json=CHAT_BODY,
        idle_timeout=60.0,
        total_timeout=120.0,
    )

    assert not result.ended_without_terminal, (
        "the backend passed an upstream truncation through to the wire. A client "
        "has nothing to react to and its streaming state never clears.\n"
        f"  observed: {_signature(result)}"
    )


async def test_backend_enforces_an_in_flight_llm_deadline(backend_server, fake_ollama):
    """BUG-088 — Batch 0's exit gate. **Must be RED on unmodified code.**

    ``stall_forever`` makes the upstream model accept the request and then never
    produce a byte. Today nothing bounds that: the turn holds its
    ``_chat_semaphore`` permit (``backend/api/chat.py:31``) and its connection
    open indefinitely, so five stalled turns exhaust the pool and the service
    stops answering while still reporting itself healthy.

    The fix (task 2.7) installs an in-flight deadline that terminates the turn
    with an ``error`` event and does not leak the task. After it lands this test
    goes green, and it then permanently guards the deadline against removal.

    This is the assertion the Python harness can hold end to end: real sockets,
    real graph, real backend process, one unambiguous product behaviour, no
    proxy and no browser anywhere in the path.
    """
    fake_ollama.set_mode(Mode.STALL_FOREVER)

    result = await read_ndjson_stream(
        backend_server.base_url,
        CHAT_PATH,
        json=CHAT_BODY,
        idle_timeout=READER_IDLE_TIMEOUT_S,
        total_timeout=READER_TOTAL_TIMEOUT_S,
    )

    assert result.saw_terminal, (
        "BUG-088: the backend held a stalled turn open for "
        f"{result.elapsed_s:.0f}s without terminating it. The turn keeps its "
        "_chat_semaphore permit, so five of these take the service down while it "
        "still reports healthy.\n"
        f"  observed: {_signature(result)}"
    )


async def test_stall_gate_outlived_the_deadline_it_asserts(backend_server, fake_ollama):
    """Guard the guard — the red above must come from the backend, not our patience.

    The method lesson from the first exit-gate run, kept deliberately. Two
    "red" tests turned out to be measuring nothing but the reader's own timeout;
    without a companion assertion Batch 0 would have closed on a reproduction
    that proved nothing.

    Here the guard is the *duration*, not ``eof_reason``. Under ``stall_forever``
    on unmodified code the reader is expected to be the party that gives up, so
    ``still_open`` is the correct observation. What must be proven is that it gave
    up only after outlasting the deadline the fix will install — otherwise the
    test above would go red on any machine slower than its own budget.
    """
    fake_ollama.set_mode(Mode.STALL_FOREVER)

    result = await read_ndjson_stream(
        backend_server.base_url,
        CHAT_PATH,
        json=CHAT_BODY,
        idle_timeout=READER_IDLE_TIMEOUT_S,
        total_timeout=READER_TOTAL_TIMEOUT_S,
    )

    assert result.elapsed_s >= DEADLINE_BUDGET_S or result.saw_terminal, (
        f"the reader gave up after {result.elapsed_s:.0f}s, short of the "
        f"{DEADLINE_BUDGET_S:.0f}s deadline budget, so the stall gate is "
        "measuring the harness rather than the backend.\n"
        f"  observed: {_signature(result)}"
    )


async def test_backend_bounds_the_ambiguous_intent_cycle(backend_server, fake_ollama):
    """BUG-082 — **Must be RED on unmodified code.**

    ``always_ambiguous`` makes every structured-output call classify the message as
    ``ambiguous`` with ``is_clear: false``. The direct route (``classify_intent`` ->
    ``request_clarification`` with ``query_analysis`` still ``None``) takes the node's
    fallback branch, which returns an answer and is then sent straight back to
    ``classify_intent`` by the unconditional edge at ``conversation_graph.py:82``.
    The turn cycles until ``recursion_limit`` 100 and ends with an ``error``
    (``RECURSION_LIMIT``) — the user's question is never answered.

    After task 2.7 the conditional edge ends the turn on the first pass and the
    fallback answer reaches the client as ``chunk`` + ``done``.
    """
    fake_ollama.set_mode(Mode.ALWAYS_AMBIGUOUS)

    result = await read_ndjson_stream(
        backend_server.base_url,
        CHAT_PATH,
        json=CHAT_BODY,
        idle_timeout=60.0,
        total_timeout=120.0,
    )

    assert result.terminal_type == "done", (
        "BUG-082: an ambiguous message cycled classify_intent -> request_clarification "
        "instead of terminating with the fallback answer.\n"
        f"  observed: {_signature(result)}"
    )
    assert result.text().strip(), (
        f"the fallback answer must reach the client, not just a terminal frame.\n  observed: {_signature(result)}"
    )
