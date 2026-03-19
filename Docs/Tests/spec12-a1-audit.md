# Spec 12: Error Handling — Wave 1 Audit Report

**Date**: 2026-03-17
**Auditor**: team-lead (A1 wave)
**Branch**: 012-error-handling

---

## T001 — backend/errors.py: Exception Hierarchy

**Verified**: 11 classes (1 base + 10 subclasses), all extend `EmbeddinatorError` directly.

```
EmbeddinatorError(Exception)        # base, no __init__ override
  |- QdrantConnectionError          # Failed to connect to or communicate with Qdrant
  |- OllamaConnectionError          # Failed to connect to or communicate with Ollama
  |- SQLiteError                    # SQLite operation failed
  |- LLMCallError                   # LLM inference call failed
  |- EmbeddingError                 # Embedding generation failed
  |- IngestionError                 # Document ingestion pipeline failed
  |- SessionLoadError               # Failed to load session from SQLite
  |- StructuredOutputParseError     # Failed to parse structured output from LLM
  |- RerankerError                  # Cross-encoder reranking failed
  |- CircuitOpenError               # Raised when a circuit breaker is open
```

**Match 12-plan.md**: ✓ EXACT MATCH

---

## T002 — backend/providers/base.py: ProviderRateLimitError

**Verified**:
- Extends `Exception` directly (NOT `EmbeddinatorError`) ✓
- Has `self.provider: str` attribute ✓
- `__init__(self, provider: str)` with `super().__init__(f"Rate limit exceeded for provider: {provider}")` ✓

**Match 12-plan.md**: ✓ EXACT MATCH

---

## T003 — backend/agent/schemas.py: ErrorDetail and ErrorResponse

**Verified**:
- `ErrorDetail(BaseModel)`: fields `code: str`, `message: str`, `details: dict = {}` ✓
- `ErrorResponse(BaseModel)`: field `error: ErrorDetail` ✓
- `ErrorResponse` has NO `trace_id` field ✓ (trace_id is added as plain dict key in handlers)

**Match 12-plan.md**: ✓ EXACT MATCH

---

## T004 — backend/config.py: Settings Fields

**Verified all 8 required fields**:
- `circuit_breaker_failure_threshold: int = 5` ✓
- `circuit_breaker_cooldown_secs: int = 30` ✓
- `retry_max_attempts: int = 3` ✓ (dead config — not wired to tenacity)
- `retry_backoff_initial_secs: float = 1.0` ✓ (dead config — not wired to tenacity)
- `rate_limit_chat_per_minute: int = 30` ✓
- `rate_limit_ingest_per_minute: int = 10` ✓
- `rate_limit_provider_keys_per_minute: int = 5` ✓
- `rate_limit_general_per_minute: int = 120` ✓

**Match 12-plan.md**: ✓ EXACT MATCH

---

## T005 — backend/main.py: create_app() Handler State

**Verified**:
- (a) `ProviderRateLimitError` handler at lines 174–179 returns WRONG format: `{"type": "error", "message": str(exc), "code": "rate_limit"}` ✓ (this is what we need to fix)
- (b) NO `EmbeddinatorError` handler exists ✓ (needs to be added)
- (c) NO `QdrantConnectionError` handler exists ✓ (needs to be added)
- (d) NO `OllamaConnectionError` handler exists ✓ (needs to be added)

**Match 12-plan.md**: ✓ EXACT MATCH — all 4 handler changes confirmed needed

---

## T006 — backend/middleware.py: RateLimitMiddleware

**Verified**: `RateLimitMiddleware.dispatch()` returns `JSONResponse(status_code=429)` with:
- `{"error": {"code": "RATE_LIMIT_EXCEEDED", "message": "...", "details": {"retry_after_seconds": 60}}, "trace_id": trace_id}` ✓
- `headers={"Retry-After": "60"}` ✓

**Match 12-plan.md**: ✓ EXACT MATCH

---

## T007 — backend/api/chat.py: Stream Error Codes

**Verified**: Three stream error codes present in source:
- `"NO_COLLECTIONS"` at line 67 ✓
- `"CIRCUIT_OPEN"` at line 211 ✓
- `"SERVICE_UNAVAILABLE"` at line 219 ✓

**Match 12-plan.md**: ✓ EXACT MATCH — do NOT touch chat.py

---

## T008 — backend/storage/qdrant_client.py: Retry Decorators

**Verified**: `@retry` decorator on all `_*_with_retry` methods:
- `stop=stop_after_attempt(3)` ✓
- `wait=wait_exponential(multiplier=1, min=1, max=10) + wait_random(0, 1)` ✓
- `reraise=True` ✓

Methods confirmed: `_ensure_collection_with_retry`, `_search_with_retry`, `_upsert_with_retry`, `_create_collection_with_retry`, `_batch_upsert_with_retry`, `_search_hybrid_with_retry`

**Match 12-plan.md**: ✓ EXACT MATCH

---

## Summary

| Task | File | Finding | Status |
|------|------|---------|--------|
| T001 | backend/errors.py | 11 classes, 10 subclasses, all direct | ✓ PASS |
| T002 | backend/providers/base.py | Extends Exception, provider attr | ✓ PASS |
| T003 | backend/agent/schemas.py | ErrorDetail/ErrorResponse correct | ✓ PASS |
| T004 | backend/config.py | All 8 config fields present | ✓ PASS |
| T005 | backend/main.py | Old handler + 3 missing handlers | ✓ PASS |
| T006 | backend/middleware.py | Nested envelope + Retry-After | ✓ PASS |
| T007 | backend/api/chat.py | 3 stream codes present | ✓ PASS |
| T008 | backend/storage/qdrant_client.py | stop_after_attempt(3) on all _*_with_retry | ✓ PASS |

No discrepancies from 12-plan.md. All assumptions verified. Wave 2 may proceed.

Gate status: PASS
