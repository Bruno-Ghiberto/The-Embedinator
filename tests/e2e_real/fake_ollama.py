"""Deterministic fake Ollama — the determinism linchpin of the real-socket harness.

The core insight: **control the LLM, not the graph.**

Injecting a mock graph across a process boundary is impossible —
``backend/api/chat.py:82-83`` prefers the graph the lifespan built. But
``backend/providers/registry.py:86-90`` constructs
``ChatOllama(base_url=settings.ollama_base_url, ...)`` straight from
``OLLAMA_BASE_URL``. Point that at this stub and the **real** production graph
runs end to end against a deterministic model. No backend code changes.

Runs as its own uvicorn subprocess, never a thread: ``stall_forever`` would
starve a worker thread and take the harness down with it.

Endpoint surface (every one of these is actually called by the backend)
----------------------------------------------------------------------
=========================  =========================================================
``GET  /api/tags``         ``backend/api/health.py:117``, ``backend/api/models.py:31``
``POST /api/chat``         ``ChatOllama`` via ``langchain_ollama``
``POST /api/generate``     ``OllamaLLMProvider`` (``backend/providers/ollama.py:26,47``)
``POST /api/embed``        ``OllamaEmbeddingProvider`` (``backend/providers/ollama.py:106``)
``POST /api/embeddings``   404 fallback path (``backend/providers/ollama.py:121``)
``POST /api/show``         ``ollama`` client model introspection
=========================  =========================================================
"""

from __future__ import annotations

import asyncio
import hashlib
import itertools
import json
import os
import struct
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

# ---------------------------------------------------------------------------
# Contracts. These are contracts, not conveniences.
# ---------------------------------------------------------------------------

#: NDJSON event types that legitimately end a ``/api/chat`` stream.
#:
#: ``clarification`` MUST be here. ``backend/api/chat.py:204-218`` emits it on the
#: LangGraph interrupt path and returns; omitting it would make the harness flag
#: correct behaviour as a bug.
TERMINAL_EVENT_TYPES: frozenset[str] = frozenset({"done", "error", "clarification"})

#: How a stream ended. Collapsing these into one outcome is a harness defect:
#: BUG-074 (frontend ignores a terminal-less EOF) and BUG-123 (proxy holds the
#: socket open) are different defects and a later batch forks on the distinction.
#:
#: ``clean_eof``   — the body terminated normally at a frame boundary.
#: ``peer_closed`` — the connection was torn down mid-body (reset / truncated).
#: ``still_open``  — our deadline expired while the server still held the stream.
EOF_REASONS: frozenset[str] = frozenset({"clean_eof", "peer_closed", "still_open"})

CONTROL_PREFIX = "/__harness__"

DEFAULT_LLM_MODEL = "qwen3:14b"
DEFAULT_EMBED_MODEL = "nomic-embed-text"
DEFAULT_EMBED_DIMENSION = 768


class Mode(str, Enum):
    """Failure-injection modes.

    ``str`` mixin so ``stats()["mode"] == Mode.NORMAL`` holds across the JSON
    round-trip through the control API.
    """

    NORMAL = "normal"
    ALWAYS_AMBIGUOUS = "always_ambiguous"
    STALL_FOREVER = "stall_forever"
    STALL_AFTER_FIRST_CHUNK = "stall_after_first_chunk"
    SLOW_FIRST_BYTE = "slow_first_byte"
    DIE_MIDSTREAM = "die_midstream"


# ---------------------------------------------------------------------------
# Deterministic payloads
# ---------------------------------------------------------------------------

ANSWER_CHUNKS: tuple[str, ...] = (
    "The harness ",
    "answer is ",
    "deterministic ",
    "by construction.",
)

DEFAULT_CLARIFICATION = "Which collection should I search for that?"


