"""Chat endpoint with NDJSON streaming via ConversationGraph.

SC-002: First words within 1 second of query submission.
Streams 10 NDJSON event types: session, status, chunk, citation,
meta_reasoning, confidence, groundedness, done, clarification, error.
"""

import json
import time
import uuid

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage

from backend.agent.conversation_graph import build_conversation_graph
from backend.agent.schemas import ChatRequest
from backend.config import settings
from backend.errors import CircuitOpenError

logger = structlog.get_logger().bind(component=__name__)

router = APIRouter()


def _get_or_build_graph(app_state) -> object:
    """Return cached compiled graph, building once on first call.

    The graph is cached on app.state to avoid recompiling per request.
    The checkpointer and research_graph stub are taken from app.state.
    """
    if not hasattr(app_state, "_conversation_graph") or app_state._conversation_graph is None:
        research_graph = getattr(app_state, "research_graph", None)
        if research_graph is None:
            from tests.mocks import build_mock_research_graph
            research_graph = build_mock_research_graph()

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
            yield json.dumps({
                "type": "error",
                "code": "SHUTTING_DOWN",
                "message": "Server is shutting down. Please retry in a moment.",
            }) + "\n"
            return

        start_time = time.monotonic()

        # Empty-collections guard
        if not body.collection_ids:
            yield json.dumps({
                "type": "error",
                "message": "Please select at least one collection before searching.",
                "code": "NO_COLLECTIONS",
                "trace_id": trace_id,
            }) + "\n"
            return

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
        }

        # Resolve active provider + LangChain model for agent nodes
        provider_name = "ollama"
        langchain_llm = None
        registry = getattr(request.app.state, "registry", None)
        if registry is not None:
            active_provider = await db.get_active_provider()
            provider_name = active_provider["name"] if active_provider else "ollama"
            langchain_llm = await registry.get_active_langchain_model(db)

        config = {
            "configurable": {
                "thread_id": session_id,
                "llm": langchain_llm,
                "tools": getattr(request.app.state, "research_tools", None),
            }
        }
        last_node = None

        try:
            # 2. Stream events from graph
            async for chunk_msg, metadata in graph.astream(
                initial_state,
                stream_mode="messages",
                config=config,
            ):
                # Status event on node transition
                current_node = metadata.get("langgraph_node")
                if current_node and current_node != last_node:
                    yield json.dumps({"type": "status", "node": current_node}) + "\n"
                    last_node = current_node

                # Chunk event for AI content
                if hasattr(chunk_msg, "content") and chunk_msg.content:
                    yield json.dumps({"type": "chunk", "text": chunk_msg.content}) + "\n"

                # Clarification interrupt detection
                if "__interrupt__" in metadata:
                    interrupt_value = metadata["__interrupt__"][0].value
                    yield json.dumps({
                        "type": "clarification",
                        "question": interrupt_value,
                    }) + "\n"
                    return  # Stream ends on clarification

            # 3. Get final state after stream completes
            final_state = graph.get_state(config).values
            latency_ms = int((time.monotonic() - start_time) * 1000)
            stage_timings = final_state.get("stage_timings", {})  # FR-005

            # 4. Citation event
            citations = final_state.get("citations", [])
            if citations:
                citation_dicts = [
                    c.model_dump() if hasattr(c, "model_dump") else c
                    for c in citations
                ]
                yield json.dumps({"type": "citation", "citations": citation_dicts}) + "\n"

            # 5. Meta-reasoning event (if strategies were attempted)
            attempted = final_state.get("attempted_strategies")
            if attempted:
                strategies_list = list(attempted) if isinstance(attempted, set) else attempted
                yield json.dumps({
                    "type": "meta_reasoning",
                    "strategies_attempted": strategies_list,
                }) + "\n"

            # 6. Confidence event (ALWAYS int 0-100)
            confidence = int(final_state.get("confidence_score", 0))
            yield json.dumps({"type": "confidence", "score": confidence}) + "\n"

            # 7. Groundedness event
            groundedness_result = final_state.get("groundedness_result")
            if groundedness_result is not None:
                yield json.dumps({
                    "type": "groundedness",
                    "overall_grounded": groundedness_result.overall_grounded,
                    "supported": sum(1 for v in groundedness_result.verifications if v.verdict == "supported"),
                    "unsupported": sum(1 for v in groundedness_result.verifications if v.verdict == "unsupported"),
                    "contradicted": sum(1 for v in groundedness_result.verifications if v.verdict == "contradicted"),
                }) + "\n"

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
                    sub_questions_json=json.dumps(
                        final_state.get("sub_questions", [])
                    ) if final_state.get("sub_questions") else None,
                    reasoning_steps_json=None,
                    strategy_switches_json=json.dumps(
                        list(attempted)
                    ) if attempted else None,
                    meta_reasoning_triggered=bool(attempted),
                    provider_name=provider_name,
                    stage_timings_json=json.dumps(stage_timings) if stage_timings else None,
                )
            except Exception:
                logger.warning("http_query_trace_write_failed", session_id=session_id)

            # 9. Done event (LAST on success)
            yield json.dumps({
                "type": "done",
                "latency_ms": latency_ms,
                "trace_id": trace_id,
            }) + "\n"

        except CircuitOpenError:
            logger.warning("http_circuit_open_during_chat", session_id=session_id, error="CircuitOpenError")
            yield json.dumps({
                "type": "error",
                "message": "A required service is temporarily unavailable. Please try again in a few seconds.",
                "code": "CIRCUIT_OPEN",
                "trace_id": trace_id,
            }) + "\n"
        except Exception as e:
            logger.error("http_chat_stream_error", error=type(e).__name__, detail=str(e), session_id=session_id)
            yield json.dumps({
                "type": "error",
                "message": "Unable to process your request. Please retry.",
                "code": "SERVICE_UNAVAILABLE",
                "trace_id": trace_id,
            }) + "\n"

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
    )
