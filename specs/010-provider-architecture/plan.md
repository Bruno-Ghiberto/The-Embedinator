# Implementation Plan: Provider Architecture

**Branch**: `010-provider-architecture` | **Date**: 2026-03-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/010-provider-architecture/spec.md`

## Summary

Extend the existing provider scaffolding (spec-08) to make all seven stub items fully operational:
add model-agnostic embedding signatures, retry-once on transient cloud errors with 429 surfacing,
schema migration adding `provider_name` to `query_traces`, and wire `ProviderRegistry` into agent
nodes, `BatchEmbedder`, and `chat.py`. All providers already exist as httpx-based classes; spec-10
extends them rather than replacing them.

## Technical Context

**Language/Version**: Python 3.14+
**Primary Dependencies**: FastAPI >= 0.135, httpx >= 0.28, cryptography >= 44.0, aiosqlite >= 0.21,
structlog >= 24.0, tenacity >= 9.0, LangGraph >= 1.0.10, langchain-ollama, langchain-openai, langchain-anthropic (for `get_active_langchain_model()`)
**Storage**: SQLite WAL mode (`data/embedinator.db`) — `query_traces` table gains `provider_name TEXT` column via `ALTER TABLE ... ADD COLUMN`
**Testing**: pytest via `zsh scripts/run-tests-external.sh -n <name> <target>` ONLY — never run pytest inside Claude Code
**Target Platform**: Linux server, Docker Compose (4 services: qdrant, ollama, backend, frontend)
**Project Type**: web-service (backend extension)
**Performance Goals**: Health checks < 5s; encryption overhead < 1ms; model-agnostic embed adds 0 latency (optional param, default None)
**Constraints**: No new service added; SQLite WAL only; no LangChain in provider layer; httpx direct
**Scale/Scope**: 1–5 concurrent users; 7 distinct code changes across 8 existing files + 1 new test file

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Assessment |
|-----------|--------|------------|
| I. Local-First Privacy | ✅ PASS | Ollama is default provider (FR-002, FR-004). Cloud providers strictly opt-in via API key. Fallback to Ollama when cloud unavailable (FR-015). Zero mandatory outbound calls. |
| II. Three-Layer Agent Architecture | ✅ PASS | Step 5 wires `ProviderRegistry.get_active_llm(db)` into `nodes.py` without restructuring the ConversationGraph/ResearchGraph/MetaReasoningGraph layers. |
| III. Retrieval Pipeline Integrity | ✅ PASS | Embedding provider interface change is additive (optional `model` param, backward-compatible). Pipeline (parent/child chunking, BM25+dense, cross-encoder) is untouched. |
| IV. Observability from Day One | ✅ PASS | FR-019 adds `provider_name` to `query_traces`. Every `POST /api/chat` already writes a trace; spec-10 extends that record with provider attribution. |
| V. Secure by Design | ✅ PASS | Fernet encryption already in `KeyManager`. FR-007–FR-011 enforce key never in logs/responses. `app.state.key_manager = None` on missing env var (no fallback plaintext). |
| VI. NDJSON Streaming Contract | ✅ PASS | `chat.py` NDJSON contract is unchanged. `provider_name` is persisted to DB, not streamed. |
| VII. Simplicity by Default | ✅ PASS | No new services. No new top-level dependencies (httpx and cryptography already in requirements.txt). `ALTER TABLE ... ADD COLUMN` over copy-create-drop. |

**Gate result: ALL PASS — no violations. Proceed to Phase 0.**

## Project Structure

### Documentation (this feature)

```text
specs/010-provider-architecture/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── provider-contract.md
│   └── schema-migration-contract.md
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
  providers/
    base.py             # LLMProvider ABC, EmbeddingProvider ABC  [EXISTS — extend: model param]
    registry.py         # ProviderRegistry active-provider model  [EXISTS — add get_active_langchain_model()]
    ollama.py           # OllamaLLMProvider, OllamaEmbeddingProvider  [EXISTS — extend: model param]
    openrouter.py       # OpenRouterLLMProvider  [EXISTS — extend: retry + 429]
    openai.py           # OpenAILLMProvider  [EXISTS — extend: retry + 429]
    anthropic.py        # AnthropicLLMProvider  [EXISTS — extend: retry + 429]
    key_manager.py      # KeyManager: Fernet encrypt/decrypt  [EXISTS — no changes]
  storage/
    sqlite_db.py        # SQLiteDB — add provider_name to query_traces  [EXTEND]
  ingestion/
    embedder.py         # BatchEmbedder — wire get_embedding_provider()  [EXTEND]
  agent/
    nodes.py            # LangGraph nodes  [UNTOUCHED — LLM injected via config["configurable"]["llm"]]
  api/
    chat.py             # Resolve + pass provider_name to create_query_trace  [EXTEND]
    models.py           # Enrich with cloud provider models when keys present  [EXTEND]

tests/
  unit/
    test_providers.py           # [EXTEND: retry, 429, model-agnostic param]
    test_providers_router.py    # [EXTEND: enriched model listing]
  integration/
    test_providers_integration.py  # [NEW: end-to-end registry wiring tests]
```

**Structure Decision**: Single backend project (Option 1). No frontend changes needed — spec-09 ProviderHub/ModelSelector already consume the existing API contract; new model entries are additive.

## Complexity Tracking

> No constitution violations detected — this section is intentionally empty.
