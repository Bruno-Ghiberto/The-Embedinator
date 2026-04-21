# Spec 10: Provider Architecture — Implementation Complete

## Status: COMPLETE — 34/34 tasks, 977 tests passing, 0 regressions

## Waves Executed
- Wave 1 (A1 backend-architect, Opus): T003-T007 — base.py + sqlite_db.py foundation
- Wave 2 (A2+A3 parallel, Sonnet): T008-T010 — ollama embed model param + cloud retry/429
- Wave 3 (A4 python-expert, Sonnet): T011-T025 — registry factory, chat.py wiring, health, models, embedder
- Wave 4 (A5 quality-engineer, Sonnet): T026-T034 — 31 new tests + final gate

## Key Changes
- `ProviderRateLimitError` in base.py; FastAPI handler returns HTTP 429
- `EmbeddingProvider.embed()/embed_single()` gain `model: str | None = None`
- `OllamaEmbeddingProvider` uses `effective_model = model or self.model`
- Cloud providers: `_call_with_retry()` on generate() + generate_stream(); 429 → ProviderRateLimitError
- `ProviderRegistry.get_active_langchain_model(db) → BaseChatModel` (ChatOllama/ChatOpenAI/ChatAnthropic)
- `chat.py` config dict: `{"configurable": {"thread_id", "llm", "tools"}}` + provider_name in trace
- `GET /api/providers/health` with asyncio.gather() concurrent checks
- `GET /api/models/llm` enriched with cloud provider models when key stored
- `BatchEmbedder` accepts `embedding_provider: EmbeddingProvider` via constructor injection
- `query_traces.provider_name TEXT` column (idempotent migration)
- `langchain-ollama`, `langchain-openai`, `langchain-anthropic` added to requirements.txt

## Bug Found and Fixed
- `upsert_provider()` did INSERT OR REPLACE without deactivating other providers
- Multiple rows had is_active=1; get_active_provider() returned wrong provider
- Fix: `UPDATE providers SET is_active = 0 WHERE name != ?` before INSERT

## Test Results
- 977 passed (946 baseline + 31 new)
- 39 pre-existing failures (33 failed + 6 errors) — unchanged
- 9 xpassed (6 pre-existing + 3 T031 tests now passing after upsert fix)
