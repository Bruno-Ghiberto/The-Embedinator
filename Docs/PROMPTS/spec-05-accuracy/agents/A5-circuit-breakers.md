# Agent: A5-circuit-breakers

**subagent_type**: python-expert | **Model**: Opus 4.6 | **Wave**: 3

## Mission

Implement circuit breakers for both external services (Qdrant vector store and LLM inference service) and error response handling. This involves three areas of work:

1. **QdrantClientWrapper** (`backend/storage/qdrant_client.py`): Standardize the existing rudimentary circuit breaker into a full Closed -> Open -> HalfOpen -> Closed state machine with cooldown, plus add Tenacity retry decorators.
2. **Inference service** (`backend/agent/nodes.py`): Add module-level circuit breaker state and functions for LLM call sites.
3. **Error handling** (`backend/api/chat.py`): Catch `CircuitOpenError` and emit informative NDJSON error frames.

## Context Files (Read FIRST)

1. `Docs/PROMPTS/spec-05-accuracy/05-implement.md` -- code specs (authoritative reference for all CB implementations)
2. `backend/storage/qdrant_client.py` -- existing `QdrantClientWrapper` class (lines 13-104). Has rudimentary CB (`_circuit_open`, `_failure_count`, `_max_failures`) but MISSING `_last_failure_time` and `_cooldown_secs`. Current CB in `search()` method uses backoff-sleep, NOT proper half-open.
3. `backend/retrieval/searcher.py` -- `HybridSearcher._check_circuit`, `_record_success`, `_record_failure` (lines 47-63) -- the spec-03 reference pattern. Note: this is the SIMPLER version without half-open. Spec-05 extends the pattern with half-open + cooldown for QdrantClientWrapper.
4. `backend/agent/nodes.py` -- add inference CB state + functions as module-level code
5. `backend/api/chat.py` -- update error handling in `generate()` function (lines 44-169)
6. `backend/errors.py` -- check if `CircuitOpenError` exists; add if missing
7. `backend/config.py` -- `settings.circuit_breaker_failure_threshold` (5), `settings.circuit_breaker_cooldown_secs` (30), `settings.retry_max_attempts` (3), `settings.retry_backoff_initial_secs` (1.0)
8. `specs/005-accuracy-robustness/spec.md` -- US6 acceptance scenarios
9. `specs/005-accuracy-robustness/adrs/adr-001-consecutive-count-circuit-breaker.md` -- consecutive-count pattern justification

## Assigned Tasks

### QdrantClientWrapper Circuit Breaker (T027-T031)

- T027: [P] Add circuit breaker state fields to `QdrantClientWrapper.__init__` in `backend/storage/qdrant_client.py`: `self._last_failure_time: float | None = None`, `self._cooldown_secs: int = settings.circuit_breaker_cooldown_secs`. Update `self._max_failures` to read from `settings.circuit_breaker_failure_threshold`.
- T028: Implement `_check_circuit(self) -> None` in `QdrantClientWrapper`: if `_circuit_open` and `time.monotonic() - _last_failure_time < _cooldown_secs` -> raise `CircuitOpenError`; if `_circuit_open` and cooldown elapsed -> set `_circuit_open = False` (half-open probe)
- T029: Implement `_record_success(self)` and `_record_failure(self)` in `QdrantClientWrapper`: success resets `_failure_count = 0` and `_circuit_open = False`; failure increments `_failure_count`, records `_last_failure_time = time.monotonic()`, sets `_circuit_open = True` when `_failure_count >= _max_failures`
- T030: Wrap `search`, `upsert`, `ensure_collection`, `health_check` public methods with `self._check_circuit()` guard at start and `self._record_success()` / `self._record_failure()` calls in try/except. Replace the existing inline CB logic in `search()` and `health_check()`.
- T031: Add Tenacity `@retry` decorator to `search`, `upsert`, `ensure_collection`: `stop=stop_after_attempt(3)`, `wait=wait_exponential(multiplier=1, min=1, max=10) + wait_random(0, 1)`, `reraise=True`. Ensure `_record_failure` is called only on FINAL failure, not on each retry attempt. Pattern: separate the retried inner call from the outer CB wrapper.

