# BUG-116: No log/event surface — only query traces; ingestion & breaker events hidden

- **Severity**: MINOR
- **Layer**: Frontend
- **Discovered**: 2026-07-11T20:20:00Z in Phase 6 (P6-S4)
- **Phase scenario**: P6-S4
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Navigate Chat / Collections / Settings / Observability.
2. Look for any raw log or event surface.
3. Observe: the full Observability page renders only System Health / Query Analytics / Metrics Trends / Query Traces / Collection Statistics — no log or event surface exists anywhere.

## Expected
Per playbook P6-S4 (Constitution IV): a log surface where a non-technical reader can understand recent operation flow.

## Actual
Runtime visibility is query-scoped traces only; no operation/event/error log surface exists. `/api/metrics` returns `circuit_breakers` + `active_ingestion_jobs`, but the UI never renders them; ingestion/provider/circuit-breaker events live only in container stdout.

## Artifacts
- Screenshot: screenshots/P6-S3-query-analytics-charts.png (gitignored)
- Log excerpt: null
- Trace: null

## Root-cause hypothesis
No log-viewer route/component exists; the observability page renders no event/breaker/active-job panels despite that data already being fetched.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: TBD
- **GitHub issue**: TBD
- **Rationale**: TBD

## Notes
Related: BUG-117 (same P6-S4 non-technical-readability mandate, different surface), BUG-114 (Metrics Trends readability gap, same panel family).
