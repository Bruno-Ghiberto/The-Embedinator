# Spec 02: ConversationGraph -- Implementation Context

## ORCHESTRATOR: READ THIS FIRST

You are a **coordinator**, NOT an implementer. You MUST NOT write code, create files, or modify source files yourself.

**MANDATORY: MULTI-PANE TMUX LAYOUT**

All agent spawning MUST use multi-pane tmux layout. This is enforced — not optional.

- The session is expected to run inside tmux
- When you spawn multiple agents in parallel (Wave 2, Wave 5), each agent MUST appear in its own visible tmux pane
- Claude Code auto-detects tmux and splits panes for spawned agents — **do NOT suppress or work around this behavior**
- Verify pane splitting occurred before treating a parallel wave as "launched"
- If tmux is not active, abort and instruct the user to start a tmux session before proceeding

**YOUR FIRST ACTION** after reading this file:

1. Read `Docs/PROMPTS/spec-02-conversation-graph/agents/agent-scaffold.md`
2. Spawn the **Agent-Scaffold** immediately using:
   - `subagent_type: "python-expert"`
   - `model: "opus"`
   - Prompt: instruct it to read its instruction file and execute its tasks
3. Wait for Agent-Scaffold to complete and verify Phase 1+2 checkpoint (all stubs importable, `pytest tests/unit/` passes)
4. Then proceed to Wave 2 (spawn 4 agents in parallel with worktree isolation)

**YOUR ONGOING ROLE**:
- Spawn agents per the wave sequence below — never skip ahead
- After each wave, verify the checkpoint criteria from `tasks.md`
- If an agent fails, diagnose via its output and re-spawn or adjust — do NOT take over its work
- Between waves, you may read files to verify state, but you MUST NOT edit source code

---

## What Is Being Built

The ConversationGraph is Layer 1 of the three-layer LangGraph agent architecture. It replaces the current direct RAG pipeline in `backend/api/chat.py` with a `StateGraph`-based orchestrator that handles:

- Session initialization and persistence
- Intent classification (rag_query, collection_mgmt, ambiguous)
- Query decomposition into 1-5 sub-questions with complexity tier classification
- Parallel dispatch to ResearchGraph instances via `Send()`
- Answer aggregation with citation deduplication
- History compression at 75% of model context window
- Clarification interrupts with checkpoint/resume (max 2 rounds)
- NDJSON streaming (`application/x-ndjson`, `stream_mode="messages"`)
- Phase 2 stubs for groundedness verification and citation validation

Until spec-03 is implemented, ResearchGraph is a mock that returns fixed `SubAnswer` data.

## Authoritative References

| Document | Path | Purpose |
|----------|------|---------|
| Spec | `specs/002-conversation-graph/spec.md` | User stories, FRs, acceptance criteria |
| Plan | `specs/002-conversation-graph/plan.md` | Architecture, agent team strategy, code patterns |
| Tasks | `specs/002-conversation-graph/tasks.md` | 52 tasks across 8 phases with dependencies |
| Research | `specs/002-conversation-graph/research.md` | Checkpointer, token counting, streaming decisions |
| Data Model | `specs/002-conversation-graph/data-model.md` | Entity definitions, state transitions |
| Chat API Contract | `specs/002-conversation-graph/contracts/chat-api.md` | NDJSON frame types, error codes |
| Quickstart | `specs/002-conversation-graph/quickstart.md` | Dev setup, test fixtures |

## Technical Decisions (Non-Negotiable)

These decisions are final. Do not deviate.

| Decision | Correct | Wrong (Do NOT Use) |
|----------|---------|---------------------|
| Streaming protocol | NDJSON (`application/x-ndjson`) | SSE (`text/event-stream`) |
| Stream API | `graph.astream(state, stream_mode="messages")` | `graph.astream_events(version="v2")` |
| Interrupt API | `interrupt()` + `Command(resume=...)` from `langgraph.types` | `.interrupt()` method |
| Checkpointer | `AsyncSqliteSaver` from `langgraph.checkpoint.sqlite.aio` | `MemorySaver` (tests only) |
| Token counting | `count_tokens_approximately` from `langchain_core.messages.utils` | `tiktoken` directly |
| Confidence scale | `int` 0-100, evidence-based via `compute_confidence()` | `float` 0.0-1.0, LLM self-assessment |
| Checkpoint DB | Separate file `data/checkpoints.db` | Same DB as `data/embedinator.db` |

