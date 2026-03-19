# Implementation Plan: ResearchGraph

**Branch**: `003-research-graph` | **Date**: 2026-03-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-research-graph/spec.md`

## Summary

The ResearchGraph is Layer 2 of the three-layer LangGraph agent architecture. It is a per-sub-question worker that runs an LLM-driven orchestrator loop to search document collections via hybrid retrieval, rerank results with a cross-encoder, deduplicate across iterations, compress context when approaching capacity, and terminate when confidence is sufficient or the search budget is exhausted. It is spawned by ConversationGraph's `route_fan_out()` edge function via `Send("research", payload)` and returns a `SubAnswer` with citations. On budget exhaustion with low confidence, it routes to the MetaReasoningGraph (stub in Phase 1).

## Technical Context

**Language/Version**: Python 3.14+
**Primary Dependencies**: LangGraph >= 1.0.10, LangChain >= 1.2.10, Qdrant Client >= 1.17.0, sentence-transformers >= 5.2.3, tenacity >= 9.0, structlog >= 24.0
**Storage**: Qdrant (hybrid dense+BM25 vector search), SQLite WAL mode (parent chunks via `backend/storage/sqlite_db.py`)
**Testing**: pytest via external runner (`scripts/run-tests-external.sh`) — NEVER inside Claude Code
**Target Platform**: Linux server (Docker Compose: qdrant, ollama, backend, frontend)
**Project Type**: Backend agent component (internal layer, no new API endpoints)
**Performance Goals**: <30s end-to-end research session for typical queries against collections with <100K chunks (SC-008)
**Constraints**: MAX_ITERATIONS=10, MAX_TOOL_CALLS=8, CONFIDENCE_THRESHOLD=0.6, compression at 75% context window
**Scale/Scope**: 1-5 concurrent users, multiple research workers per query (one per sub-question)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Notes |
|---|-----------|--------|-------|
| I | Local-First Privacy | PASS | ResearchGraph uses Ollama by default via provider registry. Cloud providers are opt-in, resolved at query time. No new outbound calls. |
| II | Three-Layer Agent Architecture | PASS | ResearchGraph IS Layer 2. Implements the tool-based retrieval loop with iteration budget. MetaReasoningGraph scaffold wired (stub to fallback in Phase 1). |
| III | Retrieval Pipeline Integrity | PASS | Implements parent/child chunking with breadcrumbs, hybrid dense+BM25 search, cross-encoder reranking (ms-marco-MiniLM-L-6-v2) on top-20 candidates. Deterministic UUID5 for child chunks (existing). |
| IV | Observability from Day One | PASS | FR-017 requires structured logging at all decision points. FR-009 requires confidence from retrieval signals (not LLM self-assessment). Existing trace recording in `POST /api/chat` path preserved. |
| V | Secure by Design | PASS | No new credential storage. Uses existing Fernet-encrypted API keys from provider registry. Parameterized SQL for parent chunk reads. structlog API-key stripping already in place. |
| VI | NDJSON Streaming Contract | N/A | ResearchGraph is an internal component. NDJSON streaming is handled at the ConversationGraph API layer (spec-02). |
| VII | Simplicity by Default | PASS | No new services (stays within 4-service Docker Compose). Uses existing SQLite + Qdrant. New files are focused modules, no premature abstractions. |

**Gate Result**: ALL PASS — proceed to Phase 0.

### Post-Design Re-Check (after Phase 1)

| # | Principle | Status | Design Validation |
|---|-----------|--------|-------------------|
| I | Local-First Privacy | PASS | R6 (tool injection) uses closure pattern with no external calls. Ollama resolved via provider registry. |
| II | Three-Layer Architecture | PASS | R2 confirms Send() pattern delivers ResearchState. MetaReasoning stub wired in graph definition. |
| III | Retrieval Pipeline Integrity | PASS | R4 implements hybrid dense+BM25 via Qdrant prefetch+fusion. R5 confirms ms-marco-MiniLM-L-6-v2 reranking on top-20. |
| IV | Observability from Day One | PASS | R8 defines signal-based confidence (5 weighted signals). FR-017 logging at all decision points. |
| V | Secure by Design | PASS | R6 closure pattern avoids globals. ParentStore uses parameterized SQL. No new credential paths. |
| VI | NDJSON Streaming Contract | N/A | Internal component — no streaming changes. |
| VII | Simplicity by Default | PASS | R6 closures over globals. R8 formula is a weighted average (no ML model). No new services. |

**Post-Design Gate Result**: ALL PASS — proceed to task generation.

## Project Structure

### Documentation (this feature)

```text
specs/003-research-graph/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
  agent/
    research_graph.py        # NEW: StateGraph definition + build_research_graph()
    research_nodes.py        # NEW: 6 node functions (orchestrator, tools_node, etc.)
    research_edges.py        # NEW: 2 edge functions (should_continue_loop, route_after_compress_check)
    tools.py                 # NEW: 6 @tool definitions
    prompts.py               # MODIFY: Add ORCHESTRATOR_SYSTEM, ORCHESTRATOR_USER, COMPRESS_CONTEXT_SYSTEM, COLLECT_ANSWER_SYSTEM
    confidence.py            # MODIFY: Replace placeholder with signal-based scoring
    conversation_graph.py    # MODIFY: Pass real research_graph to build_conversation_graph()
    state.py                 # EXISTS: ResearchState, MetaReasoningState (no changes)
    schemas.py               # EXISTS: RetrievedChunk, ParentChunk, Citation, SubAnswer (no changes)
    nodes.py                 # EXISTS: get_context_budget(), MODEL_CONTEXT_WINDOWS (no changes)
  retrieval/
    __init__.py              # NEW
    searcher.py              # NEW: HybridSearcher (Qdrant hybrid dense+BM25)
    reranker.py              # NEW: Reranker (sentence-transformers CrossEncoder)
    score_normalizer.py      # NEW: Per-collection min-max normalization
  storage/
    parent_store.py          # NEW: ParentStore (SQLite parent chunk reads)

