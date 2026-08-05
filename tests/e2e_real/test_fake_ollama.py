"""PR3 — tests for the deterministic fake Ollama stub.

The stub exists so the REAL production graph becomes deterministic: pointing
``OLLAMA_BASE_URL`` at it replaces every ``ChatOllama`` call
(``backend/providers/registry.py:86-90``) without touching a line of backend code.

These tests exercise the stub directly over a real socket. They do NOT start the
backend — that is ``test_fixture_smoke.py``.
"""

from __future__ import annotations

import asyncio
import json
import time

import httpx
import pytest

from tests.e2e_real.fake_ollama import (
    EOF_REASONS,
    TERMINAL_EVENT_TYPES,
    Mode,
)

pytestmark = pytest.mark.require_server


# --------------------------------------------------------------------------
# Contract constants — these are contracts, not conveniences.
# --------------------------------------------------------------------------


def test_terminal_event_types_is_exactly_the_three_terminals():
    """Omitting ``clarification`` would flag the correct chat.py:204 path as a bug."""
    assert TERMINAL_EVENT_TYPES == frozenset({"done", "error", "clarification"})


def test_eof_reasons_keeps_the_three_outcomes_distinct():
    """Collapsing these is a harness defect — BUG-074 and BUG-123 fork on the distinction."""
    assert EOF_REASONS == frozenset({"clean_eof", "peer_closed", "still_open"})


# --------------------------------------------------------------------------
# Endpoint surface the backend actually calls.
# --------------------------------------------------------------------------


async def test_tags_lists_the_models_the_backend_probes(fake_ollama):
    """``health.py:117`` and ``models.py:31`` GET /api/tags and read ``models[].name``."""
    async with httpx.AsyncClient(base_url=fake_ollama.base_url, timeout=10.0) as client:
        resp = await client.get("/api/tags")

    assert resp.status_code == 200
    names = {m["name"] for m in resp.json()["models"]}
    assert fake_ollama.llm_model in names
    assert fake_ollama.embed_model in names


async def test_embed_returns_embeddings_list(fake_ollama):
    """``providers/ollama.py:106`` posts to /api/embed and reads ``data["embeddings"][0]``."""
    async with httpx.AsyncClient(base_url=fake_ollama.base_url, timeout=10.0) as client:
        resp = await client.post("/api/embed", json={"model": fake_ollama.embed_model, "input": "hello"})

    assert resp.status_code == 200
    embeddings = resp.json()["embeddings"]
    assert len(embeddings) == 1
    assert len(embeddings[0]) == fake_ollama.embed_dimension
    assert all(isinstance(v, float) for v in embeddings[0])


async def test_embed_is_deterministic_for_the_same_input(fake_ollama):
    """Determinism is the whole point — the same text must embed identically."""
    async with httpx.AsyncClient(base_url=fake_ollama.base_url, timeout=10.0) as client:
        first = await client.post("/api/embed", json={"model": fake_ollama.embed_model, "input": "hello"})
        second = await client.post("/api/embed", json={"model": fake_ollama.embed_model, "input": "hello"})
        other = await client.post("/api/embed", json={"model": fake_ollama.embed_model, "input": "goodbye"})

    assert first.json()["embeddings"] == second.json()["embeddings"]
    assert first.json()["embeddings"] != other.json()["embeddings"]


async def test_embeddings_fallback_endpoint_is_served(fake_ollama):
    """``providers/ollama.py:121`` falls back to /api/embeddings and reads ``payload["embedding"]``."""
    async with httpx.AsyncClient(base_url=fake_ollama.base_url, timeout=10.0) as client:
        resp = await client.post("/api/embeddings", json={"model": fake_ollama.embed_model, "prompt": "hello"})

    assert resp.status_code == 200
    assert len(resp.json()["embedding"]) == fake_ollama.embed_dimension


# --------------------------------------------------------------------------
# /api/chat — the endpoint ChatOllama drives.
# --------------------------------------------------------------------------


