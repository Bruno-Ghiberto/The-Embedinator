# A3: Chat NDJSON Streaming

**Agent type:** `python-expert`
**Model:** Opus 4.6
**Tasks:** T008, T009, T010, T011
**Wave:** 2 (parallel with A4)

---

## Assigned Tasks

### T008: Write tests/unit/test_chat_ndjson.py
Unit tests for all 10 event types, format validation, error handling.

### T009: Write tests/integration/test_ndjson_streaming.py
End-to-end NDJSON stream parsing, media type assertion, latency check.

### T010: Rewrite event_generator() in backend/api/chat.py
Emit all 10 event types in correct order with correct format.

### T011: Fix trace recording in backend/api/chat.py
Replace non-existent db methods with `db.create_query_trace()`.

---

## File Targets

| File | Action |
|------|--------|
| `backend/api/chat.py` | Rewrite (preserve router and imports structure) |
| `tests/unit/test_chat_ndjson.py` | Create new |
| `tests/integration/test_ndjson_streaming.py` | Create new |

---

## Current State of chat.py

Read `backend/api/chat.py` first. Key issues to fix:

1. **Event types**: Only emits `chunk`, `clarification`, `metadata`, `error`. Must emit 10 types.
2. **Final event**: Emits `metadata` as final event. Must emit `done`.
3. **Trace recording**: Calls `db.create_query()`, `db.create_trace()`, `db.create_answer()` -- these DO NOT EXIST in SQLiteDB. Must use `db.create_query_trace()`.
4. **Missing events**: No `session`, `status`, `citation`, `meta_reasoning`, `confidence`, `groundedness` events.
5. **Media type**: Already correct (`application/x-ndjson`). Keep it.
6. **Format**: Already correct (`json.dumps(event) + "\n"`). Keep it.

## Implementation Specification

### Event Stream Structure

```
session (always first, before astream)
  |
  v
status (per graph node transition, from metadata["langgraph_node"])
  |
  v
chunk (token-by-token, from AIMessageChunk.content)
  |
  v
[If interrupt detected: clarification -> RETURN]
  |
  v
citation (from final_state["citations"])
  |
  v
meta_reasoning (if final_state["attempted_strategies"] is non-empty)
  |
  v
confidence (int 0-100, from final_state["confidence_score"])
  |
  v
groundedness (from final_state["groundedness_result"])
  |
  v
[write trace via db.create_query_trace()]
  |
  v
done (last event, includes latency_ms and trace_id)
```

### Rewritten generate() Function

```python
async def generate():
    start_time = time.monotonic()
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))

    # Empty-collections guard
    if not body.collection_ids:
        yield json.dumps({
            "type": "error",
            "message": "Please select at least one collection before searching.",
            "code": "NO_COLLECTIONS",
            "trace_id": trace_id,
        }) + "\n"
        return

    # 1. Session event (BEFORE astream)
    yield json.dumps({"type": "session", "session_id": session_id}) + "\n"

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

    config = {"configurable": {"thread_id": session_id}}
    last_node = None

    try:
        # 2. Stream events from graph
        async for chunk_msg, metadata in graph.astream(
            initial_state,
            stream_mode="messages",
            config=config,
        ):
            # Status event on node transition
            current_node = metadata.get("langgraph_node")
            if current_node and current_node != last_node:
                yield json.dumps({"type": "status", "node": current_node}) + "\n"
                last_node = current_node

            # Chunk event for AI content
            if hasattr(chunk_msg, "content") and chunk_msg.content:
                yield json.dumps({"type": "chunk", "text": chunk_msg.content}) + "\n"

            # Clarification interrupt detection
            if "__interrupt__" in metadata:
                interrupt_value = metadata["__interrupt__"][0].value
                yield json.dumps({
                    "type": "clarification",
                    "question": interrupt_value,
                }) + "\n"
                return  # Stream ends on clarification

        # 3. Get final state after stream completes
        final_state = graph.get_state(config).values
        latency_ms = int((time.monotonic() - start_time) * 1000)

        # 4. Citation event
        citations = final_state.get("citations", [])
        if citations:
            citation_dicts = [
                c.model_dump() if hasattr(c, "model_dump") else c
                for c in citations
            ]
            yield json.dumps({"type": "citation", "citations": citation_dicts}) + "\n"

        # 5. Meta-reasoning event (if strategies were attempted)
        attempted = final_state.get("attempted_strategies")
        if attempted:
            strategies_list = list(attempted) if isinstance(attempted, set) else attempted
            yield json.dumps({
                "type": "meta_reasoning",
                "strategies_attempted": strategies_list,
            }) + "\n"

        # 6. Confidence event (ALWAYS int 0-100)
        confidence = int(final_state.get("confidence_score", 0))
        yield json.dumps({"type": "confidence", "score": confidence}) + "\n"

        # 7. Groundedness event
        groundedness_result = final_state.get("groundedness_result")
        if groundedness_result is not None:
            yield json.dumps({
                "type": "groundedness",
                "overall_grounded": groundedness_result.overall_grounded,
                "supported": sum(1 for v in groundedness_result.verifications if v.verdict == "supported"),
                "unsupported": sum(1 for v in groundedness_result.verifications if v.verdict == "unsupported"),
                "contradicted": sum(1 for v in groundedness_result.verifications if v.verdict == "contradicted"),
            }) + "\n"

        # 8. Write trace to DB
        try:
            await db.create_query_trace(
                id=trace_id,
                session_id=session_id,
                query=body.message,
                collections_searched=json.dumps(body.collection_ids),
                chunks_retrieved_json=json.dumps(
                    [c.model_dump() if hasattr(c, "model_dump") else c for c in citations]
                ),
                latency_ms=latency_ms,
                llm_model=llm_model,
                embed_model=embed_model,
                confidence_score=confidence,
                sub_questions_json=json.dumps(
                    final_state.get("sub_questions", [])
                ) if final_state.get("sub_questions") else None,
                reasoning_steps_json=None,  # populated by research graph internals
                strategy_switches_json=json.dumps(
                    list(attempted)
                ) if attempted else None,
                meta_reasoning_triggered=bool(attempted),
            )
        except Exception:
            logger.warning("query_trace_write_failed", session_id=session_id)

        # 9. Done event (LAST on success)
        yield json.dumps({
            "type": "done",
            "latency_ms": latency_ms,
            "trace_id": trace_id,
        }) + "\n"

    except CircuitOpenError:
        logger.warning("circuit_open_during_chat", session_id=session_id)
        yield json.dumps({
            "type": "error",
            "message": "A required service is temporarily unavailable. Please try again in a few seconds.",
            "code": "CIRCUIT_OPEN",
            "trace_id": trace_id,
        }) + "\n"
    except Exception as e:
        logger.error("chat_stream_error", error=str(e), session_id=session_id)
        yield json.dumps({
            "type": "error",
            "message": "Unable to process your request. Please retry.",
            "code": "SERVICE_UNAVAILABLE",
            "trace_id": trace_id,
        }) + "\n"
```

