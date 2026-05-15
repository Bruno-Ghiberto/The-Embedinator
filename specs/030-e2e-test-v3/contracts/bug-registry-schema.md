# Contract — Bug Registry JSON Schema

**Spec**: 030-e2e-test-v3
**Phase**: 1
**Status**: locked — spec-31 consumes this schema

The machine-readable bug registry (`bugs-registry.json`) is the primary spec-31 input. Schema-validation is a Phase 8 closure gate (SC-008). A schema-invalid registry blocks hunt closure.

## JSON Schema (Draft 2020-12)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://github.com/Bruno-Ghiberto/The-Embedinator/specs/030-e2e-test-v3/contracts/bug-registry-schema.json",
  "title": "Spec-30 Bug Registry",
  "type": "object",
  "required": ["schema_version", "session", "bugs", "summary"],
  "additionalProperties": false,
  "properties": {
    "schema_version": {
      "type": "string",
      "const": "1.0.0",
      "description": "Pinned to 1.0.0 for spec-30 round 1. Future hunt rounds may bump."
    },
    "session": {
      "type": "object",
      "required": ["spec", "round", "started", "closed", "develop_sha_at_start", "develop_sha_at_close", "pilot"],
      "additionalProperties": false,
      "properties": {
        "spec": {"type": "string", "const": "030-e2e-test-v3"},
        "round": {"type": "integer", "const": 1},
        "started": {"type": "string", "format": "date-time"},
        "closed": {"type": "string", "format": "date-time"},
        "develop_sha_at_start": {"type": "string", "pattern": "^[0-9a-f]{7,40}$"},
        "develop_sha_at_close": {"type": "string", "pattern": "^[0-9a-f]{7,40}$"},
        "pilot": {"type": "string", "minLength": 1}
      }
    },
    "bugs": {
      "type": "array",
      "items": {"$ref": "#/$defs/bug"}
    },
    "summary": {
      "type": "object",
      "required": ["counts_by_severity", "blocker_patched_count", "v1_0_fix_count", "v1_1_defer_count"],
      "additionalProperties": false,
      "properties": {
        "counts_by_severity": {
          "type": "object",
          "required": ["BLOCKER", "CRITICAL", "MAJOR", "MINOR", "COSMETIC"],
          "additionalProperties": false,
          "properties": {
            "BLOCKER": {"type": "integer", "minimum": 0},
            "CRITICAL": {"type": "integer", "minimum": 0},
            "MAJOR": {"type": "integer", "minimum": 0},
            "MINOR": {"type": "integer", "minimum": 0},
            "COSMETIC": {"type": "integer", "minimum": 0}
          }
        },
        "blocker_patched_count": {"type": "integer", "minimum": 0},
        "v1_0_fix_count": {"type": "integer", "minimum": 0},
        "v1_1_defer_count": {"type": "integer", "minimum": 0}
      }
    }
  },
  "$defs": {
    "bug": {
      "type": "object",
      "required": [
        "id", "title", "severity", "layer", "phase", "scenario_id",
        "discovered_at", "reproduction_steps", "expected", "actual",
        "artifacts", "blocker_patched"
      ],
      "additionalProperties": false,
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^BUG-[0-9]{3}$"
        },
        "title": {
          "type": "string",
          "minLength": 1,
          "maxLength": 80
        },
        "severity": {
          "type": "string",
          "enum": ["BLOCKER", "CRITICAL", "MAJOR", "MINOR", "COSMETIC"]
        },
        "layer": {
          "type": "string",
          "enum": ["Frontend", "Backend", "Ingestion", "Retrieval", "Reasoning", "Observability", "Infrastructure"]
        },
        "phase": {
          "type": "integer",
          "minimum": 1,
          "maximum": 7
        },
        "scenario_id": {
          "type": "string",
          "pattern": "^P[0-7]-S[0-9]+$"
        },
        "discovered_at": {
          "type": "string",
          "format": "date-time"
        },
        "reproduction_steps": {
          "type": "array",
          "minItems": 1,
          "items": {"type": "string", "minLength": 1}
        },
        "expected": {"type": "string", "minLength": 1},
        "actual": {"type": "string", "minLength": 1},
        "artifacts": {
          "type": "object",
          "required": ["screenshot", "log", "trace", "public_evidence"],
          "additionalProperties": false,
          "properties": {
            "screenshot": {"type": ["string", "null"], "pattern": "^screenshots/"},
            "log": {"type": ["string", "null"], "pattern": "^logs/"},
            "trace": {"type": ["string", "null"], "pattern": "^traces/"},
            "public_evidence": {"type": ["string", "null"], "pattern": "^public-evidence/"}
          },
          "anyOf": [
            {"required": ["screenshot"], "properties": {"screenshot": {"type": "string"}}},
            {"required": ["log"], "properties": {"log": {"type": "string"}}},
            {"required": ["trace"], "properties": {"trace": {"type": "string"}}}
          ]
        },
        "root_cause_hypothesis": {
          "type": ["string", "null"]
        },
        "blocker_patched": {
          "type": "object",
          "required": ["applied", "commit_sha", "pilot_authorization_timestamp", "patch_summary"],
          "additionalProperties": false,
          "properties": {
            "applied": {"type": "boolean"},
            "commit_sha": {"type": ["string", "null"], "pattern": "^[0-9a-f]{7,40}$"},
            "pilot_authorization_timestamp": {"type": ["string", "null"], "format": "date-time"},
            "patch_summary": {"type": ["string", "null"]}
          },
          "allOf": [
            {
              "if": {"properties": {"applied": {"const": true}}},
              "then": {
                "required": ["commit_sha", "pilot_authorization_timestamp", "patch_summary"],
                "properties": {
                  "commit_sha": {"type": "string"},
                  "pilot_authorization_timestamp": {"type": "string"},
                  "patch_summary": {"type": "string"}
                }
              }
            }
          ]
        },
        "triage": {
          "type": "object",
          "required": ["decision", "github_issue_url", "rationale"],
          "additionalProperties": false,
          "properties": {
            "decision": {
              "type": "string",
              "enum": ["v1.0-fix", "v1.1-defer"]
            },
            "github_issue_url": {
              "type": ["string", "null"],
              "pattern": "^https://github\\.com/[^/]+/[^/]+/issues/[0-9]+$"
            },
            "rationale": {"type": "string", "minLength": 1}
          }
        },
        "notes": {
          "type": ["string", "null"]
        }
      },
      "allOf": [
        {
          "description": "MAJOR-or-higher MUST have triage block with non-null issue URL per FR-015",
          "if": {
            "properties": {"severity": {"enum": ["BLOCKER", "CRITICAL", "MAJOR"]}}
          },
          "then": {
            "required": ["triage"],
            "properties": {
              "triage": {
                "required": ["github_issue_url"],
                "properties": {
                  "github_issue_url": {"type": "string"}
                }
              }
            }
          }
        }
      ]
    }
  }
}
```

A canonical copy of this schema MUST be checked in as `specs/030-e2e-test-v3/contracts/bug-registry-schema.json` (the literal JSON file referenced by the validator at Phase 8). The fenced block above is the source of truth for the schema's shape.

## Validation invocation (Phase 8)

```bash
python -c "
import json
from jsonschema import Draft202012Validator
data = json.load(open('docs/E2E/<DATE>-round-1-bug-hunt/bugs-registry.json'))
schema = json.load(open('specs/030-e2e-test-v3/contracts/bug-registry-schema.json'))
v = Draft202012Validator(schema)
errors = sorted(v.iter_errors(data), key=lambda e: e.path)
if errors:
    for e in errors:
        print(f'{list(e.path)}: {e.message}')
    raise SystemExit(1)
