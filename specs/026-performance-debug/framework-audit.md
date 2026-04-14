# Framework Configuration Audit (FR-001)

## Executive Summary

Four confirmed `BUG` findings (BUG-010, BUG-016 ×3, BUG-019 ×2, and a new Tenacity coverage gap in `backend/providers/*`), nine `CONCERN` findings (primarily around state-channel contract drift and latency-amplifying primitives), and six clean `PASS` findings (message reducer, retry policies, Qdrant tenacity coverage, conditional-edge exhaustiveness). BUG-010's root cause is **scoring math** — a dict-vs-attribute interface mismatch between `aggregate_answers` and `compute_confidence`. The FR-005 top-1 latency candidate is `verify_groundedness`'s second LLM call, which is inert for thinking models but still pays full round-trip cost. See §Agent Methodology F4.10 for the full scorecard.

**Agent**: A2 (backend-architect, Wave 1)
**Scope**: LangGraph, LangChain, LangChain-Ollama, Tenacity primitives used by the conversation + research + meta-reasoning agent stack.
**Method**: Source-level symbol review via Serena + GitNexus, cross-checked against Context7-fetched framework documentation. Every finding carries a `file:line` citation, an authoritative doc URL, and a severity assessment (`BUG` / `CONCERN` / `PASS` / `PASS-with-note`).
**Versions audited**: LangGraph >= 1.0.10, LangChain >= 1.2.10, langchain-ollama (current stable), Tenacity >= 9.0 (per `CLAUDE.md` Active Technologies + pyproject constraints).
**Inputs this audit feeds**: A5 (BUG-010 confidence fix, Wave 3), A6 (latency top-1 fix, Wave 3). This audit does NOT fix anything; it names every suspicious primitive with enough evidence that a fixer can start without re-tracing the graph.

---

## LangGraph Primitives — Part 1: State Reducers & Checkpointer

The agent defines two state TypedDicts in `backend/agent/state.py`: `ConversationState` (outer graph, 15 fields) and `ResearchState` (inner sub-graph, 25 fields). Every `Annotated[T, reducer]` field pairs a type with a merge function that LangGraph applies when multiple nodes or a `Send()` fan-out write to the same key. When the reducer is wrong, either you overwrite concurrent writes silently or you accumulate garbage.

### F1.1 — `add_messages` reducer on `messages`

- **Current usage**: `ConversationState.messages: Annotated[list, add_messages]` at `backend/agent/state.py:45`; `ResearchState.messages: Annotated[list, add_messages]` at `backend/agent/state.py:69`.
- **Doc URL**: https://docs.langchain.com/oss/python/langgraph/graph-api (Define Graph State with Message Reducer — canonical pattern: `Annotated[list[AnyMessage], add_messages]`).
- **Assessment**: **PASS**. Matches the canonical LangGraph recipe for message channels. `add_messages` de-duplicates by message ID and supports partial updates; `operator.add` would be wrong here (no dedup, would double-append on retry).

### F1.2 — `operator.add` reducer on `sub_answers`

- **Current usage**: `ConversationState.sub_answers: Annotated[list[SubAnswer], operator.add]` at `backend/agent/state.py:47`; `ResearchState.sub_answers: Annotated[list, operator.add]` at `backend/agent/state.py:72`.
- **Doc URL**: https://docs.langchain.com/oss/python/langgraph/graph-api (Custom Reducer with Annotated for List Concatenation — `operator.add` concatenates lists from parallel branches).
- **Assessment**: **PASS** for semantics — `Send()` fan-out produces one `SubAnswer` per sub-question and we want all of them merged. Note the conservation invariant: no node may *replace* `sub_answers` with `[]` or earlier items are lost; `aggregate_answers` (nodes.py:360) correctly reads from state rather than overwriting.

### F1.3 — `operator.add` reducer on `citations`

- **Current usage**: `ConversationState.citations: Annotated[list[Citation], operator.add]` at `backend/agent/state.py:49`; `ResearchState.citations: Annotated[list[Citation], operator.add]` at `backend/agent/state.py:70`.
- **Doc URL**: https://docs.langchain.com/oss/python/langgraph/use-graph-api (Define and compile a parallel execution graph — `operator.add` example).
- **Assessment**: **CONCERN** (BUG-017 workaround). `Send()` fan-out with N sub-questions produces N copies of each shared citation, and the reducer has no dedup key. The workaround lives at `backend/api/chat.py:228-235` where the emitter post-dedups by `passage_id`. The workaround is correct but masks the underlying reducer semantics: every downstream consumer of `state["citations"]` either re-dedups or sees duplicates. A custom reducer keyed on `passage_id` (keep highest `relevance_score`) would move the invariant into the state channel where it belongs. Same fix pattern also applies to `aggregate_answers` (nodes.py:405-417) which re-implements dedup manually.

### F1.4 — Custom `_keep_last` on `session_id`

