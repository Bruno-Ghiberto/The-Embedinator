# Data Model — Spec-30 (E2E Test v3, Single-Round Bug Hunt)

**Phase**: 1 (design & contracts)
**Date**: 2026-05-15

Five schemas govern the hunt's data trail. The first three (Bug Record, Bug Registry, Session Log) are the spec-31 input surface. The other two (Triage Document, BLOCKER-PATCHED Gate Decision Record) are closure-and-audit artifacts.

---

## Entity 1 — Bug Record (`bugs/BUG-XXX-short-slug.md`)

A single registered defect. One markdown file per bug under the session directory. Authored by the Bug Registrar (pane 5, Haiku) per orchestrator dispatch.

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | yes | Sequential, format `BUG-NNN` (zero-padded to 3 digits). Starts at next free ID after prior specs (BUG-024+ per spec-30 30-specify.md bug-ID rule) |
| `title` | string | yes | One-line, ≤80 chars, imperative or descriptive |
| `severity` | enum | yes | One of: `BLOCKER`, `CRITICAL`, `MAJOR`, `MINOR`, `COSMETIC` (FR-007) |
| `layer` | enum | yes | One of: `Frontend`, `Backend`, `Ingestion`, `Retrieval`, `Reasoning`, `Observability`, `Infrastructure` |
| `discovered_at` | ISO-8601 timestamp | yes | UTC; format `YYYY-MM-DDTHH:MM:SSZ` |
| `phase` | int | yes | 1–7 (which hunt phase surfaced it) |
| `scenario_id` | string | yes | Format `P<N>-S<M>` referencing the playbook scenario; `P0-S0` for off-script discoveries |
| `reproduction_steps` | list[string] | yes | Numbered, ≥1 step (FR-006) |
| `expected` | string | yes | One sentence (FR-006) |
| `actual` | string | yes | One sentence; verbatim error included if applicable (FR-006) |
| `artifacts` | object | yes | Path references — see "Artifact references" below |
| `root_cause_hypothesis` | string | no | 1–3 sentences; may be empty at discovery, populated by Root-Cause Investigator later |
| `blocker_patched` | object | yes | Block — see "BLOCKER-PATCHED block" below; `applied: false` default |
| `triage` | object | no | Required for MAJOR-or-higher at Phase 8 closure (FR-015); see "Triage block" below |
| `notes` | string | no | Free-form. Used for: (a) severity-disagreement records per spec Edge Cases; (b) intermittent-defect markers in the format `intermittent — last seen YYYY-MM-DDTHH:MM:SSZ` for defects visible at first observation but not subsequently reproducible (per spec Edge Case "Pilot cannot reproduce a defect that was visible earlier") |

### Artifact references

```yaml
artifacts:
  screenshot: "screenshots/BUG-024.png"          # GITIGNORED path
  log: "logs/BUG-024.log"                        # GITIGNORED path
  trace: null                                    # GITIGNORED if present
  public_evidence: "public-evidence/BUG-024-redacted.png"  # TRACKED, post-Phase-8, optional
```

Paths use the dated session directory as root. At least one of `screenshot`, `log`, `trace` MUST be non-null. `public_evidence` MUST be null at discovery time; only populated during Phase 8 curation after Pilot verification (FR-027 + FR-028).

### BLOCKER-PATCHED block

```yaml
blocker_patched:
  applied: false                                       # true only after Pilot Y/N + Inline Fixer commits
  commit_sha: null                                     # string when applied; cross-ref to session-log gate entry
  pilot_authorization_timestamp: null                  # ISO-8601 when applied; matches session-log entry
  patch_summary: null                                  # one-paragraph description when applied
```

Constraints (enforced by JSON schema in `contracts/bug-registry-schema.md`):

- `applied=true` REQUIRES all three other fields non-null.
- `applied=true` does NOT downgrade severity (FR-013) — the defect remains in its original severity for spec-31 to properly fix.

### Triage block

```yaml
triage:
  decision: "v1.0-fix"                                 # one of: v1.0-fix, v1.1-defer
  github_issue_url: "https://github.com/.../issues/N"  # non-null required for MAJOR+ per FR-015
  rationale: "one sentence why this decision"
```

Constraints:

- For severity ∈ {BLOCKER, CRITICAL, MAJOR}: triage block REQUIRED at hunt close.
- For severity ∈ {MINOR}: triage OPTIONAL; if present, may use `v1.1-defer` without issue URL.
- For severity = COSMETIC: triage OMITTED (v1.1 backlog without issue).

### State transitions

```
[new] → (severity + reproduction captured at discovery, FR-008)
[new] → [triaged]   on Phase 8 closure for MAJOR+
[new] → [patched]   on Pilot Y/N approval of BLOCKER-PATCHED + commit lands
[patched] → [triaged]   on Phase 8 (patched bugs still get triage decision for spec-31 follow-up)
```

There is NO `[fixed]` or `[closed]` state at the bug-record level — fix-and-close lifecycle is spec-31's concern.

---

## Entity 2 — Bug Registry (`bugs-registry.json`)