def union_structured_payload(*, ambiguous: bool = False) -> dict[str, Any]:
    """One JSON object that satisfies every structured-output schema at once.

    The graph calls ``with_structured_output(..., method="json_mode")`` at
    ``nodes.py:214`` (``IntentClassification``), ``nodes.py:283``
    (``QueryAnalysis``) and ``nodes.py:542`` (``GroundednessResult``). ``json_mode``
    puts only ``format: "json"`` on the wire — **the schema never reaches the
    model**, so this stub cannot tell the three call sites apart.

    Pydantic v2 ``BaseModel`` defaults to ``extra='ignore'``, so a union object
    lets each parse take its own subset and drop the rest. That is what makes a
    single response correct for all three.
    """
    return {
        # --- IntentClassification (nodes.py:214) ---
        "intent": "ambiguous" if ambiguous else "rag_query",
        "reason": "deterministic harness stub",
        # --- QueryAnalysis (nodes.py:283) ---
        "is_clear": not ambiguous,
        "sub_questions": ["What does the harness return?"],
        "clarification_needed": DEFAULT_CLARIFICATION if ambiguous else None,
        "collections_hint": [],
        "complexity_tier": "lookup",
        # --- GroundednessResult (nodes.py:542) ---
        "verifications": [],
        "overall_grounded": True,
        "confidence_adjustment": 0.0,
    }


def deterministic_embedding(text: str, dimension: int = DEFAULT_EMBED_DIMENSION) -> list[float]:
    """A stable unit-norm-ish vector derived from ``text``.

    Same text in, same vector out, across processes and runs — retrieval scores
    must not drift between the RED run and the GREEN run.
    """
    digest = hashlib.blake2b(text.encode("utf-8"), digest_size=8).digest()
    seed = struct.unpack("<Q", digest)[0]
    values: list[float] = []
    state = seed or 1
    for _ in range(dimension):
        # xorshift64* — deterministic, no RNG global state, no numpy dependency.
        state ^= (state << 13) & 0xFFFFFFFFFFFFFFFF
        state ^= state >> 7
        state ^= (state << 17) & 0xFFFFFFFFFFFFFFFF
        values.append(((state % 2_000_000) / 1_000_000.0) - 1.0)
    return values


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _content_frame(model: str, content: str) -> dict[str, Any]:
    return {
        "model": model,
        "created_at": _now(),
        "message": {"role": "assistant", "content": content},
        "done": False,
    }


def _tool_frame(model: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": model,
        "created_at": _now(),
        "message": {
            "role": "assistant",
            "content": "",
            # langchain_ollama:216-217 reads tc["function"]["name"] and the arguments.
            "tool_calls": [{"function": {"name": name, "arguments": arguments}}],
        },
        "done": False,
    }


def _done_frame(model: str) -> dict[str, Any]:
    return {
        "model": model,
        "created_at": _now(),
        "message": {"role": "assistant", "content": ""},
        "done": True,
        "done_reason": "stop",
        "total_duration": 1_000_000,
        "load_duration": 100_000,
        "prompt_eval_count": 8,
        "prompt_eval_duration": 100_000,
        "eval_count": len(ANSWER_CHUNKS),
        "eval_duration": 500_000,
    }


# ---------------------------------------------------------------------------
# The app
# ---------------------------------------------------------------------------


