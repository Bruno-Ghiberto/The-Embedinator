"""Node functions for the ConversationGraph.

All node functions are stateless and pure -- state is passed in and returned.
Dependencies (LLM, reranker, DB) are injected, not imported globally.

Wave 2 agents will replace the stub implementations with full logic.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt
from pydantic import ValidationError

from statistics import mean

from langchain_core.messages import trim_messages

from backend.agent.prompts import (
    CLASSIFY_INTENT_SYSTEM,
    CLASSIFY_INTENT_USER,
    REWRITE_QUERY_SYSTEM,
    REWRITE_QUERY_USER,
    SUMMARIZE_HISTORY_SYSTEM,
    VERIFY_PROMPT,
)
from backend.agent.schemas import GroundednessResult, IntentClassification, QueryAnalysis
from backend.agent.state import ConversationState
from backend.config import settings

logger = structlog.get_logger().bind(component=__name__)

# --- Model context window sizes (in tokens) ---

MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    "qwen2.5:7b": 32_768,
    "llama3.1:8b": 131_072,
    "mistral:7b": 32_768,
    "gpt-4o": 131_072,
    "gpt-4o-mini": 131_072,
    "claude-sonnet-4-20250514": 200_000,
}

_DEFAULT_CONTEXT_WINDOW = 32_768

# --- Complexity-tier retrieval parameters ---

TIER_PARAMS: dict[str, dict] = {
    "factoid": {
        "top_k": 5,
        "max_iterations": 3,
        "max_tool_calls": 3,
        "confidence_threshold": 0.7,
    },
    "lookup": {
        "top_k": 10,
        "max_iterations": 5,
        "max_tool_calls": 5,
        "confidence_threshold": 0.6,
    },
    "comparison": {
        "top_k": 15,
        "max_iterations": 7,
        "max_tool_calls": 6,
        "confidence_threshold": 0.55,
    },
    "analytical": {
        "top_k": 25,
        "max_iterations": 10,
        "max_tool_calls": 8,
        "confidence_threshold": 0.5,
    },
    "multi_hop": {
        "top_k": 30,
        "max_iterations": 10,
        "max_tool_calls": 8,
        "confidence_threshold": 0.45,
    },
}


def get_context_budget(model_name: str) -> int:
    """Return the usable token budget (75% of the model's context window).

    Args:
        model_name: The model identifier (e.g. "gpt-4o", "qwen2.5:7b").

    Returns:
        The token budget as an integer (context_window * 0.75).
    """
    window = MODEL_CONTEXT_WINDOWS.get(model_name, _DEFAULT_CONTEXT_WINDOW)
    return int(window * 0.75)


# --- Inference Service Circuit Breaker (FR-017, ADR-001) ---
_inf_circuit_open: bool = False
_inf_failure_count: int = 0
_inf_last_failure_time: float | None = None
_inf_max_failures: int = 5  # overridden from settings at first call
_inf_cooldown_secs: int = 30  # overridden from settings at first call


def _check_inference_circuit() -> None:
    """Check inference circuit breaker. Raises CircuitOpenError if open."""
    global _inf_circuit_open, _inf_max_failures, _inf_cooldown_secs
    from backend.errors import CircuitOpenError

    _inf_max_failures = settings.circuit_breaker_failure_threshold
    _inf_cooldown_secs = settings.circuit_breaker_cooldown_secs

    if _inf_circuit_open:
        if (
            _inf_last_failure_time is not None
            and time.monotonic() - _inf_last_failure_time >= _inf_cooldown_secs
        ):
            # Half-open: allow one probe request
            _inf_circuit_open = False
            logger.info("agent_inference_circuit_half_open")
        else:
            raise CircuitOpenError("Inference service circuit breaker is open")


def _record_inference_success() -> None:
    """Reset inference circuit breaker on success."""
    global _inf_failure_count, _inf_circuit_open
    _inf_failure_count = 0
    _inf_circuit_open = False


def _record_inference_failure() -> None:
    """Increment inference failure count, open circuit if threshold reached."""
    global _inf_failure_count, _inf_circuit_open, _inf_last_failure_time
    _inf_failure_count += 1
    _inf_last_failure_time = time.monotonic()
    if _inf_failure_count >= _inf_max_failures:
        _inf_circuit_open = True
        logger.error("agent_inference_circuit_opened", failure_count=_inf_failure_count)


# --- Node implementations ---


async def init_session(state: ConversationState, **kwargs: Any) -> dict:
    """Load or create session state, restore conversation history from SQLite."""
    from langchain_core.messages import messages_from_dict

    db = kwargs.get("db")
    session_id = state["session_id"]
    log = logger.bind(session_id=session_id)

    try:
        cursor = await db.execute(
            "SELECT messages_json, selected_collections, llm_model, embed_model"
            " FROM sessions WHERE id = ?",
            (session_id,),
        )
        row = await cursor.fetchone()

        if row is None:
            raise ValueError(f"Session not found in database: {session_id}")

        messages_json, selected_collections_json, llm_model, embed_model = row

        raw_messages = json.loads(messages_json) if messages_json else []
        messages = messages_from_dict(raw_messages) if raw_messages else []

        selected_collections = (
            json.loads(selected_collections_json) if selected_collections_json else []
        )

        return {
            "messages": messages,
            "selected_collections": selected_collections,
            "llm_model": llm_model or state.get("llm_model", ""),
            "embed_model": embed_model or state.get("embed_model", ""),
        }

    except Exception as exc:
        log.warning("agent_init_session_failed", error=type(exc).__name__)
        return {
            "messages": state.get("messages", []),  # preserve incoming messages
            "selected_collections": state.get("selected_collections", []),
            "llm_model": state.get("llm_model", ""),
            "embed_model": state.get("embed_model", ""),
        }


async def classify_intent(state: ConversationState, config: RunnableConfig = None, *, store=None) -> dict:
    """Classify user message as rag_query, collection_mgmt, or ambiguous.

    Uses with_structured_output(IntentClassification) for reliable parsing (ENH-002).
    Reads preferred_collections from LangGraph Store when available (ENH-001).
    On any failure (LLM error, validation), defaults to "rag_query".
    """
    llm = (config or {}).get("configurable", {}).get("llm")
    log = logger.bind(session_id=state["session_id"])
    _VALID_INTENTS = {"rag_query", "collection_mgmt", "ambiguous"}
    _t0 = time.perf_counter()

    # ENH-001: Read preferred collections from store
    preferred_collections: list[str] = []
    if store is not None:
        try:
            user_id = (config or {}).get("configurable", {}).get("user_id", "default")
            prefs_item = await store.aget(("user_prefs", user_id), "settings")
            if prefs_item:
                preferred_collections = prefs_item.value.get("preferred_collections", [])
        except Exception as store_exc:
            log.debug("agent_store_read_failed", error=type(store_exc).__name__)

    try:
        # Format conversation history for the prompt
        history_lines = []
        for msg in state["messages"]:
            role = getattr(msg, "type", "unknown")
            content = getattr(msg, "content", str(msg))
            history_lines.append(f"{role}: {content}")
        history_text = "\n".join(history_lines[-10:])  # Last 10 messages for context

        # Last user message
        last_message = ""
        for msg in reversed(state["messages"]):
            if getattr(msg, "type", None) == "human":
                last_message = msg.content
                break

        collections_text = ", ".join(state["selected_collections"]) or "none"
        if preferred_collections:
            collections_text += f" (preferred: {', '.join(preferred_collections)})"

        user_prompt = CLASSIFY_INTENT_USER.format(
            history=history_text,
            message=last_message,
            collections=collections_text,
        )

        # ENH-002: Structured output replaces manual JSON parsing
        structured_llm = llm.with_structured_output(IntentClassification, method="json_mode")
        result: IntentClassification = await structured_llm.ainvoke([
            SystemMessage(content=CLASSIFY_INTENT_SYSTEM),
            HumanMessage(content=user_prompt),
        ])

        intent = result.intent
        if intent not in _VALID_INTENTS:
            log.warning("agent_invalid_intent_value", intent=intent, defaulting_to="rag_query")
            intent = "rag_query"

        log.info("agent_intent_classified", intent=intent, reason=result.reason)
        return {
            "intent": intent,
            "stage_timings": {
                **state.get("stage_timings", {}),
                "intent_classification": {"duration_ms": round((time.perf_counter() - _t0) * 1000, 1)},
            },
        }

    except Exception as exc:
        log.warning("agent_classify_intent_failed", exc_info=True, defaulting_to="rag_query", error=type(exc).__name__)
        return {
            "intent": "rag_query",
            "stage_timings": {
                **state.get("stage_timings", {}),
                "intent_classification": {
                    "duration_ms": round((time.perf_counter() - _t0) * 1000, 1),
                    "failed": True,
                },
            },
        }


async def rewrite_query(state: ConversationState, config: RunnableConfig = None) -> dict:
    llm = (config or {}).get("configurable", {}).get("llm")
    """Decompose query into sub-questions with Pydantic structured output.

    Uses llm.with_structured_output(QueryAnalysis) for Pydantic parsing.
    On ValidationError: retries once with a simplified single-question prompt.
    On second failure: constructs a safe fallback QueryAnalysis.
    """
    log = logger.bind(session_id=state["session_id"])

    # Extract last user message
    last_message = ""
    for msg in reversed(state["messages"]):
        if getattr(msg, "type", None) == "human":
            last_message = msg.content
            break

    collections_text = ", ".join(state["selected_collections"]) or "none"

    # Build recent conversation context (last 6 messages)
    context_lines = []
    for msg in state["messages"][-6:]:
        role = getattr(msg, "type", "unknown")
        content = getattr(msg, "content", str(msg))
        context_lines.append(f"{role}: {content}")
    context_text = "\n".join(context_lines)

    user_prompt = REWRITE_QUERY_USER.format(
        question=last_message,
        collections=collections_text,
        context=context_text,
    )

    structured_llm = llm.with_structured_output(QueryAnalysis, method="json_mode")
    messages = [
        SystemMessage(content=REWRITE_QUERY_SYSTEM),
        HumanMessage(content=user_prompt),
    ]

    # First attempt
    try:
        analysis = await structured_llm.ainvoke(messages)
        tier_params = TIER_PARAMS.get(analysis.complexity_tier, TIER_PARAMS["lookup"])
        log.info(
            "agent_query_analyzed",
            is_clear=analysis.is_clear,
            sub_questions=len(analysis.sub_questions),
            complexity=analysis.complexity_tier,
        )
        return {"query_analysis": analysis, "retrieval_params": tier_params}
    except (ValidationError, Exception) as first_err:
        log.warning("agent_rewrite_query_first_attempt_failed", error=type(first_err).__name__)

    # Retry with simplified single-question prompt
    simplified_prompt = REWRITE_QUERY_USER.format(
        question=last_message,
        collections=collections_text,
        context="(simplified retry — produce a single sub-question matching the original query)",
    )
    retry_messages = [
        SystemMessage(content=REWRITE_QUERY_SYSTEM),
        HumanMessage(content=simplified_prompt),
    ]

    try:
        analysis = await structured_llm.ainvoke(retry_messages)
        tier_params = TIER_PARAMS.get(analysis.complexity_tier, TIER_PARAMS["lookup"])
        log.info(
            "agent_query_analyzed_on_retry",
            is_clear=analysis.is_clear,
            sub_questions=len(analysis.sub_questions),
            complexity=analysis.complexity_tier,
        )
        return {"query_analysis": analysis, "retrieval_params": tier_params}
    except (ValidationError, Exception) as second_err:
        log.warning("agent_rewrite_query_fallback", error=type(second_err).__name__)

    # Final fallback — safe default
    fallback = QueryAnalysis(
        is_clear=True,
        sub_questions=[last_message] if last_message else [""],
        complexity_tier="lookup",
        collections_hint=[],
        clarification_needed=None,
    )
    log.info("agent_query_analysis_fallback_used")
    return {"query_analysis": fallback, "retrieval_params": TIER_PARAMS["lookup"]}


def request_clarification(state: ConversationState) -> dict:
    """LangGraph interrupt -- pause graph, yield clarification question to UI.

    Calls interrupt() to checkpoint state to SQLite and pause execution.
    Resumes when Command(resume=user_response) is invoked externally.
    The 2-round clarification cap is enforced by should_clarify in edges.py.
    """
    log = logger.bind(session_id=state["session_id"])

    query_analysis = state.get("query_analysis")
    if query_analysis is None or not getattr(query_analysis, "clarification_needed", None):
        # Fallback: treat as research query instead of crashing
        return {
            "final_response": "I'm not sure I understand your question. Could you please provide more details about what you'd like to know?",
            "intent": "rag_query",
        }

    clarification_question = query_analysis.clarification_needed
    log.info("agent_interrupting_for_clarification", question=clarification_question)

    user_response = interrupt(clarification_question)

    log.info("agent_clarification_received", response=user_response)

    updated_messages = state["messages"] + [HumanMessage(content=user_response)]
    return {
        "messages": updated_messages,
        "iteration_count": state["iteration_count"] + 1,
    }


def fan_out(state: ConversationState, **kwargs: Any) -> ConversationState:
    """Spawn one ResearchGraph per sub-question using Send()."""
    raise NotImplementedError("fan_out not yet implemented")


def aggregate_answers(state: ConversationState, **kwargs: Any) -> dict:
    """Merge parallel ResearchGraph results, deduplicate citations, rank by relevance.

    Collects all SubAnswer objects from state["sub_answers"], skips any with
    answer=None (failed research sub-graphs), merges valid answers with sub-question
    headers, deduplicates citations by passage_id keeping the highest relevance_score,
    and computes a 0-100 confidence score via compute_confidence().
    """
    # Local imports: safe against concurrent edits by sibling Wave-2 agents
    from backend.agent.confidence import compute_confidence
    from backend.agent.schemas import Citation, SubAnswer  # noqa: F401

    log = logger.bind(session_id=state["session_id"])
    sub_answers: list[SubAnswer] = state.get("sub_answers", [])  # type: ignore[assignment]

    # Filter out failed sub-answers (answer is None)
    valid: list[SubAnswer] = [sa for sa in sub_answers if sa.answer is not None]

    if not valid:
        log.warning("agent_aggregate_answers_no_valid_sub_answers")
        return {
            "final_response": (
                "I couldn't find relevant information to answer your question. "
                "The documents may not cover this topic, or retrieval returned no useful results."
            ),
            "citations": [],
            "confidence_score": 0,
        }

    # Merge answer texts; single answer needs no header, multiple get sub-question headers
    if len(valid) == 1:
        merged_text = valid[0].answer
    else:
        sections = [
            f"**{sa.sub_question}**\n\n{sa.answer}"
            for sa in valid
        ]
        failed_count = len(sub_answers) - len(valid)
        if failed_count > 0:
            sections.append(
                f"*Note: {failed_count} sub-question(s) could not be answered "
                "due to retrieval failures.*"
            )
        merged_text = "\n\n".join(sections)

    # Deduplicate citations by passage_id, keeping the entry with the highest relevance_score
    best_by_passage: dict[str, Citation] = {}
    for sa in valid:
        for citation in sa.citations:
            existing = best_by_passage.get(citation.passage_id)
            if existing is None or citation.relevance_score > existing.relevance_score:
                best_by_passage[citation.passage_id] = citation

    deduped_citations: list[Citation] = sorted(
        best_by_passage.values(),
        key=lambda c: c.relevance_score,
        reverse=True,
    )

    # Compute 0-100 confidence from citation relevance scores
    passages_for_confidence = [
        {"relevance_score": c.relevance_score} for c in deduped_citations
    ]
    confidence_score = compute_confidence(passages_for_confidence)

    log.info(
        "agent_aggregate_answers_merged",
        num_valid=len(valid),
        num_failed=len(sub_answers) - len(valid),
        num_citations=len(deduped_citations),
        confidence_score=confidence_score,
    )

    return {
        "final_response": merged_text,
        "citations": deduped_citations,
        "confidence_score": confidence_score,
    }


def _apply_groundedness_annotations(response: str, result: GroundednessResult) -> str:
    """Annotate response with groundedness verdicts.

    - UNSUPPORTED claims get an [unverified] suffix
    - CONTRADICTED claims are removed with an explanatory note
    - If overall_grounded is False (>50% unsupported), prepend a warning banner
    """
    annotated = response
    for v in result.verifications:
        if v.verdict == "unsupported":
            annotated = annotated.replace(v.claim, f"{v.claim} [unverified]", 1)
        elif v.verdict == "contradicted":
            annotated = annotated.replace(
                v.claim,
                f"[Removed: this claim was contradicted by the source material — {v.explanation}]",
                1,
            )

    if not result.overall_grounded:
        annotated = (
            "**Warning: A significant portion of this answer could not be "
            "verified against the source documents.**\n\n" + annotated
        )

    return annotated


async def verify_groundedness(state: ConversationState, config: RunnableConfig = None) -> dict:
    llm = (config or {}).get("configurable", {}).get("llm")
    """NLI-based claim verification against retrieved context (GAV).

    Evaluates every factual claim in the generated answer against retrieved
    context via a structured LLM call, annotates unsupported claims, removes
    contradicted claims, and computes a GAV-adjusted confidence score.
    """
    from backend.agent.schemas import SubAnswer  # noqa: F401

    log = logger.bind(session_id=state["session_id"])
    _t0 = time.perf_counter()

    # Guard: feature flag
    if not settings.groundedness_check_enabled:
        log.info("agent_verify_groundedness_disabled")
        return {"groundedness_result": None}

    final_response: str | None = state.get("final_response")
    if not final_response:
        log.info("agent_verify_groundedness_no_final_response")
        return {"groundedness_result": None}

    sub_answers: list[SubAnswer] = state.get("sub_answers", [])  # type: ignore[assignment]
    if not sub_answers:
        log.info("agent_verify_groundedness_no_sub_answers")
        return {"groundedness_result": None}

    # Build context string from sub_answers chunk texts
    context_parts: list[str] = []
    for sa in sub_answers:
        for chunk in sa.chunks:
            context_parts.append(f"[{chunk.chunk_id}] {chunk.text}")
    context = "\n\n".join(context_parts)

    if not context.strip():
        log.info("agent_verify_groundedness_empty_context")
        return {"groundedness_result": None}

    try:
        _check_inference_circuit()

        prompt = VERIFY_PROMPT.format(context=context, answer=final_response)
        structured_llm = llm.with_structured_output(GroundednessResult, method="json_mode")
        result: GroundednessResult = await structured_llm.ainvoke(prompt)

        _record_inference_success()

        # Apply annotations
        annotated = _apply_groundedness_annotations(final_response, result)

        # Compute GAV-adjusted confidence: mean(sub_answer scores) * adjustment
        raw_scores = [sa.confidence_score for sa in sub_answers]
        adjusted = int(mean(raw_scores) * result.confidence_adjustment)
        adjusted = max(0, min(100, adjusted))

        log.info(
            "agent_verify_groundedness_complete",
            overall_grounded=result.overall_grounded,
            confidence_adjustment=result.confidence_adjustment,
            adjusted_confidence=adjusted,
            num_verifications=len(result.verifications),
        )

        return {
            "groundedness_result": result,
            "confidence_score": adjusted,
            "final_response": annotated,
            "stage_timings": {
                **state.get("stage_timings", {}),
                "grounded_verification": {"duration_ms": round((time.perf_counter() - _t0) * 1000, 1)},
            },
        }

    except Exception as exc:
        _record_inference_failure()
        log.warning("agent_verify_groundedness_failed", error=type(exc).__name__)
        return {
            "groundedness_result": None,
            "stage_timings": {
                **state.get("stage_timings", {}),
                "grounded_verification": {
                    "duration_ms": round((time.perf_counter() - _t0) * 1000, 1),
                    "failed": True,
                },
            },
        }


def _extract_claim_for_citation(text: str, marker: str) -> str:
    """Return the sentence containing the citation marker.

    Splits on sentence boundaries (.!?), finds the sentence with the marker.
    Falls back to the first 200 characters if no sentence match.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text)
    for sentence in sentences:
        if marker in sentence:
            return sentence.strip()
    return text[:200]


