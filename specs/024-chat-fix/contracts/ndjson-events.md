# NDJSON Streaming Contract (Reference)

**Feature**: 024-chat-fix | **Status**: NO CHANGES — this is a reference document

The NDJSON streaming contract is defined by Constitution Principle VI (ADR-007). This spec does NOT modify the contract. This document records the event types for agent reference.

## Event Types

| Type | Schema | When Emitted |
|------|--------|-------------|
| `session` | `{"type": "session", "session_id": string}` | First event, before graph processing |
| `status` | `{"type": "status", "node": string}` | When a new graph node begins execution |
| `chunk` | `{"type": "chunk", "text": string}` | Token-level or batch text from `collect_answer` node or `final_response` fallback |
| `citation` | `{"type": "citation", "citations": Citation[]}` | After graph completes, before `done` |
| `confidence` | `{"type": "confidence", "score": int}` | 0-100 integer, after citations |
| `groundedness` | `{"type": "groundedness", "overall_grounded": bool, "supported": int, "unsupported": int, "contradicted": int}` | After confidence |
| `done` | `{"type": "done", "latency_ms": int, "trace_id": string}` | Final event on success |
| `error` | `{"type": "error", "message": string, "code": string, "trace_id": string}` | On failure |
| `clarification` | `{"type": "clarification", "question": string}` | When graph requests user input |

## BUG-017 Impact

The `citation` event's `citations` array will be deduplicated by `passage_id` before emission. The schema is unchanged — only the content is cleaned (no duplicate entries). This is NOT a contract change.
