# LangChain/LangGraph Enhancement Report — Agentic RAG Workflow

**Date**: 2026-03-27
**Branch**: `023-e2e-testing`
**Scope**: Deep investigation of LangGraph/LangChain docs for enhancement opportunities
**Method**: langchain-docs MCP queries + cross-reference with current implementation

---

## Executive Summary

10 enhancement opportunities identified from current LangGraph/LangChain documentation, ranging from "immediate quality improvement" to "future architecture evolution". The top 5 high-impact enhancements directly address answer quality, reliability, and performance without requiring architectural changes.

---

## HIGH IMPACT — Implement Soon

### ENH-001 — LangGraph Store for Cross-Session Memory

**Impact**: Users get better answers over time — the system remembers preferences, patterns, collection affinities
**Effort**: Medium | **Files**: `main.py`, `conversation_graph.py`, `nodes.py`
**Docs**: [Memory store](https://docs.langchain.com/oss/python/langgraph/persistence#memory-store), [Access store inside nodes](https://docs.langchain.com/oss/python/langgraph/add-memory#access-the-store-inside-nodes)

**What it is**: LangGraph's `Store` is a persistent key-value store that survives across threads (sessions). Unlike the checkpointer (per-thread), the Store enables cross-conversation context: user preferences, query reformulation patterns, collection usage frequency.

**Current gap**: Our system treats every session as isolated. A user who always queries the same 2 collections out of 10 has to select them every time. Query patterns that worked well aren't remembered.

**Implementation pattern**:
```python
from langgraph.store.memory import InMemoryStore  # or SQLite-backed

store = InMemoryStore()

# Compile graph with store
graph = build_conversation_graph(
    research_graph=research_graph,
    checkpointer=checkpointer,
    store=store,         # NEW
)

# In a node — LangGraph injects store automatically:
async def init_session(state, config, *, store):
    user_id = config["configurable"].get("user_id", "default")
    # Read user preferences from store
    prefs = await store.aget(("user_prefs", user_id), "settings")
    if prefs:
        # Apply preferred collections, model, etc.
        ...
    # After successful query, save what worked:
    await store.aput(("user_prefs", user_id), "settings", {
        "preferred_collections": state["selected_collections"],
        "last_model": state["llm_model"],
    })
```

**Use cases**:
- User collection preferences (most-used collections prioritized)
- Query reformulation patterns that produced high-confidence results
- Per-user model preferences (which LLM works best for their domain)
- Feedback loop: low-confidence queries → suggest collection expansion

---

### ENH-002 — `with_structured_output` for Reliable LLM Parsing

**Impact**: Eliminates JSON parsing failures in classify_intent, query_analysis, groundedness verification
**Effort**: Low | **Files**: `nodes.py`, `research_nodes.py`
**Docs**: [Structured output](https://docs.langchain.com/oss/python/langchain/structured-output), [Models - Structured output](https://docs.langchain.com/oss/python/langchain/models#structured-output)

**What it is**: `llm.with_structured_output(PydanticModel)` tells the LLM to return output conforming to a specific schema. The LLM uses function calling or JSON mode to guarantee structure. Returns a Pydantic model instance, not raw text.

**Current gap**: `classify_intent` and `rewrite_query` parse LLM output with manual string matching / regex. If the LLM returns slightly different formatting, parsing fails silently.

**Implementation pattern**:
```python
# In classify_intent:
structured_llm = llm.with_structured_output(QueryAnalysis)
result: QueryAnalysis = await structured_llm.ainvoke([system_msg, user_msg])
# result.intent, result.sub_questions, result.clarification_needed — guaranteed typed

# In verify_groundedness:
structured_llm = llm.with_structured_output(GroundednessResult)
result: GroundednessResult = await structured_llm.ainvoke([system_msg, claim_msg])
# result.overall_grounded, result.verifications — guaranteed typed
```

**Ollama compatibility**: `langchain-ollama` supports structured output via `format="json"`. For local models like `qwen2.5:7b`, use:
```python
# Method 1: JSON mode (most compatible with local models)
structured_llm = llm.with_structured_output(QueryAnalysis, method="json_mode")

# Method 2: Function calling (if model supports it)
structured_llm = llm.with_structured_output(QueryAnalysis)
```

**Apply to these nodes**:
| Node | Current | Enhancement |
|------|---------|-------------|
| `classify_intent` | Manual intent parsing | `with_structured_output(QueryAnalysis)` |
| `rewrite_query` | Manual sub-question extraction | `with_structured_output(QueryAnalysis)` |
| `verify_groundedness` | Manual verdict parsing | `with_structured_output(GroundednessResult)` |
| `collect_answer` | Free text + manual citation parsing | `with_structured_output(AnswerWithCitations)` |

---

### ENH-003 — `trim_messages` / `RemoveMessage` for Context Window Control

**Impact**: Prevents context overflow in long conversations, more reliable multi-turn sessions
**Effort**: Low | **Files**: `nodes.py` (summarize_history)
**Docs**: [Trim messages](https://docs.langchain.com/oss/python/langgraph/add-memory#trim-messages), [Delete messages](https://docs.langchain.com/oss/python/langgraph/add-memory#delete-messages)

**What it is**: Now that we use `add_messages` reducer (from the audit fix), we have access to `RemoveMessage` and `trim_messages` — LangGraph's built-in tools for managing message history length.

**Current gap**: `summarize_history` does custom LLM-based summarization. The research loop accumulates messages (orchestrator → tools → orchestrator → tools...) without any trimming. After 3-4 iterations with many tool calls, the messages list can exceed the model's context window.

**Implementation patterns**:

```python
from langchain_core.messages import trim_messages, RemoveMessage

# Pattern 1: Trim before LLM call in orchestrator
def prepare_messages(state):
    trimmed = trim_messages(
        state["messages"],
        max_tokens=4096,
        token_counter=len,  # or model-specific counter
        strategy="last",    # keep most recent
        include_system=True,
        allow_partial=False,
    )
    return trimmed

# Pattern 2: Delete specific old messages after compression
def clean_old_messages(state):
    # Keep system + last 5 messages, remove rest
    old_ids = [m.id for m in state["messages"][1:-5]]
    return {"messages": [RemoveMessage(id=mid) for mid in old_ids]}
```

**Apply to**:
- `summarize_history` — use `trim_messages` instead of custom summarization logic
- `orchestrator` (research loop) — trim before each LLM call to prevent overflow
- `compress_context` — pair with `RemoveMessage` to clean up tool messages after compression

---

### ENH-004 — `RetryPolicy` on Critical Nodes

**Impact**: Automatic recovery from transient Ollama/Qdrant failures without custom retry code
**Effort**: Low | **Files**: `research_graph.py`, `conversation_graph.py`
**Docs**: [Transient errors](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph#transient-errors), [Exception handling](https://docs.langchain.com/oss/python/langgraph/use-graph-api#exception-handling)

**What it is**: LangGraph's `RetryPolicy` provides declarative retry with exponential backoff at the NODE level. When a node raises an exception, the graph automatically retries with configurable delays.

**Current gap**: `tools_node` has custom retry-once logic. `orchestrator`, `collect_answer`, and `compress_context` have manual try/except fallbacks. No exponential backoff. The custom retry in tools_node counts both attempts against the budget (correct but brittle).

**Implementation pattern**:
```python
from langgraph.pregel import RetryPolicy

# In build_research_graph:
graph.add_node(
    "orchestrator",
    orchestrator,
    retry=RetryPolicy(max_attempts=3, initial_interval=1.0, backoff_factor=2.0)
)
graph.add_node(
    "tools",
    tools_node,
    retry=RetryPolicy(max_attempts=2, initial_interval=0.5)
)
graph.add_node(
    "collect_answer",
    collect_answer,
    retry=RetryPolicy(max_attempts=2, initial_interval=1.0)
)

# In build_conversation_graph:
graph.add_node(
    "verify_groundedness",
    verify_groundedness,
    retry=RetryPolicy(max_attempts=2, initial_interval=0.5)
)
```

**Benefit**: The custom retry-once logic in `tools_node` can be simplified — let `RetryPolicy` handle transient failures (network timeouts, Ollama 503s), keep only the deduplication and budget counting logic.

---

### ENH-005 — `CacheBackedEmbeddings` for Embedding Reuse

**Impact**: 50-80% reduction in embedding API calls for repeated/similar queries
**Effort**: Low | **Files**: `ingestion/embedder.py`, `main.py`
**Docs**: [Caching](https://docs.langchain.com/oss/python/integrations/embeddings/index#caching)

**What it is**: `CacheBackedEmbeddings` wraps any LangChain embedding model and caches results by content hash. When the same text is embedded again, it returns the cached vector instantly.

**Current gap**: Every query re-embeds the query text and every ingestion re-embeds chunks even if identical text was previously embedded. With Ollama running locally, this is ~100ms per embed call that could be 0ms.

**Implementation pattern**:
```python
from langchain.embeddings import CacheBackedEmbeddings
from langchain.storage import LocalFileStore

# In main.py lifespan:
base_embeddings = OllamaEmbeddings(model="nomic-embed-text")
store = LocalFileStore("./data/embedding_cache")
cached_embeddings = CacheBackedEmbeddings.from_bytes_store(
    base_embeddings,
    store,
    namespace=base_embeddings.model,
)
# Use cached_embeddings everywhere instead of base_embeddings
```

**Where it helps**:
- Query embedding: same/similar queries return cached vectors
- Re-ingestion: if a document is re-ingested (updated), unchanged chunks hit cache
- Cross-session: cache persists on disk via `LocalFileStore`

---

## MEDIUM IMPACT — Plan for Next Iteration

### ENH-006 — Middleware: Model Call Limit + Tool Call Limit

**Impact**: Production cost control, prevents runaway agent loops
**Effort**: Low | **Files**: `chat.py` or `main.py`
**Docs**: [Model call limit](https://docs.langchain.com/oss/python/langchain/middleware/built-in#model-call-limit-4), [Tool call limit](https://docs.langchain.com/oss/python/langchain/middleware/built-in#tool-call-limit-5)

**What it is**: LangChain v1 middleware that wraps the LLM/tools with hard limits:
- `ModelCallLimitMiddleware(max_calls=20)` — total LLM calls per invocation
- `ToolCallLimitMiddleware(max_calls=10)` — total tool invocations per invocation

**Current gap**: We have `max_iterations` and `max_tool_calls` in `settings` checked by `should_continue_loop`. But these are checked BETWEEN loop iterations — a runaway tool that makes many calls WITHIN a single node invocation isn't caught. Middleware catches it at the LLM/tool level regardless of graph structure.

---

### ENH-007 — `ToolNode` for Parallel Tool Execution

**Impact**: 2-3x speedup when orchestrator requests multiple tool calls per iteration
**Effort**: Medium | **Files**: `research_nodes.py`, `research_graph.py`
**Docs**: [ToolNode](https://docs.langchain.com/oss/python/langchain/tools#toolnode)

**What it is**: LangGraph's prebuilt `ToolNode` executes ALL tool calls from a single AIMessage in parallel via `asyncio.gather`. Our custom `tools_node` runs them sequentially.

**Approach**: Use `ToolNode` for execution, wrap with deduplication logic:
```python
from langgraph.prebuilt import ToolNode

base_tool_node = ToolNode(tools)

async def tools_node_with_dedup(state, config):
    # Run tools in parallel via ToolNode
    result = await base_tool_node(state, config)
    # Post-process: deduplicate chunks, count budget
    ...
```

---

### ENH-008 — Summarize Messages Pattern for Research Loop

**Impact**: Longer research sessions without context overflow
**Effort**: Medium | **Files**: `research_nodes.py`
**Docs**: [Summarize messages](https://docs.langchain.com/oss/python/langgraph/add-memory#manage-short-term-memory)

**What it is**: After N research iterations, summarize old orchestrator/tool messages into a single SystemMessage, then delete the originals via `RemoveMessage`. Keeps the research loop's context manageable.

**Current approach**: `compress_context` compresses CHUNKS (retrieved passages), not messages. After 3 iterations with 3 tool calls each, the messages list has ~12 messages (6 AI + 6 Tool) which can exceed smaller model context windows.

**Pattern**:
```python
# In should_compress_context (or a new node):
if len(state["messages"]) > 15:
    summary = await llm.ainvoke([
        SystemMessage("Summarize this research progress:"),
        *state["messages"][:-4]  # summarize all but last 4
    ])
    # Replace old messages with summary + keep recent
    old_ids = [m.id for m in state["messages"][:-4]]
    return {
        "messages": [RemoveMessage(id=mid) for mid in old_ids]
                   + [SystemMessage(content=f"Research so far: {summary.content}")]
    }
```

---

## LOWER IMPACT — Future Considerations

### ENH-009 — Deep Agents Coordinator-Worker Pattern

Our 3-layer architecture (Conversation → Research → MetaReasoning) loosely maps to the Deep Agents coordinator-worker pattern. The `create_deep_agent` API provides:
- Built-in streaming infrastructure
- Subagent management
- Context compression
- Human-in-the-loop patterns

**Assessment**: Our custom StateGraph gives more control than `create_deep_agent`. Worth monitoring as the Deep Agents API matures, but NOT worth migrating to now.

### ENH-010 — LangGraph Functional API

LangGraph >= 1.0 offers a functional API (`@entrypoint`, `@task`) as an alternative to StateGraph. Simpler for linear workflows but less suitable for our complex multi-graph architecture with Send/fan-out, conditional edges, and nested subgraphs.

**Assessment**: Not applicable. Our architecture requires StateGraph's expressiveness.

---

## Implementation Priority Matrix

```
             HIGH IMPACT                    MEDIUM IMPACT
         ┌────────────────────┐        ┌─────────────────────┐
  LOW    │ ENH-002 structured │        │ ENH-006 middleware   │
  EFFORT │ ENH-003 trim_msgs  │        │                     │
         │ ENH-004 RetryPolicy│        │                     │
         │ ENH-005 cache embed│        │                     │
         └────────────────────┘        └─────────────────────┘
         ┌────────────────────┐        ┌─────────────────────┐
  MED    │ ENH-001 Store      │        │ ENH-007 ToolNode    │
  EFFORT │                    │        │ ENH-008 summarize   │
         └────────────────────┘        └─────────────────────┘
```

**Recommended order**:
1. ENH-004 (RetryPolicy) — 30min, replaces fragile custom retry
2. ENH-005 (CacheBackedEmbeddings) — 30min, immediate perf gains
3. ENH-002 (structured output) — 1-2h, eliminates parsing failures
4. ENH-003 (trim_messages) — 1h, enables longer conversations
5. ENH-001 (Store) — 2-3h, biggest UX improvement long-term

---

## Further Investigation

### INV-A — Ollama structured output compatibility
Verify `ChatOllama.with_structured_output(PydanticModel)` works with `qwen2.5:7b`. Test both `method="json_mode"` and default function-calling. If function calling fails, fall back to JSON mode with Pydantic validation as a post-processing step.

### INV-B — Store backend options
`InMemoryStore` is lost on restart. For production persistence, investigate:
- SQLite-backed store (matches our existing SQLite infrastructure)
- Simple JSON file store as a lightweight alternative
- The Store API's semantic search capability (requires embedding index on stored items)

### INV-C — CacheBackedEmbeddings + Ollama interaction
Verify that `CacheBackedEmbeddings` correctly wraps `OllamaEmbeddings` from `langchain-ollama`. The cache key is content-hash based — confirm that identical text produces identical hashes across sessions.

### INV-D — RetryPolicy + circuit breaker interaction
Our existing circuit breaker pattern (in HybridSearcher and nodes) may conflict with RetryPolicy. If a node has both circuit breaker AND RetryPolicy, the circuit breaker would open after N failures while RetryPolicy tries to retry. Determine the correct ordering: RetryPolicy should be INSIDE the circuit breaker (retry transient failures, but respect circuit state).
