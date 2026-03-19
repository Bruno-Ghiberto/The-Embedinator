# Spec 02: ConversationGraph -- Implementation Plan Context

## Component Overview

The ConversationGraph is the top-level LangGraph state machine that manages every chat interaction. It handles session lifecycle, intent classification, query analysis, parallel sub-question dispatch, answer aggregation, history compression, groundedness verification (Phase 2 stub), citation validation (Phase 2 stub), and response formatting for NDJSON streaming. It is the only graph that the FastAPI chat endpoint directly invokes.

## Technical Approach

- **LangGraph StateGraph**: Define `ConversationGraph` using `StateGraph(ConversationState)` with nodes for each processing step and conditional edges for routing.
- **LangGraph Send()**: Use the `Send()` API via `add_conditional_edges` to spawn one `ResearchGraph` per sub-question for parallel execution.
- **LangGraph Interrupt**: Use `interrupt()` for the clarification flow with `Command(resume=...)` for resumption. Graph state is checkpointed to SQLite via LangGraph's `MemorySaver` or async SQLite checkpointer.
- **Pydantic Structured Output**: Use LangChain's `.with_structured_output(QueryAnalysis)` for the `rewrite_query` node.
- **Cross-Encoder** *(Phase 2)*: Use `sentence-transformers` `CrossEncoder` for citation validation alignment checks. Phase 1 stub passes citations through unvalidated.
- **Dependency Injection**: LLM, reranker, and DB instances are injected into node functions, not imported globally.
- **NDJSON Streaming**: Use LangGraph's `stream(stream_mode="messages")` for token-by-token streaming, yielding `{"type": "chunk", "text": "..."}` lines per ADR-007.

## Existing Phase 1 Modules (Reuse, Don't Rebuild)

The following modules were implemented in spec-01 and MUST be reused:

| Module | Purpose | Key Exports |
|--------|---------|-------------|
| `backend/agent/state.py` | TypedDict state schemas | `ConversationState`, `ResearchState`, `MetaReasoningState` |
| `backend/agent/schemas.py` | Pydantic models | `QueryAnalysis`, `Citation`, `SubAnswer`, `RetrievedChunk`, `ClaimVerification`, `GroundednessResult`, `TraceResponse`, `AnswerResponse` |
| `backend/agent/prompts.py` | Prompt constants | `SYSTEM_PROMPT`, `QUERY_ANALYSIS_PROMPT`, `ANSWER_SYNTHESIS_PROMPT`, `GROUNDEDNESS_CHECK_PROMPT`, `NO_RELEVANT_INFO_RESPONSE` |
| `backend/agent/retrieval.py` | Qdrant retrieval | `retrieve_passages()` |
| `backend/agent/citations.py` | Citation construction | `build_citations()`, `format_passages_for_prompt()` |
| `backend/agent/confidence.py` | Evidence-based scoring | `compute_confidence()` — weighted average → 0–100 int |
| `backend/agent/answer_generator.py` | LLM answer generation | `generate_answer_stream()`, `generate_answer()` |
| `backend/api/chat.py` | Current chat endpoint | Direct RAG pipeline (will be refactored to invoke ConversationGraph) |

**Important**: `ConversationState` in `state.py` MUST be extended to add the `intent` field (`str` — `"rag_query" | "collection_mgmt" | "ambiguous"`). All other existing fields are preserved.

## File Structure

```
backend/
  agent/
    conversation_graph.py    # StateGraph definition, node wiring, edge wiring
    nodes.py                 # All node function implementations (stateless, pure)
    edges.py                 # All conditional edge functions (routing logic)
    prompts.py               # Prompt constants (extend existing, add new)
    schemas.py               # Pydantic models (already created in spec-01)
    state.py                 # TypedDict state schemas (extend, add intent field)
    retrieval.py             # Query retrieval (already created in spec-01)
    citations.py             # Citation construction (already created in spec-01)
    confidence.py            # Confidence scoring (already created in spec-01)
    answer_generator.py      # LLM answer generation (already created in spec-01)
    tools.py                 # LangChain tool definitions (used by ResearchGraph)
  api/
    chat.py                  # FastAPI chat endpoint (refactor to invoke ConversationGraph)
```

