# Spec 04: MetaReasoningGraph -- Implementation Context

> **READ THIS SECTION FIRST. Do not skip ahead to code specifications.**

## Agent Team Orchestration Protocol

> **Prerequisite**: You MUST be running inside tmux. Agent Teams auto-detects tmux
> and spawns each teammate in its own split pane (the default `"auto"` teammateMode).
>
> **Enable**: Set `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in `~/.claude/settings.json`:
> ```json
> {
>   "env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" }
> }
> ```

### Architecture

The **lead session** (you, the orchestrator) coordinates all work via Claude Code Agent Teams:

| Component | Role |
|-----------|------|
| **Lead** | Creates team, creates tasks with dependencies, spawns teammates, runs checkpoint gates, synthesizes results |
| **Teammates** | Independent Claude Code instances, each in its own tmux pane, executing assigned tasks |
| **Task List** | Shared task list with dependency tracking — teammates self-claim unblocked tasks |
| **Mailbox** | Inter-agent messaging for status updates and checkpoint coordination |

### Wave Execution Order

```
Wave 1 (A1):       Foundation           -> Checkpoint Gate
Wave 2 (A2 + A3):  Nodes (parallel)     -> Checkpoint Gate
Wave 3 (A4):       Edges + Graph        -> Checkpoint Gate
Wave 4 (A5):       Integration          -> Checkpoint Gate
Wave 5 (A6 + A7):  Tests (parallel)     -> Checkpoint Gate
Final:              Polish (T044-T046)
```

### Step 1: Create the Team

```
Create an agent team called "spec04-meta-reasoning" to implement the MetaReasoningGraph feature.
```

The lead creates the team. All teammates will appear in their own tmux panes automatically.

### Step 2: Create Tasks with Dependencies

Create tasks in the shared task list so teammates can self-claim. Tasks encode the wave dependency chain:

```
Create the following tasks for the team:

Wave 1 — Foundation:
- T001-T008: State, config, prompts (assign to A1)

Wave 2 — Nodes (parallel, after Wave 1 completes):
- T009-T020: evaluate_retrieval_quality + decide_strategy nodes (assign to A2, depends on Wave 1)
- T021-T026: generate_alternative_queries + report_uncertainty nodes (assign to A3, depends on Wave 1)

Wave 3 — Edges + Graph (after Wave 2 completes):
- T027-T033: Edge function + graph builder (assign to A4, depends on Wave 2)

Wave 4 — Integration (after Wave 3 completes):
- T034-T041a: Mapper node + main.py wiring (assign to A5, depends on Wave 3)

Wave 5 — Tests (parallel, after Wave 4 completes):
- T042-T043: Unit tests (assign to A6, depends on Wave 4)
- T044: Integration tests (assign to A7, depends on Wave 4)

Final — Polish (after Wave 5 completes):
- T045-T046: Ruff + regression (lead handles)
```

### Step 3: Spawn Teammates per Wave

**Wave 1 — Spawn A1 (Foundation):**
```
Spawn a teammate named "A1-foundation" with model Sonnet.
Prompt: "Read your instruction file at Docs/PROMPTS/spec-04-meta-reasoning/agents/agent-a1-foundation.md FIRST, then execute all assigned tasks."
```

Wait for A1 to complete. Run checkpoint gate (see below). Then proceed to Wave 2.

**Wave 2 — Spawn A2 + A3 (parallel, each in own tmux pane):**
```
Spawn two teammates in parallel:

1. Teammate "A2-eval-strategy" with model Opus:
   "Read your instruction file at Docs/PROMPTS/spec-04-meta-reasoning/agents/agent-a2-eval-strategy-nodes.md FIRST, then execute all assigned tasks."

2. Teammate "A3-query-uncertainty" with model Sonnet:
   "Read your instruction file at Docs/PROMPTS/spec-04-meta-reasoning/agents/agent-a3-query-uncertainty-nodes.md FIRST, then execute all assigned tasks."
