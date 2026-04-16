# Contract: Human-in-the-Loop Protocol

**Version**: 1.0 | **Spec**: 025-master-debug

## Purpose

Defines the interaction protocol between the CEO agent and the human tester. The CEO directs; the human executes browser actions. This protocol ensures consistent, repeatable test execution with clear evidence capture.

## The ACTION/OBSERVE/LOG CHECK/EXPECTED Cycle

Every test action follows this 4-step cycle:

```
CEO:       ACTION: [Precise instruction for the human to execute in the browser]
HUMAN:     [Executes the action and reports what they see]
CEO:       LOG CHECK: [Docker command to inspect logs]
           Expected: [What the logs should show]
CEO:       OBSERVE: [Specific questions about what the human sees]
HUMAN:     [Reports observations]
CEO:       EXPECTED: [Comparison with expected behavior] --- PASS/FAIL.
           [Saves finding to Engram if notable]
```

## Protocol Rules

### What the CEO Does

1. **Issues ACTION instructions** with exact URLs, exact query text, exact click targets.
2. **Inspects Docker logs** after every human action via Docker MCP.
3. **Asks specific OBSERVE questions** --- not open-ended "what do you see?" but "Does the response stream character by character? How many citations appear below the response?"
4. **Evaluates PASS/FAIL** against the expected behavior defined in the FR.
5. **Persists findings** to Engram using the phase's topic key.
6. **Creates bug reports** when FAIL is determined.
7. **Escalates CRITICAL findings** to S3 (CTO) immediately.

### What the CEO Does NOT Do

1. **Never asks the human to run terminal commands** --- the CEO handles all CLI/Docker operations.
2. **Never skips the LOG CHECK step** --- even if the human reports success, logs must be verified.
3. **Never advances to the next test without recording the result** (PASS/FAIL + evidence).
4. **Never advances to the next phase without a PhaseSummary** (NFR-003).

### What the Human Does

1. **Executes browser actions** as directed (navigate, click, type, observe).
2. **Reports observations** honestly and specifically (not "it worked" but "text streamed in over 3 seconds, 4 citations appeared, confidence shows 72%").
3. **Takes screenshots** when requested by the CEO.
4. **Reports errors** immediately (blank page, console error, unexpected behavior).
5. **Does NOT interpret results** --- the CEO evaluates PASS/FAIL. The human provides raw observations.

### What the Human Does NOT Do

1. **Never runs terminal commands** --- the CEO handles all infrastructure interactions.
2. **Never self-diagnoses** bugs --- the CEO and agents handle investigation.
3. **Never skips actions** without informing the CEO.
4. **Never modifies application code** --- this is a testing-only spec (NFR-001).

## Communication Format Examples

### Example 1: Chat E2E Test

```
CEO:       ACTION: Open http://localhost:3000/chat in your browser.
           Select the "test-docs" collection from the sidebar dropdown.
           Type the following query into the chat input:
           "What are the key differences between dense and sparse retrieval?"
           Press Enter.