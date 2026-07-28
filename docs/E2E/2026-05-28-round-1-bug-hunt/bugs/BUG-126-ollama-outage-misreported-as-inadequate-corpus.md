# BUG-126: Ollama outage misreported as inadequate corpus; user sent to wrong remedy

- **Severity**: CRITICAL
- **Layer**: Backend
- **Discovered**: 2026-07-28T14:34:24Z in Phase 7 (P7-S2)
- **Phase scenario**: P7-S2
- **BLOCKER-PATCHED**: no

## Steps to Reproduce
1. `docker stop embedinator-ollama` (14:34:24.716Z).
2. Ask a question whose answer IS in the corpus — "What are the pipe sizing requirements in NAG-200?". NAG-200 was retrieved successfully minutes earlier in this same phase. Issue it direct to `:8000` so the Next proxy (BUG-054) cannot confound the result.
3. Observe the turn COMPLETES cleanly in 21.5s with a `done` event — no hang, no error.
4. Read the answer: *"I could not find any relevant information to answer: 'What are the pipe sizing requirements in NAG-200?'. **The indexed documents may not cover this topic.**"*
5. Inspect the `query_traces` row: `llm_model=qwen2.5:7b`, `provider_name=ollama`, `confidence_score=0`, `latency_ms=21486`, `chunks_retrieved_json=[]`, `stage_timings_json` carrying `"intent_classification": {"duration_ms": 5428.2, "failed": true}`, and `collections_searched=["22923ab5-…"]`. Compare against the log for the SAME trace, which records `collections_searched: []` with zero tool calls.
6. Call `GET /api/health` during the same window: HTTP 503, `status: degraded`, `ollama.error_message: "[Errno -2] Name or service not known"`.
7. `docker start embedinator-ollama` — health returns to 200/healthy, recovery clean.

## Expected
When a dependency outage prevents retrieval, the user is told that the system is degraded and cannot search right now — not that their documents are inadequate.

## Actual
The system attributes its own dependency outage to the user's corpus. With Ollama down the LLM-driven research orchestrator never issues a retrieval tool call at all, so **Qdrant is never queried once** despite being perfectly healthy; retrieval therefore yields zero chunks, and the zero-result path emits the standard "the indexed documents may not cover this topic" message. The documents were never the problem; the inference engine was dead. The user is pointed at exactly the wrong remedy and will go re-ingest documents that were fine.

A `query_traces` row IS written (unlike every other failure mode observed this phase). The row is **not** a clean bill of health — it does carry failure signals: `confidence_score = 0`, empty `chunks_retrieved_json`, and `stage_timings_json` containing `"intent_classification": {"duration_ms": 5428.2, "failed": true}`. The precise defect is narrower and survives that qualification:

- `llm_model = qwen2.5:7b` and `provider_name = ollama` — **names a model and a provider that never served this request**.
- `collections_searched = ["22923ab5-…"]` — **claims a collection was searched, while the log for the same trace records `collections_searched: []` with zero tool calls. The trace row contradicts the log.**
- There is **no error or status column**, so all four `ConnectError`s appear nowhere in the row.

So the trace attributes work to a model, a provider and a collection that were never involved, and has no field capable of recording that the dependency was down.

## Artifacts
- Screenshot: null
- Log excerpt: null
- Trace: traces/P7-S2-ollama-unavailable.md (gitignored) — full scenario record incl. the query_traces field table; traces/P7-S2-stream.ndjson — the clean `done`-terminated stream
- Public evidence: public-evidence/P7-S2-ollama-unavailable.md (tracked)

## Root-cause hypothesis
HIGH confidence, evidence-confirmed — and the mechanism is more fundamental than first assumed.

**THE MODEL IS A CONTROL-FLOW DEPENDENCY FOR THE ENTIRE RETRIEVAL PATH, not merely an answer-generation dependency.** The research orchestrator is itself LLM-driven: it is the model that decides to issue retrieval tool calls. With the LLM unreachable the orchestrator never emits a tool call, so **Qdrant was never queried once** — `chunk_count=0`, `collections_searched=[]`, zero tool calls — even though Qdrant was perfectly healthy throughout. An LLM outage therefore produces zero retrieval on a fully healthy vector database.

