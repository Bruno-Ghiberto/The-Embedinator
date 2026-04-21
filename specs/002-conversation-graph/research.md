# Phase 0 Research: ConversationGraph

**Date**: 2026-03-10
**Feature**: [spec.md](spec.md)

## Research Item 1: LangGraph Checkpointer for SQLite

**Context**: FR-011 requires saving graph state during clarification interrupts and resuming from checkpoint. The default `MemorySaver` is in-memory only — not suitable for production (state lost on server restart).

**Decision**: Use `AsyncSqliteSaver` from the `langgraph-checkpoint-sqlite` package.

**Rationale**:
- Production-grade async SQLite checkpointer maintained by LangGraph team
- Auto-creates tables on first use (no migration needed)
- Compatible with the project's existing async SQLite pattern (aiosqlite)
- Manages its own SQLite file — no interference with the app's `embedinator.db`

**Alternatives Considered**:
- `MemorySaver`: In-memory only, state lost on restart. Rejected for production but acceptable for unit tests.
- `AsyncPostgresSaver`: Requires PostgreSQL — violates Constitution Principle VII (Simplicity by Default) and Principle I (no new services without ADR).
- Custom checkpointer: Unnecessary complexity when official package exists.

**Implementation Details**:
```python
# Package: langgraph-checkpoint-sqlite>=2.0
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

# Lifespan management in main.py
async with AsyncSqliteSaver.from_conn_string("data/checkpoints.db") as checkpointer:
    graph = build_conversation_graph(research_graph, checkpointer=checkpointer)

# Thread ID mapping: session_id → thread_id
config = {"configurable": {"thread_id": session_id}}
```

**Impact**: Add `langgraph-checkpoint-sqlite>=2.0` to `requirements.txt`. Add checkpointer initialization to `create_app()` lifespan in `main.py`. Separate checkpoint DB file at `data/checkpoints.db`.

---

## Research Item 2: Token Counting for Context Window Management

**Context**: FR-009 requires compressing conversation history when it exceeds 75% of the configured model's context window. Need a multi-provider token counting strategy that works with Ollama, OpenAI, Anthropic, and OpenRouter.

**Decision**: Use `count_tokens_approximately` from `langchain_core.messages.utils` combined with `trim_messages` for context management.

**Rationale**:
- Zero new dependencies (already in langchain-core)
- Works identically across all providers (Ollama, OpenAI, Anthropic, OpenRouter)
- ~80-90% accuracy is sufficient when the threshold is 75% (conservative margin absorbs estimation error)
- Integrates directly with LangGraph StateGraph node pattern

**Alternatives Considered**:
- `tiktoken` directly: Only accurate for OpenAI models. Wrong for Claude (different tokenizer) and Ollama models (each has own SentencePiece/BPE). Rejected.
- `model.get_num_tokens_from_messages()`: Requires LangChain `BaseChatModel` wrappers. The Embedinator uses custom `httpx`-based providers, not LangChain wrappers. Would require provider refactor. Rejected.
- Character-count heuristic: Too imprecise (~4 chars/token varies wildly by language). `count_tokens_approximately` is already this heuristic but formalized and integrated with LangChain message types.

**Implementation Details**:
```python
from langchain_core.messages.utils import count_tokens_approximately, trim_messages

# Static lookup for context window sizes
MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    "qwen2.5:7b": 32_768,
    "llama3.1:8b": 128_000,
    "mistral:7b": 32_768,
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "claude-sonnet-4-20250514": 200_000,
}
DEFAULT_CONTEXT_WINDOW = 32_768  # Safe default for unknown models

def get_context_budget(model_name: str) -> int:
    """Return 75% of the model's context window."""
    window = MODEL_CONTEXT_WINDOWS.get(model_name, DEFAULT_CONTEXT_WINDOW)
    return int(window * 0.75)

def should_compress(messages: list, model_name: str) -> bool:
    """Check if messages exceed the 75% threshold."""
    token_count = count_tokens_approximately(messages)
    budget = get_context_budget(model_name)
    return token_count > budget
```

