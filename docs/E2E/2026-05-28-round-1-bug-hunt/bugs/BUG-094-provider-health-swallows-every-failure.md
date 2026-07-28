# BUG-094: provider_health swallows every failure into one bool; zero diagnostics logged

- **Severity**: MINOR
- **Layer**: Backend
- **Discovered**: 2026-07-10T14:58:57Z in Phase 5 (P5-S2)
- **Phase scenario**: P5-S2
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Ensure a provider row exists with a stored key.
2. `curl -s http://localhost:8000/api/providers/health`.
3. Observe `{"health":[{"provider":"ollama","reachable":true},{"provider":"openai","reachable":false}]}`.
4. `docker logs embedinator-backend` — the request produced exactly FOUR lines: two `http_request` middleware lines and two uvicorn access lines. ZERO at warning or error level, ZERO mentioning `openai` as a value, ZERO containing "reachable".

## Expected
When a provider health check fails, the backend should log a diagnosable reason (which of several possible causes triggered the failure), correlated to a trace_id.

## Actual
Every possible failure cause collapses into a single unlogged boolean `reachable: false`, with zero diagnostic output.

## Artifacts
- Screenshot: null
- Log excerpt: logs/BUG-094-provider-health-silent-failure.log (gitignored)
- Trace: null

## Root-cause hypothesis
`backend/api/providers.py:114-116` and `:143-145` each wrap the health probe in a bare `except Exception: reachable = False` with NO logging call inside. `provider_health()` therefore collapses at least FIVE distinct failure causes into a single boolean, emitting no diagnostic for any of them:
- `KeyManager.decrypt()` raises `InvalidToken` — corrupt ciphertext, or `EMBEDINATOR_FERNET_KEY` rotated since the key was stored
- the provider returns HTTP 401 — wrong or expired API key
- the network is unreachable — no egress, DNS failure, proxy
- the model in `config_json` does not exist
- `key_manager is None` — `EMBEDINATOR_FERNET_KEY` unset (early return at providers.py:141)

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: TBD
- **GitHub issue**: TBD
- **Rationale**: TBD

## Notes
IMPORTANT — what this cost in this very scenario: P5-S2 asks whether "decryption is transparent" after a restart. The system cannot answer that question about itself. `reachable:false` is emitted identically whether the key decrypted and OpenAI rejected it, or the decrypt itself raised. Team-lead established decryption DID succeed only by evidence gathered from OUTSIDE the product: the health request took 410.6ms and 308.8ms (network round trips, vs. the `if not has_key` early return at providers.py:141 costing under a millisecond), and by round-tripping that exact 140-char ciphertext through Fernet inside the container. The product emitted nothing. A diagnosability defect is not merely inconvenient; it defeats verification.

Compounding: `grep -rn "providers/health" frontend/` returns ZERO hits. Nothing in the UI ever calls this endpoint. It is reachable only by direct API call.

Severity MINOR, and the reasoning matters: no data loss, no corruption, no security exposure. Diagnosability only. It sits in the same dormant-until-BUG-089-is-fixed cluster as BUG-091 and BUG-093 — but note the ollama branch (providers.py:114-116) swallows TODAY, so this is not fully dormant for anyone calling the API directly per spec-08.

Layer BACKEND — root cause and fix surface are both `backend/api/providers.py`. The frontend cannot be at fault for an endpoint it never calls.

Fix surface: providers.py:114-116 and :143-145. Log the caught exception with `logger.warning("provider_health_check_failed", provider=name, error=str(exc))` — noting that `_strip_sensitive_fields` (main.py:40-48) would NOT redact a key appearing inside a free-text `error` string, since it matches by exact field name. Any such fix must not interpolate key material.

Dedup-check performed against all 70 existing bugs: BUG-073 is an uncaught `CancelledError` in chat.py discarding a computed result (different mechanism — an exception NOT caught, vs. here an exception caught and silently discarded; different file; different consequence). BUG-088 is an unbounded in-flight LLM await. BUG-034/038/046 concern the health BANNER and `/api/health`, not `/api/providers/health` — different endpoint, different handler. No existing bug owns "provider_health collapses all failure causes into one unlogged boolean." New.