## Implementation Steps

### Step 1: State Schema & Prompt Updates

1. **Extend `ConversationState`** in `backend/agent/state.py`:
   - Add `intent: str` field (values: `"rag_query"`, `"collection_mgmt"`, `"ambiguous"`)
   - Preserve all existing fields unchanged

2. **Add prompt constants** in `backend/agent/prompts.py`:
   - `CLASSIFY_INTENT_SYSTEM` / `CLASSIFY_INTENT_USER` — intent classification prompts
   - `REWRITE_QUERY_SYSTEM` / `REWRITE_QUERY_USER` — query decomposition prompts
   - `VERIFY_GROUNDEDNESS_SYSTEM` — claim verification prompt (Phase 2, define now)
   - `FORMAT_RESPONSE_SYSTEM` — citation formatting prompt
   - `SUMMARIZE_HISTORY_SYSTEM` — conversation compression prompt
   - Existing prompts (`SYSTEM_PROMPT`, `QUERY_ANALYSIS_PROMPT`, etc.) MAY be preserved for backward compatibility or removed if fully superseded

### Step 2: Node Implementations in `backend/agent/nodes.py`

All node functions are stateless and pure — state is passed in and returned.

- `init_session(state, *, db)` — Load session from SQLite, restore message history. On SQLite failure: create fresh session, log warning.
- `classify_intent(state, *, llm)` — LLM call with `CLASSIFY_INTENT_SYSTEM/USER` prompts, parse JSON response to extract intent. On LLM failure: default to `"rag_query"`.
- `rewrite_query(state, *, llm)` — LLM call with `.with_structured_output(QueryAnalysis)`. On parse failure: retry once with simplified prompt, then fall back to single-question mode (original query as sole sub-question).
- `request_clarification(state)` — Call `interrupt(state["query_analysis"].clarification_needed)`. Graph checkpoints to SQLite. Resumes via `Command(resume=user_response)`. Maximum 2 clarification rounds per query (tracked via `iteration_count`); after 2nd attempt, proceed with best-effort interpretation as `rag_query`.
- `fan_out(state)` — Produce `List[Send]` from `query_analysis.sub_questions`. If 0 sub-questions: use original query as sole sub-question. Check `selected_collections` is non-empty; if empty, return error prompting user to select a collection.
- `aggregate_answers(state)` — Merge `sub_answers`, deduplicate citations by `passage_id`, rank by relevance score. If some sub-answers failed: aggregate available, note gaps.
- `verify_groundedness(state, *, llm)` — *(Phase 2 stub)* Pass through: set `groundedness_result = None`, return state unchanged. When activated: NLI claim verification producing `GroundednessResult`.
- `validate_citations(state, *, reranker)` — *(Phase 2 stub)* Pass through: return `citations` unchanged. When activated: cross-encoder alignment check with `CITATION_ALIGNMENT_THRESHOLD` (0.3).
- `summarize_history(state, *, llm)` — Compress conversation `messages` when total tokens exceed **75% of the configured model's context window**. Uses LLM to produce a summary of older messages while preserving the most recent exchange and key context.
- `format_response(state)` — Apply inline citation markers `[1]`, `[2]`, etc. Add confidence indicator (0–100 integer). When GAV is active (Phase 2): annotate `[unverified]` claims, remove contradicted claims. Format for NDJSON delivery per ADR-007.

### Step 3: Edge Functions in `backend/agent/edges.py`

- `route_intent(state)` — Returns destination node name based on `state["intent"]`:
  - `"rag_query"` → `"rewrite_query"`
  - `"collection_mgmt"` → `"handle_collection_mgmt"` (stub, out of scope)
  - `"ambiguous"` → `"request_clarification"`
- `should_clarify(state)` — Returns `True` if `query_analysis.is_clear == False` AND `iteration_count < 2`; otherwise `False` (proceed with best-effort)
- `route_fan_out(state)` — Returns `List[Send]` for dynamic fan-out via `add_conditional_edges`

