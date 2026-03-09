# Spec 02: ConversationGraph -- Implementation Plan Context

## Component Overview

The ConversationGraph is the top-level LangGraph state machine that manages every chat interaction. It handles session lifecycle, query analysis, parallel sub-question dispatch, answer aggregation, groundedness verification, citation validation, and response formatting. It is the only graph that the FastAPI chat endpoint directly invokes.

## Technical Approach

- **LangGraph StateGraph**: Define `ConversationGraph` using `StateGraph(ConversationState)` with nodes for each processing step and conditional edges for routing.
- **LangGraph Send()**: Use the `Send()` API to spawn one `ResearchGraph` per sub-question for parallel execution.
- **LangGraph Interrupt**: Use `interrupt()` for the clarification flow -- serialize graph state to SQLite checkpoint.
- **Pydantic Structured Output**: Use LangChain's `.with_structured_output(QueryAnalysis)` for the `rewrite_query` node.
- **Cross-Encoder**: Use `sentence-transformers` `CrossEncoder` for citation validation alignment checks.
- **Dependency Injection**: LLM, reranker, and DB instances are injected into node functions, not imported globally.

## File Structure

```
backend/
  agent/
    conversation_graph.py    # StateGraph definition, node wiring, edge wiring
    nodes.py                 # All node function implementations (stateless, pure)
    edges.py                 # All conditional edge functions (routing logic)
    prompts.py               # All system and user prompt constants
    schemas.py               # Pydantic models (already created in spec-01)
    state.py                 # TypedDict state schemas (already created in spec-01)
    tools.py                 # LangChain tool definitions (used by ResearchGraph)
  api/
    chat.py                  # FastAPI chat endpoint that invokes ConversationGraph
```

## Implementation Steps

1. **Define prompt constants in `backend/agent/prompts.py`**: Add all ConversationGraph prompt templates: `CLASSIFY_INTENT_SYSTEM`, `CLASSIFY_INTENT_USER`, `REWRITE_QUERY_SYSTEM`, `REWRITE_QUERY_USER`, `VERIFY_GROUNDEDNESS_SYSTEM`, `FORMAT_RESPONSE_SYSTEM`.

2. **Implement ConversationGraph node functions in `backend/agent/nodes.py`**:
   - `init_session(state, *, db)` -- Load session from SQLite, restore message history
   - `classify_intent(state, *, llm)` -- LLM call with classify_intent prompts, parse JSON response
   - `rewrite_query(state, *, llm)` -- LLM call with structured output, produce `QueryAnalysis`
   - `request_clarification(state)` -- LangGraph `interrupt()` call
   - `fan_out(state)` -- Produce `List[Send]` from `query_analysis.sub_questions`
   - `aggregate_answers(state)` -- Merge sub_answers, deduplicate citations
   - `verify_groundedness(state, *, llm)` -- NLI claim verification, produce `GroundednessResult`
   - `validate_citations(state, *, reranker)` -- Cross-encoder alignment check
   - `summarize_history(state, *, llm)` -- Compress messages when approaching token budget
   - `format_response(state)` -- Apply citation markers, confidence indicators, format for SSE

3. **Implement edge functions in `backend/agent/edges.py`**:
   - `route_intent(state)` -- Returns destination node based on `state["intent"]`
   - `should_clarify(state)` -- Returns True if `query_analysis.is_clear == False`

4. **Define the graph in `backend/agent/conversation_graph.py`**:
   - Create `StateGraph(ConversationState)`
   - Add all nodes
   - Add conditional edges (route_intent, should_clarify)
   - Add sequential edges (aggregate -> verify -> validate -> format)
   - Compile the graph

5. **Implement the chat API endpoint in `backend/api/chat.py`**:
   - Accept `POST /api/chat` with `{message, collection_ids, llm_model, session_id}`
   - Build initial `ConversationState` from request
   - Invoke the compiled `ConversationGraph`
   - Stream response via `StreamingResponse` with `text/event-stream` content type
   - Use LangGraph's `astream_events()` for token streaming
   - Write `query_trace` record to SQLite after completion

