# BUG-076: Unregistered msgpack types in checkpointer block future LangGraph versions

- **Severity**: MAJOR
- **Layer**: Reasoning
- **Discovered**: 2026-07-03T00:00:00Z in Phase 3 (Q-014, P3 exit-checklist)
- **Phase scenario**: P3-S7
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
- **Decision**: v1.0-fix
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/175
- **Rationale**: A vendor-dated break — LangGraph states the unregistered-type path "will be blocked in a future version" — in the checkpoint layer this phase exists to validate; when it lands every existing checkpoint becomes unreadable and conversation resume breaks wholesale, so the blast radius is the whole subsystem rather than a subset.

## Notes
Latent bug — currently only warns and falls back, still functions correctly today; the risk is forward-looking (a future LangGraph version enforcing `LANGGRAPH_STRICT_MSGPACK` would hard-block checkpoint restore) plus a present, compounding performance cost. Cross-ref BUG-070 — the SAME accumulating `sub_answers`/`citations` types whose unbounded growth (BUG-070) compounds this bug's slow-serialization cost: the more citations accumulate per BUG-070, the more expensive each checkpoint write becomes via this unregistered-type fallback path. Discovered during the Q-014 exit-checklist incident investigation (control retest, trace 552e3cf6); Lead+Pilot approved MINOR/Reasoning (layer chosen over Infrastructure since this is LangGraph agent-state/schema serialization, not a deployment/ops concern).

**Scenario id normalized 2026-07-28 (schema compliance, no semantic change)**: `scenario_id` set to `P3-S7`; originally logged as `Q-014 (P3 exit-checklist, analytical multi-source)`, which does not satisfy the `bug-registry-schema.json` pattern `^P[0-7]-S[0-9]+$`. Phase 3 ran P3-S1..S6, so the exit checklist is its 7th step. The `Discovered` line above retains the original `Q-014` provenance verbatim.

**UPDATE 2026-07-28 (P7-S1 — third unregistered type + explicit vendor deprecation, and P7-S5 relevance)**: this record currently lists `SubAnswer` and `Citation`. A THIRD unregistered type is confirmed: **`QueryAnalysis`** (`backend/agent/schemas.py`). Live warning text captured at 14:21:42.969Z: *"Deserializing unregistered type … **This will be blocked in a future version.** Set LANGGRAPH_STRICT_MSGPACK=true to block now, or add to allowed_msgpack_modules."* — i.e. the vendor has stated an explicit intent to break this, so it is a DATED failure rather than a hypothetical one.

**Why this is materially more serious than the original MINOR framing**: the checkpoint persistence that Phase 7 exists to validate (P7-S5 resume) depends on exactly these unregistered types. On the next LangGraph major, every existing checkpoint becomes unreadable and conversation resume breaks wholesale — in the one subsystem this phase was convened to verify. The original MINOR adjudication rested on "currently only warns and falls back, still functions correctly today"; that remains true of TODAY's behaviour but no longer characterises the risk.

**Severity: registrar recommends MAJOR — Lead adjudication required, not applied unilaterally.** Reasoning offered for that decision: (a) the failure is dated and vendor-announced, not speculative; (b) the blast radius is total for the affected subsystem — all existing checkpoints, not a subset; (c) registry precedent already grades structural/forward-looking defects above their immediate symptom (BUG-089 CRITICAL for an advertised-but-unreachable feature, BUG-095 CRITICAL for structurally-inert settings). Counter-argument recorded for completeness: FR-013 grades on impact observed at discovery, and observed impact today is a warning plus a slower serialization path, which is MINOR on its face. Left at MINOR on disk pending the Lead's ruling. If promoted to MAJOR this record requires a triage block and a GitHub issue URL.

**SEVERITY PROMOTED MINOR -> MAJOR, 2026-07-28 (team-lead ruling, apply-7)**, adopting the registrar recommendation recorded above. Team-lead resolved the counter-argument explicitly: **FR-013 does not apply here.** FR-013 governs NOT DOWNGRADING a finding after a fix has been applied (its use in BUG-045); it does not govern latent-versus-active grading, so "impact observed at discovery" was the wrong test for this record. On the correct test, a vendor-dated break in the exact subsystem this phase was convened to validate, with total blast radius — every existing checkpoint, not a subset — is materially more than "a warning plus a slower serialization path". Triage block added (v1.0-fix); this record now requires a GitHub issue URL.
