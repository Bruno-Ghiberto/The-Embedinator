# Interface Contract: NDJSON Streaming Events

**Feature**: Accuracy, Precision & Robustness Enhancements
**Date**: 2026-03-12 | **ADR Reference**: ADR-007

## Overview

This feature extends the existing `metadata` frame of the NDJSON streaming protocol to include groundedness information. No new event types are introduced. The change is backwards compatible — clients that do not read `groundedness` are unaffected.

## Existing Protocol (unchanged)

All `POST /api/chat` responses stream newline-delimited JSON (`application/x-ndjson`):

```
{"type": "chunk", "text": "..."}\n
{"type": "chunk", "text": "..."}\n
{"type": "metadata", "trace_id": "...", "confidence": 75, "citations": [...], "latency_ms": 1240}\n
```

Error frame:
```
{"type": "error", "message": "...", "code": "..."}\n
```

## Extended metadata Frame (this feature)

The `metadata` frame gains an optional `groundedness` object:

```json
{
  "type": "metadata",
  "trace_id": "uuid-v4",
  "confidence": 75,
  "groundedness": {
    "supported": 4,
    "unsupported": 1,
    "contradicted": 0,
    "overall_grounded": true
  },
  "citations": [
    {"index": 1, "chunk_id": "...", "source_file": "..."}
  ],
  "latency_ms": 1240
}
```

### groundedness field

| Field | Type | Description |
|-------|------|-------------|
| `supported` | `int` | Count of claims verified as SUPPORTED |
| `unsupported` | `int` | Count of claims annotated `[unverified]` |
| `contradicted` | `int` | Count of claims removed as contradicted |
| `overall_grounded` | `bool` | True if ≥50% of claims are supported |

### When groundedness is null

```json
{
  "type": "metadata",
  "trace_id": "uuid-v4",
  "confidence": 75,
  "groundedness": null,
  "citations": [...],
  "latency_ms": 1240
}
```

`groundedness` is `null` when:
- `groundedness_check_enabled = false` (operator disabled)
- GAV LLM call failed (graceful degradation)
- Answer has no verifiable claims

## Confidence Field Semantics (updated)

The `confidence` integer (0-100) in the metadata frame is now the **GAV-adjusted** value:
- When GAV runs successfully: `int(mean(sub_answer_scores) × confidence_adjustment)`
- When GAV is disabled or fails: `mean(sub_answer_scores)` (pre-adjustment)
- Always clamped to [0, 100]

## Citation Remapping

When `validate_citations` remaps or strips a citation, the `citations` array reflects the corrected state. Clients should treat the `citations` array in the metadata frame as authoritative — any citations that were invalid have already been corrected or removed before the frame is emitted.

## Backwards Compatibility

- `groundedness` field is new and optional; existing clients that ignore unknown fields are unaffected
- `confidence` semantics change slightly (GAV adjustment); the value remains int 0-100
- No new event `type` values introduced
- No changes to `chunk` frames or `error` frames