print('bugs-registry.json: VALID')
"
```

Exit code 0 = valid; non-zero = invalid → Phase 8 closure blocked.

## Spec-31 contract guarantees (what spec-31 can rely on)

Given a schema-valid `bugs-registry.json`, spec-31 can rely on:

1. Every bug has a unique `id` matching `BUG-NNN`.
2. Every BLOCKER, CRITICAL, MAJOR bug has a `triage.github_issue_url` (non-null) — no dead-end findings.
3. Every `blocker_patched.applied=true` entry has a verifiable `commit_sha` (so spec-31 can `git show` to understand the unblock-patch's intent).
4. Severity values are from the closed set; no free-text drift.
5. `phase` and `scenario_id` allow spec-31 to group fixes by hunt phase if useful.
6. `summary.counts_by_severity` totals MUST equal the actual counts in `bugs[]` — spec-31 may rely on the summary for triage prioritization without re-counting.

## Future schema evolution

`schema_version` is pinned to `1.0.0` for spec-30 round 1. If a future hunt round (v1.1+) needs additional fields:

- Backwards-compatible additions (new optional fields, new optional enum values): bump to `1.0.X`.
- Backwards-incompatible (removing fields, changing required, restricting enums): bump to `2.0.0`. Spec-31 MUST be updated in lockstep.

The schema lives under the spec directory so version pinning travels with the spec.
