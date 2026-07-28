# verify-7 — R-002 gate after apply-7 (Phase 7, Recovery & State, US7)

**Change**: `single-round-bug-hunt` · **Branch**: `030-e2e-test-v3`
**Gate**: the LAST per-phase gate. It carries the **pre-closure pre-checks** that unblock apply-8.
**Run as**: a fresh `sdd-verify` sub-agent with **zero hunt context** (R-007-I). The orchestrator
delegates, then adjudicates. Never run this inside the Lead's own context — the point is
independence.

> **This change is ENGRAM-backed** (backend: engram, project `the-embedinator`), NOT OpenSpec.
> The native SDD dispatcher reads only OpenSpec files and is blind to it. Delegate directly with
> the engram references below; do not rely on the dispatcher.

---

## Reading list (in order)

1. engram `sdd/single-round-bug-hunt/spec` (#3218) — R-002 gate criteria (a/b/c/d), R-001..R-006.
2. engram `sdd/single-round-bug-hunt/amendment-autonomous-execution` (#4078) — **R-007**. Phase 7
   ran autonomously under this amendment. You are auditing whether the amendment's boundaries
   were respected, not whether the amendment itself is wise.
3. engram `sdd/single-round-bug-hunt/apply-progress` — confirm the phase-7 checkpoint exists AND
   that phases 0–6 survive **verbatim** (merge discipline; an overwrite is CRITICAL).
4. Prior verify reports for format and precedent — verify-5 #3878/#3879, verify-6 #3993/#3994.
   Match their structure and adjudication style.
5. `specs/030-e2e-test-v3/contracts/bug-registry-schema.json` — the field contract.

Paths: bug records at `docs/E2E/2026-05-28-round-1-bug-hunt/bugs/BUG-NNN-*.md`;
`session-log.md` and `next-bug-id.txt` in the parent; `logs/ screenshots/ traces/` are
gitignored artifacts; `public-evidence/` is tracked.

---

## Checks

### R-002 (a)–(d), scoped to Phase 7
- **(a)** `session-log.md` has a timestamped `Phase 7 closed` phase-transition entry.
- **(b)** All five playbook scenarios P7-S1..S5 have a session-log entry with an explicit verdict,
  or are marked "not reached" with a justification.
- **(c)** Every CRITICAL/MAJOR registered this phase has severity set, ≥1 reproduction step, and
  ≥1 non-null artifact path.
- **(d)** Every new `bugs/BUG-*.md` validates against `bug-registry-schema.json`, 0 violations.

### Pre-closure pre-checks (this gate only — these unblock apply-8)
- **All 7 phase-transition entries** present in `session-log.md` (phases 1–7 closed). This is the
  SC-010 evidence; before apply-7 it FAILED, because Phase 7 had never been entered.
- **Every MAJOR-or-higher record has a complete `triage` block**: `decision` ∈ {v1.0-fix,
  v1.1-defer}, a non-empty `rationale`, and a `github_issue_url` matching
  `^https://github\.com/[^/]+/[^/]+/issues/[0-9]+$`. Spot-check ≥5 URLs actually resolve
  (`gh issue view <n> --json number,title,state`). Confirm the count of MAJOR+ records equals
  the count of issues carrying the `spec-30-hunt` label.
- **BUG-047 and BUG-070** previously had NO `## Triage` section at all. Confirm one was inserted
  and filled, not faked.

### R-007 boundary audit (new this gate)
- **R-007-D**: `blocker_patched.applied` is `false` on all 94+ records, and `Pilot | gate | Y`
  appears 0 times in `session-log.md`. Both counts must be 0 and must match (SC-005).
- **R-007-G / R-005-A**: every Phase-7 bug-minting event in `session-log.md` is tagged
  `BugRegistrar | discovery`, never `Orchestrator | observation`. Confirm the Phase-7 commit
  touches ONLY paths under `docs/E2E/2026-05-28-round-1-bug-hunt/`.
- **R-007-B**: no evidence in the session log of a `docker compose down -v`, `docker volume rm`,
  `make clean`, or any lifecycle command outside the enumerated set.
- **R-007-A**: scenarios were driven via Playwright, and no `getResponseBody`-backed read was
  issued against an in-flight stream.

### SC-006 — zero production code
`git fetch origin develop:develop` **first**, then diff against `origin/develop` (a stale local
`develop` produces a false positive — verify-3 SUGGESTION-2):
`git diff origin/develop --name-only -- backend/ frontend/ ingestion-worker/ Makefile embedinator.sh embedinator.ps1 'docker-compose*.yml'` → **must be empty**.
Confirm `origin/develop` is an ancestor of HEAD. Note: application DATA created by P7-S3
(the `p7s3-scratch` collection, a partial document) is NOT a production-code edit.

### Structural
R-001-A (checkpoint fields present, phases 0–6 preserved) · R-003-B (IDs contiguous, no gaps or
dupes, `next-bug-id.txt` = last + 1) · dormant-directory guard (`docs/E2E/2026-05-15-round-1-bug-hunt/`
untouched — scope `git log` to `a5e0886..HEAD`, an unscoped log returns pre-apply-0 history).

---

## Known traps — do not manufacture a blocker

Every one of these produced a false positive at an earlier gate:

- **Stale local `develop`** → false SC-006 failure. Always fetch first.
- **`title` measured off the filename or the H1** → phantom >80-char overflow. The schema stores
  `id` and `title` as SEPARATE fields; measure the title WITHOUT the `BUG-NNN: ` prefix.
- **Truncated session-log read** → entries are multi-thousand-character single lines, so a
  line-capped read terminates early while looking complete. Use `tail` or explicit line numbers.
- **Case-insensitive `REGISTERED` grep** → matches "not registered" and "before registration",
  which are narrative, not minting events. Read surrounding context.
- **BUG-055..067 reference schema-valid but non-existent local artifact files** — registered
  pre-convention, artifacts gitignored per FR-022. A non-null artifact PATH satisfies check (c).
  SUGGESTION for spec-31 backfill, not CRITICAL.
- **Expected uncommitted working-tree state, not drift**: modified `.claude/skills/gitnexus/*/SKILL.md`
  (5 files), untracked `docs/superpowers/`, an amended `.claude/settings.local.json` (the R-007
  permissions rails), new files under the gitignored `notes/`.
- **A claim that reads as incoherent on a grep is often precise in full context** — read the whole
  record before calling it incoherent (verify-4/5 lesson).

Grading policy: internal incoherence, un-updated flags and un-audited surfaces are
**WARNING/SUGGESTION** scaled by how load-bearing they are. Only genuine contract violations are
CRITICAL-eligible: a schema-incomplete MAJOR+, SC-006 production drift, an R-005-A write-boundary
breach, missing/gapped IDs, an overwritten prior-phase checkpoint, or a MAJOR+ without a
resolvable issue URL.

---

## Deliverable

A verify report containing: findings graded CRITICAL / WARNING / SUGGESTION; a
**PASS / FAIL / CONDITIONAL-PASS** verdict; a Summary Table with one row per check above; an
explicit statement of whether **apply-8 is UNBLOCKED**; and a carry-forwards section that
updates verify-6's list (the 45-bug GitHub-URL debt should now be **discharged** — say so
explicitly, with the count actually observed).

Save it to engram topic `sdd/single-round-bug-hunt/verify-report-phase-7` (type `architecture`,
project `the-embedinator`, `capture_prompt: false`).

**Then ALSO return a concise Result Contract as your final message** — status, verdict,
CRITICAL/WARNING/SUGGESTION counts, whether apply-8 is unblocked, and the topic key. **Do not end
on an idle notification**: verify-6's sub-agent did exactly that and the orchestrator had to pull
the report out of engram by hand. The orchestrator gates on the returned summary AND re-pulls the
artifact independently.

**Any CRITICAL → report and STOP. Do not advance to apply-8.**