### Step 4: Graph Definition in `backend/agent/conversation_graph.py`

- Create `StateGraph(ConversationState)` with a checkpointer for interrupt/resume
- Add all nodes (including Phase 2 stubs and `handle_collection_mgmt` stub)
- Add conditional edges (`route_intent`, `should_clarify`, `route_fan_out`)
- Add sequential edges (`aggregate → verify → validate → summarize_history → format`)
- Compile with SQLite-backed checkpointer for clarification interrupt persistence
- Export `build_conversation_graph(research_graph)` factory function

### Step 5: Chat API Refactor in `backend/api/chat.py`

- Refactor existing direct RAG pipeline to invoke compiled `ConversationGraph`
- Build initial `ConversationState` from request: `{message, collection_ids, llm_model, session_id}`
- Handle `interrupt` events for clarification flow (detect `__interrupt__` in stream)
- Stream response via `StreamingResponse` with `media_type="application/x-ndjson"` per ADR-007
- Use LangGraph's `stream(stream_mode="messages")` for token-by-token NDJSON streaming
- Write `query_trace` record to SQLite after completion (Constitution Principle IV)

### Step 6: Tests

- Unit tests for each node function (mock LLM, DB, reranker)
- Unit tests for each edge function
- Integration test: full graph execution with mock ResearchGraph subgraph
- Integration test: clarification interrupt/resume round-trip
- Integration test: NDJSON streaming output format validation

## Integration Points

- **ResearchGraph (spec-03)**: ConversationGraph's `fan_out` node spawns ResearchGraph instances via `Send()`. Until spec-03 is implemented, use a mock/stub ResearchGraph that returns a fixed `SubAnswer`. The ResearchGraph must be compiled separately and passed to `build_conversation_graph()`.
- **MetaReasoningGraph (spec-04)**: ResearchGraph internally dispatches to MetaReasoningGraph when confidence is below threshold. ConversationGraph is not directly aware of MetaReasoningGraph.
- **FastAPI chat endpoint**: The only entry point for the ConversationGraph. Handles NDJSON streaming of graph output per ADR-007.
- **SQLite**: `init_session` reads session history; LangGraph checkpointer serializes graph state for interrupt/resume; `query_trace` written after response (Constitution Principle IV).
- **Provider Registry**: LLM model is resolved via `ProviderRegistry` based on `state["llm_model"]` at query time (not cached statically).

## Key Code Patterns

### Graph Definition Pattern

```python
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send, interrupt, Command
from langgraph.checkpoint.memory import MemorySaver

def build_conversation_graph(research_graph, checkpointer=None):
    graph = StateGraph(ConversationState)

    # Core nodes
    graph.add_node("init_session", init_session)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("rewrite_query", rewrite_query)
    graph.add_node("request_clarification", request_clarification)
    graph.add_node("research", research_graph)  # subgraph
    graph.add_node("aggregate_answers", aggregate_answers)
    graph.add_node("summarize_history", summarize_history)
    graph.add_node("format_response", format_response)

    # Phase 2 stub nodes
    graph.add_node("verify_groundedness", verify_groundedness)
    graph.add_node("validate_citations", validate_citations)

    # Out-of-scope stub (routing target only)
    graph.add_node("handle_collection_mgmt", handle_collection_mgmt)

    # Edges
    graph.add_edge(START, "init_session")
    graph.add_edge("init_session", "classify_intent")
    graph.add_conditional_edges("classify_intent", route_intent, {
        "rag_query": "rewrite_query",
        "collection_mgmt": "handle_collection_mgmt",
        "ambiguous": "request_clarification",
    })
    graph.add_edge("handle_collection_mgmt", END)
    graph.add_edge("request_clarification", "classify_intent")
    graph.add_conditional_edges("rewrite_query", should_clarify, {
        True: "request_clarification",
        False: "fan_out",
    })
    # fan_out uses Send() for dynamic dispatch
    graph.add_conditional_edges("rewrite_query", route_fan_out)
    graph.add_edge("research", "aggregate_answers")
    graph.add_edge("aggregate_answers", "verify_groundedness")
    graph.add_edge("verify_groundedness", "validate_citations")
    graph.add_edge("validate_citations", "summarize_history")
    graph.add_edge("summarize_history", "format_response")
    graph.add_edge("format_response", END)

    return graph.compile(checkpointer=checkpointer or MemorySaver())
```

