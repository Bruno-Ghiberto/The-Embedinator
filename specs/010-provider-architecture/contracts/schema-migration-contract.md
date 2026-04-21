# Contract: Schema Migration — query_traces.provider_name

**Date**: 2026-03-16
**Feature**: Provider Architecture (spec-10)
**Affected table**: `query_traces` in `data/embedinator.db`

---

## Migration Definition

### Column to add

```sql
ALTER TABLE query_traces ADD COLUMN provider_name TEXT;
```

| Attribute | Value |
|-----------|-------|
| Table | `query_traces` |
| Column | `provider_name` |
| Type | `TEXT` |
| Nullable | YES |
| Default | `NULL` |
| Constraint | None (application-layer validation) |

### Execution location

`SQLiteDB.initialize()` in `backend/storage/sqlite_db.py`. Applied once at application startup.

```python
try:
    await db.execute("ALTER TABLE query_traces ADD COLUMN provider_name TEXT")
    await db.commit()
except aiosqlite.OperationalError:
    pass  # column already exists — idempotent on re-deploy
```

### Idempotency

The migration is idempotent: running it on a database that already has the column raises
`aiosqlite.OperationalError: duplicate column name: provider_name`, which is silently caught.
No data is modified on re-run.

---

## Updated INSERT Contract

The `create_query_trace()` method must include `provider_name` in its INSERT statement:

```sql
INSERT INTO query_traces (
    id, session_id, query, collections_searched,
    chunks_retrieved_json, latency_ms, llm_model, embed_model,
    confidence_score, sub_questions_json, reasoning_steps_json,
    strategy_switches_json, meta_reasoning_triggered,
    provider_name   -- NEW
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
```

When `provider_name=None`, the column stores `NULL`.

---

## Valid Values

| Value | Meaning |
|-------|---------|
| `"ollama"` | Request handled by local OllamaLLMProvider |
| `"openrouter"` | Request handled by OpenRouterLLMProvider |
| `"openai"` | Request handled by OpenAILLMProvider |
| `"anthropic"` | Request handled by AnthropicLLMProvider |
| `NULL` | Trace recorded before spec-10 migration (or provider resolution failed) |

---

## Backward Compatibility

- All existing trace rows retain `NULL` in `provider_name` — no data loss.
- The `GET /api/observability/traces` endpoint (spec-15, future) must treat `NULL` as `"unknown"` in display.
- All tests that create `query_traces` rows and don't pass `provider_name` continue to work (column nullable).

---

## Rollback

To rollback (SQLite does not support `DROP COLUMN` in all versions):
1. Option A: Use copy-create-drop pattern to recreate `query_traces` without the column.
2. Option B: Leave the column in place — it is nullable and harmless.
Option B is preferred for a patch rollback. Option A only for major version rollback.