```

Wait for both A2 and A3 to complete. Run checkpoint gate. Then proceed to Wave 3.

**Wave 3 — Spawn A4 (Edges + Graph):**
```
Spawn a teammate named "A4-edges-graph" with model Sonnet.
Prompt: "Read your instruction file at Docs/PROMPTS/spec-04-meta-reasoning/agents/agent-a4-edges-graph.md FIRST, then execute all assigned tasks."
```

Wait for A4. Checkpoint gate. Proceed to Wave 4.

**Wave 4 — Spawn A5 (Integration):**
```
Spawn a teammate named "A5-integration" with model Opus.
Prompt: "Read your instruction file at Docs/PROMPTS/spec-04-meta-reasoning/agents/agent-a5-integration.md FIRST, then execute all assigned tasks."
Require plan approval before A5 makes any changes.
```

Review A5's plan, approve or reject with feedback. Wait for completion. Checkpoint gate. Proceed to Wave 5.

**Wave 5 — Spawn A6 + A7 (parallel):**
```
Spawn two teammates in parallel:

1. Teammate "A6-unit-tests" with model Sonnet:
   "Read your instruction file at Docs/PROMPTS/spec-04-meta-reasoning/agents/agent-a6-unit-tests.md FIRST, then execute all assigned tasks."

2. Teammate "A7-integration-tests" with model Sonnet:
   "Read your instruction file at Docs/PROMPTS/spec-04-meta-reasoning/agents/agent-a7-integration-tests.md FIRST, then execute all assigned tasks."
```

Wait for both. Run final checkpoint gate.

### Step 4: Checkpoint Gates (Lead Runs After Each Wave)

The lead runs these verification commands after each wave completes. If a gate fails, message the relevant teammate to fix it before proceeding.

```bash
# Wave 1: Foundation compiles
python -c "from backend.agent.state import MetaReasoningState; from backend.agent.prompts import GENERATE_ALT_QUERIES_SYSTEM, REPORT_UNCERTAINTY_SYSTEM; from backend.config import settings; print(settings.meta_relevance_threshold, settings.meta_variance_threshold)"
ruff check .

# Wave 2: All 4 nodes importable
python -c "from backend.agent.meta_reasoning_nodes import generate_alternative_queries, evaluate_retrieval_quality, decide_strategy, report_uncertainty; print('OK')"
ruff check .

# Wave 3: Graph compiles
python -c "from backend.agent.meta_reasoning_graph import build_meta_reasoning_graph; g = build_meta_reasoning_graph(); print('compiled')"
ruff check .

# Wave 4: Full chain compiles (requires running services or mocks)
python -c "from backend.agent.meta_reasoning_graph import build_meta_reasoning_graph; from backend.agent.research_graph import build_research_graph; print('imports OK')"
ruff check .

