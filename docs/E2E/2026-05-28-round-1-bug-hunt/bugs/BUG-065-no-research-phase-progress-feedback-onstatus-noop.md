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
