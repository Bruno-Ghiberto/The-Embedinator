"""Node functions for the ResearchGraph (Layer 2).

All node functions are async, stateless, and pure. Dependencies (LLM, tools)
are resolved from RunnableConfig at invocation time.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from langchain_core.runnables import RunnableConfig

import structlog
from langchain_core.messages import HumanMessage, RemoveMessage, SystemMessage, ToolMessage
from langchain_core.messages import trim_messages
from langchain_core.messages.utils import count_tokens_approximately

from backend.agent.confidence import compute_confidence
from backend.agent.nodes import get_context_budget
from backend.agent.prompts import (
    COLLECT_ANSWER_SYSTEM,
    COMPRESS_CONTEXT_SYSTEM,
    ORCHESTRATOR_SYSTEM,
    ORCHESTRATOR_USER,
)
from backend.agent.schemas import Citation, RetrievedChunk, SubAnswer
from backend.agent.state import ResearchState
from backend.config import settings
from backend.errors import LLMCallError

logger = structlog.get_logger().bind(component=__name__)


def normalize_query(query: str) -> str:
    """Normalize query string for deduplication keys."""
    return " ".join(query.lower().strip().split())


def dedup_key(query: str, parent_id: str) -> str:
    """Build deduplication key from normalized query + parent_id."""
    return f"{normalize_query(query)}:{parent_id}"


async def _maybe_summarize_research_messages(
    messages: list, llm: Any, log: Any,
) -> list:
    """ENH-008: Summarize research messages when accumulation exceeds 15.

    Keeps the last 4 messages intact, summarizes the rest into a single
    SystemMessage. Returns the original list unchanged if <= 15 messages.
    On LLM failure, returns the original messages untouched.
    """
    if len(messages) <= 15:
        return messages

    messages_to_summarize = messages[:-4]
    recent_messages = messages[-4:]

    try:
        summary_response = await llm.ainvoke([
            SystemMessage(
                content="Briefly summarize the key findings from this research "
                "session in 2-3 sentences:"
            ),
            *messages_to_summarize,
        ])
        summary_msg = SystemMessage(
            content=f"Research session summary: {summary_response.content}"
        )
        log.info(
            "agent_research_messages_summarized",
            original=len(messages),
            summarized=len(messages_to_summarize),
            kept=len(recent_messages),
        )
        # Return RemoveMessage markers for old messages + summary + recent
        removals = [RemoveMessage(id=m.id) for m in messages_to_summarize if hasattr(m, "id") and m.id]
        return removals + [summary_msg] + list(recent_messages)
    except Exception as exc:
        log.debug("agent_research_summarize_failed", error=type(exc).__name__)
        return messages


async def orchestrator(state: ResearchState, config: RunnableConfig = None) -> dict:
    """Decide which tools to call based on current context.

    Binds all available tools to the LLM and invokes with the orchestrator
    prompt. Parses tool calls from the AIMessage response. Increments
    iteration_count. If the LLM returns zero tool calls, sets _no_new_tools
    flag so should_continue_loop detects tool exhaustion (F4).

    ENH-003: Trims messages before LLM invocation to prevent context overflow.
    ENH-008: Summarizes accumulated research messages when > 15.

    Reads: sub_question, retrieved_chunks, tool_call_count, iteration_count
    Writes: iteration_count, messages (with AIMessage containing tool_calls),
            _no_new_tools flag

    The LLM and tools list are resolved from RunnableConfig (injected by
    the graph at compile/invoke time).
    """
    log = logger.bind(
        session_id=state["session_id"],
        sub_question=state["sub_question"],
        iteration=state["iteration_count"],
    )
    log.info(
        "agent_orchestrator_start",
        tool_call_count=state["tool_call_count"],
        chunk_count=len(state["retrieved_chunks"]),
    )

    # --- Resolve LLM + tools from config ---
    configurable = (config or {}).get("configurable", {})
    llm = configurable.get("llm")
    tools_list = configurable.get("tools", [])

    if llm is None:
        log.warning("agent_orchestrator_no_llm")
        return {
            "iteration_count": state["iteration_count"] + 1,
            "_no_new_tools": True,
        }

    # ENH-008: Summarize research messages if accumulation is too large
    state_messages = state.get("messages", [])
    summarized_msgs = await _maybe_summarize_research_messages(state_messages, llm, log)

    # ENH-003: Trim messages before LLM call to prevent context overflow
    trimmed_messages = trim_messages(
        summarized_msgs,
        max_tokens=6000,
        token_counter=len,  # character-based approximation
        strategy="last",
        include_system=True,
        allow_partial=False,
    )

    llm_with_tools = llm.bind_tools(tools_list) if tools_list else llm

    # --- Build prompt ---
    chunk_summaries = "\n".join(
        f"- [{c.collection}] {c.text[:120]}..." for c in state["retrieved_chunks"][:10]
    ) or "(none yet)"

    system_msg = SystemMessage(content=ORCHESTRATOR_SYSTEM.format(
        tool_descriptions="(auto-populated by bind_tools)",
        chunk_count=len(state["retrieved_chunks"]),
        chunk_summaries=chunk_summaries,
        iteration=state["iteration_count"] + 1,
        max_iterations=settings.max_iterations,
        tool_call_count=state["tool_call_count"],
        max_tool_calls=settings.max_tool_calls,
    ))

    user_msg = HumanMessage(content=ORCHESTRATOR_USER.format(
        sub_question=state["sub_question"],
        collections=", ".join(state["selected_collections"]),
        confidence_score=f"{state['confidence_score']:.2f}",
    ))

    # --- Invoke LLM with tools bound (R1) ---
    # Use trimmed messages as conversation context alongside the prompt
    invoke_messages = [system_msg] + list(trimmed_messages) + [user_msg]
    try:
        response = await llm_with_tools.ainvoke(invoke_messages)
    except Exception as exc:
        log.warning("agent_orchestrator_llm_failed", error=type(exc).__name__)
        return {
            "iteration_count": state["iteration_count"] + 1,
            "_no_new_tools": True,
        }

    tool_calls = response.tool_calls  # list[dict] from AIMessage

    # --- Detect tool exhaustion (F4) ---
    no_new_tools = len(tool_calls) == 0

    log.info(
        "agent_orchestrator_decision",
        num_tool_calls=len(tool_calls),
        no_new_tools=no_new_tools,
    )

    # Include RemoveMessage markers if summarization occurred
    result_messages = [response]  # AIMessage with tool_calls
    if any(isinstance(m, RemoveMessage) for m in summarized_msgs):
        result_messages = [m for m in summarized_msgs if isinstance(m, (RemoveMessage, SystemMessage))] + result_messages

    return {
        "iteration_count": state["iteration_count"] + 1,
        "messages": result_messages,
        "_no_new_tools": no_new_tools,
    }


async def _execute_single_tool(
    tc: dict,
    tools_by_name: dict,
    sub_question: str,
    log: Any,
) -> tuple[str | None, Any, int, str]:
    """Execute a single tool call with retry-once (FR-016).

    Returns: (tool_name, result, calls_consumed, tool_call_id)
    calls_consumed counts both original + retry attempts against the budget.
    """
    tool_name = tc["name"]
    tool_args = tc["args"]
    tool_call_id = tc["id"]
    tool_fn = tools_by_name.get(tool_name)

    if not tool_fn:
        log.warning("agent_unknown_tool", tool=tool_name)
        return tool_name, None, 0, tool_call_id

    # Retry-once pattern (R7, FR-016)
    calls_consumed = 1  # original attempt counts
    try:
        result = await tool_fn.ainvoke(tool_args)
        return tool_name, result, calls_consumed, tool_call_id
    except Exception as first_err:
        log.warning("agent_tool_call_failed", tool=tool_name, error=type(first_err).__name__)
        calls_consumed += 1  # retry also counts against budget
        try:
            result = await tool_fn.ainvoke(tool_args)
            return tool_name, result, calls_consumed, tool_call_id
        except Exception as retry_err:
            log.warning(
                "agent_tool_call_failed_after_retry",
                tool=tool_name, error=type(retry_err).__name__,
            )
            return tool_name, retry_err, calls_consumed, tool_call_id


async def tools_node(state: ResearchState, config: RunnableConfig = None) -> dict:
    """Execute pending tool calls from orchestrator in PARALLEL (ENH-007).

    ENH-007: Uses asyncio.gather for concurrent tool execution while
    preserving deduplication and budget counting logic.

    For each tool call from the orchestrator's AIMessage:
    1. Look up the tool function by name
    2. Execute ALL tool calls concurrently with retry-once (FR-016)
    3. Post-process: deduplicate results against retrieval_keys
    4. Merge new chunks into retrieved_chunks
    5. Sum tool_call_count from all executions (including retries)

    Deduplication key: f"{normalize_query(query)}:{parent_id}"

    Reads: messages (last AIMessage with tool_calls), retrieval_keys,
           retrieved_chunks, tool_call_count
    Writes: retrieved_chunks, retrieval_keys, tool_call_count, messages
    """
    log = logger.bind(session_id=state["session_id"])
    _t0 = time.perf_counter()

    # --- Resolve tools from config ---
    configurable = (config or {}).get("configurable", {})
    tools_list = configurable.get("tools", [])
    tools_by_name = {t.name: t for t in tools_list}

    messages = state.get("messages", [])
    if not messages:
        log.warning("agent_tools_node_no_messages")
        _duration_ms = round((time.perf_counter() - _t0) * 1000, 1)
        _prior = state.get("stage_timings", {})
        return {
            "retrieved_chunks": state["retrieved_chunks"],
            "retrieval_keys": state["retrieval_keys"],
            "tool_call_count": state["tool_call_count"],
            "stage_timings": {
                **_prior,
                "embedding": {"duration_ms": _duration_ms},
                "retrieval": {"duration_ms": _duration_ms},
            },
        }

    last_ai_message = messages[-1]
    tool_calls = getattr(last_ai_message, "tool_calls", [])

    new_chunks: list[RetrievedChunk] = []
    updated_keys = set(state["retrieval_keys"])
    tool_call_count = state["tool_call_count"]
    tool_messages: list[ToolMessage] = []

    try:
        # ENH-007: Execute all tool calls concurrently via asyncio.gather
        parallel_results = await asyncio.gather(
            *[
                _execute_single_tool(tc, tools_by_name, state["sub_question"], log)
                for tc in tool_calls
            ],
            return_exceptions=True,
        )

        # Post-process results: dedup, budget counting, build ToolMessages
        for i, outcome in enumerate(parallel_results):
            if isinstance(outcome, Exception):
                tc = tool_calls[i]
                log.warning("agent_tool_call_gather_error", tool=tc["name"], error=type(outcome).__name__)
                tool_messages.append(ToolMessage(
                    content=f"Tool {tc['name']} failed: {outcome}",
                    tool_call_id=tc["id"],
                ))
                continue

            tool_name, result, calls_consumed, tool_call_id = outcome
            tool_call_count += calls_consumed

            # Unknown tool — already logged inside _execute_single_tool
            if result is None and calls_consumed == 0:
                tool_messages.append(ToolMessage(
                    content=f"Unknown tool: {tool_name}",
                    tool_call_id=tool_call_id,
                ))
                continue

            # Failed after retry — result is the exception
            if isinstance(result, Exception):
                tool_messages.append(ToolMessage(
                    content=f"Tool {tool_name} failed: {result}",
                    tool_call_id=tool_call_id,
                ))
                continue

            # --- Deduplication (US4) ---
            tc = tool_calls[i]
            tool_args = tc["args"]
            if isinstance(result, list):
                before_count = len(new_chunks)
                for chunk in result:
                    if isinstance(chunk, RetrievedChunk):
                        key = dedup_key(
                            tool_args.get("query", state["sub_question"]),
                            chunk.parent_id,
                        )
                        if key not in updated_keys:
                            updated_keys.add(key)
                            new_chunks.append(chunk)
                deduped_count = len(new_chunks) - before_count
                original_new_count = len([c for c in result if isinstance(c, RetrievedChunk)])
                log.info("agent_dedup_filtered",
                         tool=tool_name,
                         original=original_new_count,
                         kept=deduped_count)

            tool_messages.append(ToolMessage(
                content=str(result),
                tool_call_id=tool_call_id,
            ))

            log.info("agent_tool_call_complete", tool=tool_name,
                     new_chunks=len(new_chunks), tool_call_count=tool_call_count)

        _duration_ms = round((time.perf_counter() - _t0) * 1000, 1)
        _prior = state.get("stage_timings", {})
        return {
            "retrieved_chunks": state["retrieved_chunks"] + new_chunks,
            "retrieval_keys": updated_keys,
            "tool_call_count": tool_call_count,
            "messages": tool_messages,
            "stage_timings": {
                **_prior,
                "embedding": {"duration_ms": _duration_ms},
                "retrieval": {"duration_ms": _duration_ms},
            },
        }

    except Exception:
        _duration_ms = round((time.perf_counter() - _t0) * 1000, 1)
        _prior = state.get("stage_timings", {})
        return {
            "retrieved_chunks": state["retrieved_chunks"] + new_chunks,
            "retrieval_keys": updated_keys,
            "tool_call_count": tool_call_count,
            "messages": tool_messages,
            "stage_timings": {
                **_prior,
                "embedding": {"duration_ms": _duration_ms, "failed": True},
                "retrieval": {"duration_ms": _duration_ms, "failed": True},
            },
        }


async def should_compress_context(state: ResearchState) -> dict:
    """Check token count against model context window.

    Uses count_tokens_approximately from langchain_core (R3 -- NOT tiktoken).
    Sets _needs_compression flag in state for route_after_compress_check
    edge to read (F3). This node does NOT do routing itself.

    Reads: retrieved_chunks, llm_model
    Writes: _needs_compression (bool flag for edge function)
    """
    log = logger.bind(session_id=state["session_id"])

    # Build messages from chunk texts for token counting
    chunk_texts = [HumanMessage(content=c.text) for c in state["retrieved_chunks"]]
    token_count = count_tokens_approximately(chunk_texts) if chunk_texts else 0
    budget = get_context_budget(state["llm_model"])
    compression_threshold = int(budget * settings.compression_threshold)

    needs_compression = token_count > compression_threshold

    log.info(
        "agent_compress_check",
        token_count=token_count,
        budget=budget,
        threshold=compression_threshold,
        needs_compression=needs_compression,
    )

    return {"_needs_compression": needs_compression}


async def compress_context(state: ResearchState, config: RunnableConfig = None) -> dict:
    """Summarize retrieved chunks when context window is approached.

    Concatenates all chunk texts, summarizes via LLM call, replaces
    retrieved_chunks with compressed versions. Preserves citation
    references (FR-011).

    On LLM failure: skip compression, continue with uncompressed chunks.

    Reads: retrieved_chunks, llm_model
    Writes: retrieved_chunks (compressed), context_compressed = True
    """
    log = logger.bind(session_id=state["session_id"])
    log.info("agent_compress_context_start", chunk_count=len(state["retrieved_chunks"]))

    # --- Resolve LLM from config ---
    configurable = (config or {}).get("configurable", {})
    llm = configurable.get("llm")

    if llm is None:
        log.warning("agent_compress_context_no_llm")
        return {}  # Skip compression

    chunks_text = "\n\n---\n\n".join(
        f"[{c.collection} | {c.source_file}] {c.text}"
        for c in state["retrieved_chunks"]
    )

    try:
        response = await llm.ainvoke([
            SystemMessage(content=COMPRESS_CONTEXT_SYSTEM),
            HumanMessage(content=f"Compress the following retrieved context:\n\n{chunks_text}"),
        ])

        # Build sources map: "[N] source_file:page" for citation reconstruction
        sources_map = "; ".join(
            f"[{i+1}] {c.source_file}:{c.page or 'N/A'}"
            for i, c in enumerate(state["retrieved_chunks"][:20])
        )
        first_chunk = state["retrieved_chunks"][0] if state["retrieved_chunks"] else None
        compressed_chunk = RetrievedChunk(
            chunk_id="compressed-context",
            text=response.content,
            source_file=first_chunk.source_file if first_chunk else "compressed",
            page=None,
            breadcrumb=f"compressed-context | sources: {sources_map}",
            parent_id=first_chunk.parent_id if first_chunk else "compressed",
            collection=first_chunk.collection if first_chunk else "compressed",
            dense_score=max(
                (c.dense_score for c in state["retrieved_chunks"]), default=0.0
            ),
            sparse_score=0.0,
            rerank_score=max(
                (c.rerank_score for c in state["retrieved_chunks"]
                 if c.rerank_score is not None),
                default=None,
            ),
        )

        log.info(
            "agent_context_compressed",
            before_chunks=len(state["retrieved_chunks"]),
            after_chunks=1,
        )
        return {"retrieved_chunks": [compressed_chunk], "context_compressed": True}

    except Exception as exc:
        log.warning("agent_compress_context_failed", error=type(exc).__name__)
        return {}  # Skip compression on failure


def _build_citations(
    chunks: list[RetrievedChunk],
    answer_text: str,
) -> list[Citation]:
    """Build Citation objects from retrieved chunks in passage index order.

    Returns citations ordered by passage index so citations[N-1] maps to
    passage [N] that the LLM references in its answer text.
    """
    return [
        Citation(
            passage_id=chunk.chunk_id,
            document_id=chunk.parent_id,
            document_name=chunk.source_file,
            start_offset=0,
            end_offset=len(chunk.text),
            text=chunk.text[:500],
            relevance_score=chunk.rerank_score if chunk.rerank_score is not None else chunk.dense_score,
        )
        for chunk in chunks[:20]
    ]


async def collect_answer(state: ResearchState, config: RunnableConfig = None, *, store=None) -> dict:
    """Generate answer from retrieved chunks, compute confidence, build citations.

    1. Build prompt with sub_question + retrieved chunks
    2. LLM generates answer with inline references
    3. Build Citation objects mapping references to chunks
    4. Compute confidence_score from retrieval signals via compute_confidence()
       -- 5-signal formula (R8), NOT LLM self-assessment

    ENH-001: Writes back used collections to LangGraph Store for cross-session
    preference learning.

    CONFIDENCE SCALE: state["confidence_score"] is float 0.0-1.0.
    SubAnswer.confidence_score is int 0-100. Conversion: int(score * 100).

    Reads: sub_question, retrieved_chunks
    Writes: answer, citations, confidence_score (float 0.0-1.0)
    """
    log = logger.bind(session_id=state["session_id"])
    _t0 = time.perf_counter()

    chunks = state["retrieved_chunks"]

    # --- Compute confidence from retrieval signals (R8) ---
    collections_hit = len({c.collection for c in chunks})
    collections_total = len(state["selected_collections"]) or 1
    confidence = compute_confidence(
        chunks,
        num_collections_searched=collections_hit,
        num_collections_total=collections_total,
    )

    log.info(
        "agent_collect_answer",
        chunk_count=len(chunks),
        confidence_score=confidence,
        sub_question=state["sub_question"],
    )

    # --- Build passages text for LLM ---
    passages_text = "\n\n".join(
        f"[{i+1}] [{c.source_file}] (score: {c.rerank_score or c.dense_score:.3f})\n{c.text}"
        for i, c in enumerate(chunks[:20])  # Cap at 20 passages
    )

    # --- Resolve LLM from config, generate answer ---
    configurable = (config or {}).get("configurable", {})
    llm = configurable.get("llm")

    if llm is None or not chunks:
        # No LLM or no chunks — return with computed confidence only
        answer_text = (
            f"Based on {len(chunks)} retrieved passage(s), here is what I found "
            f"regarding: \"{state['sub_question']}\"\n\n"
            + "\n".join(f"- {c.text[:200]}..." for c in chunks[:5])
        ) if chunks else f"No passages found for: \"{state['sub_question']}\""

        citations = _build_citations(chunks, answer_text)
        _duration_ms = round((time.perf_counter() - _t0) * 1000, 1)
        _prior = state.get("stage_timings", {})
        return {
            "confidence_score": confidence,
            "citations": citations,
            "stage_timings": {
                **_prior,
                "answer_generation": {"duration_ms": _duration_ms},
            },
            "sub_answers": [SubAnswer(
                sub_question=state["sub_question"],
                answer=answer_text,
                citations=citations,
                chunks=chunks,
                confidence_score=int(confidence * 100),
            )],
        }

    try:
        response = await llm.ainvoke([
            SystemMessage(content=COLLECT_ANSWER_SYSTEM.format(passages=passages_text)),
            HumanMessage(content=f"Sub-question: {state['sub_question']}"),
        ])
        answer_text = response.content
    except Exception as exc:
        log.warning("agent_collect_answer_llm_failed", error=type(exc).__name__)
        # Fallback: summarize chunks directly
        answer_text = (
            f"Based on {len(chunks)} retrieved passage(s) for "
            f"\"{state['sub_question']}\":\n\n"
            + "\n".join(f"- {c.text[:200]}..." for c in chunks[:5])
        )

    citations = _build_citations(chunks, answer_text)

    # ENH-001: Write back used collections to store for cross-session preferences
    if store is not None and state.get("selected_collections"):
        try:
            user_id = configurable.get("user_id", "default")
            await store.aput(
                ("user_prefs", user_id),
                "settings",
                {"preferred_collections": list(state["selected_collections"])},
            )
        except Exception as store_exc:
            log.debug("agent_store_write_failed", error=type(store_exc).__name__)

    log.info(
        "agent_research_loop_end",
        confidence=confidence,
        total_chunks=len(chunks),
        iterations=state["iteration_count"],
        citations=len(citations),
    )

    _duration_ms = round((time.perf_counter() - _t0) * 1000, 1)
    _prior = state.get("stage_timings", {})
    return {
        "confidence_score": confidence,
        "citations": citations,
        "stage_timings": {
            **_prior,
            "answer_generation": {"duration_ms": _duration_ms},
        },
        "sub_answers": [SubAnswer(
            sub_question=state["sub_question"],
            answer=answer_text,
            citations=citations,
            chunks=chunks,
            confidence_score=int(confidence * 100),
        )],
    }


async def fallback_response(state: ResearchState) -> dict:
    """Generate graceful insufficient-information response.

    Does NOT hallucinate. States what was searched, what was found (if anything),
    and why results were insufficient.

    Reads: sub_question, retrieved_chunks
    Writes: answer, confidence_score (0.0)
    """
    log = logger.bind(session_id=state["session_id"])

    chunk_count = len(state["retrieved_chunks"])
    collections_searched = list({c.collection for c in state["retrieved_chunks"]})

    if chunk_count > 0:
        answer = (
            f"I searched {len(collections_searched)} collection(s) and found "
            f"{chunk_count} passage(s), but none were sufficiently relevant to "
            f"answer: \"{state['sub_question']}\". The documents may not cover "
            f"this specific topic in enough detail."
        )
    else:
        answer = (
            f"I could not find any relevant information to answer: "
            f"\"{state['sub_question']}\". The indexed documents may not "
            f"cover this topic."
        )

    log.info("agent_fallback_triggered", chunk_count=chunk_count,
             collections_searched=collections_searched,
             iterations=state["iteration_count"],
             tool_calls=state["tool_call_count"])

    return {
        "citations": [],
        "confidence_score": 0.0,
        "sub_answers": [SubAnswer(
            sub_question=state["sub_question"],
            answer=answer,
            citations=[],
            chunks=[],
            confidence_score=0,
        )],
    }
