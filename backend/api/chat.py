"""Chat endpoint with NDJSON streaming via ConversationGraph.

SC-002: First words within 1 second of query submission.
Streams 10 NDJSON event types: session, status, chunk, citation,
meta_reasoning, confidence, groundedness, done, clarification, error.
"""

import asyncio
import json
import time
import uuid

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage

from backend.agent._request_context import selected_collections_var
from backend.agent.conversation_graph import build_conversation_graph
from backend.agent.schemas import ChatRequest
from backend.config import settings
from backend.errors import CircuitOpenError
from langgraph.errors import GraphRecursionError

logger = structlog.get_logger().bind(component=__name__)

router = APIRouter()

# BUG-015: limit concurrent graph invocations to prevent resource exhaustion
_chat_semaphore = asyncio.Semaphore(5)


class CallLimitCallback(BaseCallbackHandler):
    """ENH-006: Prevent runaway LLM/tool loops by enforcing per-request call limits.

    NOTE: This single callback instance is shared across ALL parallel Send()
    tasks (fan-out sub-questions). Limits must account for N concurrent
    research loops (default max 5 sub-questions × per-loop budget).
    Exceeding the limit logs a warning instead of raising RuntimeError,
    because RuntimeError inside callbacks can corrupt LangGraph supersteps
    during parallel execution (supersteps are transactional — any branch
    exception aborts the entire superstep with no retry for RuntimeError).
    """

    def __init__(self, max_llm_calls: int = 100, max_tool_calls: int = 50):
        self.max_llm_calls = max_llm_calls
        self.max_tool_calls = max_tool_calls
        self._llm_calls = 0
        self._tool_calls = 0
        self._llm_limit_logged = False
        self._tool_limit_logged = False

    def on_llm_start(self, *args, **kwargs):
        self._llm_calls += 1
        if self._llm_calls > self.max_llm_calls and not self._llm_limit_logged:
            self._llm_limit_logged = True
            logger.warning(
                "call_limit_llm_exceeded",
                llm_calls=self._llm_calls,
                max=self.max_llm_calls,
            )

    def on_tool_start(self, *args, **kwargs):
        self._tool_calls += 1
        if self._tool_calls > self.max_tool_calls and not self._tool_limit_logged:
            self._tool_limit_logged = True
            logger.warning(
                "call_limit_tool_exceeded",
                tool_calls=self._tool_calls,
                max=self.max_tool_calls,
            )


def _get_or_build_graph(app_state) -> object:
    """Return cached compiled graph, building once on first call.

    The graph is cached on app.state to avoid recompiling per request.
    The checkpointer and research_graph stub are taken from app.state.
    """
    # Prefer the graph built by lifespan (stored as conversation_graph, no underscore)
    if hasattr(app_state, "conversation_graph") and app_state.conversation_graph is not None:
        return app_state.conversation_graph

    if not hasattr(app_state, "_conversation_graph") or app_state._conversation_graph is None:
        research_graph = getattr(app_state, "research_graph", None)
        checkpointer = getattr(app_state, "checkpointer", None)
        app_state._conversation_graph = build_conversation_graph(
            research_graph=research_graph,
            checkpointer=checkpointer,
        )
    return app_state._conversation_graph


