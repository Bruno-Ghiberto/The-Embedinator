# Contract: Bug Report Template

**Version**: 1.0 | **Spec**: 025-master-debug

## Purpose

Every bug found during Spec-25 testing MUST follow this exact template. This ensures consistent, actionable bug reports that a developer can pick up and fix without additional context.

## Template

```markdown
### BUG-XXX: [Descriptive Title]

- **Severity**: P0-CRITICAL / P1-HIGH / P2-MEDIUM / P3-LOW
- **Phase**: P{N} ({Phase Name})
- **Component**: Backend / Frontend / Infrastructure / Inference Service / Vector Database
- **Affected Spec**: Spec-{NN} ({spec name})
- **Steps to Reproduce**:
  1. [Exact step]
  2. [Exact step]
  3. [Observe]
- **Expected Behavior**: [What should happen]
- **Actual Behavior**: [What actually happened]
- **Log Evidence**:
  ```
  [Relevant log lines with timestamps. Use code blocks.]
  ```
- **Root Cause Analysis**: [Best assessment. "Unknown" if unclear --- assign to S1.]
- **Fix Recommendation**: [Concrete suggestion for resolution]
- **Regression Test**: [What automated test should be added to prevent recurrence]
- **Screenshots**: [If applicable, reference screenshot path]
```

## Severity Classification

| Severity | Definition | Escalation | Examples |
|----------|-----------|------------|----------|
| P0-CRITICAL | Core functionality broken, data loss, security vulnerability | Immediate escalation to S3 (CTO). Blocks release. | Chat crashes, DB corruption, XSS execution, data loss |
| P1-HIGH | Major feature broken, significant UX degradation | Documented prominently. High priority fix. | Citations always wrong, dark mode unusable, session loss |
| P2-MEDIUM | Feature partially broken, workaround exists | Normal priority. Fix recommended. | Slow response, minor UI glitch, excessive log noise |
| P3-LOW | Cosmetic or minor annoyance | Low priority. Fix at convenience. | Alignment off, unnecessary warning, edge case workaround |

## Validation Rules

1. **All fields required** except `Log Evidence` (optional for UI-only bugs) and `Screenshots` (optional).
2. **Bug IDs are globally sequential** --- BUG-001, BUG-002, etc. across all phases. Not per-phase.
3. **Steps to Reproduce must have at least 2 steps** --- one action and one observation.
4. **Root Cause Analysis** of "Unknown" triggers automatic assignment to S1 (Root Cause Analyst) for investigation.
5. **Fix Recommendation** must be concrete --- "fix the bug" is not acceptable. Specify which file, function, or behavior needs to change.
6. **Regression Test** must describe a specific test scenario, not "add a test."

## Engram Persistence

Bugs are persisted to `spec-25/bugs` as a running registry, updated after each phase.

## Example

```markdown
### BUG-001: Chat response shows infinite spinner when Ollama model not loaded

- **Severity**: P1-HIGH
- **Phase**: P2 (Core Functionality Sweep)
- **Component**: Backend
- **Affected Spec**: Spec-02 (Conversation Graph)
- **Steps to Reproduce**:
  1. Switch to a model that is not yet pulled (e.g., "nonexistent:latest") via settings API.
  2. Send a chat query via the browser UI.
  3. Observe the chat interface.
- **Expected Behavior**: Error message displayed to user within 5 seconds indicating the model is not available.
- **Actual Behavior**: Infinite spinner with no error message. Backend log shows "model not found" but no error event is sent to the frontend.
- **Log Evidence**:
  ```
  2026-03-31T14:23:15.123Z ERROR backend - model not found: nonexistent:latest
  2026-03-31T14:23:15.124Z ERROR backend - ConnectionError: Ollama returned 404
  ```
- **Root Cause Analysis**: The chat endpoint catches the Ollama 404 but does not emit an NDJSON error frame. The frontend waits indefinitely for a "done" event that never arrives.
- **Fix Recommendation**: In `backend/agent/nodes.py`, the LLM call node should catch model-not-found errors and emit `{"type": "error", "message": "Model not available", "code": "MODEL_NOT_FOUND"}` before ending the stream.
- **Regression Test**: E2E test that sets an invalid model name, sends a query, and asserts an error event appears in the NDJSON stream within 10 seconds.
- **Screenshots**: N/A
```