- **Current usage**: `_keep_last` at `backend/agent/state.py:20-22`: `def _keep_last(existing, new): return new`. Applied to `ConversationState.session_id` at `state.py:44`.
- **Doc URL**: https://docs.langchain.com/oss/python/langgraph/graph-api (custom reducer functions section).
- **Assessment**: **PASS**. `session_id` is injected once at seed time (chat.py:135) and must not accumulate. `_keep_last` is the canonical "replace" reducer — LangGraph default reducer is also "keep last" when no reducer is given, so this is functionally equivalent but explicit. Explicit is better.

### F1.5 — `_keep_last` on `confidence_score` (int, ConversationState)

- **Current usage**: `ConversationState.confidence_score: Annotated[int, _keep_last]` at `backend/agent/state.py:50`.
- **Doc URL**: https://docs.langchain.com/oss/python/langgraph/graph-api.
- **Assessment**: **CONCERN — scale mismatch with inner state**. Declared as `int` on the 0–100 scale; written at `nodes.py:436` by `aggregate_answers` via `compute_confidence()` which returns an int 0–100. Also overwritten at `nodes.py:533` by `verify_groundedness` via `int(mean(raw_scores) * result.confidence_adjustment)`. The reducer itself is correct (you want last-write-wins, not accumulation). The *scale* is the defect: `ResearchState.confidence_score` is `float` 0–1 (F1.6). If a value ever flows from the inner sub-graph through `Send()`/fan-out to the outer state without the `int(x*100)` conversion done in `SubAnswer.confidence_score` (schemas.py), the emitter at `chat.py:248` `int(final_state.get("confidence_score", 0))` would truncate `0.75` to `0`. This scale-crossing is a major contributor to BUG-010 (see §Agent Methodology F4.3).

### F1.6 — `_keep_last` on `confidence_score` (float, ResearchState)

- **Current usage**: `ResearchState.confidence_score: Annotated[float, _keep_last]` at `backend/agent/state.py:65`.
- **Doc URL**: https://docs.langchain.com/oss/python/langgraph/graph-api.
- **Assessment**: **CONCERN — type divergence**. Reducer is fine, but typing this as `float` while the outer `ConversationState.confidence_score` is `int` (F1.5) means any write at `research_nodes.py:collect_answer` (which calls `compute_confidence(chunks, num_collections_searched=..., num_collections_total=...)` and stores a float 0–1) is a potential type-mismatch hazard once the value crosses the sub-graph boundary. Pick a single scale project-wide and enforce it at the Pydantic schema layer.

### F1.7 — `_keep_last` on `retrieved_chunks` + manual append anti-pattern

- **Current usage**: `ResearchState.retrieved_chunks: Annotated[list[RetrievedChunk], _keep_last]` at `backend/agent/state.py:61`. The `tools_node` implementation (`backend/agent/research_nodes.py:243-390`) works around the reducer by manually reading existing chunks and returning `state["retrieved_chunks"] + new_chunks`.
- **Doc URL**: https://docs.langchain.com/oss/python/langgraph/graph-api (reducer semantics).
- **Assessment**: **CONCERN — reducer contradicts the node's intent**. The node appends, but the reducer replaces. Today this works because `tools_node` is the *only* writer and it does the append itself. The day a second writer (e.g., a compensating retry, a meta-reasoning strategy) writes `retrieved_chunks`, one of them silently loses its data — the merge is last-writer-wins, not additive. Correct fix: swap the reducer to a custom deduping-append keyed on `(chunk_id, document_id)`; delete the manual concatenation in `tools_node`. This is exactly the class of bug LangGraph reducers exist to prevent.

### F1.8 — `_merge_dicts` on `stage_timings`

- **Current usage**: `_merge_dicts` defined at `backend/agent/state.py:25-30`; applied to `ConversationState.stage_timings: Annotated[dict, _merge_dicts]` at `state.py:52` and `ResearchState.stage_timings` at `state.py:78`.
- **Doc URL**: https://docs.langchain.com/oss/python/langgraph/graph-api (custom reducer).
- **Assessment**: **PASS**. Multiple nodes contribute stage timings (`intent_classification`, `grounded_verification`, `ranking`, etc.); dict-merge is the right semantic. Note that this is shallow merge — if two nodes write the same stage key with different durations, the second overwrites. In the current graph each stage has exactly one writer, so this is safe.

### F1.9 — `_merge_sets` on `retrieval_keys`

- **Current usage**: `_merge_sets` defined at `backend/agent/state.py:33-35`; applied to `ResearchState.retrieval_keys: Annotated[set[str], _merge_sets]` at `state.py:62`.
- **Doc URL**: https://docs.langchain.com/oss/python/langgraph/graph-api.
- **Assessment**: **PASS**. Set union is the correct semantic for de-dup tracking across parallel tool calls. Guards against the infinite-retrieval regression where the same chunk_id comes back from two sub-questions.

### F1.10 — AsyncSqliteSaver checkpointer wiring