The machine-readable rollup of all bug records, consumed by spec-31. Single JSON file per session directory. Authored by Bug Registrar at Phase 8 (FR-009, FR-023, SC-008).

### Top-level structure

```json
{
  "schema_version": "1.0.0",
  "session": { ... },
  "bugs": [ ... ],
  "summary": { ... }
}
```

### `session` object

```json
{
  "spec": "030-e2e-test-v3",
  "round": 1,
  "started": "2026-05-NNTHH:MM:SSZ",
  "closed": "2026-05-NNTHH:MM:SSZ",
  "develop_sha_at_start": "abc123...",
  "develop_sha_at_close": "def456...",
  "pilot": "Bruno Ghiberto"
}
```

`closed - started ≤ 12h` validates SC-001.

### `bugs[]` array

Each entry mirrors the Bug Record markdown but in JSON form:

```json
{
  "id": "BUG-024",
  "title": "Citation tooltip stalls on Spanish-accent characters",
  "severity": "CRITICAL",
  "layer": "Frontend",
  "phase": 3,
  "scenario_id": "P3-S2",
  "discovered_at": "2026-05-NNTHH:MM:SSZ",
  "reproduction_steps": [
    "Open chat with at least one queryable NAG doc",
    "Ask Q-001 (...)",
    "Hover citation [1] in the streamed response"
  ],
  "expected": "Tooltip shows passage text within 200ms",
  "actual": "Tooltip blanks; console shows 'Cannot read property of undefined'",
  "artifacts": {
    "screenshot": "screenshots/BUG-024.png",
    "log": "logs/BUG-024.log",
    "trace": null,
    "public_evidence": "public-evidence/BUG-024-redacted.png"
  },
  "root_cause_hypothesis": "Spanish accent encoding mismatch between citation index and passage store",
  "blocker_patched": {
    "applied": false,
    "commit_sha": null,
    "pilot_authorization_timestamp": null,
    "patch_summary": null
  },
  "triage": {
    "decision": "v1.0-fix",
    "github_issue_url": "https://github.com/Bruno-Ghiberto/The-Embedinator/issues/123",
    "rationale": "Citation reliability is core to portfolio quality"
  }
}
```

### `summary` object

```json
{
  "counts_by_severity": {
    "BLOCKER": 0,
    "CRITICAL": 1,
    "MAJOR": 4,
    "MINOR": 7,
    "COSMETIC": 3
  },
  "blocker_patched_count": 0,
  "v1_0_fix_count": 5,
  "v1_1_defer_count": 6
}
```

Derived from `bugs[]` at close. JSON schema (in `contracts/bug-registry-schema.md`) validates that `summary` reflects the actual `bugs[]` contents.

### Validation

`bugs-registry.json` MUST validate against the JSON schema in `contracts/bug-registry-schema.md` (SC-008). The Phase 8 closure step runs:

```bash
python -c "import json, jsonschema; \
  data = json.load(open('docs/E2E/.../bugs-registry.json')); \
  schema = json.load(open('specs/030-e2e-test-v3/contracts/bug-registry-schema.json')); \
  jsonschema.validate(data, schema)"
```

Schema violation blocks hunt closure.

---

## Entity 3 — Session Log (`session-log.md`)

Chronological timeline of every Pilot observation, orchestrator dispatch, and discovered defect. Single markdown file per session, append-only. Authored across multiple panes — Bug Registrar holds primary write authority but the orchestrator and Pilot may both append.

### Line format

```
[YYYY-MM-DD HH:MM:SS] <pane-role> | <category> | <free-text>
```

### Pane roles

`Pilot` | `Orchestrator` | `LogAnalyst` | `FrontendInspector` | `BugRegistrar` | `RootCauseInvestigator` | `InlineFixer`

### Categories

| Category | Purpose | Example |
|---|---|---|
| `phase-transition` | Phase boundary | `Phase 0 closed → Phase 1 open` |
| `observation` | Pilot's relay of what they see | `Pilot \| observation \| Dashboard health badge green but /healthz returns 503` |
| `dispatch` | Orchestrator spawning a sub-agent | `Orchestrator \| dispatch \| Spawning Log Analyst to correlate /healthz vs dashboard 60s window` |
| `discovery` | A new bug is registered | `BugRegistrar \| discovery \| BUG-024 registered: CRITICAL, Frontend, P1-S3` |
| `triage` | Phase 8 triage decision | `Orchestrator \| triage \| BUG-024 → v1.0-fix, issue #123` |
| `gate` | BLOCKER-PATCHED orchestrator prompt or Pilot response | See "Entity 5" |
| `secret-scan-verify` | Pilot artifact-redaction verification | `Pilot \| secret-scan-verify \| Promoted screenshots/BUG-024.png → public-evidence/BUG-024-redacted.png; verified zero secrets, redacted [120,340]-[540,380]` |
| `closure-step` | Phase 8 closure milestone | `Orchestrator \| closure-step \| SUMMARY.md drafted, awaiting peer-review` |

### Ordering and integrity

- Append-only. No edits to prior lines.
- One line per event. Multi-event observations are split into multiple lines.
- Timestamps in local time but suffixed with UTC offset on session-open and session-close lines.

