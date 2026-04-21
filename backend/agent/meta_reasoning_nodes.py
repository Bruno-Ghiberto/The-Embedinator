"""Node functions for the MetaReasoningGraph (Layer 3).

4 async node functions + 3 private strategy helpers.
Dependencies (LLM, Reranker) resolved from RunnableConfig at invocation time.
"""

from __future__ import annotations

import statistics

import structlog
from langchain_core.runnables import RunnableConfig

from backend.agent.prompts import GENERATE_ALT_QUERIES_SYSTEM, REPORT_UNCERTAINTY_SYSTEM
from backend.agent.state import MetaReasoningState
from backend.config import settings

logger = structlog.get_logger().bind(component=__name__)

# Strategy constants
STRATEGY_WIDEN_SEARCH = "WIDEN_SEARCH"
STRATEGY_CHANGE_COLLECTION = "CHANGE_COLLECTION"
STRATEGY_RELAX_FILTERS = "RELAX_FILTERS"

FALLBACK_ORDER = [STRATEGY_WIDEN_SEARCH, STRATEGY_CHANGE_COLLECTION, STRATEGY_RELAX_FILTERS]


async def generate_alternative_queries(
    state: MetaReasoningState,
    config: RunnableConfig = None,
) -> dict:
    """Produce 3 rephrased query variants using LLM (FR-001).

    Strategies: synonym replacement, sub-component breakdown, scope broadening.
    Graceful degradation: on LLM failure, return [original sub_question].

    Reads: sub_question, retrieved_chunks
    Writes: alternative_queries (list[str])
    Side effects: SSE event, structlog
    """
    sub_question = state["sub_question"]
    chunks = state.get("retrieved_chunks", [])
    attempt = state.get("meta_attempt_count", 0)

    log = logger.bind(sub_question=sub_question, attempt=attempt)

    # SSE status event (FR-014)
    # Emitted via config callback if available
    if config and config.get("configurable", {}).get("callbacks"):
        for cb in config["configurable"]["callbacks"]:
            if hasattr(cb, "on_custom_event"):
                cb.on_custom_event(
                    "meta_reasoning",
                    {"status": "Generating alternative queries...", "attempt": attempt},
                )

    chunk_summaries = "\n".join(f"- {c.text[:100]}..." for c in chunks[:5]) or "(no chunks retrieved)"

    try:
        llm = config["configurable"]["llm"]
        prompt = GENERATE_ALT_QUERIES_SYSTEM.format(
            sub_question=sub_question,
            chunk_summaries=chunk_summaries,
        )
        response = await llm.ainvoke(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Generate 3 alternative queries for: {sub_question}"},
            ]
        )

        # Parse: expect numbered list or newline-separated
        lines = [
            line.strip().lstrip("0123456789.-) ")
            for line in response.content.strip().split("\n")
            if line.strip() and not line.strip().startswith("#")
        ]
        alternatives = [item for item in lines if item][:3]

        # Pad to 3 if needed
        while len(alternatives) < 3:
            alternatives.append(sub_question)

        log.info("agent_alt_queries_generated", count=len(alternatives))
        return {"alternative_queries": alternatives}

    except Exception as exc:
        log.warning("agent_alt_queries_failed", error=type(exc).__name__)
        return {"alternative_queries": [sub_question]}


async def evaluate_retrieval_quality(
    state: MetaReasoningState,
    config: RunnableConfig = None,
) -> dict:
    """Score all retrieved chunks with cross-encoder (FR-002, FR-003).

    Uses Reranker (NOT LLM self-assessment) to compute per-chunk and mean
    relevance scores. Reranker resolved from config DI.

    Reads: sub_question, retrieved_chunks
    Writes: mean_relevance_score, chunk_relevance_scores
    Side effects: Reranker inference, SSE event, structlog
    """
    sub_question = state["sub_question"]
    chunks = state.get("retrieved_chunks", [])
    attempt = state.get("meta_attempt_count", 0)

    log = logger.bind(sub_question=sub_question, attempt=attempt)

    # SSE status event (FR-014)
    if config and config.get("configurable", {}).get("callbacks"):
        for cb in config["configurable"]["callbacks"]:
            if hasattr(cb, "on_custom_event"):
                cb.on_custom_event(
                    "meta_reasoning",
                    {"status": "Evaluating retrieval quality...", "attempt": attempt},
                )

    # Empty-chunks guard (FR-013)
    if not chunks:
        log.info("agent_eval_quality_empty_chunks")
        return {"mean_relevance_score": 0.0, "chunk_relevance_scores": []}

    # Reranker unavailability guard (FR-012)
    try:
        reranker = config["configurable"]["reranker"]
        if reranker is None:
            raise ValueError("Reranker is None")
    except KeyError, TypeError, ValueError:
        log.warning("agent_reranker_unavailable")
        return {"mean_relevance_score": 0.0, "chunk_relevance_scores": []}

    try:
        # Score ALL chunks (top_k=len to score every chunk, not just top-5)
        scored_chunks = reranker.rerank(sub_question, chunks, top_k=len(chunks))
        scores = [c.rerank_score for c in scored_chunks if c.rerank_score is not None]

        if not scores:
            log.warning("agent_reranker_no_scores")
            return {"mean_relevance_score": 0.0, "chunk_relevance_scores": []}

        mean_score = sum(scores) / len(scores)

        log.info(
            "agent_eval_quality_complete",
            mean_score=round(mean_score, 4),
            chunk_count=len(chunks),
            min_score=round(min(scores), 4),
            max_score=round(max(scores), 4),
        )
        return {"mean_relevance_score": mean_score, "chunk_relevance_scores": scores}

    except Exception as exc:
        log.warning("agent_reranker_failed", error=type(exc).__name__)
        return {"mean_relevance_score": 0.0, "chunk_relevance_scores": []}