- **Current usage**: `backend/main.py:176-182` — `checkpoint_path = settings.sqlite_path.replace("embedinator.db", "checkpoints.db")` → `checkpointer_cm = AsyncSqliteSaver.from_conn_string(checkpoint_path)` → `await checkpointer.setup()` → `app.state.checkpointer = checkpointer`. Thread wiring at `backend/api/chat.py:163` — `"thread_id": session_id` on every `astream()` invocation.
- **Doc URL**: https://langchain-ai.github.io/langgraph/reference/checkpoints/#langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver (AsyncSqliteSaver API); https://docs.langchain.com/oss/python/langgraph/add-memory (checkpointer + thread_id pattern).
- **Assessment**: **CONCERN — unbounded DB growth, no pruning**. Thread wiring is correct; every chat request uses `thread_id=session_id` so each conversation has its own checkpoint stream. But there is no pruning policy anywhere: the lifespan shutdown path at `backend/main.py:266-270` does `PRAGMA wal_checkpoint(TRUNCATE)` (a WAL flush, not a checkpoint-row delete) and closes the connection — it never deletes stale threads. Over weeks of usage `data/checkpoints.db` will grow without bound, eventually hitting SQLite write amplification and increasing checkpoint read/write latency on every new turn of every live conversation. Recommended: add a periodic task that deletes checkpoints for `thread_id` values older than N days via `DELETE FROM checkpoints WHERE thread_id = ? AND checkpoint_ns = ''` or use LangGraph's `aget_state_history` + `adelete_thread`. This is a latency contributor hypothesis for FR-005 (§Agent Methodology F4.6).

---

## LangGraph Primitives — Part 2: Edges, `Send()`, Recursion, Interrupts, Retries

### F2.1 — `add_conditional_edges` after `classify_intent`

- **Current usage**: `backend/agent/conversation_graph.py:70-74` — `graph.add_conditional_edges("classify_intent", route_intent, {"rag_query": "rewrite_query", "collection_mgmt": "handle_collection_mgmt", "ambiguous": "request_clarification"})`.
- **Doc URL**: https://docs.langchain.com/oss/python/langgraph/graph-api (`add_conditional_edges` — path-dict form).
- **Assessment**: **PASS**. Mapping is exhaustive vs. the `_VALID_INTENTS = {"rag_query", "collection_mgmt", "ambiguous"}` set at `nodes.py:160`. `route_intent` has a default branch for unknown values (defaults to `rag_query`), so no `InvalidUpdateError` risk.

### F2.2 — `add_conditional_edges` after `rewrite_query` (path-list form)

- **Current usage**: `backend/agent/conversation_graph.py:77-78` — `graph.add_conditional_edges("rewrite_query", route_after_rewrite, ["request_clarification", "research"])`.
- **Doc URL**: https://docs.langchain.com/oss/python/langgraph/graph-api (`add_conditional_edges` — path-list form where the return string is the node name).
- **Assessment**: **PASS**. The path-list form is correct when the router returns the destination node name directly. `route_after_rewrite` in `backend/agent/edges.py` either returns `"request_clarification"` or a `Send("research", payload)` — LangGraph handles the `Send` case directly; the string case resolves via the list. Note the stale comment at `backend/agent/edges.py:47-48` which claims "LangGraph does not support two add_conditional_edges from the same source node" — that claim is *not* documented in current LangGraph >= 1.0 behavior; a node can route to multiple `Send()` plus a string destination in one return. The comment is misleading.

### F2.3 — `add_conditional_edges` after `orchestrator` (dynamic target)

- **Current usage**: `backend/agent/research_graph.py:173` — `graph.add_conditional_edges("orchestrator", should_continue_loop, {"continue": "tools", "sufficient": "collect_answer", "exhausted": exhausted_target})` where `exhausted_target = "meta_reasoning" if meta_reasoning_graph else "fallback_response"` is computed at graph-build time.
- **Doc URL**: https://docs.langchain.com/oss/python/langgraph/graph-api (conditional edges mapping).
- **Assessment**: **CONCERN — build-time conditional**. The mapping is exhaustive relative to `should_continue_loop`'s return codes (`continue`, `sufficient`, `exhausted`), so LangGraph won't throw. But the dynamic target means two deployments with identical code but different env flags route `exhausted` to different nodes — this is a startup-time decision. That's fine for DI; just flag that the test matrix must cover both branches.

### F2.4 — `Send()` fan-out parallelism claim

- **Current usage**: `route_fan_out` in `backend/agent/edges.py` builds `Send("research", payload)` objects, one per sub-question. LangGraph's scheduler is documented as executing them concurrently via `asyncio.gather`.
- **Doc URL**: https://docs.langchain.com/oss/python/langgraph/use-graph-api (Define and compile a parallel execution graph).
- **Assessment**: **NEEDS A1 DATA** (CONCERN pending measurement). The primitive is correct and LangGraph *will* dispatch branches in parallel at the scheduler layer. But if every `research` branch hits the same serialized bottleneck downstream — e.g., a shared inference client with `max_connections=1`, a global Python lock, or the `_chat_semaphore` in `chat.py` — wall-clock time ≈ serial sum of sub-question durations. A1's hardware audit will tell us whether we see GPU concurrency or serialization. If serial: this is a top-1 latency contributor and is framework-usage-correct but application-blocked.

### F2.5 — `recursion_limit=100`

