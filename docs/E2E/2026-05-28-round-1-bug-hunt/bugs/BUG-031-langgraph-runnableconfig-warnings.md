# BUG-031: LangGraph RunnableConfig type-annotation UserWarnings ×6 on every cold start

- **Severity**: MINOR
- **Layer**: Backend
- **Discovered**: 2026-06-10T21:46:49Z in Phase 1 (P1-S1)
- **Phase scenario**: P1-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Perform a cold start (`docker compose up -d`)
2. Read backend startup logs
3. Observe 6× `UserWarning: RunnableConfig` type-annotation warnings from graph compilation at `backend/agent/research_graph.py` lines 49, 52, 54, 55 and `backend/agent/conversation_graph.py` lines 53, 54, 62

## Expected
Backend starts cleanly with no UserWarning output from LangGraph graph compilation.

## Actual
Six RunnableConfig type-annotation UserWarnings are emitted at graph compilation during every cold start; non-functional today but represents a forward-compatibility risk on LangGraph version upgrades.

## Artifacts
- Screenshot: null
- Log excerpt: logs/P1-S1-startup-warnings.log (gitignored)
- Trace: null

## Root-cause hypothesis
The graph node functions use `RunnableConfig` as a type annotation in a pattern that a newer LangGraph version deprecated; the warnings indicate the annotation style will be removed or change behaviour in a future LangGraph release.

## Triage (filled in Phase 8 for MAJOR+)

## Notes
Reporter: log-analyst. Affected files and lines: `backend/agent/research_graph.py` (L49, L52, L54, L55) and `backend/agent/conversation_graph.py` (L53, L54, L62).