async def validate_citations(state: ConversationState, *, reranker: Any = None) -> dict:
    """Cross-encoder alignment check for each inline citation.

    (1) For each citation: extract claim text via _extract_claim_for_citation
    (2) Score (claim_text, chunk.text) pairs via reranker
    (3) If score < threshold: remap to highest-scoring chunk or strip
    (4) Return corrected citations
    (5) Catch all exceptions -> pass-through unvalidated
    """
    from backend.config import settings

    log = logger.bind(session_id=state["session_id"])
    _t0 = time.perf_counter()

    citations = state.get("citations", [])
    final_response = state.get("final_response") or ""
    sub_answers = state.get("sub_answers", [])

    if not citations or not reranker:
        result = {"citations": citations}
        result["stage_timings"] = {
            **state.get("stage_timings", {}),
            "ranking": {"duration_ms": round((time.perf_counter() - _t0) * 1000, 1)},
        }
        return result

    # Flatten all chunks from all sub-answers
    all_chunks = [chunk for sa in sub_answers for chunk in sa.chunks]
    if not all_chunks:
        result = {"citations": citations}
        result["stage_timings"] = {
            **state.get("stage_timings", {}),
            "ranking": {"duration_ms": round((time.perf_counter() - _t0) * 1000, 1)},
        }
        return result

    threshold = settings.citation_alignment_threshold

    try:
        corrected: list = []
        for i, citation in enumerate(citations):
            marker = f"[{i + 1}]"
            claim_text = _extract_claim_for_citation(final_response, marker)

            # Score the cited chunk against the claim
            cited_chunk_text = citation.text
            scores = reranker.model.rank(
                claim_text, [cited_chunk_text], return_documents=False
            )
            cite_score = scores[0]["score"] if scores else 0.0

            if cite_score >= threshold:
                corrected.append(citation)
                continue

            # Remap: find best chunk that clears threshold
            all_texts = [c.text for c in all_chunks]
            all_scores = reranker.model.rank(
                claim_text, all_texts, return_documents=False
            )
            ranked = sorted(all_scores, key=lambda x: x["score"], reverse=True)

            if ranked and ranked[0]["score"] >= threshold:
                best_idx = all_scores.index(ranked[0])
                best_chunk = all_chunks[best_idx]
                citation.passage_id = best_chunk.chunk_id
                citation.text = best_chunk.text[:200]
                citation.relevance_score = ranked[0]["score"]
                corrected.append(citation)
                log.info("agent_citation_remapped", index=i + 1, new_score=ranked[0]["score"])
            else:
                log.info("agent_citation_stripped", index=i + 1)

        log.info(
            "agent_validate_citations_complete",
            original=len(citations),
            corrected=len(corrected),
        )
        result = {"citations": corrected}
        result["stage_timings"] = {
            **state.get("stage_timings", {}),
            "ranking": {"duration_ms": round((time.perf_counter() - _t0) * 1000, 1)},
        }
        return result

    except Exception as exc:
        log.warning("agent_validate_citations_failed", error=type(exc).__name__)
        return {
            "citations": citations,
            "stage_timings": {
                **state.get("stage_timings", {}),
                "ranking": {
                    "duration_ms": round((time.perf_counter() - _t0) * 1000, 1),
                    "failed": True,
                },
            },
        }