- **Current usage**: `backend/api/chat.py:167` — `"recursion_limit": 100` on every `graph.astream(...)` call.
- **Doc URL**: https://langchain-ai.github.io/langgraph/reference/graphs/#langgraph.graph.state.StateGraph.compile (recursion limit default is 25); https://docs.langchain.com/oss/python/langgraph/errors/ (GraphRecursionError).
- **Assessment**: **CONCERN — too permissive**. Spec-14 §Performance Budgets sets tighter bounds (expected orchestrator iterations ≤ 10, meta-reasoning attempts ≤ 2). A recursion budget of 100 means the graph can spin through ~100 node executions before LangGraph raises `GraphRecursionError`. Combined with BUG-010 (confidence always 0 means `sufficient` is never hit), the loop can only exit via `max_iterations` (10) or wall-clock deadline. `100` hides orchestrator misbehavior behind a generous ceiling. Recommended: cap at `30` (tiers × iterations + meta-reasoning + conversation overhead with slack) and treat `GraphRecursionError` as an observability signal.

### F2.6 — `interrupt()` in clarification flow

- **Current usage**: `backend/agent/nodes.py:344` — `user_response = interrupt(clarification_question)` inside `request_clarification`. Stream-side detection at `backend/api/chat.py:189-195` yields `{"type": "clarification", "question": ...}` and `return`s (the resume code path would require a separate `Command(resume=...)` invocation via a different endpoint).
- **Doc URL**: https://docs.langchain.com/oss/python/langgraph/interrupts (interrupt + Command(resume=...) pattern); https://docs.langchain.com/oss/python/langgraph/add-memory (checkpointer required for interrupts).
- **Assessment**: **CONCERN — resume path potentially dead**. A clarification request is emitted and the stream closes. Production chat UI must call back with `Command(resume=<user answer>)` for the graph to continue; a grep for `Command(resume` across `backend/` is the audit verification step. If no endpoint resumes, every clarification aborts the session — architecturally this is BUG-007-shaped dead code (the `init_session` node in BUG-007 had the same "written but never called" quality). Recommend A5/A6 confirm a POST endpoint (e.g., `/api/chat/resume`) exists and is wired to the frontend before declaring this path live.

### F2.7 — `RetryPolicy` on `orchestrator`, `format_response`, `verify_groundedness`

- **Current usage**: `research_graph.py:48` — `retry=RetryPolicy(max_attempts=3, initial_interval=1.0, backoff_factor=2.0)` on orchestrator node; `conversation_graph.py` — `RetryPolicy(max_attempts=2)` on `format_response` and `verify_groundedness`.
- **Doc URL**: https://langchain-ai.github.io/langgraph/reference/types/#langgraph.types.RetryPolicy.
- **Assessment**: **PASS**. Retries at the node layer are in addition to tenacity retries at the adapter layer (F3.8) — double protection is fine as long as each attempt is idempotent. `orchestrator`'s 3-attempt exponential backoff (1s, 2s, 4s — up to 7s per failure) is reasonable for an LLM call. Format/verify with `max_attempts=2` is light but acceptable since they fail to `None`/pass-through on second attempt.

### F2.8 — Fallback to `MemorySaver()` when no checkpointer passed

- **Current usage**: `backend/agent/conversation_graph.py` — `build_conversation_graph(research_graph, checkpointer=MemorySaver(), store=...)`.
- **Doc URL**: https://docs.langchain.com/oss/python/langgraph/persistence (MemorySaver vs. SqliteSaver).
- **Assessment**: **PASS-with-note**. Test-only fallback: production wires `AsyncSqliteSaver` via `chat.py`. Make sure unit tests use `MemorySaver` explicitly rather than relying on default, so a future change to the default doesn't silently break persistence expectations.

---

## LangChain Primitives

### F3.1 — `trim_messages(token_counter=len)` in orchestrator (BUG-019)

- **Current usage**: `backend/agent/research_nodes.py:138-143`:
  ```python
  trimmed_messages = trim_messages(
      summarized_msgs,
      max_tokens=6000,
      token_counter=len,      # <- BUG-019
      strategy="last",
      include_system=True,
      allow_partial=False,
  )
  ```
- **Doc URL**: https://docs.langchain.com/oss/python/langgraph/add-memory (canonical usage: `token_counter=count_tokens_approximately`).
- **Assessment**: **BUG** (confirms BUG-019). `token_counter=len` counts *messages* (integer length of the list) when called on a list, not tokens. LangChain's `trim_messages` expects a callable that takes a list of messages and returns an int token count. Passing `len` means `max_tokens=6000` becomes "keep up to 6000 messages" — effectively disabling the trim. The canonical fix, per the same Context7 doc URL, is `token_counter=count_tokens_approximately` (a character-based approximator that costs ~O(n) string work) or a real tokenizer. Note: `compress_context` at `research_nodes.py:394-422` does use `count_tokens_approximately` correctly — the asymmetry is a smell; they should use the same primitive. Same pattern of bug at `backend/agent/nodes.py:696` in `summarize_history` — a second BUG-019 instance that A5's scope must cover.

### F3.2 — `trim_messages(token_counter=len)` in `summarize_history` (second BUG-019 site)

