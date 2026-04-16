# LangChain/LangGraph Ecosystem Audit Report

**Date**: 2026-03-27
**Branch**: `023-e2e-testing`
**Scope**: Full audit of the LangGraph RAG pipeline against current LangChain documentation
**Method**: Codebase inspection (Serena) + LangChain docs MCP queries + cross-reference analysis

---

## Executive Summary

This audit found **2 critical architectural bugs** that make the RAG answer pipeline completely non-functional (users always see a fallback message), **1 critical state management bug** that disables loop protection, **2 high-severity issues** affecting interrupt handling and state serialization, and **7 medium/low findings** covering reliability, performance, and missing patterns.

---

## CRITICAL Findings

### CRIT-001 — `route_fan_out` is never wired into the graph

**Severity**: CRITICAL — RAG answers never delivered
**File**: `backend/agent/conversation_graph.py:69`

**Problem**:
The graph wires `rewrite_query` → `route_after_rewrite` → `"research"` (direct subgraph node):

```python
# CURRENT — WRONG
graph.add_conditional_edges("rewrite_query", route_after_rewrite,
                           ["request_clarification", "research"])
```

`route_fan_out` in `backend/agent/edges.py` is **fully implemented** with proper `Send()` API calls for each sub-question — but is **never connected to the graph**.

When the research_graph runs as a direct node (not via `Send`), it receives the full `ConversationState` as input. LangGraph maps fields by name — but `ConversationState` has **no `sub_question` field**. The research graph's `orchestrator` node builds its prompt with `state["sub_question"]` = `""` (empty or None).

**Consequence**: The orchestrator either produces no tool calls (`_no_new_tools=True` → exhausted immediately) or runs with an empty query. Either way, research is either skipped or produces irrelevant results for an empty question.

**Fix**:
```python
# conversation_graph.py — replace line 69
graph.add_conditional_edges(
    "rewrite_query",
    route_fan_out,              # uses Send() for each sub-question
    ["request_clarification", "research"],
)
```

---

### CRIT-002 — `collect_answer` never outputs `sub_answers` — fallback message always shown

**Severity**: CRITICAL — Users always receive "I couldn't find relevant information"
**Files**: `backend/agent/research_nodes.py:497`, `backend/agent/nodes.py:394`

**Problem**:
`collect_answer` returns:
```python
return {
    "confidence_score": confidence,
    "answer": answer_text,       # ResearchState field
    "citations": citations,
    "stage_timings": {...},
}
```

`ConversationState` has **no `answer` field** — it has `sub_answers: Annotated[list[SubAnswer], operator.add]`. When the research subgraph's output is merged back into the parent state, `answer` is **silently dropped** (no matching key in parent schema).

`aggregate_answers` (`nodes.py:394`) always reads:
```python
sub_answers: list[SubAnswer] = state.get("sub_answers", [])  # always []
```

→ Falls into the `if not valid:` branch → returns:
```
"I couldn't find relevant information to answer your question."
```

Every single chat request returns this fallback, regardless of documents found.

This is the root cause behind the 3 pre-existing test failures (SessionContinuity, ClarificationInterrupt) and the "chat works but returns wrong answer" symptom from BUG-008's fix.

**Fix**: Modify `collect_answer` to wrap its output into `SubAnswer`:
```python
from backend.agent.schemas import SubAnswer

# At the end of collect_answer, replace the return with:
return {
    "confidence_score": confidence,
    "citations": citations,
    "stage_timings": {...},
    "sub_answers": [SubAnswer(
        sub_question=state["sub_question"],
        answer=answer_text,
        citations=citations,
        confidence_score=int(confidence * 100),
        chunks=chunks,
    )],
}
```

Same fix required in `fallback_response` and the LLM-failure fallback path.

---

### CRIT-003 — Meta-reasoning cycle protection silently broken

**Severity**: CRITICAL — Infinite meta-reasoning loops possible
**Files**: `backend/agent/research_graph.py:77`, `backend/agent/state.py:47`