# Wave 5: Tests pass
zsh scripts/run-tests-external.sh -n spec04-unit tests/unit/test_meta_reasoning_nodes.py tests/unit/test_meta_reasoning_edges.py
zsh scripts/run-tests-external.sh -n spec04-integration tests/integration/test_meta_reasoning_graph.py
cat Docs/Tests/spec04-unit.status
cat Docs/Tests/spec04-integration.status
```

### Step 5: Shutdown and Cleanup

After all waves complete and checkpoint gates pass:

```
Ask all teammates to shut down, then clean up the team.
```

This removes the shared team resources. Always shut down teammates before cleanup.

### Orchestration Rules

1. **Never skip checkpoint gates** — a failed gate means the next wave's teammates will build on broken code.
2. **Use SendMessage for steering** — if a teammate is going off-track, message them directly in their tmux pane or via the lead's messaging system.
3. **Plan approval for A5** — the integration agent (A5) modifies existing files. Require plan approval so the lead can verify the approach before edits begin.
4. **Parallel waves share no files** — A2 and A3 write to different files; A6 and A7 write to different test files. No merge conflicts.
5. **Teammate prompts are minimal** — just point to the instruction file. All context lives in the instruction files and CLAUDE.md.
6. **Model selection** — A2 (eval+strategy nodes, complex logic) and A5 (integration, modifies existing code) use Opus. All others use Sonnet for cost efficiency.
7. **Monitor via tmux** — click into any teammate's pane to see their progress. Use `Shift+Down` in in-process mode to cycle through teammates.
8. **If a teammate fails** — shut it down and spawn a replacement with the same instruction file. The task list tracks which tasks are done.

---

## Implementation Scope

### Files to Create / Modify

| File | Action | Purpose |
|------|--------|---------|
| `backend/agent/meta_reasoning_graph.py` | Create | StateGraph definition + `build_meta_reasoning_graph()` |
| `backend/agent/meta_reasoning_nodes.py` | Create | 4 async node functions + 3 private strategy helpers |
| `backend/agent/meta_reasoning_edges.py` | Create | `route_after_strategy` conditional edge |
| `backend/agent/prompts.py` | Modify | Add `GENERATE_ALT_QUERIES_SYSTEM`, `REPORT_UNCERTAINTY_SYSTEM` |
| `backend/agent/state.py` | Modify | Add `attempted_strategies: set[str]` to `MetaReasoningState` |
| `backend/config.py` | Modify | Add `meta_relevance_threshold`, `meta_variance_threshold` |
| `backend/agent/research_graph.py` | Modify | Add ResearchState-to-MetaReasoningState mapper node body |
| `backend/main.py` | Modify | Build MetaReasoningGraph in lifespan, pass to `build_research_graph()` |
| `tests/unit/test_meta_reasoning_nodes.py` | Create | Unit tests for 4 nodes |
| `tests/unit/test_meta_reasoning_edges.py` | Create | Unit tests for edge function |
| `tests/integration/test_meta_reasoning_graph.py` | Create | Full graph compilation + execution tests |

### Files That Exist and Are NOT Modified (Verified)

- `backend/agent/research_edges.py` -- `should_continue_loop` already returns `"exhausted"` at lines 55 and 64. Do NOT modify.
- `backend/agent/research_graph.py` -- `build_research_graph` already accepts `meta_reasoning_graph: Any = None` (line 27) and routes `"exhausted"` conditionally (line 54-58). Do NOT overwrite existing routing logic.
- `backend/agent/schemas.py` -- `RetrievedChunk` with `rerank_score: float | None = None` (line 36). Use as-is.
- `backend/retrieval/reranker.py` -- `Reranker.rerank(query, chunks, top_k)` returns `list[RetrievedChunk]` with `rerank_score` populated (lines 31-79). Use as-is.
- `backend/agent/confidence.py` -- 5-signal formula returning float 0.0-1.0. Use as-is.
- `backend/errors.py` -- `LLMCallError`, `RerankerError`, `QdrantConnectionError` already defined. Use as-is.

---

## Codebase Verification (Verified via Serena MCP)

These facts were verified against the live codebase. Agents MUST respect them.

1. **MetaReasoningState** already has 10 fields in `state.py:52-63`. Only `attempted_strategies: set[str]` needs adding at line 63.
2. **Settings** already has `meta_reasoning_max_attempts: int = 2` at `config.py:42`. Do NOT re-add it.
3. **`build_research_graph()`** already accepts `meta_reasoning_graph: Any = None` and wires conditional routing at lines 49-58. A5 must NOT overwrite this -- only add the mapper node body.
4. **`should_continue_loop()`** already returns `"exhausted"` for budget/tool exhaustion. Do NOT modify this function.
5. **`Reranker.rerank(query, chunks, top_k)`** returns `list[RetrievedChunk]` with `rerank_score` populated via `model.rank()` API. NOT `model.predict()`.
6. **ConversationGraph** `build_conversation_graph` accepts `research_graph` and `checkpointer` params.
7. **Error hierarchy**: `EmbeddinatorError` base, with `LLMCallError`, `RerankerError`, `QdrantConnectionError` subclasses.
8. **Existing prompts**: `ORCHESTRATOR_SYSTEM`, `ORCHESTRATOR_USER`, `COMPRESS_CONTEXT_SYSTEM`, `COLLECT_ANSWER_SYSTEM` already in `prompts.py` -- append new constants after line 184.

---

## Code Specifications

### Critical Patterns (ALL Nodes MUST Follow)

```python
# Signature
async def node_name(state: MetaReasoningState, config: RunnableConfig = None) -> dict:
    # NOT config: RunnableConfig | None  (LangGraph quirk)

