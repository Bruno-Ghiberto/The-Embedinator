# BUG-003: OutputParserException fallback loop on every query rewrite

- **Severity**: Major
- **Layer**: Reasoning
- **Discovered**: 2026-04-28 14:34 UTC via Log scan (A5 pre-session tail, confirmed across all 6 spec-28 sessions)

## Steps to Reproduce

1. Start the full stack (`docker compose up -d`).
2. Send any chat message via `POST /api/chat` (any query, any session).
3. Tail backend logs: `docker compose logs backend --follow | grep agent_rewrite`.
4. Observe: `agent_rewrite_query_first_attempt_failed` fires, followed immediately by `agent_rewrite_query_fallback`, on every request.

## Expected

The `rewrite_query` node parses the LLM's output correctly on the first attempt. `agent_rewrite_query_first_attempt_failed` should be rare or absent under normal operating conditions; the fallback path should be the exception, not the rule.

## Actual

`OutputParserException` fires on 100% of requests across all 6 spec-28 test sessions (trace IDs: `c30b175b`, `25cc497b`, `900f691d`, `98de590c`, `c06a4cc5`, `f8a65272`). The fallback handler catches it and produces a response, so the user is never presented with an error — but every query rewrite silently travels the failure path. This is a systematic, non-intermittent failure of the first-attempt parser.

## Artifacts

- Log excerpt:
  ```
  2026-04-28 13:27:34 [warning] agent_rewrite_query_first_attempt_failed component=backend.agent.nodes error=OutputParserException session_id=p-only trace_id=f8a65272-a0f0-406e-94d3-e69ad6f3f9f5
  2026-04-28 13:27:37 [warning] agent_rewrite_query_fallback component=backend.agent.nodes error=OutputParserException session_id=p-only trace_id=f8a65272-a0f0-406e-94d3-e69ad6f3f9f5
  ```
- Hit rate: 6/6 sessions (100% — not intermittent)
- Related charter: Charter 3 (confidence-vs-answer-text alignment) — the fallback rewrite path may yield a degraded query that contributes to confidence/answer mismatches
- File ref: `backend/agent/nodes.py` (rewrite_query node, first-attempt parser vs. fallback path)

## Root-cause hypothesis

The `rewrite_query` node instructs the LLM to produce a structured output and parses it with a strict OutputParser. The LLM (local `qwen2.5:7b`) consistently produces output that doesn't match the parser's expected schema — likely returning JSON with extra fields, wrong key names, or prose wrapping around the JSON object. The fallback path catches the `OutputParserException` and uses a simpler extraction strategy. Since this fails 100% of the time, the root cause is a mismatch between the prompt's format instructions and the model's actual output format — either the prompt needs updating to match the model's output style, or the parser needs to be made more lenient. Charter 3 investigation should check whether the fallback-rewritten query is semantically equivalent to the intended rewrite, as degraded rewrites could explain confidence-vs-answer text mismatches.

**Charter 1 update (2026-04-28 14:38 UTC)**: BUG-003 is confirmed as the upstream trigger of BUG-005 and BUG-002. Every OutputParserException forces the `agent_query_analysis_fallback_used` transition (BUG-005), which drops collection scope and causes the 20-collection fan-out (BUG-002). Fixing BUG-003 (making the parser succeed on the first attempt) would break the causal chain and resolve BUG-002's Blocker impact without requiring any changes to the retrieval layer. Causal chain: **BUG-003** → BUG-005 → BUG-002 → `confidence_score=0, num_citations=0`.