async def _collect_chat(base_url: str, *, timeout: float = 30.0, body: dict | None = None) -> list[dict]:
    """POST /api/chat and return every decoded NDJSON frame."""
    payload = body or {"model": "qwen3:14b", "messages": [{"role": "user", "content": "hi"}], "stream": True}
    frames: list[dict] = []
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        async with client.stream("POST", "/api/chat", json=payload) as resp:
            async for line in resp.aiter_lines():
                if line.strip():
                    frames.append(json.loads(line))
    return frames


async def test_normal_mode_streams_content_then_done(fake_ollama):
    frames = await _collect_chat(fake_ollama.base_url)

    assert frames, "expected at least one NDJSON frame"
    assert frames[-1]["done"] is True
    content = "".join(f.get("message", {}).get("content", "") for f in frames)
    assert content.strip(), "expected non-empty assistant content"
    # Ollama streams >1 frame so LangChain emits >1 token callback.
    assert len([f for f in frames if not f.get("done")]) > 1


async def test_json_format_returns_a_union_payload_satisfying_every_schema(fake_ollama):
    """``method="json_mode"`` puts only ``format:"json"`` on the wire — never the schema.

    The stub therefore cannot tell ``IntentClassification`` (nodes.py:214) from
    ``QueryAnalysis`` (nodes.py:283). It must emit one union object; Pydantic v2
    defaults to ``extra='ignore'`` so each parse takes its own subset.
    """
    from backend.agent.schemas import GroundednessResult, IntentClassification, QueryAnalysis

    frames = await _collect_chat(
        fake_ollama.base_url,
        body={
            "model": "qwen3:14b",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
            "format": "json",
        },
    )
    content = "".join(f.get("message", {}).get("content", "") for f in frames)
    payload = json.loads(content)

    intent = IntentClassification.model_validate(payload)
    assert intent.intent == "rag_query"

    analysis = QueryAnalysis.model_validate(payload)
    assert analysis.is_clear is True
    assert analysis.sub_questions

    GroundednessResult.model_validate(payload)


async def test_always_ambiguous_mode_flips_the_intent_field(fake_ollama):
    """Reproduces the BUG-082 unbounded ``classify_intent -> request_clarification`` cycle."""
    fake_ollama.set_mode(Mode.ALWAYS_AMBIGUOUS)

    frames = await _collect_chat(
        fake_ollama.base_url,
        body={
            "model": "qwen3:14b",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
            "format": "json",
        },
    )
    payload = json.loads("".join(f.get("message", {}).get("content", "") for f in frames))

    assert payload["intent"] == "ambiguous"
    assert payload["is_clear"] is False
    assert payload["clarification_needed"]


async def test_tool_calls_are_emitted_when_tools_are_bound(fake_ollama):
    """``research_nodes.py:159`` binds tools; the stub must not invent an unknown tool."""
    frames = await _collect_chat(
        fake_ollama.base_url,
        body={
            "model": "qwen3:14b",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
            "tools": [
                {
                    "type": "function",
                    "function": {"name": "search_child_chunks", "description": "", "parameters": {}},
                }
            ],
        },
    )
    tool_calls = [tc for f in frames for tc in f.get("message", {}).get("tool_calls", [])]

    assert tool_calls, "expected the stub to answer a tool-bound request with a tool call"
    assert tool_calls[0]["function"]["name"] == "search_child_chunks"


# --------------------------------------------------------------------------
# Failure-injection modes.
# --------------------------------------------------------------------------


async def test_slow_first_byte_delays_the_first_frame(fake_ollama):
    fake_ollama.set_mode(Mode.SLOW_FIRST_BYTE, delay_s=2.0)

    started = time.monotonic()
    async with httpx.AsyncClient(base_url=fake_ollama.base_url, timeout=30.0) as client:
        async with client.stream(
            "POST", "/api/chat", json={"model": "qwen3:14b", "messages": [], "stream": True}
        ) as resp:
            first_line = await anext(aiter(resp.aiter_lines()))
    elapsed = time.monotonic() - started

    assert elapsed >= 2.0, f"first byte arrived after {elapsed:.2f}s, expected >= 2.0s"
    assert json.loads(first_line)


