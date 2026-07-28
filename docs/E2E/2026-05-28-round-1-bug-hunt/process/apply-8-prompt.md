# apply-8 — Phase 8 Closure & Registry Freeze

**Change**: `single-round-bug-hunt` · **Branch**: `030-e2e-test-v3`
**Runs**: after verify-7 PASS. Plain Claude context — the Agent Teams roster may be torn down.
**Source runbook**: `specs/030-e2e-test-v3/phase-playbook.md` §Phase 8, steps 8.1–8.11
(speckit task ids T068–T082). SDD task **T-019**.
**Close commit**: `chore(spec-30-r1): close hunt registry`

This is the commit that unblocks spec-31. R-006 defines success as five conditions holding
simultaneously; verify-8 checks all of them.

---

## Known state going in (measured 2026-07-28, pre-Phase-7)

- 94 records + whatever Phase 7 added. `next-bug-id.txt` tracks the sequence.
- The registry parser and validator are proven: `scratchpad/build_registry.py` +
  `scratchpad/validate.py`, with `jsonschema` 4.26 in `scratchpad/.validator/`
  (isolated venv — `jsonschema` is NOT installed in the project env, do not add it there).
- Pre-Phase-7 the validator reported exactly **59 violations**: 45 missing `triage`,
  10 `title` > 80 chars, 4 `scenario_id` pattern failures. The 14 non-triage ones were
  remediated during the Phase-7 close. Re-run the validator; do not assume.
- `public-evidence/` contains only `.gitkeep`. **FR-027 requires ≥1 tracked evidence artifact
  per CRITICAL**, and every raw artifact under `logs/ screenshots/ traces/` is gitignored.
  This is the single largest piece of genuine work in Phase 8.

---

## Steps

### 8.1 — Triage audit (should already be discharged)
Confirm every BLOCKER/CRITICAL/MAJOR record has `decision` ∈ {v1.0-fix, v1.1-defer}, a real
`github_issue_url`, and a non-empty rationale. Spot-check that URLs resolve. If any gap remains,
verify-7 should have caught it — treat a gap here as a verify-7 escape and say so.

### 8.2 — `public-evidence/` curation (FR-027, FR-028, SC-012)
For each BLOCKER + CRITICAL (9 pre-Phase-7), promote at least one artifact into
`public-evidence/`. **Prefer text** — log excerpts, trace JSON, SQL output — because text can be
scanned and redacted verifiably; screenshots cannot. Take a screenshot only where it is trivially
safe and adds something text cannot.

For every promoted file, before it is staged:
- scan for `sk-` key shapes, `gAAAAA` Fernet ciphertext, bearer tokens, base64 credential
  shapes, and absolute `/home/<user>/...` paths;
- record a `secret-scan-verify:` line in `session-log.md` naming the file and the result.
  FR-028 requires the verification to be *documented*, not merely performed.

The `providers` table holds a real Fernet ciphertext for the seeded `openai` row. It must never
be promoted, quoted, or paraphrased into a tracked file.

Then update each affected record's `## Artifacts` to point at the `public-evidence/` path
(schema pattern: `^public-evidence/`). bug-registrar is still the sole writer.

### 8.3 — Build `bugs-registry.json` (SC-008)
Rebuild from the `bugs/` directory — never patch incrementally. The directory is the source of
truth; the JSON is a derived view.

```
python3 scratchpad/build_registry.py \
  --out docs/E2E/2026-05-28-round-1-bug-hunt/bugs-registry.json \
  --started 2026-06-02T00:00:00Z --closed <ISO-8601 now> \
  --sha-start 3d8d5ff --sha-close <origin/develop sha now> \
  --pilot "<see below>"
```

`session.pilot` must be honest about the split: phases 0–6 human-driven by Bruno Ghiberto,
phases 7–8 autonomous under amendment R-007. Do not write a single name that implies otherwise.

### 8.4 — Validate (SC-008, hard gate)
```
scratchpad/.validator/bin/python scratchpad/validate.py \
  docs/E2E/2026-05-28-round-1-bug-hunt/bugs-registry.json
```
**0 violations required.** Any violation names a field path and a schema rule — fix the RECORD,
then rebuild. Never hand-edit the JSON to make it pass; that decouples it from the directory.

### 8.5 — `triage.md`
Severity counts, the v1.0-fix / v1.1-defer split, and the fix-wave scope grouped by layer. This
is the document spec-31 is planned from, so order v1.0-fix items by blast radius, not by ID.

### 8.6 — `SUMMARY.md` (SC-007)
Executive findings: phase coverage (all 7), total findings by severity, the top-3 risk areas,
and a methodology-repeatability note (SC-009). Written for a non-technical reader — SC-007 is a
peer-review criterion, so if it only parses for someone who ran the hunt, it fails.

State the strongest structural findings plainly. The write-only Settings page (BUG-095) and the
phantom-citation path (BUG-098) are the two that best demonstrate why an E2E hunt found what unit
tests did not.

### 8.7 — `LAUNCH-DECISION.md` (SC-011)
A structured GO / NO-GO grounded in the CRITICAL count and the v1.0-fix scope. Two open
carry-forwards MUST appear:
- **P1-S1 was measured warm-volume**, not from a true cold start. Either state the
  warm-measured caveat explicitly or record that the cold-start re-run is outstanding.
- **SC-012 was never re-audited against the Phase-6 observability sinks** (BUG-117's raw
  `JSON.stringify` in `TraceTable.tsx`, the `query_traces` table, BUG-116's absent log surface).
  verify-6 graded this SUGGESTION; it should not silently vanish at closure.

### 8.8 — README one-liner
A single line linking the registry. **Nothing else in README changes** — it is the only allowed
edit outside the session directory.

### 8.9 — SC-006 final check
`git fetch origin develop:develop` first, then
`git diff origin/develop --name-only -- backend/ frontend/ ingestion-worker/ Makefile embedinator.sh embedinator.ps1 'docker-compose*.yml'`
→ must be **empty**. Application data created during P7-S3 is not a production-code edit.

### 8.10 — SC-005 final check
`blocker_patched.applied=true` count must equal the count of `Pilot | gate | Y` lines in
`session-log.md`. Under R-007-D both are **0**, and 0 == 0 satisfies it.

### 8.11 — Close
Commit `chore(spec-30-r1): close hunt registry` (conventional, no `Co-Authored-By`), final
session-log entry, and MERGE `apply-progress` with `CHECKPOINT: phase-8 complete | registry:
BUILT | schema-valid: Y`. Phases 0–7 must survive verbatim.

---

## Constraints

SACRED (`Makefile`, `embedinator.sh`, `embedinator.ps1`, `docker-compose*.yml`) and all of
`specs/030-e2e-test-v3/**` are harness-denied — a write attempt fails rather than slipping
through. `specs/030-e2e-test-v3/tasks.md` stays untouched: it is read-only reference and its
checkboxes have been stale since Phase 1. The dormant `docs/E2E/2026-05-15-round-1-bug-hunt/`
is never touched.