async def summarize_history(state: ConversationState, **kwargs: Any) -> dict:
    """Compress conversation history when token budget is approached.

    ENH-003: Uses trim_messages to cap input before LLM summarization,
    preventing context overflow on very long histories.
    """
    from langchain_core.messages.utils import count_tokens_approximately

    llm = kwargs.get("llm")
    messages = state["messages"]
    llm_model = state["llm_model"]
    log = logger.bind(session_id=state["session_id"], llm_model=llm_model)

    budget = get_context_budget(llm_model)
    token_count = count_tokens_approximately(messages)

    if token_count <= budget:
        return {}

    # Compress oldest 50% of messages
    split_idx = len(messages) // 2
    old_messages = messages[:split_idx]
    recent_messages = messages[split_idx:]

    # ENH-003: Trim old messages before summarization to prevent LLM overflow
    trimmed_old = trim_messages(
        old_messages,
        max_tokens=4096,
        token_counter=len,  # character-based approximation
        strategy="last",
        include_system=True,
        allow_partial=False,
    )

    history_text = "\n".join(
        f"{type(m).__name__}: {m.content}" for m in trimmed_old
    )

    try:
        summary_response = await llm.ainvoke([
            SystemMessage(content=SUMMARIZE_HISTORY_SYSTEM),
            HumanMessage(
                content=f"Please summarize these conversation messages:\n\n{history_text}"
            ),
        ])
        summary = summary_response.content
        compressed_messages = [SystemMessage(content=summary)] + list(recent_messages)
        log.info(
            "agent_history_compressed",
            original_count=len(messages),
            compressed_count=len(compressed_messages),
            token_count=token_count,
            budget=budget,
        )
        return {"messages": compressed_messages}

    except Exception as exc:
        log.warning("agent_summarize_history_failed", error=type(exc).__name__)
        return {}