## Nodes (11 total)

| Node | Status | Responsibility |
|------|--------|---------------|
| `init_session` | Active | Load session from SQLite, restore messages. On failure: fresh session + log warning |
| `classify_intent` | Active | LLM call to classify as `rag_query`/`collection_mgmt`/`ambiguous`. On failure: default `rag_query` |
| `rewrite_query` | Active | `llm.with_structured_output(QueryAnalysis)`. On parse failure: retry once, then single-question fallback |
| `request_clarification` | Active | `interrupt(clarification_question)`. Resumes via `Command(resume=response)`. Increments `iteration_count` |
| `fan_out` | Active (edge) | Returns `list[Send]` for dynamic dispatch. Falls back to original query if 0 sub-questions |
| `aggregate_answers` | Active | Merge sub_answers, deduplicate citations by `passage_id`, compute confidence via `compute_confidence()` |
| `summarize_history` | Active | Compress messages when tokens > `get_context_budget(model)`. Uses LLM with `SUMMARIZE_HISTORY_SYSTEM` |
| `format_response` | Active | Apply `[N]` citation markers, confidence summary if < 70. Handles `groundedness_result=None` |
| `verify_groundedness` | Phase 2 stub | Returns `{"groundedness_result": None}` immediately |
| `validate_citations` | Phase 2 stub | Returns `{"citations": state["citations"]}` immediately |
| `handle_collection_mgmt` | Out-of-scope stub | Returns "not yet implemented" message, `confidence_score=0` |

## Edges (3 conditional)

| Edge Function | Source Node | Routing Logic |
|---------------|------------|---------------|
| `route_intent` | `classify_intent` | Returns `state["intent"]` as routing key: `rag_query` -> `rewrite_query`, `collection_mgmt` -> `handle_collection_mgmt`, `ambiguous` -> `request_clarification` |
| `should_clarify` | `rewrite_query` | Returns `True` if `query_analysis.is_clear == False` AND `iteration_count < 2`. If `query_analysis is None`: returns `False` |
| `route_fan_out` | `rewrite_query` | Returns `list[Send("research", {...})]` for each sub-question. Falls back to `[original_query]` if empty. Uses `collections_hint or selected_collections` |

## Graph Wiring

```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

def build_conversation_graph(research_graph, checkpointer=None):
    graph = StateGraph(ConversationState)

    # Core nodes
    graph.add_node("init_session", init_session)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("rewrite_query", rewrite_query)
    graph.add_node("request_clarification", request_clarification)
    graph.add_node("research", research_graph)
    graph.add_node("aggregate_answers", aggregate_answers)
    graph.add_node("summarize_history", summarize_history)
    graph.add_node("format_response", format_response)

    # Phase 2 stubs
    graph.add_node("verify_groundedness", verify_groundedness)
    graph.add_node("validate_citations", validate_citations)

    # Out-of-scope stub
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
    graph.add_conditional_edges("rewrite_query", route_fan_out)
    graph.add_edge("research", "aggregate_answers")
    graph.add_edge("aggregate_answers", "verify_groundedness")
    graph.add_edge("verify_groundedness", "validate_citations")
    graph.add_edge("validate_citations", "summarize_history")
    graph.add_edge("summarize_history", "format_response")
    graph.add_edge("format_response", END)

    return graph.compile(checkpointer=checkpointer or MemorySaver())
```

## State Transitions

```
[INIT] -> init_session -> [SESSION_LOADED]
[SESSION_LOADED] -> classify_intent -> [INTENT_CLASSIFIED]
[INTENT_CLASSIFIED] -> route_intent:
  |-- rag_query -> [QUERY_REWRITING]
  |-- collection_mgmt -> [COLLECTION_MGMT] -> [DONE]
  +-- ambiguous -> [CLARIFYING]

[QUERY_REWRITING] -> rewrite_query -> [QUERY_ANALYZED]
[QUERY_ANALYZED] -> should_clarify:
  |-- clear -> [DISPATCHING]
  |-- unclear (iteration_count < 2) -> [CLARIFYING]
  +-- unclear (iteration_count >= 2) -> [DISPATCHING] (best-effort)

[CLARIFYING] -> request_clarification -> interrupt -> [PAUSED]
[PAUSED] -> Command(resume=response) -> [SESSION_LOADED] (re-classify)

[DISPATCHING] -> fan_out -> Send() x N -> [RESEARCHING]
[RESEARCHING] -> ResearchGraph x N -> [AGGREGATING]
[AGGREGATING] -> aggregate_answers -> [VERIFYING]
[VERIFYING] -> verify_groundedness (stub) -> [VALIDATING]
[VALIDATING] -> validate_citations (stub) -> [COMPRESSING]
[COMPRESSING] -> summarize_history -> [FORMATTING]
[FORMATTING] -> format_response -> [DONE]
```