tests/
  unit/
    test_research_nodes.py   # NEW
    test_research_edges.py   # NEW
    test_tools.py            # NEW
    test_retrieval.py        # NEW
    test_confidence.py       # NEW
  integration/
    test_research_graph.py   # NEW
  mocks.py                   # MODIFY: Add build_mock_research_graph()
```

**Structure Decision**: ResearchGraph nodes and edges go in separate files (`research_nodes.py`, `research_edges.py`) to avoid bloating spec-02's `nodes.py`/`edges.py`. The retrieval layer (`backend/retrieval/`) is a new package for Qdrant search and cross-encoder reranking, keeping agent logic separate from retrieval mechanics.

## Existing Code to Build On

These files already exist from specs 01-02 and MUST be used — do NOT recreate:

| File | What Exists | Used For |
|------|-------------|----------|
| `backend/agent/state.py` | `ResearchState(TypedDict)` with all fields | Graph state — use as-is |
| `backend/agent/schemas.py` | `RetrievedChunk`, `ParentChunk`, `Citation`, `SubAnswer` | Tool return types, answer packaging |
| `backend/agent/nodes.py` | `get_context_budget(model_name)` → `int(window * 0.75)`, `MODEL_CONTEXT_WINDOWS` | 75% compression threshold (FR-010) |
| `backend/agent/nodes.py` | structlog import + `logger = structlog.get_logger(__name__)` | Logging pattern (FR-017) |
| `backend/agent/edges.py` | `route_fan_out(state)` with `Send("research", payload)` | How ResearchGraph is spawned (lines 87-101) |
| `backend/agent/conversation_graph.py` | `graph.add_node("research", research_graph)` | Integration point |
| `backend/agent/confidence.py` | `compute_confidence(passages, top_k=5)` (placeholder) | Extend for signal-based scoring (FR-009) |
| `backend/agent/answer_generator.py` | `generate_answer(llm, prompt)` | Answer generation in collect_answer |
| `backend/agent/prompts.py` | 7 existing prompt constants | Add orchestrator prompts alongside |
| `backend/storage/qdrant_client.py` | Qdrant client wrapper | Basis for HybridSearcher |
| `backend/storage/sqlite_db.py` | SQLite connection patterns | Basis for ParentStore |
| `backend/providers/base.py` | `LLMProvider` ABC | Provider resolution in orchestrator |
| `backend/config.py` | `Settings(BaseSettings)` | Configuration constants |
| `backend/errors.py` | Custom error hierarchy | Error types for tools |

## Subagent Team Design

Implementation uses Claude Code subagents organized in 5 waves. Each agent reads its instruction file first (`Docs/PROMPTS/spec-03-research-graph/agents/<name>.md`), then executes assigned tasks.

### Wave 1 — Scaffold (1 agent)

| Agent | subagent_type | Model | Scope |
|-------|---------------|-------|-------|
| agent-scaffold | python-expert | opus | Create all new files with correct stubs and interfaces, add orchestrator prompts to prompts.py, verify all imports |

**Checkpoint**: All new modules importable, stubs have correct type signatures matching `state.py` and `schemas.py`.

### Wave 2 — Core Implementation (3 parallel agents)

| Agent | subagent_type | Model | Scope |
|-------|---------------|-------|-------|
| agent-retrieval | python-expert | opus | `backend/retrieval/` — HybridSearcher, Reranker, ScoreNormalizer full implementations |
| agent-tools | python-expert | opus | `backend/agent/tools.py` — all 6 @tool definitions using retrieval layer interfaces |
| agent-nodes | python-expert | sonnet | `backend/agent/research_nodes.py` + `research_edges.py` — 6 node functions + 2 edge functions |

**Checkpoint**: Each module has full implementations coding against Wave 1 stub interfaces.

### Wave 3 — Integration (1 agent)

| Agent | subagent_type | Model | Scope |
|-------|---------------|-------|-------|
| agent-integration | backend-architect | opus | Wire `research_graph.py`, update `conversation_graph.py`, update `main.py` lifespan, update `tests/mocks.py` |

**Checkpoint**: `build_research_graph()` compiles without error, ConversationGraph uses real research graph.

### Wave 4 — Tests (2 parallel agents)

| Agent | subagent_type | Model | Scope |
|-------|---------------|-------|-------|
| agent-unit-tests | quality-engineer | sonnet | Unit tests for retrieval, tools, nodes, edges, confidence |
| agent-integration-tests | quality-engineer | opus | Integration tests for full research_graph execution flows |

**Checkpoint**: All tests pass via external runner.

### Wave 5 — Polish (1 agent)

| Agent | subagent_type | Model | Scope |
|-------|---------------|-------|-------|
| agent-polish | self-review | opus | Fix broken tests, verify FR-016 (retry) + FR-017 (logging), update CLAUDE.md |

**Checkpoint**: All tests green, CLAUDE.md updated.

### Test Execution Policy

**NEVER run pytest inside Claude Code.** Use:
```bash
zsh scripts/run-tests-external.sh -n <name> <target>
# Output: Docs/Tests/{name}.{status,summary,log}
# Poll: cat Docs/Tests/<name>.status → RUNNING|PASSED|FAILED|ERROR
# Read: cat Docs/Tests/<name>.summary (~20 lines, token-efficient)
```
