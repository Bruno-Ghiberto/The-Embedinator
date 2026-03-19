# The-Embedinator Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-03-10

## Active Technologies
- Python 3.14+ + LangGraph >=1.0.10, LangChain >=1.2.10, FastAPI >=0.135, Pydantic >=2.12, aiosqlite >=0.21, langgraph-checkpoint-sqlite >=2.0 (002-conversation-graph)
- SQLite WAL mode (existing `data/embedinator.db`), separate checkpoint DB (`data/checkpoints.db`), Qdrant (existing) (002-conversation-graph)
- Python 3.14+ + LangGraph >= 1.0.10, LangChain >= 1.2.10, Qdrant Client >= 1.17.0, sentence-transformers >= 5.2.3, tenacity >= 9.0, structlog >= 24.0 (003-research-graph)
- Qdrant (hybrid dense+BM25 vector search), SQLite WAL mode (parent chunks via `backend/storage/sqlite_db.py`) (003-research-graph)
- Python 3.14+ + LangGraph >= 1.0.10, LangChain >= 1.2.10, sentence-transformers >= 5.2.3, structlog >= 24.0, tenacity >= 9.0 (004-meta-reasoning)
- SQLite WAL mode (existing), Qdrant (existing) — no new storage for this feature (004-meta-reasoning)
- Python 3.14+ + LangGraph >= 1.0.10, LangChain >= 1.2.10, sentence-transformers >= 5.2.3, tenacity >= 9.0, Pydantic >= 2.12 (001-accuracy-robustness)
- SQLite WAL mode (existing `data/embedinator.db`); Qdrant (existing) — no new storage for this feature (001-accuracy-robustness)
- Python 3.14+ (pipeline orchestrator) + Rust 1.93.1 (ingestion worker binary) + FastAPI >= 0.135, Pydantic v2 >= 2.12, aiosqlite >= 0.21, httpx >= 0.28, tenacity >= 9.0, structlog >= 24.0 (Python); serde 1, serde_json 1, pulldown-cmark 0.12, pdf-extract 0.8, clap 4, regex 1 (Rust) (006-ingestion-pipeline)
- SQLite WAL mode (`data/embedinator.db`) for documents/jobs/parent chunks + Qdrant for child chunk vectors (006-ingestion-pipeline)
- Python 3.14+ + aiosqlite (>=0.21), qdrant-client (>=1.17.0), cryptography (>=44.0), tenacity (>=9.0) (007-storage-architecture)
- SQLite WAL mode (embedinator.db) + Qdrant (external Docker container) (007-storage-architecture)
- Python 3.14+, TypeScript 5.7 (frontend consumer, not in this spec) + FastAPI >= 0.135, Pydantic v2 >= 2.12, aiosqlite >= 0.21, cryptography >= 44.0, httpx >= 0.28, structlog >= 24.0, LangGraph >= 1.0.10 (008-api-reference)
- SQLite WAL mode (`data/embedinator.db`) via spec-07 `SQLiteDB`; Qdrant via spec-07 `QdrantStorage`; in-memory rate limit counters (per-IP, sliding window) (008-api-reference)
- TypeScript 5.7, Node.js LTS + Next.js 16, React 19, Tailwind CSS v4, SWR v2, recharts v2, react-dropzone v14, Radix UI (tooltip, dialog, select), React Hook Form, vitest v3 + React Testing Library v16, Playwright v1.50 (009-next-frontend)
- N/A — data from FastAPI backend via REST/NDJSON (`spec-08-api`) (009-next-frontend)
- Python 3.14+ + FastAPI >= 0.135, httpx >= 0.28, cryptography >= 44.0, aiosqlite >= 0.21, (010-provider-architecture)
- SQLite WAL mode (`data/embedinator.db`) — `query_traces` table gains `provider_name TEXT` column via `ALTER TABLE ... ADD COLUMN` (010-provider-architecture)
- Python 3.14+ + `inspect` (stdlib), `typing` (stdlib), `dataclasses` (stdlib), `abc` (stdlib), `pydantic` >= 2.12 (for `BaseModel`/`BaseSettings` assertions), `pytest` (test runner) (011-component-interfaces)
- N/A — contract tests introspect signatures, they do not access databases or services (011-component-interfaces)
- Python 3.14+ + FastAPI >= 0.135, Pydantic v2 >= 2.12, pytest (testing only) (012-error-handling)
- N/A — no database schema changes (012-error-handling)
- Python 3.14+ + FastAPI >=0.135, structlog >=24.0, re (stdlib), Pydantic v2 >=2.12 (013-security-hardening)
- SQLite WAL mode (`data/embedinator.db`) — existing, no schema changes (013-security-hardening)
- Python 3.14+ + LangGraph >= 1.0.10, FastAPI >= 0.135, aiosqlite >= 0.21, structlog >= 24.0 (014-performance-budgets)
- SQLite WAL mode (`data/embedinator.db`) — schema migration adds `stage_timings_json TEXT` column to `query_traces` via idempotent `ALTER TABLE` (014-performance-budgets)
- Python 3.14+ (backend), TypeScript 5.7 (frontend) + structlog >= 24.0 (contextvars, JSONRenderer), FastAPI >= 0.135, recharts 2 (frontend charts), SWR 2 (data fetching) — all already installed (015-observability)
- SQLite WAL mode (`data/embedinator.db`) — existing `query_traces` table with 15 columns, no schema changes (015-observability)
- Python 3.14+ (backend tests); TypeScript 5.7 (frontend tests — out of scope, already passing) + pytest >= 8.0, pytest-asyncio >= 0.24, pytest-cov >= 6.0, httpx >= 0.28 — all already installed (016-testing-strategy)
- In-memory SQLite (`:memory:`) for all unit tests; real Qdrant on `localhost:6333` for `@pytest.mark.require_docker` tests (016-testing-strategy)
- Python 3.14+, TypeScript 5.7, Rust 1.93 + pydantic-settings, Docker Compose v2, Make, Rust toolchain (017-infra-setup)
- SQLite WAL mode (`data/embedinator.db`), Qdrant, named Docker volumes (017-infra-setup)