### QdrantClientWrapper Tests (T032-T034)

- T032: Add unit tests for `QdrantClientWrapper` circuit breaker state machine in `tests/unit/test_accuracy_nodes.py`: 4 consecutive failures -> circuit remains closed; 5 consecutive failures -> circuit opens; open circuit rejects immediately with `CircuitOpenError` without calling Qdrant; 30s cooldown elapsed -> one probe request allowed through; probe success -> circuit closes and `_failure_count` resets; probe failure -> circuit reopens
- T033: Add unit tests for Tenacity retry behavior on `QdrantClientWrapper` in `tests/unit/test_accuracy_nodes.py`: call succeeds on 2nd attempt -> 1 retry; call fails 3 times -> reraises after 3rd; `CircuitOpenError` is NOT retried
- T034: Run US6 (Qdrant side) unit tests: `zsh scripts/run-tests-external.sh -n spec05-us6-qdrant --no-cov tests/unit/test_accuracy_nodes.py` -- poll `cat Docs/Tests/spec05-us6-qdrant.status` until PASSED

### Inference Service Circuit Breaker (T044-T045)

- T044: Add module-level inference circuit breaker state to `backend/agent/nodes.py`: `_inf_circuit_open: bool = False`, `_inf_failure_count: int = 0`, `_inf_last_failure_time: float | None = None` -- implement `_check_inference_circuit()`, `_record_inference_success()`, `_record_inference_failure()` functions following the same consecutive-count + half-open/cooldown pattern as `QdrantClientWrapper`
- T045: Add unit tests for inference service circuit breaker in `tests/unit/test_accuracy_nodes.py`: 5 consecutive LLM failures -> circuit opens; open circuit raises `CircuitOpenError` without calling LLM; cooldown elapsed -> probe request allowed; probe success -> circuit closes; verify `_check_inference_circuit` raises `CircuitOpenError` consistent with Qdrant CB pattern

### Error Response Handling (T046-T047)

- T046: Add `CircuitOpenError` and LLM-unavailable error handling to `backend/api/chat.py` streaming generator: catch `CircuitOpenError` (from either inference or Qdrant circuit) BEFORE the generic `except Exception` and emit `{"type": "error", "message": "A required service is temporarily unavailable. Please try again in a few seconds.", "code": "circuit_open"}` as NDJSON error frame; update the existing generic `except Exception` to emit `{"type": "error", "message": "Unable to process your request. Please retry.", "code": "service_unavailable"}`
- T047: Run full US6 unit tests: `zsh scripts/run-tests-external.sh -n spec05-us6 --no-cov tests/unit/test_accuracy_nodes.py` -- poll `cat Docs/Tests/spec05-us6.status` until PASSED

## Files to Create/Modify

- MODIFY: `backend/storage/qdrant_client.py` (standardize CB, add retry, add half-open/cooldown)
- MODIFY: `backend/agent/nodes.py` (add inference CB module-level state and functions)
- MODIFY: `backend/api/chat.py` (add CircuitOpenError catch + error frame emission)
- MODIFY: `backend/errors.py` (add `CircuitOpenError` if missing)
- MODIFY: `tests/unit/test_accuracy_nodes.py` (fill in `TestCircuitBreaker` test class)

## Key Patterns

### Circuit Breaker State Machine (ADR-001)

```
Closed ──(N consecutive failures)──> Open
Open   ──(cooldown elapsed)────────> HalfOpen (allow 1 probe)
HalfOpen ──(probe succeeds)────────> Closed (reset count)
HalfOpen ──(probe fails)──────────> Open (re-record failure time)
```

