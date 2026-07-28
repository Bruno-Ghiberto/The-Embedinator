# BUG-069: Intent classifier hard-fails under accumulated multi-turn context

- **Severity**: MAJOR
- **Layer**: Reasoning
- **Discovered**: 2026-06-26T20:05:00Z in Phase 3 (P3-S4)
- **Phase scenario**: P3-S4
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Continue session c5ffb174 (same session as BUG-068) to T3: ask "Con respuesta más larga me refiero a la primer pregunta de esta chat : 'Explica detalladamente todos los requisitos de las redes de distribución según NAG-200'" (trace d8cd8ef9).
2. Observe backend logs: `agent_classify_intent_failed`, `defaulting_to=rag_query`, `error=OutputParserException`.
3. Inspect the traceback: `ValidationError` — "1 validation error for IntentClassification / intent / Field required." The LLM (qwen2.5:7b) returned `{"context": "...", "response": "..."}` — it reproduced T1's Q+A pair verbatim instead of the required `{intent, reason}` schema.
4. Confirm no retry occurs — the bare `except` silently defaults to `rag_query` and the turn proceeds on that assumption.

## Expected
`classify_intent` produces valid structured output regardless of conversation length; if the LLM cannot comply, the failure surfaces distinctly rather than silently defaulting.

## Actual
Under accumulated multi-turn context, qwen2.5:7b echoes the conversation's prior Q&A content instead of the `{intent, reason}` schema; a bare `except Exception` catches the resulting `ValidationError` and silently defaults to `rag_query`, with no retry and no distinct signal beyond `stage_timings.intent_classification.failed=true`.

## Artifacts
- Screenshot: null
- Log excerpt: logs/BUG-069-classify-intent-hardfail.log (gitignored)
- Trace: traces/P3-S4-traces-db.json (gitignored) — 3-row query_traces DB export for session c5ffb174; row `d8cd8ef9` shows `stage_timings_json.intent_classification = {"duration_ms": 4377.6, "failed": true}`.

## Root-cause hypothesis
HIGH confidence, code+traceback confirmed — `backend/agent/nodes.py:213-220` calls `structured_llm.ainvoke(..., method="json_mode")` fed `history_text` built from the last 10 messages (`nodes.py:188-194`). Under accumulated context, qwen2.5:7b echoes conversational content instead of the schema. The failure is caught by a bare `except Exception` at `nodes.py:236-247`, which silently defaults to `rag_query` — no retry, no distinct handling path.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.1-defer
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/143
- **Rationale**: Lead+Pilot explicitly weighed and declined CRITICAL — the bare-except default to rag_query still produced a grounded completed answer (confidence 54, num_valid=3), so the harm is a silent internal fallback, not user-visible misreporting.

## Notes
Lead+Pilot considered CRITICAL and explicitly declined it: no data loss or outage occurs — the silent default to `rag_query` still returns a grounded answer (trace d8cd8ef9 completed with confidence_score=54, num_valid=3 post-aggregation). Severity held at MAJOR; this reasoning is recorded here so the verify gate sees the triage was deliberate, not an oversight. DISTINCT from BUG-056: BUG-056 is `rewrite_query`'s OutputParserException WITH a working fallback (MINOR, +~4.3s, correct end result); BUG-069 is `classify_intent`'s hard validation failure with NO recovery path — wrong intent, turn continues on a false premise. Layer=Reasoning per Lead direction ("Performance" is not a schema layer value; all three P3-S4 findings root in `backend/agent/`). Session: c5ffb174. Shared multi-turn correlation log: logs/P3-S4-multiturn-window.log; shared DB trace export with BUG-070: traces/P3-S4-traces-db.json.

**CLARIFICATION 2026-07-03** (Lead+Pilot, no severity/layer change — stays MAJOR/Reasoning): confirmed real on the organic shared thread c5ffb174 (T3, trace d8cd8ef9). Reachable ONLY when session continuity holds (i.e., accumulated multi-turn context is actually present in `history_text`). Interplay with BUG-064/BUG-070: when the session BREAKS (BUG-064 fires on a hook remount), there is no accumulated context, so BUG-069 cannot trigger — but the conversation is broken anyway (fresh empty thread, lost context). When the session HOLDS (BUG-064 does not fire), the accumulated context can grow large enough to trigger this classify_intent hard-fail, AND separately drives BUG-070's citation accumulation. Net: both regimes leave multi-turn chat broken — BUG-064 breaks it by losing context entirely, BUG-069/BUG-070 break it (differently) when context is retained and accumulates.

**UPDATE 2026-07-28 (P7-S1 — fresh repro, and it now has a downstream consequence)**: the same accumulated-context degradation reproduced on session `54606bb9`, which completed 3 successful turns before turn 4 hard-failed at 14:21:42 with `agent_classify_intent_failed error=OutputParserException`. This matches the P3-S4 pathology this record registers (hard failure at turn 3 there, turn 4 here) — the classifier degrades as conversation history accumulates, because history is injected into the intent prompt and overloads `qwen2.5:7b`.

**New detail worth recording — the failure mode is specific, not generic malformed output**: the LLM returned a full structured document instead of an `IntentClassification`; it attempted to ANSWER THE QUESTION inside the intent-classification call. Traceback locals show `obj = {'collection': …, 'document': 'NAG-200', 'sections': [...]}`. That is a more precise characterisation than this record's original "echoes the conversation's prior Q&A content".

**Downstream consequence not present in the original finding**: here the failure consumed **49.3s** in the first node, which pushed the first silent gap past the ~30s proxy idle timeout and wedged the entire turn (see BUG-054, broadened by this evidence). So this defect is no longer only a silent internal fallback — under accumulated context it can be the direct cause of a user-visible dead stream. Severity left at MAJOR on disk; the Lead+Pilot decision recorded above (CRITICAL considered and explicitly declined) predates this consequence and may warrant revisiting. Cross-ref BUG-054 (the timeout this failure trips), BUG-074/BUG-119 (the resulting dead stream and its indistinguishability).

**EVIDENCE-BASE AUDIT 2026-07-28 (registrar, at team-lead request before a proposed MAJOR -> CRITICAL escalation) — ESCALATION NOT APPLIED.** Team-lead proposed CRITICAL on the reasoning that this defect independently breaks any conversation at roughly turn 3-4, which for a chat product is normal usage rather than a corner case, and asked that the record be checked to confirm it actually supports "turn 3-4 reproducibly" before applying.

**It does not. The complete evidence base is TWO hard-failure data points**, both recorded above and both re-verified against this record: (1) P3-S4, organic shared thread `c5ffb174`, hard failure at **turn 3** (trace `d8cd8ef9`); (2) P7-S1, session `54606bb9`, three successful turns then hard failure at **turn 4**. There is no third occurrence, no controlled series that varied turn depth, and no measurement establishing a threshold — the two points are consistent with a turn-3-to-4 onset but do not establish one, and neither run was designed to find the boundary.

Severity therefore **held at MAJOR**, per team-lead's own instruction to prefer under-grading over manufacturing a CRITICAL from two data points. Recorded here so the question is visibly settled on evidence rather than left open. **What would settle it**: a controlled series holding model and corpus fixed while varying conversation depth, to establish whether onset is reproducible at a specific turn count or merely correlated with accumulated history length. Recommended for spec-31 alongside the BUG-123 proxy probe.
