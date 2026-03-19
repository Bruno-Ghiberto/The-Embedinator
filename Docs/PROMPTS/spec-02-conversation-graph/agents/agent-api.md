# Agent: API

**Mission**: Refactor the FastAPI chat endpoint to invoke ConversationGraph with NDJSON streaming, add checkpointer integration to the app lifespan, and handle clarification interrupts and error conditions.

**Subagent Type**: `backend-architect`
**Model**: `opus`
**Wave**: 4 (Sequential -- after Wave 3 Integration agent completes)

## Assigned Tasks

- **T041**: Refactor `backend/api/chat.py` to import and invoke `build_conversation_graph()` -- build initial `ConversationState` from request fields: `session_id`, `messages=[HumanMessage(request.message)]`, `selected_collections=request.collection_ids`, `llm_model`, `embed_model`, `intent="rag_query"` (default), `query_analysis=None`, `sub_answers=[]`, `citations=[]`, `groundedness_result=None`, `confidence_score=0`, `iteration_count=0`, `final_response=None`
- **T042**: Implement NDJSON streaming in `backend/api/chat.py` -- replace direct LLM streaming with `async for chunk, metadata in graph.astream(state, stream_mode="messages", config={"configurable": {"thread_id": session_id}}):`; yield `json.dumps({"type":"chunk","text":chunk.content}) + "\n"` for each `AIMessageChunk` with non-empty content; detect `"__interrupt__"` key in metadata and yield `json.dumps({"type":"clarification","question":value}) + "\n"` then return
- **T043**: Implement metadata frame in `backend/api/chat.py` -- after stream completes, call `graph.get_state(config).values` to get final state; yield `json.dumps({"type":"metadata","trace_id":trace_id,"confidence":final_state["confidence_score"],"citations":[c.model_dump() for c in final_state["citations"]],"latency_ms":latency_ms}) + "\n"`; preserve existing `query_trace` SQLite write (Constitution Principle IV)
- **T044**: Add empty-collections guard in `backend/api/chat.py` -- before invoking graph, if `request.collection_ids` is empty yield `json.dumps({"type":"error","message":"Please select at least one collection before searching.","code":"NO_COLLECTIONS"}) + "\n"` and return
- **T045**: Get checkpointer from `app.state.checkpointer` in `backend/api/chat.py` and pass to `build_conversation_graph(research_graph=get_research_graph_stub(), checkpointer=app.state.checkpointer)`; use `app.state` for graph instance caching

### Lifespan Task

- **T032**: Add `AsyncSqliteSaver` checkpointer to app lifespan in `backend/main.py` -- import from `langgraph.checkpoint.sqlite.aio`; open `AsyncSqliteSaver.from_conn_string("data/checkpoints.db")` in lifespan context manager; store in `app.state.checkpointer`; pass to `build_conversation_graph()` call

## Files Modified

| File | Changes |
|------|---------|
| `backend/api/chat.py` | Full refactor: ConversationGraph invocation, NDJSON streaming, interrupt handling, error guards |
| `backend/main.py` | Add `AsyncSqliteSaver` checkpointer to lifespan, store in `app.state.checkpointer` |

## Constraints

### NDJSON Streaming (NOT SSE)

- Content-Type: `application/x-ndjson` -- NOT `text/event-stream`
- Each line: complete JSON object + `\n` -- NO `data:` prefix
- Use `graph.astream(state, stream_mode="messages")` -- NOT `astream_events`
- Stream yields `(chunk, metadata)` tuples where `chunk` is `AIMessageChunk`

### Streaming Pattern

```python
async def generate():
    start_time = time.monotonic()

    async for chunk, metadata in graph.astream(
        initial_state,
        stream_mode="messages",
        config={"configurable": {"thread_id": session_id}},
    ):
        if hasattr(chunk, "content") and chunk.content:
            yield json.dumps({"type": "chunk", "text": chunk.content}) + "\n"

        if "__interrupt__" in metadata:
            interrupt_value = metadata["__interrupt__"][0].value
            yield json.dumps({
                "type": "clarification",
                "question": interrupt_value,
            }) + "\n"
            return

    final_state = graph.get_state(config).values
    latency_ms = int((time.monotonic() - start_time) * 1000)

    yield json.dumps({
        "type": "metadata",
        "trace_id": trace_id,
        "confidence": final_state["confidence_score"],
        "citations": [c.model_dump() for c in final_state["citations"]],
        "latency_ms": latency_ms,
    }) + "\n"

return StreamingResponse(generate(), media_type="application/x-ndjson")
```

### NDJSON Frame Types (from contracts/chat-api.md)

| Frame | Schema |
|-------|--------|
| Chunk | `{"type": "chunk", "text": "..."}` |
| Clarification | `{"type": "clarification", "question": "..."}` |
| Metadata | `{"type": "metadata", "trace_id": "...", "confidence": 87, "citations": [...], "latency_ms": 1240}` |
| Error | `{"type": "error", "message": "...", "code": "NO_COLLECTIONS"}` |

### Initial State Construction

```python
initial_state = {
    "session_id": session_id,
    "messages": [HumanMessage(content=body.message)],
    "intent": "rag_query",
    "query_analysis": None,
    "sub_answers": [],
    "selected_collections": body.collection_ids,
    "llm_model": llm_model,
    "embed_model": embed_model,
    "final_response": None,
    "citations": [],
    "groundedness_result": None,
    "confidence_score": 0,
    "iteration_count": 0,
}
```

### Checkpointer Lifespan (main.py)

```python
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

async with AsyncSqliteSaver.from_conn_string("data/checkpoints.db") as checkpointer:
    app.state.checkpointer = checkpointer
    # ... rest of lifespan
```

### Error Handling

- Empty `collection_ids`: yield error frame `{"type":"error","message":"...","code":"NO_COLLECTIONS"}` and return
- Empty/whitespace message: HTTP 400 (use existing validation)
- Message too long: HTTP 400 (use existing validation)
- Internal errors during streaming: yield error frame `{"type":"error","message":"...","code":"INTERNAL_ERROR"}`

### Preserved Behaviors

- `query_trace` SQLite write after response (Constitution Principle IV)
- Rate limiting (30 req/min per client)
- Existing request validation for message length and content
- `trace_id` generation via `uuid4` or existing pattern
- `session_id` generation when not provided in request

## Dependencies

- Wave 3 (Integration) must be complete: `build_conversation_graph()` compiles successfully
- `AsyncSqliteSaver` available from `langgraph-checkpoint-sqlite>=2.0`
- Existing `backend/api/chat.py` and `backend/main.py` must be present

## Done Criteria

- [ ] `chat.py` invokes `build_conversation_graph()` instead of direct RAG pipeline
- [ ] NDJSON streaming works with `stream_mode="messages"` and `application/x-ndjson` content type
- [ ] Chunk frames (`{"type":"chunk","text":"..."}`) are yielded for each LLM token
- [ ] Clarification frames (`{"type":"clarification","question":"..."}`) are yielded on interrupt
- [ ] Metadata frame is the final frame with `confidence` (int 0-100), `citations`, `latency_ms`
- [ ] Empty `collection_ids` yields `NO_COLLECTIONS` error frame
- [ ] `query_trace` SQLite write is preserved after response
- [ ] `AsyncSqliteSaver` is initialized in `main.py` lifespan and stored in `app.state.checkpointer`
- [ ] Checkpointer is passed to `build_conversation_graph()` from `app.state`
- [ ] Graph instance is cached on `app.state` (not rebuilt per request)
