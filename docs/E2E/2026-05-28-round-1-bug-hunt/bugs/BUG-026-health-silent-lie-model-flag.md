# BUG-026: Aggregate health stays "healthy" and UI green while a model flag is false

> **FIXED 2026-08-05** by spec-31 Batch 1, task 1.2 — commit `96d8704`. The filed root-cause
> hypothesis held. See [Resolution](#resolution) below.

- **Severity**: MAJOR
- **Layer**: Backend
- **Discovered**: 2026-06-10T21:46:49Z in Phase 1 (P1-S1)
- **Fixed**: 2026-08-05 (spec-31 task 1.2, commit `96d8704`)
- **Phase scenario**: P1-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Start the stack (`docker compose up -d`)
2. Run `curl localhost:8000/api/health` — observe outer `"status": "healthy"` while `models["nomic-embed-text"]` is `false`
3. Open `http://localhost:3000` — observe dashboard shows "Backend connected" only, with no model warning

## Expected
When any required model flag is false, the aggregate health status reflects degradation and the UI surfaces a warning to the user so they are not silently operating with a missing capability.

## Actual
`/api/health` returns `"status": "healthy"` and the dashboard displays "Backend connected" with no warning, even when `models["nomic-embed-text"]` is `false`; a genuinely missing required model would be entirely invisible to users end-to-end.

## Artifacts
- Screenshot: screenshots/P1-S2-dashboard-first-paint.png (gitignored)
- Log excerpt: logs/P1-S1-startup-warnings.log (gitignored)
- Trace: null

## Root-cause hypothesis
The health aggregation logic does not incorporate model availability flags into the outer status decision; the frontend status component only checks the outer `status` field and does not render per-model state from the health response payload.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.0-fix
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/124
- **Rationale**: Aggregate status asserts "healthy" and the dashboard says "Backend connected" while a required model is missing — a missing capability is invisible end-to-end.

## Notes
Reporters: frontend-inspector + log-analyst. Related to BUG-025 (false model flag source — tag-suffix mismatch) and BUG-027 (no per-service UI badges). Note: the BUG-025 false flag is a string-match bug; this bug describes the separate architectural issue that any false model flag does not propagate to aggregate health or UI regardless of its cause.

## Resolution

**FIXED** — spec-31 Batch 1, task 1.2. Commit `96d8704`, 4 files, +179/-12.

The filed root-cause hypothesis was correct for the backend half: the aggregation tested only
`status == "error"`, so the `models` flags were computed and then ignored. The aggregate now
degrades when any required model flag is false. The `ollama` service entry deliberately stays
`ok` — the service IS reachable, and marking it `error` would be a second lie in the opposite
direction.

**BUG-025 shipped inside this commit as a prerequisite, not as a second target.** Ollama's
`/api/tags` reports bare-named models as `<name>:latest` while `config.py` sets an untagged
`nomic-embed-text`, so the exact string comparison was permanently false on a *correct* install.
Shipping BUG-026 alone would have made every default stack report itself degraded forever. Both
sides are now normalized; distinct tags still compare as distinct models.

**Compose healthchecks moved to `/api/health/live`** (`docker-compose.yml` and
`cli/internal/engine/embedded/docker-compose.yml`). `/api/health` is a readiness probe and is now
Ollama-gated, so a missing model would have held the backend container unhealthy and stopped
`frontend.depends_on: service_healthy` from ever starting — leaving no UI at all instead of a UI
reporting the degradation. CI had already migrated for this reason (`_ci-core.yml:363-364`).

Two latent defects in `tests/unit/test_health_router.py` were repaired in the same commit:

- Nothing reset the module-level `_first_probe` global, so these tests passed only because
  `tests/integration/` sorts before `tests/unit/` and burned the flag first. Run as its own
  target — which is how the external runner invokes it — the first test received `"starting"`.
- `_mock_httpx_success()` returned a bare `MagicMock` whose `.json()["models"]` iterates empty, so
  five "all healthy" tests ran with BOTH model flags false and still asserted 200 `healthy`. They
  were asserting BUG-026's behaviour under the name of health.

**Scope note.** This closes the backend half of the filed Expected. The UI reflects the
degradation because the status provider renders aggregate status, narrowed to one ~5s cycle by
BUG-034's fix (`c87812e`). Per-service and per-model UI badges remain BUG-027, a separate record.

**Evidence**: run `s31-b1-026-regress`, target `tests/` — 1542 passed, 34 skipped, 48 xfailed,
16 xpassed, 0 failed, exit 0. The delta over the `s31-baseline` 1534 is exactly the 8 new tests.
