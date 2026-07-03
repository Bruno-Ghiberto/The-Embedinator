# BUG-076: Unregistered msgpack types in checkpointer block future LangGraph versions

- **Severity**: MINOR
- **Layer**: Reasoning
- **Discovered**: 2026-07-03T00:00:00Z in Phase 3 (Q-014, P3 exit-checklist)
- **Phase scenario**: Q-014 (P3 exit-checklist, analytical multi-source)
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Run any chat query — the LangGraph checkpointer serializes `ConversationState` at every superstep.
2. Observe (trace `552e3cf6`, 17:53:12): LangGraph logs `Deserializing unregistered type backend.agent.schemas.SubAnswer from checkpoint. This will be blocked in a future version. Set LANGGRAPH_STRICT_MSGPACK=true to block now, or add to allowed_msgpack_modules to allow explicitly.` — the SAME warning also fires for `backend.agent.schemas.Citation`.
3. Confirm the impact has two parts: (a) forward-looking — a future LangGraph version will BLOCK deserialization of these unregistered types, breaking checkpoint restore on upgrade; (b) current — the fallback msgpack path is slower, and gets worse as `sub_answers`/`citations` accumulate in state.

## Expected
Custom Pydantic types stored in checkpointed state are registered with LangGraph's msgpack serializer (or represented in a serializer-native form) so no unregistered-type warning fires and no future-version breakage risk exists.

## Actual
`SubAnswer` and `Citation` (`backend/agent/schemas.py`) are stored inside `ConversationState` (`sub_answers`, `citations` fields) but are not registered with LangGraph's msgpack serializer and are not present in `allowed_msgpack_modules`, so every checkpoint write/read logs the deserialization warning and falls back to the slower generic path.

## Artifacts
- Screenshot: null
- Log excerpt: logs/P3-Q014-retest-control.log (gitignored) — contains the two warning lines (trace 552e3cf6).
- Trace: null

## Root-cause hypothesis
`backend/agent/schemas.py`'s `SubAnswer` and `Citation` are custom Pydantic types held in `ConversationState` (`sub_answers`, `citations`) but never registered with LangGraph's msgpack serializer / `allowed_msgpack_modules`. Fix: register the types explicitly (or add the module to `allowed_msgpack_modules`), or switch these fields to a serializer-native representation (e.g. plain dict) before checkpointing.

## Triage (filled in Phase 8 for MAJOR+)
<!-- MINOR — triage optional -->

## Notes
Latent bug — currently only warns and falls back, still functions correctly today; the risk is forward-looking (a future LangGraph version enforcing `LANGGRAPH_STRICT_MSGPACK` would hard-block checkpoint restore) plus a present, compounding performance cost. Cross-ref BUG-070 — the SAME accumulating `sub_answers`/`citations` types whose unbounded growth (BUG-070) compounds this bug's slow-serialization cost: the more citations accumulate per BUG-070, the more expensive each checkpoint write becomes via this unregistered-type fallback path. Discovered during the Q-014 exit-checklist incident investigation (control retest, trace 552e3cf6); Lead+Pilot approved MINOR/Reasoning (layer chosen over Infrastructure since this is LangGraph agent-state/schema serialization, not a deployment/ops concern).
