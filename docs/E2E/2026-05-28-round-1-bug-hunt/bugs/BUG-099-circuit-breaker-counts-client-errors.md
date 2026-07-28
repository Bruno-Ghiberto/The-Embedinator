# BUG-099: Circuit breaker counts Qdrant 4xx as failures; one bad collection degrades all

- **Severity**: MAJOR
- **Layer**: Backend
- **Discovered**: 2026-07-10T15:29:14Z in Phase 5 (P5-S4)
- **Phase scenario**: P5-S4
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Query a collection whose embedder mismatches the request embedder (see BUG-098), producing repeated Qdrant HTTP 400 responses.
2. Observe the `HybridSearcher`'s failure counter increments on each 400, identical to how it would increment on a genuine Qdrant-unavailability error.
3. Confirm the breaker is a single app-wide instance (`app.state.hybrid_searcher`), not scoped per collection.

## Expected
Client-side errors (malformed/incompatible requests) should not count toward an availability-protection circuit breaker; a broken collection should not degrade retrieval for unrelated healthy collections.

## Actual
`HybridSearcher` wraps its Qdrant call in a bare `except Exception` and records ANY exception — including HTTP 400 client errors — as a failure toward the shared circuit breaker. Five such failures against one collection would trip the breaker for the entire app, denying retrieval against every collection for 60 seconds, even though Qdrant itself is healthy.

## Artifacts
- Screenshot: null
- Log excerpt: logs/BUG-099-circuit-breaker-client-error.log (gitignored)
- Trace: null

## Root-cause hypothesis
`HybridSearcher` wraps its Qdrant call in `except Exception` (`searcher.py:216-219`) and calls `_record_failure()` on ANY exception, then raises `QdrantConnectionError`. But the P5-S4 failure was HTTP 400 Bad Request — a CLIENT error (a malformed vector was sent), not a Qdrant-availability failure. Retrying it can never help. Yet it increments the SAME `_failure_count` (`searcher.py:64-70`) whose purpose is to trip when Qdrant is DOWN. Threshold is 5 (`config.py`, `circuit_breaker_failure_threshold`), cooldown 60s (`circuit_breaker_cooldown_secs`). P5-S4 hit exactly 4 — one short. A 5th malformed sub-question would have opened the breaker.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.1-defer
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/161
- **Rationale**: A real cross-collection availability defect, but it needs 5 failures to trigger (P5-S4 reached 4, never tripping), is bounded to a 60s cooldown and self-heals — impact is bounded and was not reproduced.

## Notes
The blast radius is app-wide: `main.py:606` constructs ONE `HybridSearcher` and stores it at `app.state.hybrid_searcher` — a single shared instance for the whole app, not per-collection. `_circuit_open`/`_failure_count` are instance attributes. So 5 malformed queries against ONE broken collection would open the breaker and reject searches against EVERY healthy collection, for the full 60s cooldown — while Qdrant is fine and returning 200s. A client-side input error is allowed to trigger an availability-protection mechanism that then denies service to unrelated healthy data.

Severity MAJOR: a self-inflicted, cross-collection denial of retrieval triggered by querying one mismatched collection. Not CRITICAL only because it is bounded (60s) and self-heals, and requires 5 failures to trigger. Fix: classify exceptions — do not count 4xx client errors toward the availability breaker; and/or scope the breaker per collection.

Dedup-check performed: BUG-098 is the embedder mismatch (correctness); this is the breaker's mishandling of the resulting failures (resilience) — different file, different fix. No existing bug owns "circuit breaker counts client errors / shared-singleton cross-collection degradation." New. Also relevant to Phase 7 (Recovery/State); registered now because it is code-confirmed and reproduced, not deferred.
