# BUG-010: Confidence:0 on in-corpus Spanish factoid queries

- **Severity**: Major
- **Layer**: Reasoning
- **Discovered**: 2026-04-28 14:44 UTC via Exploratory (Charter 1 — A3 Finding 4, corroborated by A5 charter1-step3-factoid trace)

## Steps to Reproduce

1. Stack up: 4 services healthy. NAG corpus seeded (18 PDFs, 2633 chunks — NAG-200.pdf confirmed present).
2. Issue a direct factoid query about a document confirmed in the corpus:
   ```
   POST /api/chat
   {"message": "¿Cuál es el objeto del Reglamento Técnico NAG-200?", "session_id": "test",
    "collection_ids": ["22923ab5-ea0d-4bea-8ef2-15bf0262674f"]}
   ```
3. Observe `confidence_score` in `agent_format_response_formatted` log event.
4. Observe the user-facing response text.

## Expected

NAG-200.pdf is in the corpus. A direct factoid question about NAG-200's object/scope should retrieve the relevant passage, score it above the confidence threshold, and return an answer with ≥1 citation.

## Actual

Three separate sessions querying NAG-200's object all return `confidence=0` and the user-facing message "found N passage(s), but none were sufficiently relevant":

| Session | Trace | Query | confidence | num_citations | passages found |
|---------|-------|-------|------------|---------------|----------------|
| charter1-step3-factoid | 4c62606d | "diámetro mínimo NAG-200" | 0 | 0 | 10 |
| charter1-q001 | 03a9018d | "objeto del Reglamento Técnico NAG-200?" | 0 | 0 | 5 |
| charter1-q001b | ab12fe4b | same | 0 | 0 | 10 |

The system FINDS 5–10 passages but reports them as "not sufficiently relevant." NAG-200.pdf is confirmed in the corpus by other successful queries that cited it. English-language responses are returned despite Spanish-language queries, suggesting language-handling issues may affect scoring.

## Artifacts

- Traces: `4c62606d` (step3-factoid, 14:40:21 UTC), `03a9018d` (charter1-q001), `ab12fe4b` (charter1-q001b)
- A5 log excerpt (charter1-step3-factoid):
  ```
  {"collections_searched": 20, "total_results": 30, "event": "retrieval_search_all_complete", "timestamp": "14:40:25"}
  → agent_loop_exit_exhausted (iterations=3), confidence=0, num_citations=0 (wall time ~29s)
  ```
- A3 observation: system response language is English despite all queries in Spanish — possible language-handling gap affecting grounding score
- File refs:
  - `backend/agent/confidence.py` — 5-signal confidence scoring; threshold check (`confidence_threshold: int = 60` per config.py default)
  - `backend/retrieval/reranker.py` — CrossEncoder reranking scores for Spanish passages
  - `backend/agent/prompts.py` — system prompt language (English-only templates may affect LLM's ability to ground Spanish passages)

## Root-cause hypothesis

Two candidates, possibly compounding: (a) **Confidence threshold too high for Spanish-language queries**: `nomic-embed-text` embeddings and `ms-marco-MiniLM-L-6-v2` CrossEncoder are trained primarily on English data; Spanish passage scores may be systematically lower than the `confidence_threshold=60` floor, causing factoid passages that would pass on English queries to fail the threshold check. (b) **Language mismatch in grounding**: The LLM receives Spanish passages but the system prompt is in English; the LLM may struggle to ground Spanish evidence into a coherent answer, causing the answer-relevance signal to score near zero, which propagates through the 5-signal confidence formula. Note: BUG-002's scope leak also contributes here (20 collections searched → irrelevant cross-collection chunks dilute the relevant NAG-200 results), but even on runs with fewer leaked chunks (1–2 sessions returned non-zero citations), confidence remained at 0 — suggesting the threshold/language issue is independent.
