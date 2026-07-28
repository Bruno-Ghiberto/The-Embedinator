# BUG-046: Health surface blind to agent-graph execution path

- **Severity**: MAJOR
- **Layer**: Observability
- **Discovered**: 2026-06-11T12:55:00Z in Phase 2 (P2-S2)
- **Phase scenario**: P2-S2
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. With BUG-045 active (chat 100% failing), curl localhost:8000/api/health → 200 {"status":"healthy", sqlite ok 0.1ms, qdrant ok 0.8ms, ollama ok 5ms}.
2. Observe frontend banner "Backend connected".
3. Inspect health models field: {qwen3:14b: true, nomic-embed-text: false}.

## Expected
Health/readiness reflects core user-facing capability (or degrades), and model checks reference the ACTIVE runtime configuration.

## Actual
Health probes only infra connectivity (SQLite SELECT 1, Qdrant health_check, Ollama /api/tags + static model list); never exercises the agent graph; stays fully "healthy" while every chat fails. It checks the CODE default model (qwen3:14b) instead of the persisted runtime setting (qwen2.5:7b per /api/settings), and reports nomic-embed-text=false without degrading status. The build-time config-injection UserWarning sat in startup logs un-promoted to any health signal.

## Artifacts
- Screenshot: screenshots/BUG-045-chat-error.png (gitignored)
- Log excerpt: logs/BUG-046-health-paradox.txt (gitignored)
- Trace: null

## Root-cause hypothesis
Health surface designed as infra-connectivity check only; no graph-execution or config-injection self-check exists at startup or in readiness.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.1-defer
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/133
- **Rationale**: The record's own framing is decisive — the probe is "honest about infra, blind to wiring"; a deeper graph-execution readiness check is a missing capability, and the false-model-flag half is owned by BUG-026.

## Notes
Extends the phase-1 silent-health-lie family — cross-reference BUG-026, BUG-034 (distinct gap: honest about infra, blind to wiring).

**CORROBORATION 2026-07-28 (P7-S1)**: this record's "honest about infra, blind to wiring" framing confirmed live and at scale. Through a **160s wedged turn** — a request stalled after `agent_intent_classified` with zero forward progress — `GET /api/health` returned **200 OK 21 consecutive times** (14:02:43Z–14:05:14Z) and the container never went unhealthy. The event loop was demonstrably alive and serving health checks while the user's only in-flight request was permanently stuck. Adds a stalled-request dimension to the original finding (which covered a fully-failing chat path): health is green not only when chat is broken, but while a specific request is wedged. Artifact: logs/P7-S1-backend-killboundary.log. No severity change; no new ID.
