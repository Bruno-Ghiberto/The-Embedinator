# ADR-007: SSE for Streaming Responses

**Status**: Accepted
**Date**: 2026-03-03
**Decision Makers**: Architecture Team

## Context

LLM responses can take 2-15 seconds for full generation. Without streaming, users stare at a blank screen. The system needs token-by-token delivery to minimize perceived latency.

## Decision

Use **Server-Sent Events (SSE)** via FastAPI's `StreamingResponse` with `text/event-stream` content type, forwarding LangGraph `astream_events()` to the browser.

Phase 1 implementation uses **NDJSON** (`application/x-ndjson`) as a simpler variant.

## Rationale

1. **Sub-500ms first token**: User sees the first token within 200-500ms of submitting a query
2. **Unidirectional simplicity**: SSE is simpler than WebSocket — no handshake complexity, no bidirectional state management
3. **Native browser support**: `EventSource` API and `ReadableStream` work in all modern browsers without a library
4. **Rich event types**: Separate event types (token, citation, confidence, meta_reasoning, done) enable progressive UI rendering
5. **LangGraph integration**: `astream_events()` is a native async generator — natural fit for SSE

## Alternatives Considered

| Alternative | Why Rejected |
|---|---|
| WebSocket | Bidirectional capability not needed; more complex connection lifecycle |
| Long polling | Higher latency; more server resources per request |
| gRPC streaming | Requires gRPC client in browser (gRPC-Web); adds complexity |
| Full response then send | Unacceptable perceived latency (2-15s blank screen) |

## Consequences

### Positive
- Eliminates perceived latency for large responses
- Citations rendered as separate events without waiting for full response
- Compatible with standard HTTP infrastructure (proxies, load balancers)

### Negative
- SSE connections are long-lived — proxy timeout configuration may be needed
- Error handling mid-stream requires special `{"type": "error"}` events
- Browser `EventSource` auto-reconnects on failure (may need to suppress)