- **Current usage**: `backend/agent/nodes.py:693-700` — identical `token_counter=len` bug in the conversation history summarization path.
- **Doc URL**: https://docs.langchain.com/oss/python/langgraph/add-memory.
- **Assessment**: **BUG** (BUG-019, second site). The `ENH-003` comment at `nodes.py:692` claims "trim old messages before summarization to prevent LLM overflow" — but with `token_counter=len`, the trim allows up to 4096 *messages* through to the LLM summarizer. In practice conversations never reach 4096 turns, so this trim is a no-op. Same fix as F3.1: `count_tokens_approximately`.

### F3.3 — `bind_tools` on Ollama-backed LLM

- **Current usage**: `backend/agent/research_nodes.py:145` — `llm_with_tools = llm.bind_tools(tools_list) if tools_list else llm`. Tools are registered via closure in `backend/agent/tools.py:32`.
- **Doc URL**: https://python.langchain.com/docs/integrations/llms/ollama/index (Define and Bind User Tool in Python); https://python.langchain.com/docs/integrations/chat/ollama/ (ChatOllama.bind_tools tool schema format).
- **Assessment**: **PASS-with-note** (verification gap). `bind_tools` is the documented LangChain pattern for function-calling LLMs. `qwen2.5:7b` is the default model (`config.py:default_llm_model`). qwen2.5 *does* support tool calling via the Ollama tool schema, but the current provider flow (`backend/providers/ollama_provider.py`) needs to return an `AIMessage` with populated `.tool_calls` field for `bind_tools` to round-trip correctly. Verification gap: no test exercises a 2-tool-call turn end-to-end with the Ollama adapter. Recommend A5/A6 add one; mismatched tool-schema formats between qwen's native JSON and LangChain's `ToolCall` shape would be a silent failure.

### F3.4 — `with_structured_output(..., method="json_mode")` — intent classifier

- **Current usage**: `backend/agent/nodes.py:201` — `structured_llm = llm.with_structured_output(IntentClassification, method="json_mode")`.
- **Doc URL**: https://docs.langchain.com/oss/python/langchain/models (Get Raw AIMessage with Structured Output; `method="json_mode"` vs `method="json_schema"`); https://python.langchain.com/docs/integrations/llms/ollama/index (Generate Structured Output with Pydantic — default method).
- **Assessment**: **BUG** (contributes to BUG-016). `method="json_mode"` asks the model to emit a JSON object and parses the entire completion as JSON. Thinking-model variants (e.g., `qwen3:8b-thinking`, `deepseek-r1`) wrap their output in `<think>…</think>` tags *before* the JSON, so `json.loads()` fails. Recommended migration per the same Context7 doc: `method="json_schema"` (native OpenAI/Ollama JSON-schema enforcement with server-side validation) where available, or strip `<think>…</think>` before parsing. Note: classify_intent has a broad `except Exception` at `nodes.py:221` that defaults to `"rag_query"` on parse failure — so the bug is silent: thinking-model users get everything routed to `rag_query` no matter what they ask.

### F3.5 — `with_structured_output(..., method="json_mode")` — query analyzer

- **Current usage**: `backend/agent/nodes.py:268` — `structured_llm = llm.with_structured_output(QueryAnalysis, method="json_mode")`.
- **Doc URL**: https://docs.langchain.com/oss/python/langchain/models.
- **Assessment**: **BUG** (BUG-016, second site). Same `method="json_mode"` issue. Unlike F3.4, this site has an explicit retry flow (first attempt → simplified prompt → final fallback to a hand-constructed `QueryAnalysis`). Thinking-model users fall through to the `last_message` fallback, which means the router always treats queries as `complexity_tier="lookup"` with a single sub-question — defeating the multi-hop research flow entirely.

### F3.6 — `with_structured_output(..., method="json_mode")` — groundedness verifier

- **Current usage**: `backend/agent/nodes.py:510` — `structured_llm = llm.with_structured_output(GroundednessResult, method="json_mode")`.
- **Doc URL**: https://docs.langchain.com/oss/python/langchain/models.
- **Assessment**: **BUG** (BUG-016, third site). Same root cause. This site has NO retry — a single `except Exception` at `nodes.py:541` returns `{"groundedness_result": None}`, silently skipping groundedness for every request from thinking-model users. The user sees no warning banner, no `[unverified]` annotations, no confidence adjustment. The feature is inert.

### F3.7 — Retry wrapper coverage on `with_structured_output`

- **Current usage**: `rewrite_query` has a two-pass retry (`nodes.py:275-321`). `classify_intent` and `verify_groundedness` catch-all-exception to default/None. No explicit retry.
- **Doc URL**: https://docs.langchain.com/oss/python/langchain/models (include_raw + parsing_error handling); https://python.langchain.com/docs/integrations/chat/ollama/ (output parser retry patterns).
- **Assessment**: **CONCERN — inconsistent retry coverage**. Three structured-output call sites, three different retry stories: one has a full retry (rewrite), one silently defaults (classify), one silently returns None (verify). Recommendation: standardize on `with_structured_output(..., include_raw=True)` so each call site has access to `parsing_error`, then wrap with a common retry helper. Today a thinking-model user hits three different failure modes in one turn.