def build_app(
    *,
    llm_model: str = DEFAULT_LLM_MODEL,
    embed_model: str = DEFAULT_EMBED_MODEL,
    embed_dimension: int = DEFAULT_EMBED_DIMENSION,
) -> FastAPI:
    app = FastAPI(title="fake-ollama")

    state: dict[str, Any] = {"mode": Mode.NORMAL, "params": {}, "chat_calls": 0}
    stalls: dict[int, asyncio.Event] = {}
    stall_ids = itertools.count()

    def _release_all() -> int:
        released = len(stalls)
        for event in list(stalls.values()):
            event.set()
        return released

    # -- control plane -----------------------------------------------------

    @app.post(f"{CONTROL_PREFIX}/mode")
    async def set_mode(request: Request):
        body = await request.json()
        state["mode"] = Mode(body["mode"])
        state["params"] = body.get("params") or {}
        return {"mode": state["mode"].value, "params": state["params"]}

    @app.post(f"{CONTROL_PREFIX}/drain")
    async def drain():
        """Release every stalled stream so the backend frees its ``_chat_semaphore`` permit.

        ``backend/api/chat.py:31`` caps concurrent turns at 5. A permit held by a
        stalled turn makes the *next* test hang for reasons that look unrelated —
        the single largest flakiness source in this codebase.
        """
        return {"released": _release_all()}

    @app.get(f"{CONTROL_PREFIX}/stats")
    async def stats():
        return {
            "mode": state["mode"].value,
            "params": state["params"],
            "chat_calls": state["chat_calls"],
            "active_stalls": len(stalls),
        }

    @app.post(f"{CONTROL_PREFIX}/reset")
    async def reset():
        released = _release_all()
        state["mode"] = Mode.NORMAL
        state["params"] = {}
        state["chat_calls"] = 0
        return {"released": released}

    # -- ollama surface ----------------------------------------------------

    @app.get("/api/tags")
    async def tags():
        return {
            "models": [
                {
                    "name": name,
                    "model": name,
                    "modified_at": _now(),
                    "size": 1,
                    "digest": hashlib.sha256(name.encode()).hexdigest(),
                    "details": {"family": "fake", "parameter_size": "0B", "quantization_level": "Q4_K_M"},
                }
                for name in (llm_model, embed_model)
            ]
        }

    @app.post("/api/show")
    async def show(request: Request):
        body = await request.json()
        return {
            "license": "harness",
            "modelfile": "# fake",
            "parameters": "",
            "template": "",
            "details": {"family": "fake", "parameter_size": "0B"},
            "model_info": {"general.architecture": "fake"},
            "capabilities": ["completion", "tools"],
            "model": body.get("model", llm_model),
        }

    @app.post("/api/embed")
    async def embed(request: Request):
        body = await request.json()
        raw = body.get("input", "")
        texts = raw if isinstance(raw, list) else [raw]
        return {
            "model": body.get("model", embed_model),
            "embeddings": [deterministic_embedding(t, embed_dimension) for t in texts],
            "total_duration": 1_000,
            "prompt_eval_count": len(texts),
        }

    @app.post("/api/embeddings")
    async def embeddings_legacy(request: Request):
        body = await request.json()
        return {"embedding": deterministic_embedding(body.get("prompt", ""), embed_dimension)}

    @app.post("/api/generate")
    async def generate(request: Request):
        """``OllamaLLMProvider`` (``backend/providers/ollama.py:26,47``)."""
        body = await request.json()
        model = body.get("model", llm_model)
        if not body.get("stream", True):
            return {
                "model": model,
                "created_at": _now(),
                "response": "".join(ANSWER_CHUNKS),
                "done": True,
                "done_reason": "stop",
            }

        async def gen() -> AsyncIterator[bytes]:
            for piece in ANSWER_CHUNKS:
                yield (
                    json.dumps({"model": model, "created_at": _now(), "response": piece, "done": False}).encode()
                    + b"\n"
                )
            yield (
                json.dumps(
                    {"model": model, "created_at": _now(), "response": "", "done": True, "done_reason": "stop"}
                ).encode()
                + b"\n"
            )

        return StreamingResponse(gen(), media_type="application/x-ndjson")

    @app.post("/api/chat")
    async def chat(request: Request):
        body = await request.json()
        state["chat_calls"] += 1
        mode: Mode = state["mode"]
        params: dict[str, Any] = state["params"]
        model = body.get("model", llm_model)

        frames = _plan_frames(body, model, ambiguous=mode is Mode.ALWAYS_AMBIGUOUS)

        async def stream() -> AsyncIterator[bytes]:
            stall_id = next(stall_ids)
            try:
                if mode is Mode.SLOW_FIRST_BYTE:
                    # BUG-054 needs a FIRST-BYTE gap: Next.js proxyTimeout is an
                    # idle timeout, so a slow trickle will not reproduce it.
                    await asyncio.sleep(float(params.get("delay_s", 35.0)))

                if mode is Mode.STALL_FOREVER:
                    event = asyncio.Event()
                    stalls[stall_id] = event
                    await event.wait()
                    return  # released by drain: end the body with no terminal frame

                for index, frame in enumerate(frames):
                    yield json.dumps(frame).encode() + b"\n"

                    if mode is Mode.DIE_MIDSTREAM and index == 0:
                        # Close the body mid-stream with no done:true — the exact
                        # shape frontend/lib/api.ts:157-160 silently swallows.
                        return

                    if mode is Mode.STALL_AFTER_FIRST_CHUNK and index == 0:
                        event = asyncio.Event()
                        stalls[stall_id] = event
                        await event.wait()
                        return
            finally:
                # ALWAYS discard the registration. A leaked entry keeps
                # active_stalls above zero forever and poisons every later test.
                stalls.pop(stall_id, None)

        return StreamingResponse(stream(), media_type="application/x-ndjson")

    @app.get("/")
    async def root():
        return JSONResponse({"status": "fake-ollama", "mode": state["mode"].value})

    return app


