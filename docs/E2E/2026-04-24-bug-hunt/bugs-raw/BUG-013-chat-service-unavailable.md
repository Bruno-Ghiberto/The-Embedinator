# BUG-013: Every /api/chat request ends in SERVICE_UNAVAILABLE

- **Severity**: Blocker
- **Layer**: Backend (Reasoning secondary)
- **Discovered**: 2026-04-28 ~17:00 UTC via Live Block Charter 1 BUG-006 fix verification (A3)
- **F/D/P decision**: D (defer to v1.1 / follow-up debug sprint; Live Block budget exhausted; deeper investigation needed beyond the Live Block scope)

## Steps to Reproduce

1. Stack up: 4 services healthy. Backend HEAD includes BUG-002 + BUG-006 fixes (commits 97bbe98 + 7c4203e + 6d8b27a).
2. Issue any /api/chat request with valid `collection_ids`:
   ```
   POST /api/chat
   {"message": "diámetro mínimo NAG-200", "session_id": "any", "collection_ids": ["22923ab5-ea0d-4bea-8ef2-15bf0262674f"]}
   ```
3. Observe NDJSON stream.

## Expected

Stream completes with `{"type": "done", ...}` event after `chunk` and `confidence` events.

## Actual

Stream ends in error event with code `SERVICE_UNAVAILABLE` after the orchestrator→tools→orchestrator pattern. Exception escapes `chat.py`'s `except Exception` handler without logging; root error never surfaces in `docker compose logs backend`.

## Artifacts

- A3's baseline trace `bug006-v1.ndjson` (captured BEFORE BUG-006 fix) shows the IDENTICAL error pattern, exonerating commit 6d8b27a
- Orchestrator's prior end-to-end verify at trace `b95d971d` (15:14 UTC, post-BUG-002-amendment) returned cleanly with `done` event — so the regression appeared between 15:14 and ~17:00 UTC
- File refs (probable):
  - `backend/api/chat.py` — exception handler around `except Exception as e` (ENH-006 / FR-050 area)
  - `backend/agent/research_graph.py` — research → conversation state merge
  - `backend/utils/logging_config.py` (or equivalent) — `cache_logger_on_first_use=True` setting causing chat.py logger to cache before `_configure_logging()` runs

## Root-cause hypothesis

Multiple plausible causes, no single root identified within Live Block budget:

1. **structlog config race**: `cache_logger_on_first_use=True` causes `backend.api.chat` logger to be cached BEFORE `_configure_logging()` runs at startup, so `logger.error("http_chat_stream_error", ...)` calls are silently swallowed. Fix: configure logging earlier in app startup, or remove `cache_logger_on_first_use`.

2. **State-merge issue between research_graph and conversation_graph**: exception fires AFTER `collect_answer` streams its content but before `done`/`citation` events emit, suggesting failure during state merge from the subgraph back to the parent. Could be a Pydantic validation error on a state field that the merge introduces.

3. **Qdrant DNS workaround lost on backend restart**: A3 noted earlier (during BUG-002 first-fix verify at ~15:00 UTC) that the backend container required a manual `/etc/hosts` entry to resolve `qdrant`. That entry won't survive container recreate, so any restart afterwards returns the system to broken state. But A3 also confirmed Qdrant is reachable from inside the container during BUG-013 investigation — so this hypothesis is partially refuted.

4. **Contextvar plumbing from BUG-002 amendment**: the `selected_collections_var` contextvar might not be propagating across asyncio task boundaries within the LangGraph executor. ContextVar.set() inside an async function only affects the current Task; child tasks need explicit context binding (e.g., `asyncio.copy_context()`).

## Causal context / spec-28 implications

- Did NOT regress in commits 97bbe98, 7c4203e, or 6d8b27a — A3 confirmed via baseline trace
- Blocks live verification of BUG-006 fix (~75% citation target unmeasurable while every request fails)
- Blocks RAGAS Wave 3 execution (every Q&A query would fail) — Wave 3 cannot proceed until BUG-013 is fixed
- Investigation outside Live Block scope: needs dedicated debug session with deeper logging (likely temporary `cache_logger_on_first_use=False` to capture the actual error) and step-through across the research → conversation graph state-merge boundary

## Defer rationale (for D decision)

Live Block budget effectively exhausted at 4h+ elapsed; remaining time prioritized for proper close-out (validator, commit, TeamDelete, engram session_summary). BUG-013 surfaces a real production-blocker but needs methodical debugging that cannot fit a F-path patch — would risk an under-investigated fix landing without proper observability. v1.1 spec investigates with a clean slate.
