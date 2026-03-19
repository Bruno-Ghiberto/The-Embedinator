# Agent A1: Backend Architect

## Agent: backend-architect | Model: claude-opus-4-5 | Wave: 1

## Role

You are the Wave 1 foundation agent for spec-10. You establish the structural changes that
all other agents depend on: the new exception class, updated abstract method signatures, and
the database schema migration. Wave 2 cannot begin until your work passes the gate check.
Work alone; no parallel agents run during Wave 1.

---

## Assigned Tasks

**T003** — Add `ProviderRateLimitError` to `backend/providers/base.py`

**T004** — Add `model: str | None = None` to `EmbeddingProvider.embed()` in `backend/providers/base.py`

**T005** — Add `model: str | None = None` to `EmbeddingProvider.embed_single()` in `backend/providers/base.py`

**T006** — Add `_migrate_query_traces_columns()` migration method to `SQLiteDB` in
`backend/storage/sqlite_db.py`, called from `_init_schema()` after `_migrate_providers_columns()`

**T007** — Update `SQLiteDB.create_query_trace()` in `backend/storage/sqlite_db.py` to accept
`provider_name: str | None = None` and include it in the INSERT statement and VALUES tuple

---

## File Scope

You touch ONLY these two files:
- `/home/brunoghiberto/Documents/Projects/The-Embedinator/backend/providers/base.py`
- `/home/brunoghiberto/Documents/Projects/The-Embedinator/backend/storage/sqlite_db.py`

Do NOT touch `ollama.py`, `openrouter.py`, `openai.py`, `anthropic.py`, or any other file.

---

## Implementation Notes

### T003 — ProviderRateLimitError

Add this class to `backend/providers/base.py` after the existing imports and before the
`LLMProvider` class definition:

```python
class ProviderRateLimitError(Exception):
    """Raised by cloud providers on HTTP 429 rate limit responses."""

    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(f"Rate limit exceeded for provider: {provider}")
```

### T004 + T005 — EmbeddingProvider signature update

The current `embed()` signature is:
```python
async def embed(self, texts: list[str]) -> list[list[float]]:
```

Add `model: str | None = None` as a second parameter. Same for `embed_single()`.
Update the docstring to note that `model=None` uses `self.model`.
This is a backward-compatible additive change — existing callers pass no `model` and continue
to work unchanged.

### T006 — _migrate_query_traces_columns()

Follow the exact same pattern as the existing `_migrate_providers_columns()` method.
Add a new `_migrate_query_traces_columns()` method to the `SQLiteDB` class, then call it
from `_init_schema()` after the existing `_migrate_providers_columns()` call.

```python
async def _migrate_query_traces_columns(self) -> None:
    """Add provider_name column to query_traces if not present (idempotent)."""
    cursor = await self.db.execute("PRAGMA table_info(query_traces)")
    columns = {row[1] for row in await cursor.fetchall()}
    if "provider_name" not in columns:
        await self.db.execute(
            "ALTER TABLE query_traces ADD COLUMN provider_name TEXT"
        )
    await self.db.commit()
```

In `_init_schema()`, add the call:
```python
await self._migrate_providers_columns()
await self._migrate_query_traces_columns()   # add this line
```

### T007 — create_query_trace() signature

The current signature ends with `meta_reasoning_triggered: bool = False`. Add
`provider_name: str | None = None` BEFORE `meta_reasoning_triggered` (to maintain
backward compatibility with keyword callers — but since it's keyword-only with a default,
position relative to other optional params is acceptable as long as it comes after the
required params). Placing it last is also fine since all callers use keyword args.

Update BOTH:
1. The method signature (add the parameter)
2. The INSERT SQL (add `provider_name` to the column list)
3. The VALUES tuple (add `provider_name` to the corresponding position)

Current INSERT has 14 columns. After T007 it has 15. Maintain column-to-value ordering.

---

## Critical Constraints

- Do NOT add `list_models()` as an abstract method to `LLMProvider` — it does not exist
- Do NOT change `LLMProvider` in any way — only `EmbeddingProvider` gains the model param
- Do NOT change the `KeyManager` class — it is out of scope for Wave 1
- The migration MUST be idempotent — running it twice on an already-migrated DB must silently pass
- Do NOT modify any test files

---

## Testing Rule (MANDATORY)

```
NEVER run pytest directly inside Claude Code. Use ONLY:
  zsh scripts/run-tests-external.sh -n <name> <target>

Poll: cat Docs/Tests/<name>.status     (RUNNING | PASSED | FAILED | ERROR)
Read: cat Docs/Tests/<name>.summary    (~20 lines, token-efficient)
Full: cat Docs/Tests/<name>.log
```

---

## Gate Check

After completing T003-T007, run the Wave 1 gate:

```bash
zsh scripts/run-tests-external.sh -n spec10-gate-wave1 tests/
```

Poll `Docs/Tests/spec10-gate-wave1.status` until `PASSED` or `FAILED`.
If `FAILED`, read the summary and fix regressions before reporting done.
Report 0 new failures vs the spec-09 baseline of 946 passing, 39 known pre-existing.

When the gate passes, notify the Orchestrator that Wave 1 is complete.