**Problem**:
`meta_reasoning_mapper` returns cycle-tracking state:
```python
updates["_meta_attempt_count"] = result.get("meta_attempt_count", 0)
updates["_attempted_strategies"] = result.get("attempted_strategies", set())
```

But `ResearchState` TypedDict **has no fields named `_meta_attempt_count` or `_attempted_strategies`**. LangGraph silently drops unknown keys from node return dicts. These values are **never persisted in graph state**.

On every meta-reasoning invocation, the mapper reads:
```python
"meta_attempt_count": state.get("_meta_attempt_count", 0),   # always 0
"attempted_strategies": state.get("_attempted_strategies", set()),  # always empty set
```

The meta-reasoning graph always sees attempt_count=0 and an empty strategies set — it can never detect it has already tried a strategy. The loop protection logic is completely inoperative.

**Fix**: Add the missing fields to `ResearchState` in `state.py`:
```python
class ResearchState(TypedDict):
    # ... existing fields ...
    _meta_attempt_count: Annotated[int, _keep_last]
    _attempted_strategies: Annotated[set, _keep_last]   # or list[str] for serializability
    _top_k_retrieval: Annotated[int | None, _keep_last]
    _top_k_rerank: Annotated[int | None, _keep_last]
    _payload_filters: Annotated[dict | None, _keep_last]
```

---

## HIGH Findings

### HIGH-001 — Interrupt detection broken in `stream_mode="messages"`

**Severity**: HIGH — Clarification flow never works
**File**: `backend/api/chat.py:131`

**Problem**:
```python
if "__interrupt__" in metadata:   # This never triggers
    interrupt_value = metadata["__interrupt__"][0].value
    yield json.dumps({"type": "clarification", ...})
```

According to LangGraph docs, **interrupts are not surfaced via metadata in `stream_mode="messages"`**. When `interrupt()` fires in `request_clarification`, the graph pauses — but `__interrupt__` does NOT appear in the `(chunk_msg, metadata)` tuples.

The correct pattern (from docs: *"Stream with human-in-the-loop (HITL) interrupts"*) requires:
```python
stream_mode=["messages", "updates"]
```

In `"updates"` mode, a graph interrupt yields a special `{"__interrupt__": [...]}` update dict. The current code only uses `"messages"` mode and will **never detect the interrupt**.

Result: the clarification event is never emitted, the stream ends silently, the user sees nothing, and the session is stuck in a paused checkpoint state.

**Fix**:
```python
async for event in graph.astream(
    initial_state,
    stream_mode=["messages", "updates"],
    config=config,
):
    if isinstance(event, dict) and "__interrupt__" in event:
        interrupt_value = event["__interrupt__"][0].value
        yield json.dumps({"type": "clarification", "question": interrupt_value}) + "\n"
        return
    # message handling for (chunk_msg, metadata) tuples
    if isinstance(event, tuple):
        chunk_msg, metadata = event
        # ... existing logic ...
```

---

### HIGH-002 — `set[str]` in TypedDict state — serialization fragility

**Severity**: HIGH — Potential crash or silent data loss
**File**: `backend/agent/state.py:55,78`

**Problem**:
Two fields use raw Python `set`:
- `ResearchState.retrieval_keys: set[str]` — no `Annotated` reducer
- `MetaReasoningState.attempted_strategies: set[str]` — no `Annotated` reducer

`JsonPlusSerializer` (used by `AsyncSqliteSaver`) does handle Python sets in recent LangGraph versions via special encoding, but:

1. `retrieval_keys: set[str]` has **no `Annotated` reducer** — the entire set is overwritten on each node return. Any concurrent/parallel update would silently discard the other's deduplication keys.
2. When `attempted_strategies` (a set) is JSON-serialized in `chat.py` (`list(attempted)`), it works. But if the checkpoint is ever inspected externally or deserialized by a different LangGraph version, behavior is undefined.
3. `set` is not compatible with LangGraph's typed state schema inference tools.

