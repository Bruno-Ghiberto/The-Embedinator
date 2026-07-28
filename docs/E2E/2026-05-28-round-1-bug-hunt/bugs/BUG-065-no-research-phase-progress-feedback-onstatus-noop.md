# BUG-065: No research-phase progress feedback — onStatus no-op hides stage indicator

- **Severity**: MINOR
- **Layer**: Frontend
- **Discovered**: 2026-06-26T19:10:00Z in Phase 3 (P3-S3)
- **Phase scenario**: P3-S3
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Send any question in the chat UI.
2. During the research phase (30s–2min), observe the UI.
3. Inspect the NDJSON stream in DevTools — status events with node names are present.
4. Observe that the UI shows only a static skeleton shimmer with zero progress text at any point.

## Expected
During the research graph phase (orchestrator → retrieve → rerank → synthesize) the UI displays stage progress text via the PipelineStageIndicator component, reflecting the current node name forwarded by backend status events.

## Actual
UI shows only a static skeleton shimmer with zero progress text. Status events arrive in the NDJSON stream but are silently discarded — no stage name is ever rendered.

## Artifacts
- Screenshot: screenshots/BUG-065.png (gitignored)
- Log excerpt: logs/BUG-065.log (gitignored)
- Trace: null

## Root-cause hypothesis
Callback chain severed at useStreamChat.ts:41 `onStatus: () => {}` — discards the node-name string that api.ts:171-172 (`case "status": callbacks.onStatus?.(event.node)`) forwards from backend status events. page.tsx never passes a currentStage prop to ChatPanel (L361-365), so ChatPanel.tsx:211-213 `<PipelineStageIndicator stage={currentStage ?? null} isVisible={!!currentStage} />` always receives undefined → isVisible=false → renders nothing. The component exists and is wired; only the callback chain is severed.

## Triage (filled in Phase 8 for MAJOR+)
<!-- MINOR — triage optional -->

## Notes
Pilot-confirmed observation during P3-S3. Forwarding the node name from onStatus into currentStage state in page.tsx is the minimal fix path. Primary artifact: frontend/hooks/useStreamChat.ts:41; secondary: frontend/app/chat/page.tsx:361-365, frontend/components/ChatPanel.tsx:211-213, frontend/lib/api.ts:171-172. Analyst-correlated HIGH confidence.

**CORROBORATION 2026-07-28 (P7-S1) — ADDED AND THEN WITHDRAWN THE SAME DAY; THIS RECORD STANDS AS ORIGINALLY WRITTEN.** A P7-S1 corroboration was appended here claiming the backend emitted ZERO status events across a 187s stream, i.e. that there was nothing for the frontend to discard. **That claim is RETRACTED.** The frontend-inspector, whose observation it was, withdrew it on review: zero status events was a property of the WEDGED run only (the turn never progressed past `classify_intent`, so no further stage transitions existed to emit). A healthy turn carries **8 status events** — `classify_intent, rewrite_query, orchestrator, tools, orchestrator, tools, orchestrator, collect_answer` — so the backend does emit stage transitions normally and this record's original finding (the FRONTEND discards `onStatus`) is both correct and unmodified by Phase 7.

Recorded as an explicit withdrawal rather than a silent deletion so the add-and-remove is auditable: no part of this record's severity, layer, root cause or fix surface was ever changed by the withdrawn text.