async def decide_strategy(
    state: MetaReasoningState,
    config: RunnableConfig = None,
) -> dict:
    """Select recovery strategy based on quantitative evaluation (FR-004).

    Decision logic (plan.md):
      mean < threshold AND chunk_count < 3     -> WIDEN_SEARCH
      mean < threshold AND chunk_count >= 3    -> CHANGE_COLLECTION
      mean >= threshold AND variance > var_thr -> RELAX_FILTERS
      mean >= threshold AND variance <= var_thr -> None (report_uncertainty)
      attempt >= max_attempts                  -> None (forced, FR-006)
      candidate in attempted_strategies        -> next untried or None (FR-015)

    Reads: mean_relevance_score, chunk_relevance_scores, retrieved_chunks,
           meta_attempt_count, attempted_strategies
    Writes: recovery_strategy, modified_state, meta_attempt_count, attempted_strategies
    Side effects: structlog
    """
    mean_score = state.get("mean_relevance_score", 0.0)
    scores = state.get("chunk_relevance_scores", [])
    chunks = state.get("retrieved_chunks", [])
    chunk_count = len(chunks)
    attempt = state.get("meta_attempt_count", 0)
    attempted = set(state.get("attempted_strategies", set()))
    alt_queries = state.get("alternative_queries", [])

    # Resolve settings from config or use module-level default
    cfg_settings = settings
    if config and config.get("configurable", {}).get("settings"):
        cfg_settings = config["configurable"]["settings"]

    log = logger.bind(
        attempt=attempt,
        mean_score=round(mean_score, 4),
        chunk_count=chunk_count,
    )

    # Guard: max attempts (FR-006)
    if attempt >= cfg_settings.meta_reasoning_max_attempts:
        log.info("agent_max_attempts_reached", max_attempts=cfg_settings.meta_reasoning_max_attempts)
        return {
            "recovery_strategy": None,
            "modified_state": None,
            "meta_attempt_count": attempt,
        }

    # Compute variance (R2): stdev of chunk_relevance_scores
    if len(scores) < 2:
        score_variance = 0.0
    else:
        score_variance = statistics.stdev(scores)

    log = log.bind(score_variance=round(score_variance, 4))

    # Determine candidate strategy from evaluation signals
    rel_thr = cfg_settings.meta_relevance_threshold
    var_thr = cfg_settings.meta_variance_threshold

    candidate = None
    if mean_score < rel_thr and chunk_count < 3:
        candidate = STRATEGY_WIDEN_SEARCH
    elif mean_score < rel_thr and chunk_count >= 3:
        candidate = STRATEGY_CHANGE_COLLECTION
    elif mean_score >= rel_thr and score_variance > var_thr:
        candidate = STRATEGY_RELAX_FILTERS
    # else: mean >= threshold, variance <= threshold -> no strategy helps

    # Strategy dedup (FR-015): if candidate already tried, find next untried
    if candidate and candidate in attempted:
        candidate = None
        for fallback in FALLBACK_ORDER:
            if fallback not in attempted:
                candidate = fallback
                break

    # No viable strategy -> report_uncertainty
    if candidate is None:
        log.info("agent_no_viable_strategy")
        return {
            "recovery_strategy": None,
            "modified_state": None,
            "meta_attempt_count": attempt,
        }

    # Build modified_state via strategy helper
    if candidate == STRATEGY_WIDEN_SEARCH:
        modified = _build_modified_state_widen(alt_queries)
    elif candidate == STRATEGY_CHANGE_COLLECTION:
        modified = _build_modified_state_change_collection(alt_queries)
    else:
        modified = _build_modified_state_relax()

    new_attempted = attempted | {candidate}

    log.info(
        "agent_strategy_selected",
        strategy=candidate,
        attempted_strategies=list(new_attempted),
    )

    return {
        "recovery_strategy": candidate,
        "modified_state": modified,
        "meta_attempt_count": attempt + 1,
        "attempted_strategies": new_attempted,
    }