## File Structure

### New Files

| File | Purpose |
|------|---------|
| `backend/agent/conversation_graph.py` | `build_conversation_graph()` factory — StateGraph definition, node/edge wiring, compile |
| `backend/agent/nodes.py` | All 11 node function implementations (stateless, pure) |
| `backend/agent/edges.py` | 3 conditional edge functions: `route_intent`, `should_clarify`, `route_fan_out` |
| `tests/mocks.py` | `build_mock_research_graph()` — compiled StateGraph returning fixed SubAnswer |
| `tests/unit/test_nodes.py` | Unit tests for all node functions |
| `tests/unit/test_edges.py` | Unit tests for all edge functions |
| `tests/integration/test_conversation_graph.py` | Graph execution, interrupt/resume, NDJSON format |

### Modified Files

| File | Changes |
|------|---------|
| `backend/agent/state.py` | Add `intent: str` field to `ConversationState` |
| `backend/agent/prompts.py` | Add 7 new prompt constants: `CLASSIFY_INTENT_SYSTEM`, `CLASSIFY_INTENT_USER`, `REWRITE_QUERY_SYSTEM`, `REWRITE_QUERY_USER`, `VERIFY_GROUNDEDNESS_SYSTEM`, `FORMAT_RESPONSE_SYSTEM`, `SUMMARIZE_HISTORY_SYSTEM` |
| `backend/api/chat.py` | Refactor to invoke ConversationGraph. Replace direct pipeline with `graph.astream(stream_mode="messages")`. NDJSON streaming with interrupt detection |
| `backend/main.py` | Add `AsyncSqliteSaver` checkpointer to lifespan. Store in `app.state.checkpointer` |

## Phase 1 Modules (MUST Reuse)

These modules exist from spec-01. Import and use them directly. Do NOT rewrite.

| Module | Key Exports | Used By |
|--------|-------------|---------|
| `backend/agent/state.py` | `ConversationState`, `ResearchState` | All nodes, edges, graph |
| `backend/agent/schemas.py` | `QueryAnalysis`, `Citation`, `SubAnswer`, `RetrievedChunk`, `GroundednessResult`, `ClaimVerification` | nodes.py (structured output, type hints) |
| `backend/agent/retrieval.py` | `retrieve_passages()` | ResearchGraph (NOT ConversationGraph) |
| `backend/agent/citations.py` | `build_citations()`, `format_passages_for_prompt()` | `aggregate_answers`, `format_response` |
| `backend/agent/confidence.py` | `compute_confidence()` | `aggregate_answers` |
| `backend/agent/answer_generator.py` | `generate_answer_stream()` | ResearchGraph (NOT ConversationGraph) |
| `backend/agent/prompts.py` | `SYSTEM_PROMPT`, `QUERY_ANALYSIS_PROMPT`, `ANSWER_SYNTHESIS_PROMPT` | Existing prompts preserved |
| `backend/config.py` | `Settings` (Pydantic Settings) | `chat.py` for defaults |
| `backend/errors.py` | Custom error hierarchy | Error handling in nodes |

## NDJSON Streaming Pattern