## Integration Points

- **ResearchGraph (spec-03)**: ConversationGraph's `fan_out` node spawns ResearchGraph instances via `Send()`. The ResearchGraph must be compiled and registered as a subgraph.
- **MetaReasoningGraph (spec-04)**: ResearchGraph internally dispatches to MetaReasoningGraph when confidence is below threshold. ConversationGraph is not directly aware of MetaReasoningGraph.
- **FastAPI chat endpoint**: The only entry point for the ConversationGraph. Handles SSE streaming of graph events.
- **SQLite**: `init_session` reads session history; graph checkpoint serialization uses SQLite; `query_trace` written after response.
- **Provider Registry**: LLM model is resolved via `ProviderRegistry` based on `state["llm_model"]`.

## Key Code Patterns

### Graph Definition Pattern

```python
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

def build_conversation_graph(research_graph):
    graph = StateGraph(ConversationState)

    graph.add_node("init_session", init_session)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("rewrite_query", rewrite_query)
    graph.add_node("request_clarification", request_clarification)
    graph.add_node("fan_out", fan_out)
    graph.add_node("research", research_graph)  # subgraph
    graph.add_node("aggregate_answers", aggregate_answers)
    graph.add_node("verify_groundedness", verify_groundedness)
    graph.add_node("validate_citations", validate_citations)
    graph.add_node("format_response", format_response)

    graph.add_edge(START, "init_session")
    graph.add_edge("init_session", "classify_intent")
    graph.add_conditional_edges("classify_intent", route_intent, {
        "rag_query": "rewrite_query",
        "collection_mgmt": "collection_mgmt",
        "ambiguous": "request_clarification",
    })
    graph.add_edge("request_clarification", "classify_intent")
    graph.add_conditional_edges("rewrite_query", should_clarify, {
        True: "request_clarification",
        False: "fan_out",
    })
    graph.add_edge("fan_out", "research")
    graph.add_edge("research", "aggregate_answers")
    graph.add_edge("aggregate_answers", "verify_groundedness")
    graph.add_edge("verify_groundedness", "validate_citations")
    graph.add_edge("validate_citations", "format_response")
    graph.add_edge("format_response", END)

    return graph.compile()
```

### Fan-Out with Send() Pattern

```python
from langgraph.types import Send

async def fan_out(state: ConversationState) -> List[Send]:
    sends = []
    for sub_q in state["query_analysis"].sub_questions:
        sends.append(Send("research", {
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
        }))
    return sends
```

### SSE Streaming Pattern

```python
from fastapi.responses import StreamingResponse

async def chat_endpoint(request: ChatRequest):
    async def event_stream():
        async for event in graph.astream_events(initial_state, version="v2"):
            if event["event"] == "on_chat_model_stream":
                token = event["data"]["chunk"].content
                yield f'data: {{"type": "token", "content": {json.dumps(token)}}}\n\n'
            elif event["event"] == "on_chain_end" and "citations" in event["data"]:
                for citation in event["data"]["citations"]:
                    yield f'data: {{"type": "citation", ...}}\n\n'
        yield f'data: {{"type": "done", "latency_ms": {latency}}}\n\n'

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

## Phase Assignment

- **Phase 1 (MVP)**: ConversationGraph + ResearchGraph (two layers). All nodes except MetaReasoningGraph trigger. GAV node is deferred to Phase 2.
  - Phase 1 nodes: `init_session`, `classify_intent`, `rewrite_query`, `request_clarification`, `route_intent`, `fan_out`, `aggregate_answers`, `format_response`
  - Phase 1 skips: `verify_groundedness` (GAV), `validate_citations` (citation alignment)
- **Phase 2 (Performance & Resilience)**: Add `verify_groundedness` (GAV) and `validate_citations` nodes. Add computed confidence scoring.
