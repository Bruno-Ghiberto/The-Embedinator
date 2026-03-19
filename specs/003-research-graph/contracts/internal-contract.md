# Internal Contract: ResearchGraph

**Feature**: 003-research-graph | **Date**: 2026-03-11

## Overview

ResearchGraph is an internal component with no external API. Its contract is defined by:
1. **Input**: `ResearchState` TypedDict populated by `route_fan_out()` in `backend/agent/edges.py`
2. **Output**: Completed `ResearchState` with `answer`, `citations`, `confidence_score` fields populated
3. **Packaging**: `collect_answer` node converts state into a `SubAnswer` Pydantic model consumed by `aggregate_answers` in ConversationGraph

## Input Contract

The ResearchGraph receives its initial state via `Send("research", payload)` from `route_fan_out()` (edges.py:87-101):

```python
payload: ResearchState = {
    "sub_question": str,           # Non-empty sub-question text
    "session_id": str,             # Valid session UUID
    "selected_collections": list[str],  # At least one collection name
    "llm_model": str,              # Valid model identifier (e.g., "qwen2.5:7b")
    "embed_model": str,            # Valid embedding model identifier
    "retrieved_chunks": [],        # Always empty at start
    "retrieval_keys": set(),       # Always empty at start
    "tool_call_count": 0,          # Always 0 at start
    "iteration_count": 0,          # Always 0 at start
    "confidence_score": 0.0,       # Always 0.0 at start
    "answer": None,                # Always None at start
    "citations": [],               # Always empty at start
    "context_compressed": False,   # Always False at start
}
```

## Output Contract

On completion, the ResearchGraph state contains:

| Field | Guaranteed | Value |
|-------|-----------|-------|
| answer | Yes | Non-None string (either answer text or fallback message) |
| citations | Yes | List of Citation objects (may be empty for fallback) |
| confidence_score | Yes | float 0.0–1.0 (converted to int 0-100 for SubAnswer) |
| retrieved_chunks | Yes | List of RetrievedChunk objects (may be empty) |
| tool_call_count | Yes | int <= MAX_TOOL_CALLS (8) + retry overhead |
| iteration_count | Yes | int <= MAX_ITERATIONS (10) |

## Tool Interface Contracts

All tools use LangChain `@tool` decorator and return typed results:

| Tool | Input | Output | Side Effects |
|------|-------|--------|-------------|
| `search_child_chunks` | `query: str, collection: str, top_k: int=20, filters: dict\|None=None` | `list[RetrievedChunk]` | Qdrant search + rerank |
| `retrieve_parent_chunks` | `parent_ids: list[str]` | `list[ParentChunk]` | SQLite read |
| `cross_encoder_rerank` | `query: str, chunks: list[RetrievedChunk], top_k: int=5` | `list[RetrievedChunk]` | CrossEncoder inference |
| `filter_by_collection` | `collection_name: str` | `dict` (state modification) | None |
| `filter_by_metadata` | `filters: dict` | `dict` (state modification) | None |
| `semantic_search_all_collections` | `query: str, top_k: int=20` | `list[RetrievedChunk]` | Multi-collection Qdrant search |

## Integration with ConversationGraph

```python
# In conversation_graph.py:
graph.add_node("research", research_graph)  # compiled ResearchGraph

# Send() dispatches to "research" node with ResearchState payload
# ConversationGraph expects: graph.add_edge("research", "aggregate_answers")
# aggregate_answers reads SubAnswer from completed research state
```
