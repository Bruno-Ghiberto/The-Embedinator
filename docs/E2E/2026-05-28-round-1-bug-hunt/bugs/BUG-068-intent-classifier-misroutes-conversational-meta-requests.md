# BUG-068: Conversational meta-requests misrouted as rag_query by intent classifier

- **Severity**: MAJOR
- **Layer**: Reasoning
- **Discovered**: 2026-06-26T20:05:00Z in Phase 3 (P3-S4)
- **Phase scenario**: P3-S4
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. T1 (session c5ffb174): ask "Explica detalladamente todos los requisitos de las redes de distribución según NAG-200" — completes normally (trace f88056f6).
2. T2, same session: ask "Necesito una respuesta mas larga" — a pure conversational instruction referencing the prior answer, with zero document-topic content.
3. Observe backend logs: `agent_intent_classified` reports `intent=rag_query` (trace 2b9065af), triggering a full retrieval re-run for what is not a retrieval request.
4. Observe `agent_rewrite_query_first_attempt_failed` fires immediately after — the meta-request also fails as a retrieval query, so a fallback rewrite executes.

## Expected
The intent classifier recognizes a conversational/formatting meta-instruction referencing the prior answer and skips the retrieval re-run entirely.

## Actual
Classifier returns `intent=rag_query` for "Necesito una respuesta mas larga", triggering an unnecessary full retrieval cycle that itself fails query rewriting and falls back (trace 2b9065af).

## Artifacts
- Screenshot: null
- Log excerpt: logs/BUG-068-intent-misroute.log (gitignored)
- Trace: null

## Root-cause hypothesis
HIGH confidence, code-confirmed — `backend/agent/prompts.py:47-54` (`CLASSIFY_INTENT_SYSTEM`) defines a closed 3-intent taxonomy (`rag_query`|`collection_mgmt`|`ambiguous`) with no "conversational instruction about a prior answer" category; prompt wording ("requires searching documents") biases the LLM toward `rag_query`. `backend/agent/nodes.py:173` (`_VALID_INTENTS`) confirms the closed taxonomy has no escape hatch for this case.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: <v1.0-fix | v1.1-defer>
- **GitHub issue**: <url>
- **Rationale**: <one sentence>

## Notes
Lead+Pilot confirmed severity=MAJOR, layer=Reasoning — "Performance" is not in the bug-registry-schema layer enum (Frontend|Backend|Ingestion|Retrieval|Reasoning|Observability|Infrastructure), and all three P3-S4 findings root in `backend/agent/`. Co-occurs with BUG-056 on the SAME turn (T2) — the misrouted intent feeds a `rewrite_query` call that also fails (BUG-056's OutputParserException + fallback recovery). Session: c5ffb174. Shared multi-turn correlation log: logs/P3-S4-multiturn-window.log. Raw capture (staged read-only, superseded by the durable copy above): /tmp/spec30-captures/UNREG-A-P3-S4-T2-intent-misroute.log.