**Fix**: Use `list[str]` with deduplication logic, or at minimum add `Annotated`:
```python
retrieval_keys: Annotated[set[str], lambda a, b: a | b]  # merge union
```

---

### HIGH-003 — No `recursion_limit` set — silent `GraphRecursionError`

**Severity**: HIGH — Complex queries silently fail with opaque error
**File**: `backend/api/chat.py:111`

**Problem**:
LangGraph default recursion limit = **25 steps**. The nested graph structure (ConversationGraph → ResearchGraph loop → MetaReasoning → back to orchestrator) can easily exceed 25 for queries requiring 3+ iterations.

`GraphRecursionError` is caught by `except Exception as e` and returns:
```
"Unable to process your request. Please retry."
```

No user-visible indication of what happened. No retry guidance.

**Fix**:
```python
from langgraph.errors import GraphRecursionError

config = {
    "configurable": {...},
    "recursion_limit": 100,   # explicit, generous limit
}

# In exception handling:
except GraphRecursionError:
    yield json.dumps({
        "type": "error",
        "message": "The query required too many reasoning steps. Try a more specific question.",
        "code": "RECURSION_LIMIT",
    }) + "\n"
```

---

## MEDIUM Findings

### MED-001 — `messages` uses `operator.add` instead of `add_messages`

**Severity**: Medium — Duplicate messages on checkpoint resume, no RemoveMessage support
**File**: `backend/agent/state.py:32,56`

**Current**:
```python
messages: Annotated[list, operator.add]
```

**LangGraph recommendation** (from docs: *"Using messages in your graph"*):
```python
from langgraph.graph.message import add_messages
messages: Annotated[list, add_messages]
```

`add_messages` provides:
- **Deduplication by `id`**: prevents duplicate messages when resuming from a checkpoint (interrupt → resume appends the same HumanMessage twice with `operator.add`)
- **`RemoveMessage` support**: allows deleting specific messages for context window management
- **Proper `AIMessageChunk` merging**: streaming chunks are merged into a single `AIMessage`

Without `add_messages`, after a clarification interrupt/resume, the HumanMessage appears twice in the messages list.

---

### MED-002 — `llm.bind_tools()` called on every orchestrator invocation

**Severity**: Medium — Unnecessary object creation per loop iteration
**File**: `backend/agent/research_nodes.py:72`

```python
# Called 3× in a 3-iteration research loop
llm_with_tools = llm.bind_tools(tools_list) if tools_list else llm
```

`bind_tools()` creates a new LLM wrapper on every call. Should be done once, either at graph compile time via `configurable_fields()` or cached per-session.

**Fix**: Pass `llm_with_tools` (pre-bound) via `config["configurable"]` rather than the raw `llm` + separate `tools`. Bind once in `chat.py` before invoking the graph.

---

### MED-003 — Custom `tools_node` misses `ToolNode` prebuilt capabilities

**Severity**: Medium — Missing error handling patterns and parallel execution
**File**: `backend/agent/research_nodes.py:131`

The custom `tools_node` manually processes `AIMessage.tool_calls`. It misses what LangGraph's prebuilt `ToolNode` provides:

1. **`handle_tool_error`** — automatic error capture into `ToolMessage(status="error", content=str(e))` instead of manual retry logic
2. **Parallel tool execution** — `ToolNode` executes all tool calls from one `AIMessage` concurrently via `asyncio.gather`; the custom implementation loops sequentially
3. **Proper error status** — `ToolMessage.status` field (`"success"` / `"error"`) used by the LLM to understand failure
4. **`inject_tool_store`** — allows tools to access the LangGraph `Store` for cross-thread memory

The custom retry-once logic (try → catch → retry) counts BOTH attempts against `tool_call_count`, which is correct but differs from standard patterns.

---