```python
import json
import time
from fastapi.responses import StreamingResponse

async def chat_endpoint(request: ChatRequest):
    graph = get_compiled_graph()
    initial_state = build_initial_state(request)
    config = {"configurable": {"thread_id": request.session_id}}

    async def generate():
        start_time = time.monotonic()

        async for chunk, metadata in graph.astream(
            initial_state,
            stream_mode="messages",
            config=config,
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

### NDJSON Frame Types

| Frame | Schema | When |
|-------|--------|------|
| Chunk | `{"type": "chunk", "text": "..."}` | Each LLM token |
| Clarification | `{"type": "clarification", "question": "..."}` | Graph interrupts for clarification |
| Metadata | `{"type": "metadata", "trace_id": "...", "confidence": 87, "citations": [...], "latency_ms": 1240}` | Final frame after all chunks |
| Error | `{"type": "error", "message": "...", "code": "NO_COLLECTIONS"}` | On failure |

## Clarification Interrupt Pattern

```python
from langgraph.types import interrupt, Command

def request_clarification(state: ConversationState) -> dict:
    clarification = state["query_analysis"].clarification_needed
    user_response = interrupt(clarification)
    return {
        "messages": state["messages"] + [HumanMessage(content=user_response)],
        "iteration_count": state["iteration_count"] + 1,
    }
```

Resume from the client side:

```python
# Client sends a new POST /api/chat with same session_id
# Server detects interrupted state and resumes:
graph.invoke(Command(resume=user_clarification), config)
```

Max 2 clarification rounds. `should_clarify` returns `False` when `iteration_count >= 2`, forcing best-effort processing.

## Fan-Out with Send() Pattern

```python
from langgraph.types import Send

def route_fan_out(state: ConversationState) -> list[Send]:
    sub_questions = state["query_analysis"].sub_questions
    if not sub_questions:
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

## Context Window Management

```python
from langchain_core.messages.utils import count_tokens_approximately

MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    "qwen2.5:7b": 32_768,
    "llama3.1:8b": 131_072,
    "mistral:7b": 32_768,
    "gpt-4o": 131_072,
    "gpt-4o-mini": 131_072,
    "claude-sonnet-4-20250514": 200_000,
}
DEFAULT_CONTEXT_WINDOW = 32_768

def get_context_budget(model_name: str) -> int:
    window = MODEL_CONTEXT_WINDOWS.get(model_name, DEFAULT_CONTEXT_WINDOW)
    return int(window * 0.75)
```

`summarize_history` triggers compression when `count_tokens_approximately(messages) > get_context_budget(model)`.

## Error Handling

| Node | Failure Mode | Recovery |
|------|-------------|----------|
| `init_session` | SQLite read failure | Create fresh session, log warning |
| `classify_intent` | LLM call failure | Default to `"rag_query"` intent |
| `rewrite_query` | Structured output parse failure | Retry once; fall back to single-question mode |
| `fan_out` | No sub-questions | Use original query as sole sub-question |
| `fan_out` | No collections selected | Return error prompting user to select |
| `aggregate_answers` | Some ResearchGraphs failed | Aggregate available, note gaps |
| `verify_groundedness` | LLM call failure (Phase 2) | Skip, set `groundedness_result = None` |
| `validate_citations` | Cross-encoder failure (Phase 2) | Pass citations through unvalidated |
| `summarize_history` | LLM call failure | Keep messages uncompressed |

## Clarification Decisions (from spec clarification session)

1. `handle_collection_mgmt` is OUT OF SCOPE -- stub returns "not implemented" message
2. Max 2 clarification rounds per query; after 2, proceed best-effort as rag_query
3. History compression triggers at 75% of configured model's context window
4. No collections selected -> prompt user to select at least one (error frame `NO_COLLECTIONS`)

## Constitution Principles (must not violate)

| # | Principle | Implication |
|---|-----------|-------------|
| I | Local-First Privacy | All LLM calls via existing ProviderRegistry. No new outbound deps |
| II | Three-Layer Agent Architecture | ConversationGraph is Layer 1. ResearchGraph dispatched via `Send()` |
| III | Retrieval Pipeline Integrity | Retrieval is in ResearchGraph, not ConversationGraph |
| IV | Observability from Day One | `query_trace` preserved. Confidence in every metadata frame |
| V | Secure by Design | No new credentials. Existing security unchanged |
| VI | NDJSON Streaming Contract | `{"type":"chunk","text":"..."}` format. `application/x-ndjson`. No SSE |
| VII | Simplicity by Default | SQLite checkpoint. No new Docker services |

## Agent Team Strategy

Implementation is parallelized across 6 waves using Claude Code subagents with worktree isolation.