@router.post("/api/chat")
async def chat(body: ChatRequest, request: Request):
    """Stream answer as NDJSON. Each line is a JSON object followed by newline."""
    db = request.app.state.db
    graph = _get_or_build_graph(request.app.state)

    session_id = body.session_id or str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(session_id=session_id)
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))

    llm_model = body.llm_model or settings.default_llm_model
    embed_model = body.embed_model or settings.default_embed_model

    async def generate():
        # FR-050: Reject requests during graceful shutdown
        if getattr(request.app.state, "shutting_down", False):
            yield (
                json.dumps(
                    {
                        "type": "error",
                        "code": "SHUTTING_DOWN",
                        "message": "Server is shutting down. Please retry in a moment.",
                    }
                )
                + "\n"
            )
            return

        start_time = time.monotonic()

        # Empty-collections guard
        if not body.collection_ids:
            yield (
                json.dumps(
                    {
                        "type": "error",
                        "message": "Please select at least one collection before searching.",
                        "code": "NO_COLLECTIONS",
                        "trace_id": trace_id,
                    }
                )
                + "\n"
            )
            return

        # spec-28 BUG-002 fix: bind authorized collections for tool-call validation.
        # selected_collections_var is consumed by search_child_chunks in
        # backend/agent/tools.py to enforce the user's collection_ids filter.
        # Contextvars propagate to asyncio tasks spawned from this request context,
        # so LangGraph sub-tasks (research subgraph tool calls) inherit this value.
        selected_collections_var.set(list(body.collection_ids))

        # 1. Session event (BEFORE astream)
        yield json.dumps({"type": "session", "session_id": session_id}) + "\n"

        message = body.message[:10_000]  # FR-001: silent truncation

        initial_state = {
            "session_id": session_id,
            "messages": [HumanMessage(content=message)],
            "intent": "rag_query",
            "query_analysis": None,
            "sub_answers": [],
            "selected_collections": body.collection_ids,
            "llm_model": llm_model,
            "embed_model": embed_model,
            "final_response": None,
            "citations": [],
            "groundedness_result": None,
            "confidence_score": 0,
            "iteration_count": 0,
            "stage_timings": {},
        }

        # Resolve active provider + LangChain model for agent nodes
        provider_name = "ollama"
        langchain_llm = None
        registry = getattr(request.app.state, "registry", None)
        if registry is not None:
            active_provider = await db.get_active_provider()
            provider_name = active_provider["name"] if active_provider else "ollama"
            langchain_llm = await registry.get_active_langchain_model(db)

        call_limit_cb = CallLimitCallback()
        config = {
            "configurable": {
                "thread_id": session_id,
                "llm": langchain_llm,
                "tools": getattr(request.app.state, "research_tools", None),
            },
            "recursion_limit": 100,
            "callbacks": [call_limit_cb],
        }
        last_node = None
        has_streamed_response = False

        try:
            async with _chat_semaphore:
                # 2. Stream events from graph
                # version="v2" returns StreamPart dicts with type/ns/data keys
                # subgraphs=True enables visibility into ResearchGraph nodes
                # (collect_answer lives in the research subgraph)
                async for chunk in graph.astream(
                    initial_state,
                    stream_mode=["messages", "updates"],
                    subgraphs=True,
                    version="v2",
                    config=config,
                ):
                    if chunk["type"] == "updates":
                        data = chunk["data"]
                        # Interrupt detection (clarification request)
                        if "__interrupt__" in data:
                            interrupt_value = data["__interrupt__"][0].value
                            yield (
                                json.dumps(
                                    {
                                        "type": "clarification",
                                        "question": interrupt_value,
                                    }
                                )
                                + "\n"
                            )
                            return
                    elif chunk["type"] == "messages":
                        chunk_msg, metadata = chunk["data"]
                        current_node = metadata.get("langgraph_node")
                        if current_node and current_node != last_node:
                            yield json.dumps({"type": "status", "node": current_node}) + "\n"
                            last_node = current_node
                        if (
                            current_node == "collect_answer"
                            and isinstance(chunk_msg, (AIMessage, AIMessageChunk))
                            and chunk_msg.content
                        ):
                            yield json.dumps({"type": "chunk", "text": chunk_msg.content}) + "\n"
                            has_streamed_response = True

                # 3. Get final state after stream completes
                snapshot = await graph.aget_state(config)
                final_state = snapshot.values
                latency_ms = int((time.monotonic() - start_time) * 1000)
                stage_timings = final_state.get("stage_timings", {})  # FR-005

            # 3b. Emit final_response if not already streamed token-by-token
            final_response = final_state.get("final_response") or ""
            if final_response and not has_streamed_response:
                yield json.dumps({"type": "chunk", "text": final_response}) + "\n"

            # 4. Citation event
            citations = final_state.get("citations", [])
            if citations:
                citation_dicts = [c.model_dump() if hasattr(c, "model_dump") else c for c in citations]
                # Deduplicate by passage_id (BUG-017: Send() fan-out produces N copies)
                seen_pids = set()
                unique_citations = []
                for cd in citation_dicts:
                    pid = cd.get("passage_id")
                    if pid not in seen_pids:
                        seen_pids.add(pid)
                        unique_citations.append(cd)
                yield json.dumps({"type": "citation", "citations": unique_citations}) + "\n"

            # 5. Meta-reasoning event (if strategies were attempted)
            attempted = final_state.get("attempted_strategies")
            if attempted:
                strategies_list = list(attempted) if isinstance(attempted, set) else attempted
                yield (
                    json.dumps(
                        {
                            "type": "meta_reasoning",
                            "strategies_attempted": strategies_list,
                        }
                    )
                    + "\n"
                )

            # 6. Confidence event (ALWAYS int 0-100)
            confidence = int(final_state.get("confidence_score", 0))
            yield json.dumps({"type": "confidence", "score": confidence}) + "\n"

            # 7. Groundedness event
            groundedness_result = final_state.get("groundedness_result")
            if groundedness_result is not None:
                yield (
                    json.dumps(
                        {
                            "type": "groundedness",
                            "overall_grounded": groundedness_result.overall_grounded,
                            "supported": sum(1 for v in groundedness_result.verifications if v.verdict == "supported"),
                            "unsupported": sum(
                                1 for v in groundedness_result.verifications if v.verdict == "unsupported"
                            ),
                            "contradicted": sum(
                                1 for v in groundedness_result.verifications if v.verdict == "contradicted"
                            ),
                        }
                    )
                    + "\n"
                )

            # 8. Write trace to DB via create_query_trace()
            try:
                await db.create_query_trace(
                    id=trace_id,
                    session_id=session_id,
                    query=message,
                    collections_searched=json.dumps(body.collection_ids),
                    chunks_retrieved_json=json.dumps(
                        [c.model_dump() if hasattr(c, "model_dump") else c for c in citations]
                    ),
                    latency_ms=latency_ms,
                    llm_model=llm_model,
                    embed_model=embed_model,
                    confidence_score=confidence,
                    sub_questions_json=json.dumps(final_state.get("sub_questions", []))
                    if final_state.get("sub_questions")
                    else None,
                    reasoning_steps_json=None,
                    strategy_switches_json=json.dumps(list(attempted)) if attempted else None,
                    meta_reasoning_triggered=bool(attempted),
                    provider_name=provider_name,
                    stage_timings_json=json.dumps(stage_timings) if stage_timings else None,
                )
            except Exception:
                logger.warning("http_query_trace_write_failed", session_id=session_id)

            # 9. Done event (LAST on success)
            yield (
                json.dumps(
                    {
                        "type": "done",
                        "latency_ms": latency_ms,
                        "trace_id": trace_id,
                    }
                )
                + "\n"
            )

        except GraphRecursionError:
            logger.warning("http_chat_recursion_limit", session_id=session_id)
            yield (
                json.dumps(
                    {
                        "type": "error",
                        "message": "The query required too many reasoning steps. Try a more specific question.",
                        "code": "RECURSION_LIMIT",
                        "trace_id": trace_id,
                    }
                )
                + "\n"
            )
        except RuntimeError as e:
            if "call limit exceeded" in str(e):
                logger.warning("http_chat_call_limit", session_id=session_id, detail=str(e))
                yield (
                    json.dumps(
                        {
                            "type": "error",
                            "message": "The query exceeded the maximum number of allowed operations. Try a simpler question.",
                            "code": "CALL_LIMIT_EXCEEDED",
                            "trace_id": trace_id,
                        }
                    )
                    + "\n"
                )
            else:
                raise
        except CircuitOpenError:
            logger.warning("http_circuit_open_during_chat", session_id=session_id, error="CircuitOpenError")
            yield (
                json.dumps(
                    {
                        "type": "error",
                        "message": "A required service is temporarily unavailable. Please try again in a few seconds.",
                        "code": "CIRCUIT_OPEN",
                        "trace_id": trace_id,
                    }
                )
                + "\n"
            )
        except Exception as e:
            logger.error("http_chat_stream_error", error=type(e).__name__, detail=str(e), session_id=session_id)
            yield (
                json.dumps(
                    {
                        "type": "error",
                        "message": "Unable to process your request. Please retry.",
                        "code": "SERVICE_UNAVAILABLE",
                        "trace_id": trace_id,
                    }
                )
                + "\n"
            )

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
    )