# Import
from langchain_core.runnables import RunnableConfig

# Return partial dict, NOT {**state, ...}
return {"field_a": value_a, "field_b": value_b}

# Resolve dependencies from config DI
llm = config["configurable"]["llm"]
reranker = config["configurable"]["reranker"]
settings_obj = config["configurable"].get("settings", settings)

# Structlog pattern
logger = structlog.get_logger(__name__)
```

---

### backend/agent/meta_reasoning_nodes.py (CREATE)

```python
"""Node functions for the MetaReasoningGraph (Layer 3).

4 async node functions + 3 private strategy helpers.
Dependencies (LLM, Reranker) resolved from RunnableConfig at invocation time.
"""
from __future__ import annotations

import statistics

import structlog
from langchain_core.runnables import RunnableConfig

from backend.agent.prompts import GENERATE_ALT_QUERIES_SYSTEM, REPORT_UNCERTAINTY_SYSTEM
from backend.agent.schemas import RetrievedChunk
from backend.agent.state import MetaReasoningState
from backend.config import settings

logger = structlog.get_logger(__name__)

# Strategy constants
STRATEGY_WIDEN_SEARCH = "WIDEN_SEARCH"
STRATEGY_CHANGE_COLLECTION = "CHANGE_COLLECTION"
STRATEGY_RELAX_FILTERS = "RELAX_FILTERS"

FALLBACK_ORDER = [STRATEGY_WIDEN_SEARCH, STRATEGY_CHANGE_COLLECTION, STRATEGY_RELAX_FILTERS]