### F3.8 — Tenacity `@retry` coverage on Qdrant storage path

- **Current usage**: `backend/storage/qdrant_client.py` — six `@retry` decorators at lines 100, 131, 164, 329, 449, 508.
- **Doc URL**: https://tenacity.readthedocs.io/en/latest/ (reference); https://langchain-ai.github.io/langgraph/reference/types/#langgraph.types.RetryPolicy (LangGraph's complementary node-level retry).
- **Assessment**: **PASS**. Dense, sparse, and hybrid search paths are all covered; batch upsert is covered; collection CRUD is covered. Exponential backoff with jitter is the standard recipe. Double protection with LangGraph node-level retries (F2.7) is redundant but not harmful.

### F3.9 — Tenacity gap in `backend/providers/*` (Ollama call path)

- **Current usage**: `backend/providers/ollama_provider.py`, `backend/providers/base.py`, `backend/providers/registry.py`. Grep for `@retry` across `backend/providers/**.py` returns zero hits. A comment at `backend/providers/registry.py:71` notes "Used by agent graph nodes (ainvoke, with_structured_output, bind_tools)" — confirming this is the hot path for every LLM call.
- **Doc URL**: https://tenacity.readthedocs.io/en/latest/ (retry + stop/wait combinators); https://python.langchain.com/docs/integrations/llms/ollama/index (Ollama transport reliability).
- **Assessment**: **BUG (coverage gap)**. Every LLM call (intent, query rewrite, orchestrator, groundedness, summarization) goes through the provider registry unwrapped. A transient 500 from Ollama or a dropped connection propagates as a raw exception — only the LangGraph node-level `RetryPolicy` (where present) catches it, and not every node has one. The orchestrator's node-level retry *does* cover this for the research loop, but intent classification does not — a blip on intent classification defaults the turn to `rag_query` with no retry signal. Fix: add `@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), retry=retry_if_exception_type((httpx.RequestError, ConnectionError)))` around the provider's HTTP-facing `ainvoke` and `astream`.

### F3.10 — `count_tokens_approximately` vs `len` asymmetry

- **Current usage**: `backend/agent/research_nodes.py:394-422` (`should_compress_context`) uses `count_tokens_approximately` correctly. Same file at line 141 (`orchestrator`) uses `token_counter=len`. `backend/agent/nodes.py:682` (`summarize_history`) uses `count_tokens_approximately` for the *branch decision* but `len` for the inner `trim_messages` call.
- **Doc URL**: https://docs.langchain.com/oss/python/langgraph/add-memory.
- **Assessment**: **CONCERN**. The same file mixes the correct and the buggy token counter. That is the clearest possible signal that BUG-019 was a copy-paste error and that a clean-up pass should standardize on `count_tokens_approximately` everywhere — or better, on the same tokenizer the chat model uses, via `from langchain_core.messages.utils import count_tokens_approximately`.

---

## Agent Methodology

### F4.1 — Confidence threshold scaling

- **Current usage**: `backend/agent/research_edges.py:34-35` — `confidence = state["confidence_score"]; threshold = settings.confidence_threshold / 100`. `settings.confidence_threshold` is int `60` per `backend/config.py`. Compared against `ResearchState.confidence_score` which is a float 0–1.
- **Doc URL**: internal (see F1.5, F1.6); https://docs.langchain.com/oss/python/langgraph/graph-api.
- **Assessment**: **PASS-with-note**. The scaling math is correct: `60 / 100 = 0.6`, compared against a float 0–1. The surrounding data-shape contract (F1.5 vs F1.6) is the bug, not the comparison itself. But BUG-010 makes the `"sufficient"` branch unreachable in practice because `confidence_score` at the inner sub-graph is always set to `0.0` (see F4.3).

### F4.2 — `should_continue_loop` stop-signal quality

- **Current usage**: `backend/agent/research_edges.py` — branches: `"sufficient"` (confidence ≥ threshold), `"continue"` (budget remaining, new tool calls), `"exhausted"` (F4 tool-exhaustion path). Wall-clock deadline from BUG-008 fix is also a forced `exhausted` case.
- **Doc URL**: https://docs.langchain.com/oss/python/langgraph/agents (agent loop / control flow).
- **Assessment**: **CONCERN — stop signal dominated by `exhausted`**. With BUG-010 masking `"sufficient"`, every successful turn exits via `"exhausted"`, which routes to `meta_reasoning` (if enabled) or `fallback_response`. The measured distribution should be ≥ 80% `"sufficient"` in healthy operation; today it's 100% `"exhausted"`. After A5 fixes BUG-010, re-measure — this is SC-003 territory.

### F4.3 — BUG-010 scoring-chain root cause

