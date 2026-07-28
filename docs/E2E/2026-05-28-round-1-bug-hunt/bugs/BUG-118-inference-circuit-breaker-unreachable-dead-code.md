# BUG-118: Inference circuit breaker is unreachable dead code behind a disabled flag

- **Severity**: MAJOR
- **Layer**: Backend
- **Discovered**: 2026-07-28T14:19:03Z in Phase 7 (P7-S1)
- **Phase scenario**: P7-S1
- **BLOCKER-PATCHED**: no

## Steps to Reproduce
1. `rg` the whole of `backend/` for the inference-breaker helpers — exactly three call sites exist: `nodes.py:539` `_check_inference_circuit()`, `nodes.py:545` `_record_inference_success()`, `nodes.py:606` `_record_inference_failure()`. There are no others.
2. Observe all three sit inside `verify_groundedness` (`nodes.py:495-619`).
3. Observe `verify_groundedness` returns early at `nodes.py:509-511` — `if not settings.groundedness_check_enabled: return {...}` — which is BEFORE line 539, so no breaker call is reachable.
4. Confirm the flag is off by default: `config.py:85` `groundedness_check_enabled: bool = False` (spec-26 FR-005 — the check costs a full-context round-trip).
5. Confirm it is off at RUNTIME, not merely by default: the `settings` table row reads `False` and `GET /api/settings` returns `false`.
6. Confirm live: `agent_verify_groundedness_disabled` logged at 14:15:23.780Z and 14:19:03.487Z during this phase's own runs.

## Expected
An inference circuit breaker that exists in the codebase is reachable and actually protects inference calls; or, if it is deliberately inert, that is documented rather than presented as a working safety mechanism.

## Actual
Every inference-breaker call site is behind an early return that always fires under the shipped configuration, so the breaker never executes a single count in production. It is unreachable dead code: the failure counter never increments, the circuit never opens, and no inference call is ever protected by it.

## Artifacts
- Screenshot: null
- Log excerpt: logs/P7-S1-backend-killboundary.log (gitignored) — contains the `agent_verify_groundedness_disabled` emissions at 14:15:23.780Z and 14:19:03.487Z
- Trace: traces/P7-S1-stall-rootcause.txt (gitignored)

## Root-cause hypothesis
HIGH confidence, code-confirmed via exhaustive call-site enumeration (log-analyst, six independently verified links). The breaker was implemented inside `verify_groundedness` rather than at the inference boundary itself, so its reachability is coupled to an unrelated feature flag. When spec-26 FR-005 defaulted `groundedness_check_enabled` to `False` for performance reasons, the breaker was silently disabled as a side effect — nothing in the change would have surfaced that, because nothing downstream depends on the breaker working. Fix surface: move the breaker to the inference call boundary so its lifetime is independent of the groundedness feature flag.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.1-defer
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/168
- **Rationale**: A safety mechanism that never executes is a real structural defect, but practical impact is bounded — nothing downstream depends on it, no user-visible behaviour changes, and no core flow breaks; the same property is why it went unnoticed.

## Notes
Reporter: log-analyst. **NOT a duplicate of BUG-099** — dedup-checked before minting: BUG-099 is the Qdrant/retrieval breaker on the shared `HybridSearcher` instance, which counts the WRONG things (4xx client errors toward an availability breaker). This record is the separate INFERENCE breaker, which counts NOTHING at all because its call sites are unreachable. Different object, different failure state, different fix surface.

Framing worth preserving (team-lead): the system ships two circuit breakers — **one miscounts (BUG-099) and the other never counts at all**.

Honest caveat recorded per log-analyst: practical impact is bounded precisely because nothing downstream consumes the breaker's state. That is what kept it invisible, and it is also why this is filed as a bounded defect rather than an outage risk.
