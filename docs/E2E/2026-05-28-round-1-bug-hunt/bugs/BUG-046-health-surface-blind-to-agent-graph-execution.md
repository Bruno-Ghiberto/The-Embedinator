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
- **Decision**: TBD
- **GitHub issue**: TBD
- **Rationale**: TBD

## Notes
Extends the phase-1 silent-health-lie family — cross-reference BUG-026, BUG-034 (distinct gap: honest about infra, blind to wiring).