### Fan-Out with Send() Pattern

```python
from langgraph.types import Send

def route_fan_out(state: ConversationState) -> list[Send]:
    """Dynamic fan-out: one ResearchGraph per sub-question."""
    sub_questions = state["query_analysis"].sub_questions
    if not sub_questions:
        # Edge case: fall back to original query
        sub_questions = [state["messages"][-1].content]

    return [
        Send("research", {
            "sub_question": sub_q,
            "session_id": state["session_id"],
            "selected_collections": state["query_analysis"].collections_hint
                or state["selected_collections"],
            "llm_model": state["llm_model"],
            "embed_model": state["embed_model"],
            "retrieved_chunks": [],
            "retrieval_keys": set(),
            "tool_call_count": 0,
            "iteration_count": 0,
            "confidence_score": 0.0,
            "answer": None,
            "citations": [],
            "context_compressed": False,
        })
        for sub_q in sub_questions
    ]
```

### Clarification Interrupt Pattern

```python
from langgraph.types import interrupt, Command

def request_clarification(state: ConversationState) -> dict:
    """Pause graph and yield clarification question to the UI."""
    clarification = state["query_analysis"].clarification_needed
    # interrupt() checkpoints graph state and yields to the caller
    user_response = interrupt(clarification)
    # When resumed via Command(resume=user_response), execution continues here
    return {
        "messages": state["messages"] + [
            HumanMessage(content=user_response)
        ],
        "iteration_count": state["iteration_count"] + 1,
    }
```

### NDJSON Streaming Pattern (ADR-007)

```python
import json
from fastapi.responses import StreamingResponse

async def chat_endpoint(request: ChatRequest):
    graph = get_compiled_graph()
    initial_state = build_initial_state(request)
    config = {"configurable": {"thread_id": request.session_id}}

    async def generate():
        start_time = time.monotonic()
        final_state = None

        async for chunk, metadata in graph.astream(
            initial_state,
            stream_mode="messages",
            config=config,
        ):
            if hasattr(chunk, "content") and chunk.content:
                yield json.dumps({"type": "chunk", "text": chunk.content}) + "\n"

            # Check for interrupt (clarification needed)
            if "__interrupt__" in metadata:
                interrupt_value = metadata["__interrupt__"][0].value
                yield json.dumps({
                    "type": "clarification",
                    "question": interrupt_value,
                }) + "\n"
                return

        # Get final state for metadata
        final_state = graph.get_state(config).values
        latency_ms = int((time.monotonic() - start_time) * 1000)

        # Final metadata frame
        yield json.dumps({
            "type": "metadata",
            "trace_id": trace_id,
            "confidence": final_state["confidence_score"],
            "citations": [c.model_dump() for c in final_state["citations"]],
            "latency_ms": latency_ms,
        }) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")
```

## Node Error Handling

| Node | Failure Mode | Recovery |
|------|-------------|----------|
| `init_session` | SQLite read failure | Create fresh session, log warning |
| `classify_intent` | LLM call failure | Default to `"rag_query"` intent |
| `rewrite_query` | Structured output parse failure | Retry once with simplified prompt; fall back to single-question mode |
| `fan_out` | No sub-questions generated | Use original query as sole sub-question |
| `fan_out` | No collections selected | Return error prompting user to select a collection |
| `aggregate_answers` | One or more ResearchGraphs failed | Aggregate available answers, note gaps |
| `verify_groundedness` | LLM call failure *(Phase 2)* | Skip verification, set `groundedness_result = None`, log warning |
| `validate_citations` | Cross-encoder failure *(Phase 2)* | Pass citations through unvalidated |
| `summarize_history` | LLM call failure | Keep messages uncompressed, log warning |