### MED-004 — `compress_context` destroys per-citation metadata

**Severity**: Medium — Citations broken after context compression
**File**: `backend/agent/research_nodes.py:344`

After compression, ALL retrieved chunks are replaced with ONE synthetic chunk:
```python
compressed_chunk = RetrievedChunk(
    chunk_id="compressed-context",
    source_file=first_chunk.source_file,  # only first chunk's metadata
    parent_id=first_chunk.parent_id,
    ...
)
```

The `_build_citations` function later tries to link answer references `[1]`, `[2]` to specific chunks — but all passages now come from a single "compressed-context" chunk. All citations after compression point to the same source. This silently breaks citation accuracy for long research sessions.

**Fix**: Preserve a `sources_map` alongside the compressed text — a dict mapping `[N]` → original `(source_file, page, breadcrumb)` metadata, stored in the compressed chunk's breadcrumb or as a parallel state field.

---

### MED-005 — LLM / tools injected via untyped `configurable` dict

**Severity**: Medium — No compile-time validation, silent degradation
**File**: `backend/api/chat.py:107`, `backend/agent/research_nodes.py:67`

```python
config = {
    "configurable": {
        "thread_id": session_id,
        "llm": langchain_llm,        # untyped Any
        "tools": research_tools,     # untyped Any
    }
}
```

LangGraph's typed `ConfigSchema` pattern (via `graph.compile(config_schema=...)`) provides:
- Compile-time validation of configurable fields
- Type safety across node functions
- Auto-documentation of required config keys

Currently, if `llm` is `None` (e.g., provider not configured), every node silently degrades to "no LLM" fallback paths. No error at the API boundary.

---

### MED-006 — `stage_timings` not initialized in `initial_state`

**Severity**: Low — Minor inconsistency, safe due to `_merge_dicts` handling None
**File**: `backend/api/chat.py:84`

`initial_state` dict doesn't include `stage_timings: {}`. The `_merge_dicts` reducer handles `None` as the left value safely. But nodes that do `state.get("stage_timings", {})` and then spread it (`{**_prior, ...}`) will still work. No crash, but the first node's `stage_timings` output starts from scratch rather than from an explicit empty dict.

---

### MED-007 — Double chunk emission risk if `format_response` is ever made async

**Severity**: Low — Latent, not currently triggered
**File**: `backend/api/chat.py:121-126, 156`

The streaming code has two paths that can both emit the final answer:

1. **During stream**: `current_node == "format_response" AND isinstance(chunk_msg, AIMessageChunk)` → emits token
2. **After stream**: `final_state.get("final_response")` → emits full text

`format_response` is currently sync (no LLM call), so path 1 never fires. But if a future developer makes it async/streaming, users receive the answer **twice**: once token-by-token during streaming, once as a complete block after. This should be either documented or made mutually exclusive via a `has_streamed` flag.

---

## Further Investigation Topics

### INV-001 — Does Send output correctly populate `sub_answers` via reducer?

Once CRIT-001 and CRIT-002 are fixed (route_fan_out wired + collect_answer outputs sub_answers), verify that LangGraph's Send mechanism correctly applies the `operator.add` reducer to accumulate `SubAnswer` objects from parallel research runs. The LangGraph docs confirm this pattern (see: *"Map-Reduce and the Send API"*), but it should be verified against the specific LangGraph version (>=1.0.10).

### INV-002 — `AsyncSqliteSaver` serialization of `set` type

Verify whether `JsonPlusSerializer` in `langgraph-checkpoint-sqlite >= 2.0` handles Python `set` correctly under checkpoint save/restore cycles. Test: save state with `retrieval_keys={"a", "b"}`, restore, verify the set is not converted to `list` or lost. If converted to `list`, the `if key not in updated_keys` check still works for `list` (via `__contains__`), but the type annotation would be wrong.

### INV-003 — Clarification interrupt full round-trip after HIGH-001 fix