def _plan_frames(body: dict[str, Any], model: str, *, ambiguous: bool) -> list[dict[str, Any]]:
    """Decide what a real Ollama would have streamed for this request.

    Three discriminable request shapes, in priority order:

    1. ``tools`` present  -> ``research_nodes.py:159`` bound tools; answer with a
       tool call naming one of the tools that were actually offered (inventing a
       name would make the graph raise instead of exercising the tool path).
    2. ``format`` present -> ``with_structured_output(..., method="json_mode")``;
       answer with the union JSON object.
    3. otherwise          -> free text, chunked so LangChain emits several token
       callbacks and the backend produces several ``chunk`` NDJSON events.
    """
    tools = body.get("tools") or []
    if tools:
        name = _first_tool_name(tools)
        if name:
            return [_tool_frame(model, name, _tool_arguments(name, body)), _done_frame(model)]

    if body.get("format"):
        payload = json.dumps(union_structured_payload(ambiguous=ambiguous))
        # Split so the transport still behaves like a stream.
        midpoint = len(payload) // 2
        return [
            _content_frame(model, payload[:midpoint]),
            _content_frame(model, payload[midpoint:]),
            _done_frame(model),
        ]

    return [_content_frame(model, piece) for piece in ANSWER_CHUNKS] + [_done_frame(model)]


def _first_tool_name(tools: list[Any]) -> str | None:
    for tool in tools:
        if isinstance(tool, dict):
            function = tool.get("function")
            if isinstance(function, dict) and function.get("name"):
                return str(function["name"])
            if tool.get("name"):
                return str(tool["name"])
    return None


def _tool_arguments(name: str, body: dict[str, Any]) -> dict[str, Any]:
    """Best-effort arguments for the tool the graph offered."""
    query = ""
    for message in reversed(body.get("messages") or []):
        if message.get("role") == "user" and message.get("content"):
            query = str(message["content"])[:200]
            break
    if "search" in name or "retrieve" in name:
        return {"query": query or "harness query"}
    return {}


# ---------------------------------------------------------------------------
# Control client — the handle tests and fixtures drive the stub with.
# ---------------------------------------------------------------------------


class FakeOllamaHandle:
    """Synchronous client for a running fake-Ollama subprocess."""

    def __init__(
        self,
        base_url: str,
        *,
        llm_model: str = DEFAULT_LLM_MODEL,
        embed_model: str = DEFAULT_EMBED_MODEL,
        embed_dimension: int = DEFAULT_EMBED_DIMENSION,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.llm_model = llm_model
        self.embed_model = embed_model
        self.embed_dimension = embed_dimension
        self._client = httpx.Client(base_url=self.base_url, timeout=10.0)

    def set_mode(self, mode: Mode | str, **params: Any) -> None:
        value = mode.value if isinstance(mode, Mode) else str(mode)
        resp = self._client.post(f"{CONTROL_PREFIX}/mode", json={"mode": value, "params": params})
        resp.raise_for_status()

    def drain_chat_semaphore(self) -> int:
        """Release every stalled stream; returns how many were released.

        Named for what it protects: the backend's ``_chat_semaphore``
        (``backend/api/chat.py:31``). Call it in teardown, always.
        """
        resp = self._client.post(f"{CONTROL_PREFIX}/drain")
        resp.raise_for_status()
        return int(resp.json()["released"])

    def stats(self) -> dict[str, Any]:
        resp = self._client.get(f"{CONTROL_PREFIX}/stats")
        resp.raise_for_status()
        return resp.json()

    def reset(self) -> None:
        resp = self._client.post(f"{CONTROL_PREFIX}/reset")
        resp.raise_for_status()

    def wait_until_idle(self, timeout: float = 15.0) -> bool:
        """Block until no stalled streams remain. Returns False on timeout."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.stats()["active_stalls"] == 0:
                return True
            time.sleep(0.05)
        return False

    def close(self) -> None:
        self._client.close()


# Module-level ASGI target so uvicorn can import it as ``tests.e2e_real.fake_ollama:app``.
app = build_app(
    llm_model=os.environ.get("FAKE_OLLAMA_LLM_MODEL", DEFAULT_LLM_MODEL),
    embed_model=os.environ.get("FAKE_OLLAMA_EMBED_MODEL", DEFAULT_EMBED_MODEL),
    embed_dimension=int(os.environ.get("FAKE_OLLAMA_EMBED_DIM", DEFAULT_EMBED_DIMENSION)),
)
