# BUG-066: Trace chunks_retrieved_json inflated 4x vs unique chunks retrieved

- **Severity**: MINOR
- **Layer**: Observability
- **Discovered**: 2026-06-26T19:10:00Z in Phase 3 (P3-S3)
- **Phase scenario**: P3-S3
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Run an analytical query (e.g., P3-Q-A "Explica detalladamente todos los requisitos...").
2. Inspect query_traces.chunks_retrieved_json for the resulting trace row in data/embedinator.db.
3. Count total entries vs unique (document_id, score) tuples.
4. Observe 20 total entries = 5 unique chunks × 4 repetitions, with research_tools_calls=1.

## Expected
chunks_retrieved_json records the set of unique chunks actually retrieved in this query; the count should equal the number of unique chunks served to the model (research_tools_calls=1 → 5 unique chunks → 5 entries).

## Actual
Analytical trace 618fb649: chunks_retrieved_json holds 20 entries = 5 unique chunks (scores +1.78/-0.15/-1.22/-1.51/-1.54, all NAG-200.pdf) × 4 repetitions, despite research_tools_calls=1.

## Artifacts
- Screenshot: screenshots/BUG-066.png (gitignored)
- Log excerpt: logs/BUG-066.log (gitignored)
- Trace: traces/BUG-066-618fb649.trace.zip (gitignored)

## Root-cause hypothesis
MEDIUM confidence — symptom is HIGH-confidence DB-verified (20 entries confirmed in query_traces row 618fb649); root cause is ambiguous. Candidate (a): chunks_retrieved_json accumulation does not deduplicate across loop iterations or sub-questions, so the same retrieval set is appended multiple times. Candidate (b): 2 orchestrator iterations × the same retrieval set stored twice + parent-chunk expansion producing the 4× factor. sub_questions_json is NULL in this trace so sub-question fan-out is unconfirmed. AMBIGUITY NOTE: do not assert a single cause until code inspection confirms the accumulation path. Cross-ref BUG-057 (observability cluster — ranking timing 0.0ms); relates to BUG-055 (2nd-iteration mechanism that may drive the repetition).

## Triage (filled in Phase 8 for MAJOR+)
<!-- MINOR — triage optional -->

## Notes
Pilot-confirmed register. DB-verified from query_traces row trace_id 618fb649 in data/embedinator.db. Artifact: /tmp/spec30-captures/P3-S3-analytical-trace.log. Inflated count does not necessarily mean extra chunks were served to the model — the inflation may be in the recording path only. Analyst-correlated; root-cause ambiguity explicitly preserved per Lead instruction.
P3-S4 (2026-07-03) live re-confirmation on BOTH clean-probe turns, same 4× pattern: T1 = 5 unique chunks → 20 formatted entries in chunks_retrieved_json (4×, payload 15,932 bytes); T2 = 3 unique chunks → 12 formatted entries (4×, payload 8,880 bytes). Consistent 4× factor across both turns, independent of query type (factoid T1, drifted-topic T2) and independent of BUG-070 (this is the WITHIN-turn inflation; see BUG-070 for the separate ACROSS-turn accumulation on the same chunks_retrieved_json field — cross-ref both directions, same field/layer/severity, distinct mechanism).

P4-S4 (2026-07-07) fresh repro data point: on the BUG-083 prompt-injection-compliance trace, the same 5→20 citation-count amplification recurred — `aggregate_answers` recorded num_citations=5 while `format_response` reported num_citations=20 — confirming the inflation is independent of answer content (it recurs even when the "answer" is the hijacked literal "pwned").
