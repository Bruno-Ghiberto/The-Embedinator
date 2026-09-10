"""One wall-clock deadline for every in-flight LLM call (BUG-088)."""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from backend.config import settings
from backend.errors import LLMDeadlineExceeded

log = structlog.get_logger(__name__)


async def invoke_with_deadline(
    runnable: Any,
    input: Any,
    *,
    timeout: float | None = None,
    site: str = "llm",
    **kwargs: Any,
) -> Any:
    """Await ``runnable.ainvoke(input, **kwargs)`` under ``timeout`` seconds.

    ``ChatOllama``'s ``request_timeout`` did not bound a call whose socket was frozen
    (553 s observed) and ``max_loop_seconds`` is only checked between graph steps, so
    nothing could interrupt an in-flight await.

    What this guarantees, precisely: on expiry ``asyncio.timeout`` delivers cancellation
    to the call and awaits its completion, and this helper never returns a value produced
    past the deadline. What it cannot guarantee: a callee that *suppresses* cancellation
    cannot be bounded at all without orphaning it, so such a call is reported as a
    deadline (``late_completion=True``) while its own coroutine finishes unobserved.
    Every client on this path is httpx-based and honours cancellation.

    A ``TimeoutError`` raised by the runnable itself (a provider's own read timeout) keeps
    its identity and is not relabelled as this deadline.
    """
    limit = settings.llm_call_timeout_seconds if timeout is None else timeout
    try:
        async with asyncio.timeout(limit) as cm:
            result = await runnable.ainvoke(input, **kwargs)
    except TimeoutError as exc:
        if not cm.expired():
            # The runnable raised its OWN TimeoutError (a provider read timeout) — keep its identity.
            raise
        log.warning("agent_llm_deadline_exceeded", site=site, timeout_s=limit)
        raise LLMDeadlineExceeded(f"LLM call exceeded {limit:g}s") from exc
    if cm.expired():
        # The callee suppressed cancellation and finished late: still a deadline, never a late value.
        log.warning("agent_llm_deadline_exceeded", site=site, timeout_s=limit, late_completion=True)
        raise LLMDeadlineExceeded(f"LLM call exceeded {limit:g}s (callee ignored cancellation)")
    return result
