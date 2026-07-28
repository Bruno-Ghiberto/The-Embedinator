# BUG-100: Retrieval fallback message conflates search-failure with empty-result

- **Severity**: MINOR
- **Layer**: Backend
- **Discovered**: 2026-07-10T15:29:14Z in Phase 5 (P5-S4)
- **Phase scenario**: P5-S4
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Trigger a retrieval error that results in an empty `retrieved_chunks` list (e.g. BUG-098's embedder/dimension mismatch).
2. Observe the fallback message: "I could not find any relevant information to answer: '...'. The indexed documents may not cover this topic."
3. Note the true cause was a search error, not an absence of relevant documents.

## Expected
The fallback message should distinguish "search returned genuinely no results" from "search failed/errored," and should not blame the documents when the real cause is a system fault.

## Actual
`fallback_response()` branches only on the count of retrieved chunks; when it is 0, it emits the same hardcoded "documents may not cover this topic" message regardless of whether the chunks list is empty because nothing matched or because the search errored and was swallowed upstream.

## Artifacts
- Screenshot: null
- Log excerpt: logs/BUG-100-fallback-message-conflation.log (gitignored)
- Trace: null

## Root-cause hypothesis
`fallback_response()` (`research_nodes.py:743-791`) branches only on `chunk_count = len(state["retrieved_chunks"])` (`:754`). When the count is 0 it emits the hardcoded literal (`:766-768`): "I could not find any relevant information to answer: '...'. The indexed documents may not cover this topic." But `retrieved_chunks` is empty whether the search returned nothing OR the search ERRORED and the exception was swallowed upstream (`research_nodes.py:265` `agent_tool_call_failed`, `:272` `agent_tool_call_failed_after_retry` — both `except Exception` blocks that log and return empty rather than re-raising). The function has no signal for WHY the list is empty, and unconditionally blames the documents.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: TBD
- **GitHub issue**: TBD
- **Rationale**: TBD

## Notes
In P5-S4 the true cause was an embedder/dimension mismatch (BUG-098); the user was told their documents may not cover the topic. That is a misdiagnosis that could prompt destructive remediation — a user may delete or re-ingest documents that are actually fine.

Severity MINOR: no data loss or corruption occurs from the message itself; it is a diagnostic-accuracy defect on the failure path. Flagged: the misdiagnosis points the user at the wrong fix. Same family as BUG-094 (provider_health collapses distinct causes into one signal) — a recurring "the system cannot tell you WHY it failed" pattern. Fix: distinguish empty-result from swallowed-error before composing the message.

Dedup-check performed: distinct from BUG-084 (raw scaffolding leak — an internal marker) and from BUG-094 (a different endpoint/handler). New.