- **Current usage**: `backend/agent/nodes.py:420-423` — `aggregate_answers` computes `passages_for_confidence = [{"relevance_score": c.relevance_score} for c in deduped_citations]` and calls `confidence_score = compute_confidence(passages_for_confidence)`. But `compute_confidence` / `_signal_confidence` at `backend/agent/confidence.py:87-148` expects objects with *attribute* access: `c.rerank_score`, `c.dense_score` (confidence.py:107). A list of plain dicts does not satisfy `c.rerank_score` — either an `AttributeError` is caught somewhere up the stack and the fallback path returns 0, or `scored = []` and the dense-score fallback path also returns 0 because dict lookup is not attribute access.
- **Doc URL**: internal — see `_signal_confidence` body in `confidence.py:87-148`.
- **Assessment**: **BUG — root cause for BUG-010**. The "state write" vs "scoring math" vs "emission" triage: this is **scoring math** (interface-shape mismatch between the caller's dict-shaped payload and the callee's attribute-based expectation). The emission site at `chat.py:248` `int(final_state.get("confidence_score", 0))` is correct — it is receiving the `int 0` that `aggregate_answers` stored, not mis-coercing a valid value. Fix direction for A5: either (a) `compute_confidence` takes a list of dicts and uses `.get("rerank_score")` / `.get("dense_score")` with fallback to `relevance_score`, or (b) `aggregate_answers` passes the actual `RetrievedChunk` objects it has access to via `sa.chunks`. (b) is cleaner because it preserves `chunk_count` and `top_score` signals that a relevance-only projection loses.

### F4.4 — Meta-reasoning attempts

- **Current usage**: `settings.meta_reasoning_max_attempts=2` (Constitution Principle II). Invoked from the `exhausted` edge when `meta_reasoning_graph` is non-None.
- **Doc URL**: https://docs.langchain.com/oss/python/langgraph/subgraphs (sub-graph invocation pattern).
- **Assessment**: **UNMEASURED**. No pytest or benchmark in the repo records per-strategy efficacy. With BUG-010 forcing every turn through `exhausted`, meta-reasoning runs on every request — amplifying its latency cost while its success rate is un-instrumented. After A5 fixes BUG-010, re-measure meta-reasoning trigger rate and per-strategy win rate; the current setting of `2` may be excessive if most turns should short-circuit at `sufficient`.

### F4.5 — Groundedness validation (second LLM call)

- **Current usage**: `backend/agent/nodes.py:467-553` — `verify_groundedness` makes an LLM call with `method="json_mode"` (F3.6 — BUG-016) against the final response and every chunk in `sub_answers`. Stage timed to `state["stage_timings"]["grounded_verification"]`.
- **Doc URL**: https://docs.langchain.com/oss/python/langgraph/agents (multi-step agent validation patterns).
- **Assessment**: **CONCERN — latency cost vs. broken output**. Groundedness adds a full LLM round-trip (likely 2–8 seconds at qwen2.5:7b on CPU; ~1–3 seconds on GPU) to every response. Because it uses `method="json_mode"`, thinking-model users get `groundedness_result=None` silently — the feature is inert but still pays the latency. If A6 must pick the top-1 latency contributor to fix first without fixing BUG-016, gate groundedness behind a check for whether the active model is a thinking-model. Better: fix BUG-016 first, then measure.

### F4.6 — Citation validation (cross-encoder reranker call)

- **Current usage**: `backend/agent/nodes.py:569-665` — `validate_citations` runs cross-encoder `.rank()` twice per citation: once for the cited chunk, and if the score is below threshold, once more across all chunks.
- **Doc URL**: https://www.sbert.net/docs/package_reference/cross_encoder.html (CrossEncoder.rank); https://docs.langchain.com/oss/python/langgraph/agents.
- **Assessment**: **CONCERN — O(citations × chunks) worst case**. For a multi-hop query with 10 citations and 30 retrieved chunks, worst case is 10 + 10×30 = 310 cross-encoder scorings — potentially 2–5 seconds depending on batch size. The stage is timed to `state["stage_timings"]["ranking"]` so a latency profile is available from spec-14. A6 should consult stage timings before picking a fix: if `ranking` is > 20% of total latency, batch all `claim × chunk` pairs into a single `.rank()` call (the cross-encoder API supports this natively).

### F4.7 — Circuit breaker wiring (module-level state)

- **Current usage**: `backend/agent/nodes.py:102-144` — module-level `_inf_circuit_open`, `_inf_failure_count`, `_inf_max_failures`. `_check_inference_circuit` consults `settings.circuit_breaker_failure_threshold` and `settings.circuit_breaker_cooldown_secs` *every call* (re-reads settings). Applied only in `verify_groundedness` at `nodes.py:507`.
- **Doc URL**: https://martinfowler.com/bliki/CircuitBreaker.html (pattern); https://docs.langchain.com/oss/python/langgraph/agents (resilience guidance).
- **Assessment**: **CONCERN — only one consumer of the breaker**. The breaker is defined module-wide but only `verify_groundedness` calls `_check_inference_circuit` / `_record_inference_success/failure`. The orchestrator LLM call (research_nodes.py:orchestrator) — which is called orders of magnitude more often — has no breaker. If Ollama degrades, groundedness fails fast but orchestrator keeps retrying via LangGraph's `RetryPolicy`. Asymmetric. Either remove the breaker (lean on LangGraph retries + tenacity in F3.9) or extend it to every inference call site. BUG-018 in the spec registry is likely this same symptom.

### F4.8 — Tool-exhaustion F4 logic