## Agent Team Strategy (Claude Code)

Implementation can be parallelized using Claude Code's Agent tool with worktree isolation. Tasks are organized into sequential waves; within each wave, agents run in parallel.

### Wave 1: Scaffold (Sequential, Fast)

**Agent: Scaffold**
- Extend `ConversationState` in `state.py` — add `intent` field
- Add all new prompt constants to `prompts.py`
- Create `edges.py` with `route_intent`, `should_clarify`, `route_fan_out`

> This wave unblocks all node implementations. Run as a single agent since changes are small and interdependent.

### Wave 2: Node Implementations (Parallel, Worktrees)

All node functions are stateless and pure — ideal for parallel development.

| Agent | Worktree | Nodes | Dependencies |
|-------|----------|-------|-------------|
| **Agent A** | `worktree-nodes-session` | `init_session`, `summarize_history` | `state.py`, `prompts.py`, `aiosqlite` |
| **Agent B** | `worktree-nodes-analysis` | `classify_intent`, `rewrite_query` | `state.py`, `prompts.py`, `schemas.py` |
| **Agent C** | `worktree-nodes-dispatch` | `fan_out`, `aggregate_answers`, `format_response` | `state.py`, `schemas.py`, `citations.py`, `confidence.py` |
| **Agent D** | `worktree-nodes-interrupt` | `request_clarification`, `handle_collection_mgmt` (stub), `verify_groundedness` (stub), `validate_citations` (stub) | `state.py`, `schemas.py` |

> Each agent works on a subset of nodes with no shared file conflicts. Merge all into `nodes.py` after completion.

### Wave 3: Integration (Sequential)

**Agent: Integration**
- Wire all nodes into `conversation_graph.py` using `build_conversation_graph()`
- Create mock/stub `ResearchGraph` for testing until spec-03 is implemented
- Verify graph compiles without errors

### Wave 4: API Refactor (Sequential)

**Agent: API**
- Refactor `chat.py` to invoke `ConversationGraph` instead of direct RAG pipeline
- Implement NDJSON streaming with `stream_mode="messages"`
- Handle clarification interrupt detection and response
- Preserve `query_trace` recording (Constitution Principle IV)

### Wave 5: Tests (Parallel, Worktrees)

| Agent | Worktree | Test Scope |
|-------|----------|------------|
| **Agent E** | `worktree-tests-unit` | Unit tests for all nodes and edges (mock LLM, DB, reranker) |
| **Agent F** | `worktree-tests-integration` | Integration tests: graph execution, interrupt/resume, NDJSON format |

## Clarification Decisions

These decisions were made during `/speckit.clarify` and MUST be respected in implementation:

1. **Collection management handler**: Out of scope — `handle_collection_mgmt` is a stub node that returns a "not implemented" or pass-through response. ConversationGraph only classifies and routes.
2. **Clarification round cap**: Maximum 2 rounds per query. After 2 clarification attempts, proceed with best-effort interpretation as a document query. Track via `iteration_count`.
3. **History compression threshold**: Trigger when conversation history exceeds 75% of the configured model's context window.
4. **No collections selected**: If `selected_collections` is empty when a `rag_query` is routed, prompt the user to select at least one collection before proceeding.

## Phase Assignment

- **Phase 1 (This Spec)**: ConversationGraph with all nodes. Phase 2 features are present as stub pass-throughs.
  - Active nodes: `init_session`, `classify_intent`, `rewrite_query`, `request_clarification`, `fan_out`, `aggregate_answers`, `summarize_history`, `format_response`, `handle_collection_mgmt` (stub)
  - Stub nodes: `verify_groundedness` (returns `groundedness_result = None`), `validate_citations` (passes citations through unchanged)
- **Phase 2 (Future Spec)**: Activate `verify_groundedness` (GAV) with NLI-based claim verification. Activate `validate_citations` with cross-encoder alignment checks (`CITATION_ALIGNMENT_THRESHOLD = 0.3`).