def format_response(state: ConversationState, **kwargs: Any) -> dict:
    """Apply citation annotations, confidence indicator, format for NDJSON streaming.

    Applies inline [N] citation markers to the response text, appends a numbered
    reference list, and adds a confidence summary note when confidence_score < 70.

    Phase 1: groundedness_result is always None — groundedness annotations are skipped.
    Phase 2: When groundedness_result is populated, unsupported claims will be annotated
             with [unverified] and contradicted claims will be removed.

    Uses FORMAT_RESPONSE_SYSTEM prompt rules as the formatting specification.
    """
    from backend.agent.prompts import FORMAT_RESPONSE_SYSTEM  # noqa: F401 (Phase 2 LLM call)
    from backend.agent.schemas import Citation  # noqa: F401

    log = logger.bind(session_id=state["session_id"])
    final_response: str = state.get("final_response") or ""  # type: ignore[assignment]
    citations: list[Citation] = state.get("citations", [])  # type: ignore[assignment]
    confidence_score: int = state.get("confidence_score", 0)  # type: ignore[assignment]
    groundedness_result = state.get("groundedness_result")  # None in Phase 1

    if not final_response:
        log.warning("agent_format_response_empty_final_response")
        return {"final_response": final_response}

    formatted = final_response

    if citations:
        # Apply inline [N] markers by matching document name mentions in the response text
        for i, citation in enumerate(citations):
            marker = f"[{i + 1}]"
            doc_name = citation.document_name
            # Replace the first un-annotated occurrence of the document name
            if doc_name in formatted and marker not in formatted:
                formatted = formatted.replace(doc_name, f"{doc_name}{marker}", 1)

        # Append numbered citation reference section
        citation_lines = "\n".join(
            f"[{i + 1}] {c.document_name}: {c.text[:200]}"
            for i, c in enumerate(citations)
        )
        formatted += f"\n\n---\n**References:**\n{citation_lines}"

    # Phase 1: groundedness_result is None — skip all groundedness annotations entirely.
    # Phase 2 (when groundedness_result is populated):
    #   - Annotate unsupported claims with [unverified]
    #   - Remove contradicted claims and note the contradiction
    if groundedness_result is not None:
        log.debug("agent_format_response_groundedness_annotations")

    # Append confidence summary when score is below threshold
    if confidence_score < 70:
        formatted += (
            f"\n\n*Note: Confidence score is {confidence_score}/100. "
            "The retrieved information may be incomplete or partially relevant to your question.*"
        )

    log.info(
        "agent_format_response_formatted",
        num_citations=len(citations),
        confidence_score=confidence_score,
        has_groundedness=groundedness_result is not None,
    )

    return {"final_response": formatted}


def handle_collection_mgmt(state: ConversationState, **kwargs: Any) -> dict:
    """Handle collection management commands (create, delete, list).

    Out-of-scope stub for Spec 02. Returns a user-facing message directing
    users to the Collections page. No LLM call, no side effects.
    """
    logger.bind(session_id=state["session_id"]).info(
        "agent_handle_collection_mgmt_stub_invoked"
    )
    return {
        "final_response": (
            "Collection management is not yet implemented. "
            "Please use the Collections page."
        ),
        "confidence_score": 0,
    }