- Python 3.14+, TypeScript 5.7, Rust 1.93.1 (Phase 2 ingestion worker) + FastAPI >= 0.135, LangGraph >= 1.0.10, LangChain >= 1.2.10, Qdrant Client >= 1.17.0, sentence-transformers >= 5.2.3, Pydantic v2 >= 2.12, aiosqlite >= 0.21, cryptography (Fernet) >= 44.0, structlog >= 24.0, tenacity >= 9.0 | Next.js 16, React 19, Tailwind CSS 4, SWR 2, recharts 2 (001-vision-arch)

## Project Structure

```text
backend/
  agent/
    conversation_graph.py  # StateGraph definition + compile (Layer 1)
    research_graph.py      # ResearchGraph builder (Layer 2)
    research_nodes.py      # 6 research node functions (orchestrator, tools_node, etc.)
    research_edges.py      # 2 research edge functions (should_continue_loop, route_after_compress_check)
    nodes.py               # 11 conversation node function implementations
    edges.py               # 3 conditional edge functions (ConversationGraph)
    state.py               # ConversationState, ResearchState TypedDicts
    schemas.py             # Pydantic models (ChatRequest, Citation, RetrievedChunk, etc.)
    prompts.py             # Prompt constants for all nodes
    confidence.py          # 5-signal confidence scoring (R8) + legacy backward compat
    tools.py               # 6 research tools via closure-based factory (R6)
  retrieval/
    searcher.py            # HybridSearcher: Qdrant dense+BM25 with circuit breaker (C1)
    reranker.py            # CrossEncoder reranking via model.rank() (R5)
    score_normalizer.py    # Per-collection min-max score normalization
  storage/
    parent_store.py        # SQLite parent chunk reader
  api/
    chat.py                # NDJSON streaming endpoint via ConversationGraph
  config.py                # Pydantic Settings
  main.py                  # App factory + lifespan (DB, Qdrant, checkpointer, research graph)
data/
  embedinator.db           # Main SQLite database (WAL mode)
  checkpoints.db           # LangGraph checkpoint storage (auto-created)
tests/
  mocks.py                 # Mock ResearchGraph + simple chat graph
  unit/
    test_research_nodes.py       # Research node unit tests
    test_research_edges.py       # Research edge unit tests
    test_research_confidence.py  # 5-signal confidence tests
    test_research_tools.py       # Tool factory tests
    test_hybrid_searcher.py      # HybridSearcher + ScoreNormalizer tests
  integration/
    test_research_graph.py       # Full graph compilation + execution tests
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.14+, TypeScript 5.7, Rust 1.93.1 (Phase 2 ingestion worker): Follow standard conventions

## Recent Changes
- 017-infra-setup: Added Python 3.14+, TypeScript 5.7, Rust 1.93 + pydantic-settings, Docker Compose v2, Make, Rust toolchain
- 016-testing-strategy: Added Python 3.14+ (backend tests); TypeScript 5.7 (frontend tests — out of scope, already passing) + pytest >= 8.0, pytest-asyncio >= 0.24, pytest-cov >= 6.0, httpx >= 0.28 — all already installed
- 015-observability: Added Python 3.14+ (backend), TypeScript 5.7 (frontend) + structlog >= 24.0 (contextvars, JSONRenderer), FastAPI >= 0.135, recharts 2 (frontend charts), SWR 2 (data fetching) — all already installed


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **The-Embedinator** (4955 symbols, 10163 relationships, 160 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` — find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` — see all callers, callees, and process participation
3. `READ gitnexus://repo/The-Embedinator/process/{processName}` — trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` — see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool | When to use | Command |
|------|-------------|---------|
| `query` | Find code by concept | `gitnexus_query({query: "auth validation"})` |
| `context` | 360-degree view of one symbol | `gitnexus_context({name: "validateUser"})` |
| `impact` | Blast radius before editing | `gitnexus_impact({target: "X", direction: "upstream"})` |
| `detect_changes` | Pre-commit scope check | `gitnexus_detect_changes({scope: "staged"})` |
| `rename` | Safe multi-file rename | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher` | Custom graph queries | `gitnexus_cypher({query: "MATCH ..."})` |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK — direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED — indirect deps | Should test |
| d=3 | MAY NEED TESTING — transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/The-Embedinator/context` | Codebase overview, check index freshness |
| `gitnexus://repo/The-Embedinator/clusters` | All functional areas |
| `gitnexus://repo/The-Embedinator/processes` | All execution flows |
| `gitnexus://repo/The-Embedinator/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## CLI

- Re-index: `npx gitnexus analyze`
- Check freshness: `npx gitnexus status`
- Generate docs: `npx gitnexus wiki`

<!-- gitnexus:end -->