- **Current usage**: `backend/agent/research_edges.py` `should_continue_loop` — when LLM returns zero new tool calls on a given iteration AND we have chunks, routes to `collect_answer` implicitly via `"sufficient"`; otherwise `"exhausted"`.
- **Doc URL**: https://docs.langchain.com/oss/python/langgraph/agents (tool-calling loop).
- **Assessment**: **PASS-with-note**. Logic is reasonable: if the LLM decides it has enough, respect that. The risk surface is the orchestrator prompt — a bad prompt produces premature zero-tool-call responses. The prompt is in `backend/agent/prompts.py`; not audited here (not a framework primitive). Flag for A5: if BUG-010 is fixed but `should_continue_loop` still never yields `"sufficient"`, inspect whether orchestrator is emitting zero-tool-calls on iteration 1 spuriously.

### F4.9 — Confidence-dimension contract hazard

- **Current usage**: Across all sites writing `confidence_score`: `aggregate_answers` (int 0–100 via `compute_confidence`), `verify_groundedness` (int 0–100 via `int(mean(raw_scores) * adjustment)`), `fallback_response` in `research_nodes.py:651-694` (float `0.0`), `collect_answer` in `research_nodes.py:518-647` (float via `_signal_confidence`). The outer `ConversationState.confidence_score: int` at `state.py:50`; inner `ResearchState.confidence_score: float` at `state.py:65`.
- **Doc URL**: https://docs.pydantic.dev/latest/usage/strict_mode/ (Pydantic strictness for contract enforcement).
- **Assessment**: **BUG (secondary to BUG-010)**. Four writers, two scales, two types — plus a reducer (`_keep_last`) that happily accepts any type. This is the antithesis of a state contract. The fix for BUG-010 (F4.3) must also pick one scale (recommend int 0–100 at every write site) and enforce it at the Pydantic schema layer or at the reducer itself.

### F4.10 — Summary scorecard

| Primitive | Site | Severity | Spec bug |
|---|---|---|---|
| trim_messages token_counter | research_nodes.py:141, nodes.py:696 | BUG | BUG-019 |
| with_structured_output method=json_mode | nodes.py:201, :268, :510 | BUG | BUG-016 |
| compute_confidence dict/attr mismatch | nodes.py:423 → confidence.py:107 | BUG | BUG-010 |
| Tenacity gap in providers/* | backend/providers/*.py | BUG | new finding |
| confidence_score type/scale divergence | state.py:50 vs state.py:65 | CONCERN | BUG-010 contributor |
| citations reducer no dedup | state.py:49, :70 | CONCERN | BUG-017 (workaround in emitter) |
| retrieved_chunks reducer contradicts node | state.py:61 | CONCERN | latent |
| recursion_limit=100 | chat.py:167 | CONCERN | masks BUG-010 |
| AsyncSqliteSaver no pruning | main.py:176-182 | CONCERN | FR-005 candidate |
| Circuit breaker single-consumer | nodes.py:102-144 | CONCERN | BUG-018 likely |
| interrupt resume path | nodes.py:344 | CONCERN | spec-21 style |
| add_conditional_edges exhaustiveness | conversation_graph.py:70-78, research_graph.py:173 | PASS |  |
| RetryPolicy on nodes | conversation_graph.py, research_graph.py:48 | PASS |  |
| Tenacity retries on Qdrant | qdrant_client.py:100,131,164,329,449,508 | PASS |  |
| add_messages, _merge_dicts, _merge_sets | state.py:45, :52, :62 | PASS |  |

---

## Unresolved / Flagged for Follow-up

- **Ollama ChatOllama tool-schema round-trip**: Context7 returned examples but no version-pinned schema for qwen2.5. Canonical URL: https://python.langchain.com/docs/integrations/chat/ollama/. Verify in A5/A6 with a real 2-tool-call turn.
- **Send() wall-clock vs serial-sum**: Needs A1 hardware data to determine whether fan-out is actually parallel at the execution layer.
- **Meta-reasoning efficacy**: Un-instrumented; re-measure after A5 fix.
- **`validate_citations` O(n×m) cost**: Measure via spec-14 stage timings before picking as FR-005 candidate.

## BUG-010 Root-Cause Hypothesis (for A5)

**scoring math** — specifically, `aggregate_answers` (`backend/agent/nodes.py:423`) feeds a list of plain dicts `[{"relevance_score": ...}]` to `compute_confidence`, which delegates to `_signal_confidence` (`backend/agent/confidence.py:107`) — a function that uses *attribute* access (`c.rerank_score`, `c.dense_score`). Result is `scored = []` → dense-fallback path → eventually returns 0. The emission site (`chat.py:248`) is correct; it truncates an already-zero int.

## FR-005 Top-1 Latency Contributor Hypothesis (for A6)

**`verify_groundedness` second LLM call** (`backend/agent/nodes.py:467-553`). Adds a full model round-trip on every chat turn, uses `method="json_mode"` (broken for thinking models — returns `None` silently), and is un-gated. Secondary candidate: **`validate_citations`** (`nodes.py:569-665`) with potentially O(citations × chunks) cross-encoder calls depending on alignment-threshold miss rate.

---

*End of framework-audit.md*
