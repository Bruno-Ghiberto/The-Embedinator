# Data Model: ResearchGraph

**Feature**: 003-research-graph | **Date**: 2026-03-11

## Entity Overview

The ResearchGraph operates on entities already defined in spec-01/02. This document maps spec requirements to existing models and identifies modifications needed.

## Existing Entities (No Changes Required)

### ResearchState (TypedDict)

**Source**: `backend/agent/state.py:33-46`
**Role**: Graph state for each research worker instance. Populated by `route_fan_out()` in `edges.py`.

| Field | Type | Description |
|-------|------|-------------|
| sub_question | `str` | The focused research query to investigate |
| session_id | `str` | Parent conversation session ID |
| selected_collections | `list[str]` | Target Qdrant collections to search |
| llm_model | `str` | Model identifier for orchestrator decisions |
| embed_model | `str` | Model identifier for embedding queries |
| retrieved_chunks | `list[RetrievedChunk]` | Accumulated evidence from all search iterations |
| retrieval_keys | `set[str]` | Deduplication index: `"{normalized_query}:{parent_id}"` |
| tool_call_count | `int` | Running total of tool calls (including retries per FR-016) |
| iteration_count | `int` | Running total of orchestrator loop iterations |
| confidence_score | `float` | Internal confidence (0.0–1.0) computed from retrieval signals |
| answer | `str \| None` | Generated answer text (populated by collect_answer or fallback_response) |
| citations | `list[Citation]` | Citations referencing source documents |
| context_compressed | `bool` | Whether context compression has been applied |

### RetrievedChunk (Pydantic Model)

**Source**: `backend/agent/schemas.py:26-36`
**Role**: A piece of evidence found during search.

| Field | Type | Description |
|-------|------|-------------|
| chunk_id | `str` | Deterministic UUID5 identifier |
| text | `str` | Chunk content text |
| source_file | `str` | Origin document filename |
| page | `int \| None` | Page number (if applicable) |
| breadcrumb | `str` | Structural path (e.g., "Chapter 3 > 3.2 Auth") |
| parent_id | `str` | Reference to parent chunk for broader context |
| collection | `str` | Collection of origin |
| dense_score | `float` | Dense vector similarity score |
| sparse_score | `float` | BM25 sparse similarity score |
| rerank_score | `float \| None` | Cross-encoder rerank score (populated after reranking) |

### ParentChunk (Pydantic Model)

**Source**: `backend/agent/schemas.py:39-45`
**Role**: Broader context chunk fetched from SQLite when a child chunk matches.

| Field | Type | Description |
|-------|------|-------------|
| parent_id | `str` | Unique identifier |
| text | `str` | Full parent chunk text (2000-4000 chars) |
| source_file | `str` | Origin document filename |
| page | `int \| None` | Page number (if applicable) |
| breadcrumb | `str` | Structural path |
| collection | `str` | Collection of origin |

### Citation (Pydantic Model)

**Source**: `backend/agent/schemas.py:83-93`
**Role**: Reference to source evidence in an answer.

| Field | Type | Description |
|-------|------|-------------|
| passage_id | `str` | Referenced chunk ID |
| document_id | `str` | Source document ID |
| document_name | `str` | Source document name |
| start_offset | `int` | Text start offset |
| end_offset | `int` | Text end offset |
| text | `str` | Cited passage text |
| relevance_score | `float` | 0.0–1.0 relevance score |
| source_removed | `bool` | True if source deleted since indexing |

### SubAnswer (Pydantic Model)

**Source**: `backend/agent/schemas.py:96-101`
**Role**: Packaged output of a research session, returned to ConversationGraph.

| Field | Type | Description |
|-------|------|-------------|
| sub_question | `str` | The investigated sub-question |
| answer | `str` | Generated answer text |
| citations | `list[Citation]` | Supporting citations |
| chunks | `list[RetrievedChunk]` | All retrieved evidence |
| confidence_score | `int` | 0-100 integer (converted from internal 0.0-1.0 float) |

## Modified Entity

### compute_confidence (Function)

**Source**: `backend/agent/confidence.py:8-30`
**Change**: Replace Phase 1 placeholder with signal-based computation per FR-009.

**Current** (placeholder): Weighted average of passage relevance scores only.

**New** (signal-based): Compute from multiple retrieval signals:

| Signal | Weight | Description |
|--------|--------|-------------|
| Mean rerank score | 0.4 | Average of top-K cross-encoder rerank scores |
| Chunk count factor | 0.2 | `min(1.0, chunk_count / expected_chunks)` — coverage ratio |
| Top score quality | 0.2 | Highest individual rerank score (best evidence quality) |
| Score variance | 0.1 | Low variance among top scores = higher confidence |
| Collection coverage | 0.1 | Fraction of target collections that returned results |

**Input**: `list[RetrievedChunk]` + `list[str]` (target collections)
**Output**: `float` (0.0–1.0) — converted to `int` (0–100) in `collect_answer` via `int(score * 100)`

## New Internal Entities (Not Persisted)

### Deduplication Key

**Scope**: In-memory per research worker instance (stored in `ResearchState.retrieval_keys`)

```
format: "{normalized_query}:{parent_id}"
normalization: lowercase, strip whitespace, collapse multiple spaces
```

**Lifecycle**: Created when a chunk is first retrieved. Checked before adding any new chunk. Never persisted — lives only for the duration of one research session.

## State Transitions

```
ResearchState lifecycle:

[Initial State] ──────► orchestrator
  (from Send() payload)     │
       ┌────────────────────┘
       ▼
  ┌─────────┐     sufficient    ┌───────────────┐
  │orchestra-│──────────────────►│ collect_answer │──► [SubAnswer returned]
  │   tor    │                  └───────────────┘
  └────┬─────┘
       │ continue
       ▼
  ┌─────────┐
  │  tools   │ (retry once on failure, both count against budget)
  └────┬─────┘
       │
       ▼
  ┌──────────────────┐    compress    ┌──────────────────┐
  │should_compress_   │──────────────►│ compress_context  │
  │    context        │               └────────┬─────────┘
  └────────┬─────────┘                         │
           │ continue                          │
           └──────────┐    ┌───────────────────┘
                      ▼    ▼
                  orchestrator (loop back)

  On budget exhaustion + low confidence:
  orchestrator ──► meta_reasoning (stub) ──► fallback_response ──► [END]

  On tool exhaustion (no new tool calls):
  orchestrator ──► fallback_response ──► [END]
```

## Relationships

```
ConversationGraph ──Send()──► ResearchGraph (1 per sub-question)
ResearchGraph ──uses──► HybridSearcher (Qdrant)
ResearchGraph ──uses──► Reranker (CrossEncoder)
ResearchGraph ──uses──► ParentStore (SQLite)
ResearchGraph ──returns──► SubAnswer → ConversationGraph.aggregate_answers
ResearchGraph ──routes──► MetaReasoningGraph (stub in Phase 1)
```
