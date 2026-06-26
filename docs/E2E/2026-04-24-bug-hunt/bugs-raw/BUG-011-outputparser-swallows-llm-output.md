# BUG-011: OutputParserException swallows raw LLM output — root-cause diagnosis impossible

- **Severity**: Minor
- **Layer**: Observability
- **Discovered**: 2026-04-28 14:50 UTC via Log scan (A5 Charter 1 — present on all 9/9 traced sessions)

## Steps to Reproduce

1. Stack up and issue any query (OutputParserException fires on 100% of requests — see BUG-003).
2. Observe backend logs: `agent_rewrite_query_first_attempt_failed` fires with `error=OutputParserException`.
3. Attempt to diagnose WHY parsing failed by searching for the raw LLM output in logs.
4. Observe: raw LLM output is not logged anywhere. The exception handler silently discards it.

## Expected

When `OutputParserException` fires in the `query_rewriter` node, the raw LLM output that failed to parse should be captured in a warning-level log event (e.g., `raw_llm_output_unparseable`). This allows engineers to determine whether the failure is due to malformed JSON, wrong schema fields, truncated output, or hallucinated field names — which is essential for fixing BUG-003.

## Actual

structlog only emits:
```
agent_rewrite_query_first_attempt_failed component=backend.agent.nodes error=OutputParserException session_id=... trace_id=...
```
The raw LLM output that triggered the exception is not captured anywhere. Without this, the root cause of BUG-003 cannot be diagnosed from logs alone — code inspection of `backend/agent/nodes.py` (query_rewriter node, OutputParser invocation) is required to see what format the parser expects, and a live debug session would be needed to capture actual model output.

## Artifacts

- Trace IDs (all show same log gap): `fc5518e8`, `d01799b7`, `2cb0daa4`, `dbc3da00`, `4c62606d`, `d073a61b`, `f85602ba`, `03a9018d`, `ab12fe4b` (9/9 Charter 1 sessions)
- File ref: `backend/agent/nodes.py` — query_rewriter node's exception handler; look for the `try/except OutputParserException` block where `logger.warning("agent_rewrite_query_first_attempt_failed", ...)` is called without `raw=response.content`

## Root-cause hypothesis

The `OutputParserException` handler in `backend/agent/nodes.py` logs the error class name but does not capture the underlying LLM response content. Adding `raw_output=str(e.llm_output)` (or equivalent, depending on the LangChain `OutputParserException` attributes) to the warning log call would provide full diagnostic context at zero runtime cost. This is a one-line fix in the exception handler and is independent of fixing BUG-003 itself — it makes BUG-003 diagnosable without code changes to the parser.

**Cross-reference**: BUG-003 (the OutputParserException firing — this bug is the companion observability gap for diagnosing it).

**Proposed fix**:
```python
# In query_rewriter node's except OutputParserException block:
logger.warning(
    "agent_rewrite_query_first_attempt_failed",
    error="OutputParserException",
    raw_llm_output=getattr(e, 'llm_output', str(e)),  # capture raw output
    session_id=state["session_id"],
    trace_id=state["trace_id"],
)
```
