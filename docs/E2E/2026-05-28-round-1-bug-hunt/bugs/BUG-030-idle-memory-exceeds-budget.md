# BUG-030: Backend idle RSS 610.8 MiB exceeds the SC-005 600 MB budget on every boot

- **Severity**: MINOR
- **Layer**: Backend
- **Discovered**: 2026-06-10T21:46:49Z in Phase 1 (P1-S1)
- **Phase scenario**: P1-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Perform a cold start (`docker compose up -d`)
2. Read backend startup logs — observe `{"estimated_total_model_mb":700,"budget_target_mb":600,"note":"SC-005...","level":"warning"}`
3. Run `docker stats --no-stream` — observe backend container RSS ≈ 610.8 MiB at idle

## Expected
Backend idle RSS is ≤600 MB per SC-005; no SC-005 budget warning in startup logs.

## Actual
Backend idle RSS is ~610.8 MiB (~1.8% over budget); SC-005 budget warning fires in every cold-start log sequence.

## Artifacts
- Screenshot: null
- Log excerpt: logs/P1-S1-startup-warnings.log (gitignored)
- Trace: null

## Root-cause hypothesis
The loaded model stack (cross-encoder reranker + embedding model) plus FastAPI/LangGraph runtime exceeds the 600 MB SC-005 baseline; the budget was likely set before the current model combination was finalized.

## Triage (filled in Phase 8 for MAJOR+)

## Notes
Reporter: log-analyst. Formal SC-005 breach + persistent startup log noise. System operates normally above budget — no crash or functional degradation observed.