This corrects an earlier prediction (log-analyst) that retrieval would still succeed while Qdrant was up, and it is the fact that makes an Ollama outage's blast radius far larger than assumed. It is also precisely why the user is told "your documents may not cover this topic": from the answer path's point of view the retrieval genuinely returned nothing, and it has no way to distinguish "searched and found nothing" from "never searched at all".

The reporting defect sits on top of that: the zero-retrieval path has a single explanation for an empty result set and no branch for "could not search", so an infrastructure outage is collapsed into an ordinary empty-result message. Fix surface: treat "the orchestrator could not run" as a distinct condition from "retrieval returned nothing", and consult the health state that already exists in-process before attributing an empty result to corpus coverage.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.0-fix
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/174
- **Rationale**: During a dependency outage the product asserts a specific, false diagnosis about the user's own data and directs them to a remedy that cannot help, while its own health surface holds the correct answer in the same process at the same moment.

## Notes
Reporters: team-lead (P7-S2 execution). Dedup-checked before minting against all 99 prior records.

**One genuine PASS, recorded as a PASS and not softened**: `/api/health` detected the outage IMMEDIATELY and correctly — HTTP 503, `status: degraded`, `ollama=error` with the real cause surfaced (`[Errno -2] Name or service not known`, DNS removal), while `sqlite` and `qdrant` correctly remained ok; it returned to 200/healthy within ~2s of `docker start`. This is engineered and citable at `backend/api/health.py:60` `_probe_ollama()` and `:67-68`, meeting this phase's binding standard that a clean result counts only if the code engineering it can be named. Recording it as a PASS makes the defect sharper rather than softer: **health knew, and the chat path never asked.** The information needed to tell the user the truth existed in the same process at the same moment and was not consulted.

**Two on-record predictions were both wrong, recorded because the miss is informative**: team-lead predicted a BUG-054-style hang (wrong — the turn completed in 21.5s with `done`), and log-analyst predicted a degraded-but-plausible answer produced quickly (wrong — no answer was produced at all). The actual behaviour was worse than either, because neither prediction accounted for the model being a CONTROL-FLOW dependency of retrieval — the LLM-driven orchestrator never issues a retrieval call when the model is unreachable, so a healthy Qdrant is simply never asked.

**Severity CRITICAL — reasoning recorded, decision delegated by team-lead.** The registrar does not normally adjudicate severity; team-lead explicitly delegated this one and asked for reasoning. CRITICAL rather than MAJOR because: (a) the product does not merely fail to answer, it asserts a specific false diagnosis about the user's own data; (b) it prescribes a wrong and costly remedy (re-ingestion of a corpus that is intact); (c) the trace surface, while not asserting the turn was healthy, attributes the work to a model, provider and collection that were never involved and contradicts its own log on `collections_searched`, so the record of what happened is itself wrong; and (d) the correct information was available in-process and unused, which places this alongside BUG-034 (silent health-lie) and BUG-098 (confident output after zero retrievals), both CRITICAL. Counter-argument recorded for completeness: the behaviour is bounded to dependency-outage windows, the turn completes cleanly, no data is lost, and recovery was clean — a defensible MAJOR case. Judged to be outweighed by the false-diagnosis-plus-wrong-remedy combination.

**Distinct from its family members**: BUG-095 (structural deception — settings stored, readable, never honoured) and BUG-098 (no embedder/collection compatibility check; confident output after zero retrievals) share the theme, but the mechanism here is specific and new — a DEPENDENCY OUTAGE misattributed to CORPUS COVERAGE, via a shared Ollama dependency between embedding and generation that collapses an infrastructure failure into an ordinary empty-result path. Cross-ref BUG-116: this is the affirmative half of its story — a completed-but-degraded turn DOES write a trace row, and that row is actively misleading.

**Both halves of the health story belong here, and they point opposite ways**: health is BLIND to a stuck turn (BUG-046 — 21 consecutive 200 OKs through a 160s wedge) but CORRECT about a dead dependency (this scenario — immediate, accurate, per-service 503). The probe's weakness is that it tests dependency reachability, not whether work is progressing; this scenario happens to fall on its strong side.

**Method disclosure (log-analyst, self-reported)**: a stale-buffer fault was found in its own health-polling harness — `curl` leaving a previous response body in place on timeout, which could make a stale sample look like a fresh one. It was caught before reporting, and log-analyst confirmed none of the findings in this record rest on affected samples. Recorded because a verifier should be able to see that the instrument was checked, not only the result.
