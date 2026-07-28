# BUG-035: Health endpoint hangs ~18s on qdrant TCP stall — no per-probe sub-timeout

- **Severity**: MAJOR
- **Layer**: Backend
- **Discovered**: 2026-06-10T22:13:34Z in Phase 1 (P1-S3)
- **Phase scenario**: P1-S3
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Ensure stack is healthy
2. Run `docker pause embedinator-qdrant`
3. Run `curl -m 4 localhost:8000/api/health` repeatedly
4. Observe: requests return empty/timeout for ~15-20s (two consecutive 4s curl timeouts at 22:08:47 and 22:08:56) before fast 503 responses begin after circuit breaker opens at 22:08:58

## Expected
`GET /api/health` responds with degraded status within the polling interval (~3s) when any downstream service is unavailable; per-service probes have individual sub-timeouts that prevent the endpoint from blocking callers.

## Actual
`GET /api/health` → `QdrantStorage.health_check()` → `qdrant_client.get_collections()` blocks on TCP for ~8-10s per request; health surface returned nothing for ~18s (22:08:47–22:09:05) across two consecutive curl timeouts until the circuit breaker accumulated `failure_count=5` and opened (`circuit_qdrant_opened` at 22:08:58); impatient clients receive pure timeouts, patient browser clients receive a delayed 503.

## Artifacts
- Screenshot: null
- Log excerpt: logs/P1-S3-health-poll.log (gitignored)
- Trace: null

## Root-cause hypothesis
The qdrant client `get_collections()` call inside the health-check path uses the default connection timeout rather than a short probe-specific timeout (e.g., 1-2s); adding a per-probe `asyncio.wait_for()` wrapper or configuring the client's timeout for health checks would bound the hang to one polling interval.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.1-defer
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/127
- **Rationale**: Once BUG-034/038 treat any non-200 or timeout as degraded, this reduces to a probe-latency/resilience issue that no longer produces a user-visible false state.

## Notes
Reporter: log-analyst. Additional log: logs/P1-S3-backend-circuit-breaker.log. Circuit breaker open total ~65s vs 30s Constitution cooldown target (medium confidence — config check pending; see candidate finding to be registered separately). This hang is the upstream cause of BUG-034's silent-lie window — the banner cannot report degradation until the backend itself produces a response.