**Impact**: No new packages. Add `MODEL_CONTEXT_WINDOWS` dict to `backend/config.py` or `backend/agent/nodes.py`. Use `count_tokens_approximately` in `summarize_history` node.

---

## Research Item 3: ResearchGraph Stub for Testing

**Context**: ConversationGraph dispatches to ResearchGraph via `Send()`, but ResearchGraph (spec-03) doesn't exist yet. Need a testable stub that returns realistic data.

**Decision**: Create a mock `ResearchGraph` as a simple `StateGraph` that returns a fixed `SubAnswer` with dummy citations and passages.

**Rationale**:
- Enables full graph compilation and execution testing before spec-03
- Uses real Pydantic models (`SubAnswer`, `Citation`, `RetrievedChunk`) for type safety
- Can be gradually replaced with the real implementation

**Alternatives Considered**:
- Skip integration testing until spec-03: Delays validation of the core graph flow. Rejected.
- Mock at the `Send()` level: Would require patching LangGraph internals. Fragile. Rejected.
- Use a plain function instead of a graph: `Send()` requires a compiled graph or callable node. A simple function works for the node, but using a StateGraph is closer to the real implementation.

**Implementation Details**:
```python
from langgraph.graph import StateGraph, START, END

def mock_research_node(state: ResearchState) -> dict:
    """Stub: returns a fixed SubAnswer for testing."""
    return {
        "answer": f"Mock answer for: {state['sub_question']}",
        "confidence_score": 0.85,
        "citations": [
            Citation(
                passage_id="mock-p1",
                document_id="mock-doc",
                document_name="test.pdf",
                start_offset=0,
                end_offset=100,
                text="Mock passage text for testing.",
                relevance_score=0.85,
            )
        ],
        "retrieved_chunks": [],
    }

def build_mock_research_graph():
    graph = StateGraph(ResearchState)
    graph.add_node("research", mock_research_node)
    graph.add_edge(START, "research")
    graph.add_edge("research", END)
    return graph.compile()
```

**Impact**: Create `tests/conftest.py` fixture for mock research graph. Use in both unit and integration tests.

---

## Research Item 4: LangGraph Streaming with FastAPI

**Context**: FR-014 requires streaming via NDJSON. Need to confirm the correct LangGraph streaming API for token-by-token output compatible with FastAPI's `StreamingResponse`.

**Decision**: Use `graph.astream(input, stream_mode="messages", config=config)` which yields `(message_chunk, metadata)` tuples.

**Rationale**:
- `stream_mode="messages"` is the documented approach for token-level streaming in LangGraph
- Returns `AIMessageChunk` objects with `.content` attribute — directly mappable to `{"type":"chunk","text":"..."}`
- Async iteration is compatible with FastAPI's `StreamingResponse` generator pattern
- Metadata includes node information for tracking which node is streaming

**Alternatives Considered**:
- `astream_events(version="v2")`: More verbose, returns all graph events (not just LLM tokens). Requires filtering. Overhead for simple token streaming. Rejected for primary use case but could be useful for debug/trace mode.
- `stream_mode="values"`: Returns full state after each node. Not token-level granularity. Rejected.
- `stream_mode="updates"`: Returns state updates per node. Better for monitoring but not for token streaming. Rejected.

**Implementation Details**:
```python
async def generate():
    async for chunk, metadata in graph.astream(
        initial_state,
        stream_mode="messages",
        config={"configurable": {"thread_id": session_id}},
    ):
        if hasattr(chunk, "content") and chunk.content:
            yield json.dumps({"type": "chunk", "text": chunk.content}) + "\n"

    # After stream completes, yield metadata frame
    final_state = graph.get_state(config).values
    yield json.dumps({
        "type": "metadata",
        "trace_id": trace_id,
        "confidence": final_state["confidence_score"],
        "citations": [c.model_dump() for c in final_state["citations"]],
        "latency_ms": latency_ms,
    }) + "\n"

return StreamingResponse(generate(), media_type="application/x-ndjson")
```

**Impact**: Refactor `chat.py` to use this pattern. The existing NDJSON streaming structure is preserved — only the source of tokens changes (LangGraph stream → NDJSON lines instead of direct LLM stream → NDJSON lines).
