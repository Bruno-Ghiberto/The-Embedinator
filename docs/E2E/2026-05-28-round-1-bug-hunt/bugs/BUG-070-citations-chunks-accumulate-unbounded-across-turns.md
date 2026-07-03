# BUG-070: Citations/chunks accumulate unbounded across conversation turns

- **Severity**: MINOR
- **Layer**: Observability
- **Discovered**: 2026-06-26T20:05:00Z in Phase 3 (P3-S4)
- **Phase scenario**: P3-S4
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. In a session where session continuity holds (a shared LangGraph thread across turns — see Reachability note below), compare `agent_aggregate_answers_merged.num_citations` per turn — each turn's OWN deduped citation count (organic session c5ffb174: T1=5, T2=10, T3=10) — against `agent_format_response_formatted.num_citations` for the SAME turn — the accumulated conversation-STATE total (T1=20, T2=70, T3=170).
2. Cross-reference `query_traces.chunks_retrieved_json` byte length across the 3 turns: 14,408 → 49,544 → 120,258 bytes (~8.3x growth by T3), confirmed via DB export.
3. Compare against what the CLIENT actually receives: the streamed `citation` NDJSON event, and the "sources" panel count in the UI.

## Expected
The backend's internal `ConversationState.citations` accumulator either resets between turns or is deduplicated at every consumption site, so the trace-persistence column (`chunks_retrieved_json`) does not balloon across an open-ended conversation.

## Actual
`ConversationState.citations` accumulates unbounded across turns via the `operator.add` reducer, never reset within a shared thread — confirmed CONFINED to backend state plus the `chunks_retrieved_json` trace column (raw entries 20→70→170, ~120KB by turn 3, DB-verified). This is corrected as of 2026-07-03 (see Notes) — it is NOT user-visible in the assistant's answer text. Secondary (mild) user-visible effect: the "sources" panel count grows and stale prior-turn sources persist into later turns (5→10→10, bounded to the count of unique passages retrieved so far, not unbounded).

## Artifacts
- Screenshot: null
- Log excerpt: logs/BUG-070-citation-growth.log (gitignored)
- Trace: traces/P3-S4-traces-db.json (gitignored) — same 3-row DB export as BUG-069; `citation_entry_count` column shows 20/70/170 and `chunks_json_len` shows 14408/49544/120258 across the 3 turns.

## Root-cause hypothesis
HIGH confidence, code-confirmed, 3-part: (a) `backend/agent/state.py:54` — `citations: Annotated[list[Citation], operator.add]` on `ConversationState`; the LangGraph reducer concatenates every node write onto the checkpointed session state, and nothing resets it between `HumanMessage` turns within the same `thread_id`. (b) `backend/agent/nodes.py:804` + `814-825` (`format_response`) computes inline `[N]` markers + a "**References:**" section from the FULL accumulated `state.get("citations", [])` with no dedup — BUT this computed text is DISCARDED, not sent to the client: `backend/api/chat.py:239-242` skips re-emitting `final_response` because token-by-token streaming already fired via `collect_answer` at `chat.py:231`. The bloated reference text never reaches the browser. (c) `backend/api/chat.py:303-305` — `chunks_retrieved_json` (the trace-persistence column) serializes the same raw accumulated list with no dedup; this is a real, DB-verified defect, confined to the observability/trace surface. By contrast, the streamed `citation` NDJSON event IS deduped by `passage_id` (`chat.py:245-256`, comment "# BUG-017: Send() fan-out produces N copies") — so the user-facing citation count the client actually renders is the TRUE unique count per turn (5→10→10, plateauing at 10, never ballooning to 170).

## Triage (filled in Phase 8 for MAJOR+)
<!-- MINOR — triage optional -->

## Notes
**REVISED 2026-07-03** (Lead+Pilot ruling, after code trace): severity downgraded MAJOR → MINOR, layer changed Reasoning → Observability. The original registration incorrectly claimed `format_response` "bakes the accumulated list into the assistant's VISIBLE final_response, so by turn 5-6 the chat bubble holds hundreds of duplicate reference lines" — this is FACTUALLY WRONG and is retracted: `chat.py:239-242` proves the computed `final_response` text (with its bloated inline references) is discarded, never re-emitted to the client, because token streaming already delivered the answer via `collect_answer`. The bug is real but confined to backend state (`state.py:54`) and the trace-persistence column (`chunks_retrieved_json`) — an observability/audit-trail concern, not a user-facing correctness defect. Kept as a DISTINCT bug — NOT merged into BUG-066. Cross-ref BUG-066 both directions: BUG-066 = WITHIN-turn 4× inflation (Send() fan-out on a single trace, root cause left ambiguous by design); BUG-070 = ACROSS-turn accumulation via the `operator.add` reducer (root cause HIGH-confidence code-pinned). Same field (`chunks_retrieved_json` inflation), same layer (Observability), same severity (MINOR) as BUG-066 post-revision — but a distinct mechanism and a distinct fix (BUG-066's fix is at the retrieval/fan-out layer; BUG-070's fix is a reset-or-dedup at the state-reducer / trace-persistence layer). Reachability note: this bug ONLY manifests when session continuity HOLDS (a shared thread across turns) — i.e., only when BUG-064 does NOT fire. When BUG-064 fires (session breaks on remount), each turn starts a fresh empty thread and there is nothing to accumulate. Session c5ffb174; shares its 3-turn DB trace export with BUG-069 (traces/P3-S4-traces-db.json).