### Wave 1: Scaffold (Sequential)
- Single agent creates file shells, extends `state.py`, adds prompts, implements edges, `init_session`
- Tasks: T001-T005 (Setup) + T006-T011 (Foundational non-test tasks)
- BLOCKS all subsequent waves

### Wave 2: Node Implementations (4 Parallel Agents)
- Agent-A: `init_session` implementation, `summarize_history` (T012, T031)
- Agent-B: `classify_intent`, `rewrite_query` (T016, T021)
- Agent-C: `handle_collection_mgmt` stub, `aggregate_answers`, `format_response` (T017, T022, T025)
- Agent-D: `verify_groundedness` stub, `validate_citations` stub, `request_clarification` (T023, T024, T036)
- All work in separate worktrees. No shared file conflicts.

### Wave 3: Integration (Sequential)
- Single agent wires all nodes into `conversation_graph.py`, wires all edges
- Tasks: T018, T026, T033, T037
- Requires all Wave 2 agents complete

### Wave 4: API Refactor (Sequential)
- Single agent refactors `chat.py`, adds NDJSON streaming, checkpointer integration, `main.py` lifespan
- Tasks: T041-T045
- Requires Wave 3 complete

### Wave 5: Tests (2 Parallel Agents)
- Agent-E: All unit tests (T013, T014, T015, T019, T020, T027, T028, T029, T034, T038)
- Agent-F: All integration tests + mock graph (T005, T030, T035, T039, T040, T046, T047)
- Requires Wave 4 complete

### Wave 6: Polish (Sequential)
- Single agent: coverage, NDJSON validation, `source_removed`, quickstart validation, CLAUDE.md update
- Tasks: T048-T052
- Requires Wave 5 complete

## Agent Team Instructions

The orchestrator MUST spawn agents using the instruction files below. Each file contains the agent's role, assigned tasks, file scope, constraints, dependencies, and done criteria.

| Agent | Instruction File | Wave |
|-------|-----------------|------|
| Scaffold | `Docs/PROMPTS/spec-02-conversation-graph/agents/agent-scaffold.md` | 1 |
| Session & History | `Docs/PROMPTS/spec-02-conversation-graph/agents/agent-session-history.md` | 2 |
| Intent & Analysis | `Docs/PROMPTS/spec-02-conversation-graph/agents/agent-intent-analysis.md` | 2 |
| Dispatch & Aggregation | `Docs/PROMPTS/spec-02-conversation-graph/agents/agent-dispatch-aggregation.md` | 2 |
| Interrupt & Stubs | `Docs/PROMPTS/spec-02-conversation-graph/agents/agent-interrupt-stubs.md` | 2 |
| Integration | `Docs/PROMPTS/spec-02-conversation-graph/agents/agent-integration.md` | 3 |
| API | `Docs/PROMPTS/spec-02-conversation-graph/agents/agent-api.md` | 4 |
| Unit Tests | `Docs/PROMPTS/spec-02-conversation-graph/agents/agent-unit-tests.md` | 5 |
| Integration Tests | `Docs/PROMPTS/spec-02-conversation-graph/agents/agent-integration-tests.md` | 5 |
| Polish | `Docs/PROMPTS/spec-02-conversation-graph/agents/agent-polish.md` | 6 |

### Spawning Protocol (Step-by-Step)

**RULE**: You MUST follow this sequence exactly. Do NOT combine waves. Do NOT write code yourself.

**TMUX MULTI-PANE REQUIREMENT**: All parallel agent spawns (Wave 2, Wave 5) MUST result in each agent running in a dedicated tmux pane. Claude Code automatically handles pane splitting when inside a tmux session. This behavior is **required** — every parallel agent must be visible in its own pane for the orchestrator to monitor progress.

**Wave 1** — Spawn immediately after reading this file:
```
Agent(subagent_type="python-expert", model="opus", prompt="Read Docs/PROMPTS/spec-02-conversation-graph/agents/agent-scaffold.md then execute all assigned tasks.")
```
- Wait for completion
- Verify: all stubs importable, `pytest tests/unit/` passes

