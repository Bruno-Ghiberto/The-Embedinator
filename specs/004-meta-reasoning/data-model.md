# Data Model: MetaReasoningGraph

**Branch**: `004-meta-reasoning` | **Date**: 2026-03-11 | **Spec**: [spec.md](spec.md)

## Entities

### MetaReasoningState (TypedDict)

**Location**: `backend/agent/state.py` (existing, needs update)

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `sub_question` | `str` | ResearchState | The sub-question being researched |
| `retrieved_chunks` | `list[RetrievedChunk]` | ResearchState | Chunks retrieved during research |
| `alternative_queries` | `list[str]` | `generate_alternative_queries` | 3 rephrased query formulations |
| `mean_relevance_score` | `float` | `evaluate_retrieval_quality` | Mean cross-encoder score across all chunks |
| `chunk_relevance_scores` | `list[float]` | `evaluate_retrieval_quality` | Per-chunk cross-encoder scores |
| `meta_attempt_count` | `int` | `decide_strategy` | Current attempt number (0-based, incremented per strategy) |
| `recovery_strategy` | `str \| None` | `decide_strategy` | Selected strategy: WIDEN_SEARCH, CHANGE_COLLECTION, RELAX_FILTERS, or None |
| `modified_state` | `dict \| None` | `decide_strategy` | ResearchState field overrides for retry |
| `answer` | `str \| None` | `report_uncertainty` | Uncertainty report text (only set on failure) |
| `uncertainty_reason` | `str \| None` | `report_uncertainty` | Why results were insufficient |
| `attempted_strategies` | `set[str]` | `decide_strategy` | **NEW** — Previously attempted strategies for dedup (FR-015) |

**Validation rules**:
- `meta_attempt_count` must be `>= 0` and `<= settings.meta_reasoning_max_attempts`
- `alternative_queries` must contain exactly 3 items when populated
- `recovery_strategy` must be one of `"WIDEN_SEARCH"`, `"CHANGE_COLLECTION"`, `"RELAX_FILTERS"`, or `None`
- `attempted_strategies` must be a subset of `{"WIDEN_SEARCH", "CHANGE_COLLECTION", "RELAX_FILTERS"}`

**State transitions**:
1. **Entry** → `sub_question`, `retrieved_chunks` populated from ResearchState; all other fields at defaults
2. **After generate_alternative_queries** → `alternative_queries` populated (3 items)
3. **After evaluate_retrieval_quality** → `mean_relevance_score`, `chunk_relevance_scores` populated
4. **After decide_strategy (recovery)** → `recovery_strategy`, `modified_state`, `meta_attempt_count`, `attempted_strategies` updated
5. **After decide_strategy (no recovery)** → `recovery_strategy = None`
6. **After report_uncertainty** → `answer`, `uncertainty_reason` populated

### Recovery Strategy (Enum-like constants)

**Location**: `backend/agent/meta_reasoning_nodes.py` (inline constants)

| Strategy | Trigger Condition | Modified State Fields |
|----------|-------------------|----------------------|
| `WIDEN_SEARCH` | `mean < threshold AND chunk_count < 3` | `selected_collections: ALL`, `top_k_retrieval: 40`, uses `alternative_queries` |
| `CHANGE_COLLECTION` | `mean < threshold AND chunk_count >= 3` | `selected_collections: ROTATE`, `sub_question: alternative_queries[0]` |
| `RELAX_FILTERS` | `mean >= threshold AND variance > threshold` | `top_k_retrieval: 40`, `payload_filters: NONE`, `top_k_rerank: 10` |

### Settings Fields (new)

**Location**: `backend/config.py` (existing, needs update)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `meta_relevance_threshold` | `float` | `0.2` | Mean cross-encoder score below which retrieval is considered poor |
| `meta_variance_threshold` | `float` | `0.15` | Score stdev above which results are considered noisy |
| `meta_reasoning_max_attempts` | `int` | `2` | Maximum recovery attempts (already exists) |

### Prompt Constants (new)

**Location**: `backend/agent/prompts.py` (existing, needs update)

| Constant | Used By | Placeholders |
|----------|---------|-------------|
| `GENERATE_ALT_QUERIES_SYSTEM` | `generate_alternative_queries` | `{sub_question}`, `{chunk_summaries}` |
| `REPORT_UNCERTAINTY_SYSTEM` | `report_uncertainty` | Context built from state fields |

## Relationships

```
ResearchState --[triggers]--> MetaReasoningState
  via should_continue_loop "exhausted" edge

MetaReasoningState --[produces]--> modified_state (dict)
  applied back to ResearchState for retry

MetaReasoningState --[produces]--> answer + uncertainty_reason
  propagated through ResearchGraph to ConversationGraph

Settings --[configures]--> decide_strategy
  via meta_relevance_threshold, meta_variance_threshold, meta_reasoning_max_attempts

Reranker --[scores]--> chunk_relevance_scores
  via evaluate_retrieval_quality node

LLM --[generates]--> alternative_queries, answer
  via generate_alternative_queries, report_uncertainty nodes
```

## Dependency on Existing Models

- **RetrievedChunk** (`backend/agent/schemas.py`): Pydantic model with `rerank_score: float | None` field, used by `evaluate_retrieval_quality`
- **Reranker** (`backend/retrieval/reranker.py`): Wraps `CrossEncoder`, provides `.rerank(query, chunks, top_k)` method returning scored `RetrievedChunk` list
- **Settings** (`backend/config.py`): Pydantic `BaseSettings` with env var loading