def _build_modified_state_widen(alternative_queries: list[str]) -> dict:
    """Build modified state for WIDEN_SEARCH strategy (FR-005).

    "ALL" signals the mapper node to iterate over all available collections
    and merge results. Increases top_k_retrieval to 40.
    """
    return {
        "selected_collections": "ALL",
        "top_k_retrieval": 40,
        "alternative_queries": alternative_queries,
    }


def _build_modified_state_change_collection(alternative_queries: list[str]) -> dict:
    """Build modified state for CHANGE_COLLECTION strategy (FR-005).

    "ROTATE" signals the mapper node to select the next collection that
    differs from the current one. Uses first alternative query.
    """
    return {
        "selected_collections": "ROTATE",
        "sub_question": alternative_queries[0] if alternative_queries else "",
    }


def _build_modified_state_relax() -> dict:
    """Build modified state for RELAX_FILTERS strategy (FR-005).

    Removes restrictive metadata filters, increases retrieval and rerank limits.
    """
    return {
        "top_k_retrieval": 40,
        "payload_filters": None,
        "top_k_rerank": 10,
    }


async def report_uncertainty(
    state: MetaReasoningState,
    config: RunnableConfig = None,
) -> dict:
    """Generate honest uncertainty report (FR-007, FR-008).

    Uses LLM with REPORT_UNCERTAINTY_SYSTEM prompt to produce a transparent
    explanation. No-fabrication guardrail baked into the prompt.

    Reads: sub_question, retrieved_chunks, mean_relevance_score,
           meta_attempt_count, alternative_queries
    Writes: answer, uncertainty_reason
    Side effects: LLM call, SSE event, structlog
    """
    sub_question = state["sub_question"]
    chunks = state.get("retrieved_chunks", [])
    mean_score = state.get("mean_relevance_score", 0.0)
    attempt = state.get("meta_attempt_count", 0)
    alt_queries = state.get("alternative_queries", [])

    log = logger.bind(
        sub_question=sub_question,
        mean_score=round(mean_score, 4),
        chunk_count=len(chunks),
        attempt=attempt,
    )

    # SSE status event (FR-014)
    if config and config.get("configurable", {}).get("callbacks"):
        for cb in config["configurable"]["callbacks"]:
            if hasattr(cb, "on_custom_event"):
                cb.on_custom_event(
                    "meta_reasoning",
                    {"status": "Could not find sufficient evidence", "attempt": attempt},
                )

    # Build context for LLM prompt
    collections_searched = list({c.collection for c in chunks}) if chunks else ["(none)"]
    chunk_summary = (
        "\n".join(f"- [{c.collection}] {c.text[:80]}... (score: {c.rerank_score or 'N/A'})" for c in chunks[:5])
        or "(no chunks retrieved)"
    )

    context = (
        f"Question: {sub_question}\n"
        f"Alternative queries tried: {', '.join(alt_queries) if alt_queries else '(none)'}\n"
        f"Collections searched: {', '.join(collections_searched)}\n"
        f"Mean relevance score: {mean_score:.3f}\n"
        f"Chunks retrieved: {len(chunks)}\n"
        f"Recovery attempts: {attempt}\n\n"
        f"Top retrieved chunks:\n{chunk_summary}"
    )

    try:
        llm = config["configurable"]["llm"]
        prompt = REPORT_UNCERTAINTY_SYSTEM
        response = await llm.ainvoke(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": context},
            ]
        )
        answer = response.content.strip()
        uncertainty_reason = (
            f"Mean relevance {mean_score:.3f} below threshold after {attempt} "
            f"recovery attempt(s). Collections: {', '.join(collections_searched)}."
        )
    except Exception as exc:
        # Fallback: static template without LLM
        log.warning("agent_uncertainty_llm_failed", error=type(exc).__name__)
        answer = (
            f"I was unable to find sufficient evidence to answer your question: "
            f'"{sub_question}"\n\n'
            f"Collections searched: {', '.join(collections_searched)}\n"
            f"Chunks found: {len(chunks)} (mean relevance: {mean_score:.2f})\n\n"
            f"Suggestions:\n"
            f"- Try rephrasing your question using different terminology\n"
            f"- Check if the relevant documents have been uploaded to a collection\n"
            f"- Try selecting a different collection that may contain this information\n"
            f"- Upload additional documents that cover this topic"
        )
        uncertainty_reason = (
            f"LLM unavailable for report. Mean relevance {mean_score:.3f}, "
            f"{attempt} attempt(s). Collections: {', '.join(collections_searched)}."
        )

    log.info(
        "agent_report_uncertainty_complete",
        answer_length=len(answer),
        collections_searched=collections_searched,
    )

    return {"answer": answer, "uncertainty_reason": uncertainty_reason}
