# BUG-078: Append-only sub_answers reducer corrupts turn 2+ answer text (no reset)

- **Severity**: MAJOR
- **Layer**: Backend
- **Discovered**: 2026-07-03T19:21:29Z in Phase 4 (P4-S1)
- **Phase scenario**: P4-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Ask ≥2 turns within one thread (directly, or via BUG-077 — any "New Chat" that silently reuses a thread).
2. Observe turn 2+ answer text: it is prepended with `**{sub_question}**` headers and concatenated with the RAW prior-turn text.
3. Live: same-chat Query B (turn 2 of the P4-S1 same-chat run) rendered "NO PASSAGE SUPPORTS THE SUB-QUESTION..." — turn 1's raw `collect_answer` text replayed inside turn 2's visible answer (see screenshot).

## Expected
Each turn's answer reflects only that turn's question and retrieval — per-turn state reset works as intended.

## Actual
`backend/agent/state.py:48` (`sub_answers`) and `:54` (`citations`) are both `Annotated[list, operator.add]` — append-only reducers. `backend/api/chat.py:157/162` passes `initial_state={"sub_answers": [], "citations": []}`, which is a silent no-op against a persisted checkpoint (`operator.add(existing, []) == existing`). `aggregate_answers` (`backend/agent/nodes.py:405-412`), when `len(valid) > 1`, prepends `**{sub_question}**` headers and concatenates every turn's raw `collect_answer` output with NO synthesis or cleanup LLM pass (`format_response`, `nodes.py:787-846`, is pure Python — no LLM call). Confirmed via trace: `aggregate` `num_valid` progresses 1→2→3 and `format_response` `num_citations` progresses 20→70→170 across turns A/B/C of the same thread.

## Artifacts
- Screenshot: screenshots/BUG-078-subquestion-leak-samechat.png (gitignored) — turn 2 answer showing the leaked `**{sub_question}**` header + prior-turn raw text.
- Log excerpt: logs/BUG-078-state-accumulation-traces.log (gitignored) — primary trace evidence, full capture.
- Log excerpt: logs/BUG-078-req68-accumulation.network-response (gitignored) — request 68 network response.
- Trace: null

## Root-cause hypothesis
HIGH confidence, code-confirmed (log-analyst, code + trace). See Actual — three-part chain: (a) append-only `operator.add` reducers on `sub_answers`/`citations`, (b) `initial_state` reset is a no-op against a live checkpoint, (c) `aggregate_answers` naively concatenates every accumulated sub-answer with no dedup or synthesis pass, so the corruption reaches the user-visible answer text starting at turn 2.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: <v1.0-fix | v1.1-defer>
- **GitHub issue**: <url>
- **Rationale**: <one sentence>

## Notes
Cross-ref: BUG-070 — sibling `sub_answers`/`citations` reducer problem, but distinct facet. BUG-070's finding was that its `citations` accumulation is CONFINED to backend state + the `chunks_retrieved_json` trace column and does NOT reach visible answer text (that claim was verified via `chat.py:239-242` — the bloated `final_response` text is computed but discarded, never re-emitted, because token streaming already delivered the answer via `collect_answer`). BUG-078 is the sibling reducer (`sub_answers`) that DOES reach visible text, via `aggregate_answers`' header-prepend-and-concatenate path — a different code path than the one BUG-070 examined. BUG-070's severity (MINOR) is UNCHANGED by this finding; its "not user-visible" rationale applies only to the citations facet it investigated, not to this separate `sub_answers` facet.
