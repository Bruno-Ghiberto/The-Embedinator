# BUG-036: Misleading degradation message — "Vector database is starting up." shown while backend reports "Qdrant circuit breaker is open"

- **Severity**: MAJOR
- **Layer**: Frontend
- **Discovered**: 2026-06-10T22:10:48Z in Phase 1 (P1-S3)
- **Phase scenario**: P1-S3
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Run `docker pause embedinator-qdrant` and wait ≥15s for the circuit breaker to open
2. Observe the dashboard banner — it shows "Vector database is starting up."
3. Run `curl localhost:8000/api/health` — observe `error_message: "Qdrant circuit breaker is open"`

## Expected
The UI degradation banner accurately reflects the backend error state; a circuit-breaker open condition (outage/cooldown requiring potential operator intervention) is communicated as an error, not as a benign startup in progress.

## Actual
The frontend maps the circuit-breaker error string to the generic startup message "Vector database is starting up.", causing users to wait passively for a "startup" that is actually an outage or cooldown state that may require operator action.

## Artifacts
- Screenshot: screenshots/P1-S3-during-pause.png (gitignored)
- Log excerpt: logs/P1-S3-health-poll.log (gitignored)
- Trace: null

## Root-cause hypothesis
The frontend status component maps all non-healthy qdrant states to a single startup message string rather than branching on the specific `error_message` content from the health response; a state machine or message-map keyed on the backend error string would allow accurate messaging (e.g., "Vector database is unavailable — retrying" for CB-open vs. "Vector database is starting" for actual first-boot).

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: TBD
- **GitHub issue**: TBD
- **Rationale**: TBD

## Notes
Reporters: frontend-inspector + Pilot. Additional artifact: screenshots/P1-S3-vector-db-banner-during-pause.png (Pilot capture). Cross-reference: BUG-034 (silent health-lie window — separate issue, precedes this message appearing). Root cause source-confirmed: frontend/components/StatusBanner.tsx:18 — `if (qdrant?.status === "error") return "Vector database is starting up.";` — single string for ALL qdrant error states, no distinction between genuine startup and circuit-breaker-open failure.