---

## Entity 4 — Triage Document (`triage.md`)

Phase 8 severity rollup. One markdown file. Authored by orchestrator at closure.

### Required sections

```markdown
## Severity Rollup

| Severity | Count | Filed in registry | Triaged |
|---|---|---|---|
| BLOCKER | 0 | 0 | 0 |
| CRITICAL | 1 | 1 | 1 (1 v1.0-fix, 0 v1.1-defer) |
| MAJOR | 4 | 4 | 4 (3 v1.0-fix, 1 v1.1-defer) |
| MINOR | 7 | 7 | optional |
| COSMETIC | 3 | 3 | omitted |

## MAJOR-or-Higher Triage Decisions

| ID | Severity | Layer | Decision | Issue | Rationale |
|---|---|---|---|---|---|
| BUG-024 | CRITICAL | Frontend | v1.0-fix | #123 | ... |
| BUG-025 | MAJOR | Backend | v1.1-defer | #124 | ... |

## BLOCKER-PATCHED Log

| ID | Commit SHA | Pilot Y/N timestamp | Patch summary |
|---|---|---|---|
| _none_ | | | |

## Exit Criterion Check (FR-014, FR-015)

- [ ] All CRITICAL filed with complete records (SC-002)
- [ ] All MAJOR-or-higher have triage decision with GitHub issue URL (SC-003)
- [ ] All BLOCKER-PATCHED entries have Pilot Y/N capture in session-log (SC-005)
- [ ] `git diff develop -- backend/ frontend/ ingestion-worker/` empty OR matches BLOCKER-PATCHED commits (SC-006)
- [ ] `rg -i 'sk-(test|live|proj)|api[_-]?key\\s*=' docs/E2E/.../*.md docs/E2E/.../bugs/ docs/E2E/.../public-evidence/` zero hits (SC-012)
```

---

## Entity 5 — BLOCKER-PATCHED Gate Decision Record

Not a standalone file — inline in `session-log.md` AND in the affected bug record's `blocker_patched` block. Documents the rare BLOCKER-PATCHED inline-fix gate (FR-011, FR-012, FR-013, FR-016, SC-005).

### Session-log capture format

```
[YYYY-MM-DD HH:MM:SS] Orchestrator | gate | BLOCKER-PATCHED proposal for BUG-XXX:
  Defect: <one-line summary>
  Severity: BLOCKER
  Proposed patch: <one-paragraph diff sketch with file paths>
  Patch scope: MINOR | COSMETIC                       # NEVER MAJOR or higher
  Estimated time: <minutes, ≤5>                       # ≤5min required per FR-011
  Risk assessment: zero-risk because <one sentence>
  Pilot decision: [Y / N]
[YYYY-MM-DD HH:MM:SS] Pilot | gate | Y                # or N
   — <optional one-line rationale>
```

Constraints (enforced in plan + contracts):

- `Patch scope` MUST be `MINOR` or `COSMETIC` (FR-011 narrow exception).
- `Estimated time` MUST be ≤5 minutes.
- `Risk assessment` MUST cite a concrete reason (e.g., "single-line CSS change, no logic", "logging-format-only, no behavior change").
- Pilot decision MUST be exactly `Y` or `N` on a separate timestamped line.
- If `N`: orchestrator pauses, registers BUG, descopes phase or closes hunt early. NO retry of the same proposal.
- If `Y`: Inline Fixer dispatched with explicit prompt; commit lands within the estimated time; bug record `blocker_patched` block populated.

### Cross-references

- Bug record `blocker_patched.pilot_authorization_timestamp` MUST equal the Pilot line's timestamp.
- Bug record `blocker_patched.commit_sha` MUST be the SHA of the inline-fix commit.
- These cross-references are validated by the JSON schema during Phase 8 closure.

---

## Identity & Uniqueness Rules

- **Bug IDs**: Sequential `BUG-NNN`, globally unique across all hunt rounds (spec-21/26/28/30 history). Starting value for spec-30 = highest prior ID + 1. Bug Registrar polls existing IDs at Phase 0 and writes the starting value to `session-log.md`.
- **GitHub issue numbers**: assigned by GitHub at `gh issue create` time; recorded in `triage.github_issue_url` and `triage.md`.
- **Session directory name**: `docs/E2E/YYYY-MM-DD-round-1-bug-hunt/` — date is the Phase 0 calendar date. Single session, single directory; spec-30 is single-round so `round-1` is invariant for this spec.

---

## Validation Summary

| Schema | Validator | Trigger | Blocks |
|---|---|---|---|
| Bug record markdown | Manual review at registration | Per bug | Hunt continuation |
| Bug registry JSON | `jsonschema` against `contracts/bug-registry-schema.json` | Phase 8 closure | Hunt closure (SC-008) |
| Session log line format | Manual review (regex-checkable) | Continuous | Audit only — not a closure gate |
| Triage document | Manual review | Phase 8 closure | Hunt closure (FR-015) |
| BLOCKER-PATCHED record | JSON schema (embedded in bug registry schema) | Phase 8 closure | Hunt closure (SC-005) |