**Wave 2** — Spawn ALL 4 agents in a SINGLE message (parallel, worktree isolation):
```
Agent(subagent_type="python-expert", model="sonnet", isolation="worktree", prompt="Read Docs/PROMPTS/spec-02-conversation-graph/agents/agent-session-history.md then execute all assigned tasks.")
Agent(subagent_type="python-expert", model="opus",   isolation="worktree", prompt="Read Docs/PROMPTS/spec-02-conversation-graph/agents/agent-intent-analysis.md then execute all assigned tasks.")
Agent(subagent_type="python-expert", model="sonnet", isolation="worktree", prompt="Read Docs/PROMPTS/spec-02-conversation-graph/agents/agent-dispatch-aggregation.md then execute all assigned tasks.")
Agent(subagent_type="python-expert", model="sonnet", isolation="worktree", prompt="Read Docs/PROMPTS/spec-02-conversation-graph/agents/agent-interrupt-stubs.md then execute all assigned tasks.")
```
- Wait for ALL 4 to complete
- Merge worktree changes into main branch
- Verify: all node functions implemented, no import errors

**Wave 3** — Sequential, main branch:
```
Agent(subagent_type="backend-architect", model="opus", prompt="Read Docs/PROMPTS/spec-02-conversation-graph/agents/agent-integration.md then execute all assigned tasks.")
```
- Wait for completion
- Verify: graph compiles, mock ResearchGraph works

**Wave 4** — Sequential, main branch:
```
Agent(subagent_type="backend-architect", model="opus", prompt="Read Docs/PROMPTS/spec-02-conversation-graph/agents/agent-api.md then execute all assigned tasks.")
```
- Wait for completion
- Verify: `POST /api/chat` produces NDJSON output

**Wave 5** — Spawn BOTH agents in a SINGLE message (parallel, worktree isolation):
```
Agent(subagent_type="quality-engineer", model="sonnet", isolation="worktree", prompt="Read Docs/PROMPTS/spec-02-conversation-graph/agents/agent-unit-tests.md then execute all assigned tasks.")
Agent(subagent_type="quality-engineer", model="opus",   isolation="worktree", prompt="Read Docs/PROMPTS/spec-02-conversation-graph/agents/agent-integration-tests.md then execute all assigned tasks.")
```
- Wait for BOTH to complete
- Merge worktree changes
- Verify: `pytest tests/` passes

**Wave 6** — Sequential, main branch:
```
Agent(subagent_type="self-review", model="opus", prompt="Read Docs/PROMPTS/spec-02-conversation-graph/agents/agent-polish.md then execute all assigned tasks.")
```
- Wait for completion
- Verify: coverage >= 80%, all frames match contract, CLAUDE.md updated

### Anti-Drift Rules

- **NEVER** write Python code yourself — that is the agents' job
- **NEVER** create or modify source files — only read them to verify
- **NEVER** skip a wave or start the next wave before the current one's checkpoint passes
- **NEVER** spawn a Wave 2+ agent before Wave 1 is verified complete
- If an agent's output indicates failure, analyze the error and re-spawn the agent with corrective guidance — do NOT fix it yourself
- Your only tools are: spawning agents, reading files for verification, and running the external test script for checkpoint checks

### Test Execution Policy

**NEVER run pytest directly inside Claude Code.** Test output consumes thousands of tokens and is wasteful.

All test execution MUST use the external test runner script:

```zsh
# Launch tests (returns immediately, runs in background):
zsh scripts/run-tests-external.sh -n <run-name> <test-target>

# Poll status (~5 tokens):
cat Docs/Tests/<run-name>.status
# → RUNNING | PASSED | FAILED | ERROR | NO_TESTS

# Read summary when done (~20 lines, ~100 tokens):
cat Docs/Tests/<run-name>.summary

# Debug specific failures only if needed:
grep "FAILED" Docs/Tests/<run-name>.log
grep -A5 "test_specific_name" Docs/Tests/<run-name>.log
```

Examples for checkpoint verification:
```zsh
# Wave 1 checkpoint — verify stubs importable + unit tests pass:
zsh scripts/run-tests-external.sh -n wave1-check tests/unit/

# Wave 5 checkpoint — full test suite:
zsh scripts/run-tests-external.sh -n wave5-full tests/

# Quick import check (this one is OK to run inline, it's 1 line):
python3 -c "from backend.agent.nodes import init_session; print('OK')"
```

Agents themselves MUST also use this script for their test tasks (T013-T015, T019-T020, etc.). Include this instruction when spawning test agents.