async def generate_alternative_queries(
    state: MetaReasoningState, config: RunnableConfig = None,
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

    chunk_summaries = "\n".join(
        f"- {c.text[:100]}..." for c in chunks[:5]
    ) or "(no chunks retrieved)"

    try:
        llm = config["configurable"]["llm"]
        prompt = GENERATE_ALT_QUERIES_SYSTEM.format(
            sub_question=sub_question,
            chunk_summaries=chunk_summaries,
        )
        response = await llm.ainvoke([
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Generate 3 alternative queries for: {sub_question}"},
        ])

        # Parse: expect numbered list or newline-separated
        lines = [
            line.strip().lstrip("0123456789.-) ")
            for line in response.content.strip().split("\n")
            if line.strip() and not line.strip().startswith("#")
        ]
        alternatives = [l for l in lines if l][:3]

        # Pad to 3 if needed
        while len(alternatives) < 3:
            alternatives.append(sub_question)

        log.info("alt_queries_generated", count=len(alternatives))
        return {"alternative_queries": alternatives}

    except Exception as exc:
        log.warning("alt_queries_failed", error=str(exc))
        return {"alternative_queries": [sub_question]}


async def evaluate_retrieval_quality(
    state: MetaReasoningState, config: RunnableConfig = None,
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
        log.info("eval_quality_empty_chunks")
        return {"mean_relevance_score": 0.0, "chunk_relevance_scores": []}

    # Reranker unavailability guard (FR-012)
    try:
        reranker = config["configurable"]["reranker"]
        if reranker is None:
            raise ValueError("Reranker is None")
    except (KeyError, TypeError, ValueError):
        log.warning("reranker_unavailable")
        return {"mean_relevance_score": 0.0, "chunk_relevance_scores": []}

    try:
        # Score ALL chunks (top_k=len to score every chunk, not just top-5)
        scored_chunks = reranker.rerank(sub_question, chunks, top_k=len(chunks))
        scores = [c.rerank_score for c in scored_chunks if c.rerank_score is not None]

        if not scores:
            log.warning("reranker_no_scores")
            return {"mean_relevance_score": 0.0, "chunk_relevance_scores": []}

        mean_score = sum(scores) / len(scores)

        log.info(
            "eval_quality_complete",
            mean_score=round(mean_score, 4),
            chunk_count=len(chunks),
            min_score=round(min(scores), 4),
            max_score=round(max(scores), 4),
        )
        return {"mean_relevance_score": mean_score, "chunk_relevance_scores": scores}

    except Exception as exc:
        log.warning("reranker_failed", error=str(exc))
        return {"mean_relevance_score": 0.0, "chunk_relevance_scores": []}


async def decide_strategy(
    state: MetaReasoningState, config: RunnableConfig = None,
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
        log.info("max_attempts_reached", max_attempts=cfg_settings.meta_reasoning_max_attempts)
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
        log.info("no_viable_strategy")
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
        "strategy_selected",
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
    state: MetaReasoningState, config: RunnableConfig = None,
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
    chunk_summary = "\n".join(
        f"- [{c.collection}] {c.text[:80]}... (score: {c.rerank_score or 'N/A'})"
        for c in chunks[:5]
    ) or "(no chunks retrieved)"

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
        response = await llm.ainvoke([
            {"role": "system", "content": prompt},
            {"role": "user", "content": context},
        ])
        answer = response.content.strip()
        uncertainty_reason = (
            f"Mean relevance {mean_score:.3f} below threshold after {attempt} "
            f"recovery attempt(s). Collections: {', '.join(collections_searched)}."
        )
    except Exception as exc:
        # Fallback: static template without LLM
        log.warning("uncertainty_llm_failed", error=str(exc))
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
        "report_uncertainty_complete",
        answer_length=len(answer),
        collections_searched=collections_searched,
    )

    return {"answer": answer, "uncertainty_reason": uncertainty_reason}
```

---

### backend/agent/meta_reasoning_edges.py (CREATE)

```python
"""Edge functions (routing logic) for the MetaReasoningGraph.

Single conditional edge: route_after_strategy.
"""
from __future__ import annotations

from backend.agent.state import MetaReasoningState


def route_after_strategy(state: MetaReasoningState) -> str:
    """Route after decide_strategy.

    Returns:
        "retry": recovery_strategy is set -> END (modified_state ready for
                 ResearchGraph to re-enter with new parameters)
        "report": recovery_strategy is None -> report_uncertainty
    """
    if state.get("recovery_strategy"):
        return "retry"
    return "report"
```

---

### backend/agent/meta_reasoning_graph.py (CREATE)

```python
"""MetaReasoningGraph -- Layer 3 of the three-layer LangGraph agent.

Failure diagnosis and recovery when the ResearchGraph exhausts its
iteration/tool budget without reaching confidence threshold.

Flow:
  START -> generate_alternative_queries -> evaluate_retrieval_quality
        -> decide_strategy -> [retry: END | report: report_uncertainty -> END]
"""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from backend.agent.meta_reasoning_edges import route_after_strategy
from backend.agent.meta_reasoning_nodes import (
    decide_strategy,
    evaluate_retrieval_quality,
    generate_alternative_queries,
    report_uncertainty,
)
from backend.agent.state import MetaReasoningState


def build_meta_reasoning_graph() -> Any:
    """Build and compile the MetaReasoningGraph.

    Returns:
        Compiled LangGraph StateGraph.
    """
    graph = StateGraph(MetaReasoningState)

    # Nodes
    graph.add_node("generate_alternative_queries", generate_alternative_queries)
    graph.add_node("evaluate_retrieval_quality", evaluate_retrieval_quality)
    graph.add_node("decide_strategy", decide_strategy)
    graph.add_node("report_uncertainty", report_uncertainty)

    # Edges
    graph.add_edge(START, "generate_alternative_queries")
    graph.add_edge("generate_alternative_queries", "evaluate_retrieval_quality")
    graph.add_edge("evaluate_retrieval_quality", "decide_strategy")
    graph.add_conditional_edges("decide_strategy", route_after_strategy, {
        "retry": END,                # modified_state ready; ResearchGraph re-enters
        "report": "report_uncertainty",
    })
    graph.add_edge("report_uncertainty", END)

    return graph.compile()
```

---

### backend/agent/prompts.py (MODIFY -- append after line 184)

```python
# --- MetaReasoningGraph prompt constants (Spec 04) ---

GENERATE_ALT_QUERIES_SYSTEM = """The retrieval system failed to find sufficient evidence
for the following question. Generate exactly 3 alternative query formulations that might
retrieve better results.

Apply these 3 strategies (one per query):
1. Synonym replacement: rephrase using different terminology (technical vs. plain language)
2. Sub-component breakdown: break into a simpler, more focused sub-question
3. Scope broadening: remove specific constraints, ask more generally

Original question: {sub_question}
Retrieved chunks (low relevance): {chunk_summaries}

Respond with exactly 3 queries, one per line, numbered 1-3. No explanations."""

REPORT_UNCERTAINTY_SYSTEM = """Generate an honest response explaining that the system
could not find sufficient evidence to answer the user's question.

Your response MUST include:
1. Which collections were searched
2. What was found (if anything partially relevant)
3. Why the results were insufficient
4. Actionable suggestions for the user (rephrase query, select different collection, upload more documents)

CRITICAL GUARDRAILS:
- Do NOT fabricate an answer.
- Do NOT say "based on the available context" and then guess.
- Do NOT present speculation as evidence.
- If nothing relevant was found, say so directly.
- Keep the response helpful and constructive."""
```

---

### backend/agent/state.py (MODIFY -- add field at line 63)

Add `attempted_strategies: set[str]` as the last field of `MetaReasoningState`:

```python
class MetaReasoningState(TypedDict):
    sub_question: str
    retrieved_chunks: list[RetrievedChunk]
    alternative_queries: list[str]
    mean_relevance_score: float
    chunk_relevance_scores: list[float]
    meta_attempt_count: int
    recovery_strategy: str | None
    modified_state: dict | None
    answer: str | None
    uncertainty_reason: str | None
    attempted_strategies: set[str]  # FR-015: dedup across attempts
```

---

### backend/config.py (MODIFY -- add after line 42)

Add two new fields to the `# Agent` section, after `meta_reasoning_max_attempts`:

```python
    meta_reasoning_max_attempts: int = 2
    meta_relevance_threshold: float = 0.2   # R4: mean cross-encoder score threshold
    meta_variance_threshold: float = 0.15   # R4: stdev threshold for noisy results
```

---

### backend/agent/research_graph.py (MODIFY -- add mapper node)

The existing `build_research_graph` already wires `"exhausted" -> meta_reasoning` when `meta_reasoning_graph` is provided (lines 49-58). The new work is replacing the raw subgraph pass-through with a wrapper node that maps ResearchState to MetaReasoningState and back.

Replace `graph.add_node("meta_reasoning", meta_reasoning_graph)` (line 50) with a mapper closure:

```python
    if meta_reasoning_graph:
        async def meta_reasoning_mapper(state: ResearchState, config: RunnableConfig = None) -> dict:
            """Map ResearchState -> MetaReasoningState, invoke subgraph, map back."""
            from backend.agent.state import MetaReasoningState

            # Forward map: ResearchState -> MetaReasoningState input
            meta_input = {
                "sub_question": state["sub_question"],
                "retrieved_chunks": state["retrieved_chunks"],
                "alternative_queries": [],
                "mean_relevance_score": 0.0,
                "chunk_relevance_scores": [],
                "meta_attempt_count": state.get("_meta_attempt_count", 0),
                "recovery_strategy": None,
                "modified_state": None,
                "answer": None,
                "uncertainty_reason": None,
                "attempted_strategies": state.get("_attempted_strategies", set()),
            }

            # Invoke the compiled MetaReasoningGraph subgraph
            try:
                result = await meta_reasoning_graph.ainvoke(meta_input, config=config)
            except Exception as exc:
                # FR-017: infrastructure error during subgraph -> report_uncertainty
                logger.warning("meta_reasoning_infra_error", error=str(exc))
                return {
                    "answer": (
                        f"I was unable to complete the search due to an infrastructure "
                        f"error: {exc}. Please try again later."
                    ),
                    "confidence_score": 0.0,
                }

            # Reverse map: MetaReasoningState result -> ResearchState updates
            strategy = result.get("recovery_strategy")

            if strategy is not None:
                # Recovery path: apply modified_state back to ResearchState
                modified = result.get("modified_state", {})
                updates = {
                    "_meta_attempt_count": result.get("meta_attempt_count", 0),
                    "_attempted_strategies": result.get("attempted_strategies", set()),
                }

                collections = modified.get("selected_collections")
                if collections == "ALL":
                    # Iterate all collections -- set empty list to signal "search all"
                    updates["selected_collections"] = []
                elif collections == "ROTATE":
                    # Next different collection
                    current = state.get("selected_collections", [])
                    if len(current) <= 1:
                        # Only one collection; rotation impossible -> uncertainty
                        return {
                            "answer": result.get("answer", "Unable to find relevant information."),
                            "confidence_score": 0.0,
                        }
                    # Rotate: move first collection to end
                    updates["selected_collections"] = current[1:] + current[:1]

                if "sub_question" in modified:
                    updates["sub_question"] = modified["sub_question"]
                if "top_k_retrieval" in modified:
                    updates["_top_k_retrieval"] = modified["top_k_retrieval"]
                if "top_k_rerank" in modified:
                    updates["_top_k_rerank"] = modified["top_k_rerank"]
                if "payload_filters" in modified:
                    updates["_payload_filters"] = modified["payload_filters"]

                # Reset loop state for retry
                updates["retrieved_chunks"] = []
                updates["retrieval_keys"] = set()
                updates["tool_call_count"] = 0
                updates["iteration_count"] = 0
                updates["confidence_score"] = 0.0
                updates["context_compressed"] = False
                updates["_no_new_tools"] = False
                updates["_needs_compression"] = False

                return updates
            else:
                # Uncertainty path: propagate answer back
                return {
                    "answer": result.get("answer", "Unable to find relevant information."),
                    "confidence_score": 0.0,
                    "uncertainty_reason": result.get("uncertainty_reason"),
                }

        graph.add_node("meta_reasoning", meta_reasoning_mapper)
```

Also add at the top of `research_graph.py`:

```python
from langchain_core.runnables import RunnableConfig
```

---

### backend/main.py (MODIFY -- update lifespan graph build section)

Replace lines 99-106 with inside-out graph assembly and FR-011 guard:

```python
    # --- Spec 04: MetaReasoningGraph (Layer 3) ---
    from backend.agent.meta_reasoning_graph import build_meta_reasoning_graph

    # FR-011: skip meta-reasoning if max_attempts=0
    meta_reasoning_graph = None
    if settings.meta_reasoning_max_attempts > 0:
        meta_reasoning_graph = build_meta_reasoning_graph()
        logger.info("meta_reasoning_graph_compiled")

    # Build graph chain inside-out: MetaReasoning -> Research -> Conversation
    research_graph = build_research_graph(
        tools=research_tools,
        meta_reasoning_graph=meta_reasoning_graph,
    )
    conversation_graph = build_conversation_graph(
        research_graph=research_graph,
        checkpointer=checkpointer,
    )
    app.state.conversation_graph = conversation_graph
    logger.info("graphs_compiled", meta_reasoning_enabled=meta_reasoning_graph is not None)
```

---

## Configuration

| Field | Type | Default | Location | Description |
|-------|------|---------|----------|-------------|
| `meta_reasoning_max_attempts` | `int` | `2` | `config.py:42` | Max recovery attempts (already exists) |
| `meta_relevance_threshold` | `float` | `0.2` | `config.py` (new) | Mean score below which retrieval is "poor" |
| `meta_variance_threshold` | `float` | `0.15` | `config.py` (new) | Stdev above which results are "noisy" |
| `confidence_threshold` | `int` | `60` | `config.py:40` | Triggers meta-reasoning when below (existing) |
| `reranker_model` | `str` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | `config.py:49` | Cross-encoder model (existing) |

Environment variables: `META_RELEVANCE_THRESHOLD`, `META_VARIANCE_THRESHOLD`, `META_REASONING_MAX_ATTEMPTS`

---

## Error Handling

| Node | Error | Recovery |
|------|-------|----------|
| `generate_alternative_queries` | LLM call fails | Return `[original sub_question]`, log warning |
| `evaluate_retrieval_quality` | Reranker is None or raises | Return `mean=0.0, scores=[]`, log warning (FR-012) |
| `evaluate_retrieval_quality` | Empty chunks list | Return `mean=0.0, scores=[]` immediately (FR-013) |
| `decide_strategy` | All strategies already attempted | Return `recovery_strategy=None` (FR-015) |
| `decide_strategy` | Max attempts reached | Return `recovery_strategy=None` (FR-006) |
| `report_uncertainty` | LLM call fails | Generate static template response without LLM |
| `meta_reasoning_mapper` | Infrastructure error during subgraph | Return `answer` with error noted, `confidence_score=0.0` (FR-017) |

---

## Testing Protocol

**NEVER run pytest inside Claude Code.** All test execution uses the external runner.

```bash
# Unit tests:
zsh scripts/run-tests-external.sh -n spec04-unit tests/unit/test_meta_reasoning_nodes.py tests/unit/test_meta_reasoning_edges.py

# Integration tests:
zsh scripts/run-tests-external.sh -n spec04-integration tests/integration/test_meta_reasoning_graph.py

# Regression (all specs):
zsh scripts/run-tests-external.sh -n spec04-regression tests/

# Check status:
cat Docs/Tests/spec04-unit.status       # RUNNING | PASSED | FAILED | ERROR
cat Docs/Tests/spec04-unit.summary      # ~20 lines summary

cat Docs/Tests/spec04-integration.status
cat Docs/Tests/spec04-integration.summary
```

---

## Done Criteria

- [ ] `build_meta_reasoning_graph()` compiles a valid LangGraph StateGraph with 4 nodes
- [ ] `generate_alternative_queries` produces exactly 3 alternatives, degrades gracefully on LLM failure
- [ ] `evaluate_retrieval_quality` uses Reranker (not LLM), handles empty chunks and Reranker unavailability
- [ ] `decide_strategy` selects WIDEN_SEARCH (low mean + few chunks), CHANGE_COLLECTION (low mean + many chunks), RELAX_FILTERS (moderate mean + high variance)
- [ ] `decide_strategy` enforces max_attempts guard and strategy dedup via `attempted_strategies`
- [ ] `report_uncertainty` produces honest report with collections searched, findings, suggestions -- no fabrication
- [ ] `route_after_strategy` returns `"retry"` when strategy set, `"report"` when None
- [ ] `_build_modified_state_*` helpers produce correct state overrides for each strategy
- [ ] `attempted_strategies: set[str]` field added to `MetaReasoningState`
- [ ] `meta_relevance_threshold` and `meta_variance_threshold` added to `Settings`
- [ ] `GENERATE_ALT_QUERIES_SYSTEM` and `REPORT_UNCERTAINTY_SYSTEM` prompts added
- [ ] ResearchGraph mapper node maps ResearchState-to-MetaReasoningState and back
- [ ] `main.py` builds inside-out: MetaReasoning -> Research -> Conversation
- [ ] FR-011 guard: `max_attempts=0` skips meta-reasoning (passes None to `build_research_graph`)
- [ ] FR-017: infrastructure error during retry routes to report_uncertainty with error noted
- [ ] All SSE events emitted (FR-014), all structlog events emitted (FR-016)
- [ ] Unit tests pass for all 4 nodes + 1 edge function
- [ ] Integration tests pass for full graph compilation, recovery flow, uncertainty flow, strategy dedup, max_attempts=0 bypass, infrastructure error
- [ ] Regression suite passes (no regressions across specs 01-03)
- [ ] `ruff check .` passes on all new and modified files
