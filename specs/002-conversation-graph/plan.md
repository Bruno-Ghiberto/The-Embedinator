# Implementation Plan: ConversationGraph — Agent Layer 1

**Branch**: `002-conversation-graph` | **Date**: 2026-03-10 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-conversation-graph/spec.md`

## Summary

Implement the ConversationGraph as a LangGraph `StateGraph` — the outermost layer of the three-layer agent architecture. It replaces the current direct RAG pipeline in `chat.py` with a graph-based orchestrator that handles intent classification, query decomposition, parallel sub-question dispatch via `Send()`, answer aggregation, history compression, and NDJSON streaming. Phase 2 features (groundedness verification, citation validation) are present as stub pass-through nodes.

## Technical Context

**Language/Version**: Python 3.14+
**Primary Dependencies**: LangGraph >=1.0.10, LangChain >=1.2.10, FastAPI >=0.135, Pydantic >=2.12, aiosqlite >=0.21, langgraph-checkpoint-sqlite >=2.0
**Storage**: SQLite WAL mode (existing `data/embedinator.db`), separate checkpoint DB (`data/checkpoints.db`), Qdrant (existing)
**Testing**: pytest with pytest-cov (>=80% backend line coverage)
**Target Platform**: Linux server (Docker Compose, 4 services)
**Project Type**: Web service — backend agent layer
**Performance Goals**: First token <1s (SC-004), full answer <5s (simple) / <15s (complex)
**Constraints**: 1–5 concurrent users, local-first (no mandatory outbound calls), no auth
**Scale/Scope**: Single-user self-hosted tool, 20+ exchange conversations (SC-008)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Notes |
|---|-----------|--------|-------|
| I | Local-First Privacy | **PASS** | All LLM calls go through existing provider registry (Ollama default, cloud opt-in). No new outbound dependencies. |
| II | Three-Layer Agent Architecture | **PASS** | ConversationGraph is Layer 1. ResearchGraph (Layer 2) is dispatched via `Send()`. MetaReasoningGraph (Layer 3) scaffold deferred to spec-04. |
| III | Retrieval Pipeline Integrity | **PASS** | No changes to retrieval pipeline. Existing `retrieve_passages()`, hybrid search, and cross-encoder reranking are invoked by ResearchGraph, not ConversationGraph. |
| IV | Observability from Day One | **PASS** | `query_trace` recording preserved in chat.py refactor. Confidence score (0–100 int, evidence-based) included in every NDJSON metadata frame. |
| V | Secure by Design | **PASS** | No new API keys or credentials. Existing Fernet encryption, parameterized SQL, rate limits, CORS all unchanged. structlog trace IDs preserved. |
| VI | NDJSON Streaming Contract | **PASS** | All streaming uses `{"type":"chunk","text":"..."}` + `{"type":"metadata",...}` format with `application/x-ndjson`. No SSE. |
| VII | Simplicity by Default | **PASS** | SQLite remains sole relational DB. Checkpoint DB is a second SQLite file (not a new service). No new Docker services. `langgraph-checkpoint-sqlite` is the only new package. |

All 7 gates pass. No violations to justify.

## Project Structure

### Documentation (this feature)

```text
specs/002-conversation-graph/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── chat-api.md      # Chat endpoint contract
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
  agent/
    conversation_graph.py    # NEW — StateGraph definition, node wiring, edge wiring
    nodes.py                 # NEW — All node function implementations
    edges.py                 # NEW — All conditional edge functions
    prompts.py               # EXTEND — Add intent/rewrite/format/summarize prompts
    state.py                 # EXTEND — Add `intent` field to ConversationState
    schemas.py               # EXISTING — Reuse QueryAnalysis, Citation, SubAnswer, etc.
    retrieval.py             # EXISTING — Reuse retrieve_passages()
    citations.py             # EXISTING — Reuse build_citations(), format_passages_for_prompt()
    confidence.py            # EXISTING — Reuse compute_confidence()
    answer_generator.py      # EXISTING — Reuse generate_answer_stream()
    tools.py                 # EXISTING — LangChain tool definitions
  api/
    chat.py                  # REFACTOR — Invoke ConversationGraph instead of direct pipeline
  main.py                    # EXTEND — Add checkpointer to lifespan

frontend/                    # NO CHANGES for this spec

tests/
  unit/
    test_nodes.py            # NEW — Unit tests for all node functions
    test_edges.py            # NEW — Unit tests for edge functions
  integration/
    test_conversation_graph.py  # NEW — Graph execution tests
```

**Structure Decision**: Web application (backend + frontend). This spec only modifies backend. Frontend is unchanged — the NDJSON streaming contract is preserved.

## Phase 0: Research

See [research.md](research.md) for full findings. Summary of decisions:

| Research Item | Decision | Rationale |
|---------------|----------|-----------|
| LangGraph checkpointer | `AsyncSqliteSaver` from `langgraph-checkpoint-sqlite` | Production-grade, async, separate DB file, auto-creates tables |
| Token counting | `count_tokens_approximately` from `langchain_core` | Zero new deps, works across all providers, ~80-90% accuracy sufficient for 75% threshold |
| Context window sizes | Static `MODEL_CONTEXT_WINDOWS` dict | Simple, no runtime queries, safe 32K default for unknown models |
| ResearchGraph stub | Mock returning fixed `SubAnswer` | Enables full graph testing before spec-03 is implemented |

## Phase 1: Design

### Data Model

See [data-model.md](data-model.md) for entity definitions, field types, relationships, and state transitions.

### Contracts

See [contracts/chat-api.md](contracts/chat-api.md) for the refactored chat API contract.

### Quickstart

See [quickstart.md](quickstart.md) for development setup instructions.

## Agent Team Strategy (Claude Code)

Implementation is parallelized using Claude Code agents with worktree isolation, organized in 5 sequential waves.

### Wave 1: Scaffold (Sequential — ~15 min)

**Single agent**: Extend `state.py` (add `intent` field), add all new prompt constants to `prompts.py`, create `edges.py` with routing functions.

### Wave 2: Node Implementations (4 Parallel Agents — ~45 min)

| Agent | Isolation | Nodes | Key Dependencies |
|-------|-----------|-------|-----------------|
| A | worktree | `init_session`, `summarize_history` | state.py, aiosqlite, langchain_core.messages.utils |
| B | worktree | `classify_intent`, `rewrite_query` | state.py, prompts.py, schemas.py (QueryAnalysis) |
| C | worktree | `fan_out`, `aggregate_answers`, `format_response` | state.py, schemas.py, citations.py, confidence.py |
| D | worktree | `request_clarification`, `handle_collection_mgmt` (stub), `verify_groundedness` (stub), `validate_citations` (stub) | state.py, schemas.py, langgraph.types |

All node functions are stateless and pure — no shared file conflicts.

### Wave 3: Integration (Sequential — ~30 min)

**Single agent**: Wire all nodes into `conversation_graph.py`, create mock ResearchGraph, verify graph compiles.

### Wave 4: API Refactor (Sequential — ~30 min)

**Single agent**: Refactor `chat.py` to invoke ConversationGraph, add checkpointer to lifespan, implement NDJSON streaming with `stream_mode="messages"`.

### Wave 5: Tests (2 Parallel Agents — ~45 min)

| Agent | Isolation | Scope |
|-------|-----------|-------|
| E | worktree | Unit tests: all nodes, all edges (mock LLM, DB, reranker) |
| F | worktree | Integration tests: graph execution, interrupt/resume, NDJSON format |

## Complexity Tracking

No constitution violations. No complexity justifications needed.