All three instances (HybridSearcher, QdrantClientWrapper, inference nodes) use consecutive-count, NOT time-windowed counting. See ADR-001.

### QdrantClientWrapper Refactoring

The existing `search()` method has inline CB logic (lines 66-70) that does backoff-sleep when circuit is open. **REPLACE** this with the standardized `_check_circuit()` / `_record_success()` / `_record_failure()` pattern. Similarly, `health_check()` has inline CB logic (lines 40-47) that should be replaced.

### Tenacity Retry + CB Separation

The retry decorator and circuit breaker must be layered correctly:
```python
# OUTER: circuit breaker check + recording
async def search(self, ...):
    self._check_circuit()  # raises CircuitOpenError if open
    try:
        result = await self._search_inner(...)  # inner has @retry
        self._record_success()
        return result
    except Exception:
        self._record_failure()
        raise

# INNER: retried operation
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10) + wait_random(0, 1),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def _search_inner(self, collection_name, query_vector, limit):
    # actual Qdrant call
    ...
```

This ensures `_record_failure` is called only ONCE after all retries are exhausted, not on each individual retry.

### CircuitOpenError

Add to `backend/errors.py` (if not already present):
```python
class CircuitOpenError(EmbeddinatorError):
    """Raised when a circuit breaker is open -- service unavailable."""
```

### Inference CB in nodes.py

Module-level globals + functions. The `_check_inference_circuit()` is called inside `verify_groundedness` (by A2) and can be called in `rewrite_query` and other LLM-calling nodes. Place the CB code BEFORE the node functions in the file (after imports).

### chat.py Error Handling

The `CircuitOpenError` catch MUST come BEFORE the generic `except Exception`. Both are inside the `try:` block of the `generate()` inner function (around line 96).

## CRITICAL: Shared Files

- **nodes.py**: A2, A3, A4 from Wave 2 modified different functions. You add module-level CB state and functions at the TOP of the file (after imports, before node functions). Do NOT touch `verify_groundedness`, `validate_citations`, `rewrite_query`, `TIER_PARAMS`, or their helpers.
- **chat.py**: A6 (running in parallel) modifies the metadata frame section. You modify the error handling section. These are different parts of the `generate()` function. Do NOT touch the metadata frame code around line 149.

## Constraints

- NEVER run pytest inside Claude Code. Use: `zsh scripts/run-tests-external.sh -n <name> <target>`
- NEVER modify `searcher.py` (HybridSearcher CB is left as-is from spec-03)
- NEVER modify `schemas.py`, `state.py`, `config.py`, `confidence.py`, or `conversation_graph.py`
- NEVER touch node function bodies added by A2/A3/A4
- `import time` must be at the top of both `nodes.py` and `qdrant_client.py`
- `from tenacity import retry, stop_after_attempt, wait_exponential, wait_random, retry_if_exception_type` in `qdrant_client.py`
- Use `monkeypatch` for settings overrides in tests
- For testing CB timing, use `monkeypatch` to set `_last_failure_time` to a time in the past (e.g., `time.monotonic() - 31` for cooldown-elapsed)
- Do NOT use `asyncio.sleep()` in CB logic -- cooldown is checked via `time.monotonic()` comparison

## Checkpoint

All three circuit breaker instances functional. `CircuitOpenError` defined. Error frames emitted in chat.py. Running the following succeeds:
```bash
python -c "from backend.errors import CircuitOpenError; print('CircuitOpenError OK')"
python -c "from backend.storage.qdrant_client import QdrantClientWrapper; q = QdrantClientWrapper('x', 0); print('CB:', hasattr(q, '_check_circuit'), hasattr(q, '_last_failure_time'))"
python -c "from backend.agent.nodes import _check_inference_circuit, _record_inference_success, _record_inference_failure; print('inference CB OK')"
ruff check backend/storage/qdrant_client.py backend/agent/nodes.py backend/api/chat.py backend/errors.py
```
