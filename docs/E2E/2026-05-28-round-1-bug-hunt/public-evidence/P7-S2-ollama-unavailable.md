# P7-S2 — Ollama unavailable. VERDICT: FAIL (false attribution)

`docker stop embedinator-ollama` 14:34:24.716Z → chat → `docker start` 14:35:25.201Z.
Chat issued direct to :8000 so the Next proxy (BUG-054) could not confound the result.

## Two predictions were made on the record. Both were wrong.
- team-lead predicted another BUG-054 hang. **Wrong** — the turn completed in 21.5s with a
  `done` event. No hang.
- log-analyst predicted a "degraded but plausible answer" produced fast. **Wrong** — no answer
  was produced at all, because embedding also depends on Ollama, so retrieval returned nothing.

The actual result is worse than either prediction.

## What the user is told
> "I could not find any relevant information to answer: *What are the pipe sizing requirements
> in NAG-200?*. **The indexed documents may not cover this topic.**"

Confidence 0. Latency 21.5s. Stream closed cleanly with `done`.

**This is a false attribution.** NAG-200 is in the corpus — it was retrieved successfully minutes
earlier in this same phase. The documents are fine. The inference engine was dead. The system
tells the user their corpus is inadequate and points them at exactly the wrong remedy: they will
go re-ingest documents that were never the problem.

## What was recorded
`query_traces` row **was** written (unlike every other failure mode in this phase):

| field | value |
|---|---|
| `llm_model` | `qwen2.5:7b` — **asserts a model that was not running** |
| `confidence_score` | 0 |
| `latency_ms` | 21486 |
| `chunks_retrieved_json` | `[]` — **zero chunks** |
| `collections_searched` | the correct collection |

So the observability surface records a completed, healthy-looking turn against a live model,
for a turn served with no model at all.

## The one genuine PASS
`/api/health` detected the outage **immediately** — HTTP 503, `status: degraded`,
`ollama.error_message: "[Errno -2] Name or service not known"` (DNS removal). Engineered, and
citable at `health.py:60` `_probe_ollama()` / `:67-68`.

That makes the failure sharper, not softer: **health knew, and the chat path never asked.** The
information needed to tell the user the truth existed in the same process at the same moment.

## Dedup
Same family as BUG-095 (structural deception) and BUG-098 (confident output after zero
retrievals), but a distinct mechanism: this is dependency-outage misattributed to corpus
coverage. Recommend a new ID, MAJOR minimum — it misleads the user about system state, which is
the v1.0-fix criterion.