### Key Details

- `trace_id` comes from `request.state.trace_id` (set by TraceIDMiddleware)
- `llm_model` resolved from `body.llm_model or settings.default_llm_model`
- `embed_model` resolved from `body.embed_model or settings.default_embed_model`
- `graph` obtained via `_get_or_build_graph(request.app.state)` -- keep existing helper
- Error codes in events MUST be UPPERCASE: `CIRCUIT_OPEN`, `SERVICE_UNAVAILABLE`, `NO_COLLECTIONS`
- `attempted_strategies` is a `set[str]` in state -- convert to `list` before JSON serialization
- `citations` may be Pydantic models or dicts -- use `model_dump()` when available

### db.create_query_trace() Signature

This is the ONLY trace recording method. The methods `db.create_query()`, `db.create_trace()`, and `db.create_answer()` DO NOT EXIST.

```python
await db.create_query_trace(
    id: str,                          # trace UUID
    session_id: str,                  # chat session
    query: str,                       # user message
    collections_searched: str,        # JSON string of collection IDs
    chunks_retrieved_json: str,       # JSON string
    latency_ms: int,                  # total latency
    llm_model: str | None = None,
    embed_model: str | None = None,
    confidence_score: int | None = None,   # 0-100 int
    sub_questions_json: str | None = None,
    reasoning_steps_json: str | None = None,
    strategy_switches_json: str | None = None,
    meta_reasoning_triggered: bool = False,
)
```

Note: `collections_searched` is a JSON STRING, not a list. Pass `json.dumps(body.collection_ids)`.

---

## Test Specifications

### test_chat_ndjson.py (Unit)

Mock `ConversationGraph` (use `tests/mocks.py` patterns). Test:

1. All 10 event types can be emitted (mock appropriate state)
2. `media_type="application/x-ndjson"` on the StreamingResponse
3. Format: every line is `json.dumps(obj) + "\n"` (no `data:` prefix, no double newline)
4. Confidence score is int 0-100 (not float)
5. Session event is FIRST line
6. Done event is LAST line on success
7. Error event with `trace_id` on CircuitOpenError
8. Clarification event on `__interrupt__` in metadata
9. Multi-turn session continuity: send two requests with same session_id, verify graph receives prior context via checkpointer
10. `db.create_query_trace()` called (not `db.create_query` etc.)

### test_ndjson_streaming.py (Integration)

Use FastAPI TestClient with `stream=True`. Test:

1. Parse each response line as JSON (no line starts with `data:`)
2. Assert `Content-Type` header contains `application/x-ndjson`
3. Assert all 10 event types exercised across test scenarios
4. First event type is `session`
5. Last event type is `done` on success path

---

## Test Command

```bash
zsh scripts/run-tests-external.sh -n spec08-chat tests/unit/test_chat_ndjson.py
cat Docs/Tests/spec08-chat.status
cat Docs/Tests/spec08-chat.summary
```

---

## What NOT to Do

- Do NOT use SSE format (`data:` prefix, `text/event-stream`) -- this is NDJSON
- Do NOT emit a `metadata` event -- that is the old format. Use separate `citation`, `confidence`, `groundedness`, and `done` events
- Do NOT call `db.create_query()`, `db.create_trace()`, or `db.create_answer()` -- they do not exist
- Do NOT use float for confidence -- always `int()`
- Do NOT change the `/api/chat` path or the `ChatRequest` schema (A1 handles schema changes)
- Do NOT remove `_get_or_build_graph()` helper -- it is used for caching the compiled graph
- Do NOT buffer events -- yield each event immediately as it becomes available
- Do NOT run pytest inside Claude Code -- use the external test runner
