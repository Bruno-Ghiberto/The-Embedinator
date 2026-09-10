"""BUG-088 — one deadline for every in-flight LLM call.

All RED on the unmodified tree (``backend/agent/llm_deadline.py`` does not exist
yet and ``backend.errors`` has no ``LLMDeadlineExceeded``); each test imports the
new names inside its body on purpose (Ruling R12) so a missing symbol fails that
test alone and never breaks collection of the file.

Production change that makes these pass: a new ``invoke_with_deadline`` helper
that wraps ``runnable.ainvoke`` in ``asyncio.wait_for`` bounded by
``settings.llm_call_timeout_seconds`` and re-raises as ``LLMDeadlineExceeded``.
"""

import asyncio

import pytest


class _HangingRunnable:
    """ainvoke never resolves; records whether the await was cancelled."""

    def __init__(self) -> None:
        self.cancelled = False
        self.started = asyncio.Event()

    async def ainvoke(self, _input, **_kwargs):
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise


class _FastRunnable:
    async def ainvoke(self, _input, **_kwargs):
        return "answer"


@pytest.mark.asyncio
async def test_a_hung_call_raises_the_deadline_error_and_is_cancelled():
    from backend.agent.llm_deadline import invoke_with_deadline
    from backend.errors import LLMDeadlineExceeded

    runnable = _HangingRunnable()
    with pytest.raises(LLMDeadlineExceeded):
        await asyncio.wait_for(invoke_with_deadline(runnable, "q", timeout=0.05), 2.0)
    assert runnable.started.is_set()
    assert runnable.cancelled, "the in-flight call must be cancelled, not abandoned"


@pytest.mark.asyncio
async def test_a_call_inside_the_deadline_returns_its_value():
    from backend.agent.llm_deadline import invoke_with_deadline

    assert await invoke_with_deadline(_FastRunnable(), "q", timeout=1.0) == "answer"


@pytest.mark.asyncio
async def test_the_default_deadline_is_the_setting(monkeypatch):
    from backend.agent.llm_deadline import invoke_with_deadline
    from backend.config import settings
    from backend.errors import LLMDeadlineExceeded

    monkeypatch.setattr(settings, "llm_call_timeout_seconds", 0.05)
    with pytest.raises(LLMDeadlineExceeded):
        await asyncio.wait_for(invoke_with_deadline(_HangingRunnable(), "q"), 2.0)


def test_the_deadline_error_is_a_timeout_error_so_langgraph_never_retries_it():
    from backend.errors import LLMCallError, LLMDeadlineExceeded

    err = LLMDeadlineExceeded("LLM call exceeded 90s")
    assert isinstance(err, TimeoutError) and isinstance(err, LLMCallError)


# ---------------------------------------------------------------------------
# Helper hardening (review panel, fix round 2). Both RED on HEAD 591f3af.
# ---------------------------------------------------------------------------


class _OwnTimeoutRunnable:
    """A provider whose own read timeout fires — not our deadline."""

    async def ainvoke(self, _input, **_kwargs):
        raise TimeoutError("upstream read timeout")


class _CancellationSuppressingRunnable:
    """A badly behaved callee: it swallows the cancellation and answers anyway."""

    def __init__(self) -> None:
        self.suppressed = False

    async def ainvoke(self, _input, **_kwargs):
        import asyncio

        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.suppressed = True
        await asyncio.sleep(0.05)
        return "late"


@pytest.mark.asyncio
async def test_a_runnable_that_raises_its_own_timeout_error_is_not_relabelled():
    """A provider-side timeout keeps its identity.

    `ChatOllama(request_timeout=120.0)` raises a plain `TimeoutError` of its own. If the
    helper relabelled it, every such failure would be reported to the user as "the model
    did not respond within 90s" — a false statement about a call that never reached 90s,
    and a misleading trace for anyone debugging the provider.
    """
    from backend.agent.llm_deadline import invoke_with_deadline
    from backend.errors import LLMDeadlineExceeded

    with pytest.raises(TimeoutError) as exc_info:
        await invoke_with_deadline(_OwnTimeoutRunnable(), "q", timeout=1.0)

    assert not isinstance(exc_info.value, LLMDeadlineExceeded), (
        "the provider's own timeout was relabelled as our deadline"
    )
    assert "upstream read timeout" in str(exc_info.value)


@pytest.mark.asyncio
async def test_a_callee_that_suppresses_cancellation_still_ends_with_the_deadline_error():
    """The deadline is not advisory: a callee that eats the cancellation cannot win.

    If the helper let a suppressed cancellation through, the deadline would be a
    suggestion — the very stall BUG-088 exists to bound would still return a value
    long after the budget expired.
    """
    import asyncio

    from backend.agent.llm_deadline import invoke_with_deadline
    from backend.errors import LLMDeadlineExceeded

    runnable = _CancellationSuppressingRunnable()

    outcome: object = "<never ran>"
    try:
        outcome = await asyncio.wait_for(invoke_with_deadline(runnable, "q", timeout=0.05), 2.0)
    except LLMDeadlineExceeded:
        outcome = "<deadline raised>"

    assert outcome == "<deadline raised>", (
        f"the helper returned {outcome!r} instead of raising the deadline — a callee that "
        "swallows its cancellation must not be able to answer after the budget expired"
    )
    assert runnable.suppressed, "the callee must have seen the cancellation it then swallowed"