async def test_die_midstream_yields_content_then_no_terminal_frame(fake_ollama):
    """The stub must close the body WITHOUT ``done: true`` — that is the defect shape."""
    fake_ollama.set_mode(Mode.DIE_MIDSTREAM)

    frames = await _collect_chat(fake_ollama.base_url)

    assert frames, "expected content before the stream died"
    assert not any(f.get("done") for f in frames), "die_midstream must never emit done:true"


async def test_stall_after_first_chunk_emits_one_frame_then_hangs(fake_ollama):
    fake_ollama.set_mode(Mode.STALL_AFTER_FIRST_CHUNK)

    frames: list[dict] = []
    async with httpx.AsyncClient(base_url=fake_ollama.base_url, timeout=httpx.Timeout(30.0, read=3.0)) as client:
        with pytest.raises(httpx.ReadTimeout):
            async with client.stream(
                "POST", "/api/chat", json={"model": "qwen3:14b", "messages": [], "stream": True}
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        frames.append(json.loads(line))

    assert len(frames) >= 1, "expected exactly the first chunk before the stall"
    assert not any(f.get("done") for f in frames)


async def test_stall_forever_hangs_a_live_connection_until_drain_releases_it(fake_ollama):
    """``_chat_semaphore`` leaks are the #1 flakiness source — drain must always work.

    The client stays CONNECTED throughout. That is the case drain exists for: a
    disconnect already triggers the generator's ``finally`` (covered by the next
    test), so a drain measured after a disconnect would report zero and prove
    nothing.
    """
    fake_ollama.set_mode(Mode.STALL_FOREVER)
    frames: list[dict] = []

    async def consume() -> None:
        async with httpx.AsyncClient(base_url=fake_ollama.base_url, timeout=60.0) as client:
            async with client.stream(
                "POST", "/api/chat", json={"model": "qwen3:14b", "messages": [], "stream": True}
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        frames.append(json.loads(line))

    task = asyncio.create_task(consume())
    try:
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline and fake_ollama.stats()["active_stalls"] < 1:
            await asyncio.sleep(0.05)

        assert fake_ollama.stats()["active_stalls"] == 1, "server should be holding exactly one stalled stream"
        assert not task.done(), "stall_forever must not complete on its own"

        assert fake_ollama.drain_chat_semaphore() == 1, "drain must report the stalled stream it released"
        await asyncio.wait_for(task, timeout=15.0)
    finally:
        task.cancel()

    assert frames == [], "stall_forever must never emit a frame"
    assert fake_ollama.stats()["active_stalls"] == 0


async def test_finally_clears_stall_registry_when_the_client_disconnects(fake_ollama):
    """Every stalled stream closes in a ``finally`` — a leaked entry hangs the NEXT test.

    Here the client walks away mid-stall. Cleanup must happen without any drain
    call at all, because a real test that times out will not get to call one.
    """
    fake_ollama.set_mode(Mode.STALL_FOREVER)

    async with httpx.AsyncClient(base_url=fake_ollama.base_url, timeout=httpx.Timeout(30.0, read=1.5)) as client:
        with pytest.raises(httpx.ReadTimeout):
            async with client.stream(
                "POST", "/api/chat", json={"model": "qwen3:14b", "messages": [], "stream": True}
            ) as resp:
                async for _line in resp.aiter_lines():
                    pytest.fail("stall_forever must not emit any frame")

    assert fake_ollama.wait_until_idle(timeout=15.0), "disconnect alone must clear the stall registry"
    assert fake_ollama.stats()["active_stalls"] == 0


async def test_reset_restores_normal_mode(fake_ollama):
    fake_ollama.set_mode(Mode.DIE_MIDSTREAM)
    fake_ollama.reset()

    assert fake_ollama.stats()["mode"] == Mode.NORMAL
    frames = await _collect_chat(fake_ollama.base_url)
    assert frames[-1]["done"] is True