After fixing interrupt detection (`stream_mode=["messages","updates"]`), test the full clarification round-trip:
1. Ambiguous query → `request_clarification` → interrupt fires
2. Frontend receives `{"type": "clarification", "question": "..."}` → shows input
3. User responds → `graph.astream(Command(resume=user_response), config=config)`
4. Graph resumes from checkpoint → `request_clarification` returns `user_response` → back to `classify_intent`
5. Verify the session_id/thread_id continuity across the two astream calls

### INV-004 — MetaReasoningGraph strategy exhaustion under load

After CRIT-003 fix (adding `_meta_attempt_count` to ResearchState), stress-test the meta-reasoning cycle: trigger a query that exhausts confidence threshold 3+ times, verify `attempted_strategies` correctly accumulates tried strategies and the uncertainty path is correctly reached.

### INV-005 — LangGraph Store integration for cross-session context

Investigate adding `langgraph.store.base.BaseStore` to the graph for cross-thread user context (e.g., preferred collections, query reformulation patterns). The current implementation only uses the checkpointer (per-thread). The Store would enable the agent to learn from past sessions.

### INV-006 — `validate_citations` node uses cross-encoder reranker for validation

`validate_citations` (nodes.py) reads `sub_answers` and `final_response` and uses the cross-encoder reranker to validate citation relevance. Verify this node works correctly after CRIT-002 fix (sub_answers now populated). The `all_chunks = [chunk for sa in sub_answers for chunk in sa.chunks]` line requires `SubAnswer.chunks` to be populated — verify the `SubAnswer` schema has a `chunks` field and it is filled by `collect_answer`.

---

## Audit Coverage Matrix

| Component | File | Status |
|-----------|------|--------|
| ConversationGraph wiring | `conversation_graph.py` | ❌ CRIT-001 |
| ResearchGraph wiring | `research_graph.py` | ⚠️ CRIT-003 |
| ConversationState schema | `state.py` | ⚠️ MED-001, HIGH-002 |
| ResearchState schema | `state.py` | ❌ CRIT-003, HIGH-002 |
| MetaReasoningState schema | `state.py` | ⚠️ HIGH-002 |
| `orchestrator` node | `research_nodes.py` | ⚠️ MED-002, MED-005 |
| `tools_node` | `research_nodes.py` | ⚠️ MED-003 |
| `collect_answer` node | `research_nodes.py` | ❌ CRIT-002 |
| `fallback_response` node | `research_nodes.py` | ❌ CRIT-002 (needs same fix) |
| `compress_context` node | `research_nodes.py` | ⚠️ MED-004 |
| `aggregate_answers` node | `nodes.py` | Correct (consumer of broken sub_answers) |
| `request_clarification` node | `nodes.py` | Correct (uses `interrupt()` properly) |
| `route_fan_out` edge | `edges.py` | ❌ Never wired (CRIT-001) |
| Chat streaming | `api/chat.py` | ❌ HIGH-001, HIGH-003, MED-007 |
| HybridSearcher | `retrieval/searcher.py` | ✅ No issues found |
| Embedder | `ingestion/embedder.py` | ✅ BUG-009 already fixed |

---

## Fix Priority Order

```
1. CRIT-001 + CRIT-002  (wire route_fan_out + fix collect_answer → sub_answers)
   → Together these restore the entire answer delivery pipeline

2. CRIT-003             (add _meta_attempt_count + _attempted_strategies to ResearchState)
   → Restores loop protection before stress testing

3. HIGH-001             (stream_mode=["messages","updates"] for interrupt detection)
   → Fixes clarification flow; the 3 pre-existing test failures should resolve

4. HIGH-003             (recursion_limit + GraphRecursionError handler)
   → Prevents silent failures under load

5. MED-001              (add_messages instead of operator.add)
   → Before any interrupt/resume testing

6. MED-002 + MED-005    (bind_tools once, typed ConfigSchema)
   → Performance + reliability hardening
```
