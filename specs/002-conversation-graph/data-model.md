# Data Model: ConversationGraph

**Date**: 2026-03-10
**Feature**: [spec.md](spec.md)

## Entities

### ConversationState (TypedDict — extends existing)

The top-level state for the ConversationGraph. Passed through all nodes.

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `session_id` | `str` | Existing | UUID identifying the conversation session |
| `messages` | `list[BaseMessage]` | Existing | LangChain message history (Human, AI, System) |
| `intent` | `str` | **NEW** | `"rag_query"` \| `"collection_mgmt"` \| `"ambiguous"` — set by `classify_intent` |
| `query_analysis` | `QueryAnalysis \| None` | Existing | Structured decomposition from `rewrite_query` node |
| `sub_answers` | `list[SubAnswer]` | Existing | Results from parallel ResearchGraph instances |
| `selected_collections` | `list[str]` | Existing | Collection IDs the user has selected for search |
| `llm_model` | `str` | Existing | Model identifier (e.g., `"qwen2.5:7b"`) |
| `embed_model` | `str` | Existing | Embedding model identifier |
| `final_response` | `str \| None` | Existing | Aggregated and formatted answer text |
| `citations` | `list[Citation]` | Existing | Deduplicated citation list with passage references |
| `groundedness_result` | `GroundednessResult \| None` | Existing | Phase 2: per-claim verification results |
| `confidence_score` | `int` | Existing | 0–100 integer, evidence-based (weighted avg of passage scores) |
| `iteration_count` | `int` | Existing | Tracks clarification rounds (max 2) |

**Validation Rules**:
- `intent` must be one of `{"rag_query", "collection_mgmt", "ambiguous"}`
- `confidence_score` must be in range [0, 100]
- `iteration_count` must be in range [0, 2] for clarification tracking
- `selected_collections` must be non-empty for `rag_query` intent (checked in `fan_out`)

### QueryAnalysis (Pydantic — existing)

Structured output from the `rewrite_query` node via LLM structured output.

| Field | Type | Validation | Description |
|-------|------|------------|-------------|
| `is_clear` | `bool` | Required | Whether the query is clear enough to proceed |
| `sub_questions` | `list[str]` | Max 5 items | Decomposed sub-questions, each targeting a specific aspect |
| `clarification_needed` | `str \| None` | Optional | Human-readable clarification prompt (when `is_clear=False`) |
| `collections_hint` | `list[str]` | Optional | Suggested collection names to search |
| `complexity_tier` | `Literal[...]` | Enum | `"factoid"` \| `"lookup"` \| `"comparison"` \| `"analytical"` \| `"multi_hop"` |

### Intent (Implicit — string enum)

Not a separate model; stored as `str` in `ConversationState.intent`.

| Value | Meaning | Routing Target |
|-------|---------|----------------|
| `"rag_query"` | User is asking a document question | `rewrite_query` node |
| `"collection_mgmt"` | User wants to manage collections | `handle_collection_mgmt` stub |
| `"ambiguous"` | Intent unclear, needs clarification | `request_clarification` node |

### SubAnswer (Pydantic — existing)

Result of researching a single sub-question via ResearchGraph.

| Field | Type | Description |
|-------|------|-------------|
| `sub_question` | `str` | The original sub-question |
| `answer` | `str` | Generated answer text |
| `citations` | `list[Citation]` | Supporting citations for this sub-answer |
| `chunks` | `list[RetrievedChunk]` | Retrieved passages used for generation |
| `confidence` | `float` | Per-sub-question confidence (0.0–1.0 internal) |

### Citation (Pydantic — existing)

A reference to a specific source passage.

| Field | Type | Description |
|-------|------|-------------|
| `passage_id` | `str` | Unique ID of the cited passage/chunk |
| `document_id` | `str` | ID of the parent document |
| `document_name` | `str` | Human-readable document name |
| `start_offset` | `int` | Start character offset in parent chunk |
| `end_offset` | `int` | End character offset in parent chunk |
| `text` | `str` | Excerpt of the cited passage (max 200 chars) |
| `relevance_score` | `float` | Cross-encoder relevance score (0.0–1.0) |

### GroundednessResult (Pydantic — existing, Phase 2)

Per-claim verification of the generated answer. Stub returns `None` in Phase 1.

| Field | Type | Description |
|-------|------|-------------|
| `verifications` | `list[ClaimVerification]` | Per-claim verdict list |
| `overall_grounded` | `bool` | `True` if >50% claims are supported |
| `confidence_adjustment` | `float` | Modifier applied to confidence score |

### Session (SQLite — existing)

Session persistence in the existing `embedinator.db`. No schema changes needed.

| Column | Type | Description |
|--------|------|-------------|
| `id` | `TEXT PRIMARY KEY` | UUID session identifier |
| `messages_json` | `TEXT` | JSON-serialized message history |
| `selected_collections` | `TEXT` | JSON array of collection IDs |
| `llm_model` | `TEXT` | Active LLM model name |
| `embed_model` | `TEXT` | Active embedding model name |
| `created_at` | `TEXT` | ISO 8601 creation timestamp |
| `updated_at` | `TEXT` | ISO 8601 last update timestamp |

## Relationships

```
ConversationState
├── contains → messages: list[BaseMessage]
├── contains → intent: str (set by classify_intent)
├── contains → query_analysis: QueryAnalysis (set by rewrite_query)
├── contains → sub_answers: list[SubAnswer] (set by aggregate_answers)
│   └── each SubAnswer contains → citations: list[Citation]
│   └── each SubAnswer contains → chunks: list[RetrievedChunk]
├── contains → citations: list[Citation] (deduplicated by aggregate_answers)
├── contains → groundedness_result: GroundednessResult | None (Phase 2 stub)
└── persisted via → Session (SQLite row, loaded by init_session)
```

## State Transitions

### ConversationGraph Flow

```
[INIT] → init_session → [SESSION_LOADED]
[SESSION_LOADED] → classify_intent → [INTENT_CLASSIFIED]
[INTENT_CLASSIFIED] → route_intent:
  ├── rag_query → [QUERY_REWRITING]
  ├── collection_mgmt → [COLLECTION_MGMT] → [DONE]
  └── ambiguous → [CLARIFYING]

[QUERY_REWRITING] → rewrite_query → [QUERY_ANALYZED]
[QUERY_ANALYZED] → should_clarify:
  ├── clear → [DISPATCHING]
  └── unclear (iteration_count < 2) → [CLARIFYING]
  └── unclear (iteration_count >= 2) → [DISPATCHING] (best-effort)

[CLARIFYING] → request_clarification → interrupt → [PAUSED]
[PAUSED] → Command(resume=response) → [SESSION_LOADED] (re-classify)

[DISPATCHING] → fan_out → Send() × N → [RESEARCHING]
[RESEARCHING] → ResearchGraph × N → [AGGREGATING]
[AGGREGATING] → aggregate_answers → [VERIFYING]
[VERIFYING] → verify_groundedness (stub) → [VALIDATING]
[VALIDATING] → validate_citations (stub) → [COMPRESSING]
[COMPRESSING] → summarize_history → [FORMATTING]
[FORMATTING] → format_response → [DONE]
```

### Clarification State Machine

```
Round 0: Query arrives → rewrite_query → is_clear=False → interrupt (iteration_count=0→1)
Round 1: User responds → rewrite_query → is_clear=False → interrupt (iteration_count=1→2)
Round 2: User responds → rewrite_query → is_clear=False → SKIP (iteration_count=2, proceed as rag_query)
```
