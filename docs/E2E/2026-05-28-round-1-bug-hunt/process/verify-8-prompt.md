# verify-8 — FINAL gate. Emits "spec-31 UNBLOCKED" or blocks it.

**Change**: `single-round-bug-hunt` · **Branch**: `030-e2e-test-v3`
**Run as**: a fresh `sdd-verify` sub-agent with **zero hunt context** (R-007-I).
**Gates**: R-006's five simultaneous close conditions + SC-001..SC-012.

> **ENGRAM-backed change.** The native SDD dispatcher reads only OpenSpec and is blind to this.
> Delegate directly with the engram references below.

This is the last gate. Nothing follows it but `sdd-archive`. A CRITICAL here leaves spec-31
blocked (R-006-C), so the cost of a false positive is a stalled fix wave — and the cost of a
false negative is a public registry asserting something untrue. Neither error is cheap.

## Reading list

engram `sdd/single-round-bug-hunt/spec` (#3218, R-001..R-006) · `amendment-autonomous-execution`
(#4078, R-007 — phases 7–8 ran autonomously; audit its boundaries) · `apply-progress` (#3227) ·
`verify-report-phase-7` · prior gate reports for format precedent ·
`specs/030-e2e-test-v3/contracts/bug-registry-schema.json`.

## R-006 — five conditions, all must hold simultaneously

1. `bugs-registry.json` schema-valid, **0 violations** (SC-008)
2. `SUMMARY.md` committed and non-empty (SC-007)
3. `LAUNCH-DECISION.md` committed and non-empty (SC-011)
4. Close commit `chore(spec-30-r1): close hunt registry` present on `030-e2e-test-v3`
5. `sdd-archive` not yet run — this gate precedes it

## Checks

**SC-008 — registry validity.** Validate `bugs-registry.json` against the schema. Tooling exists at
`scratchpad/`: `build_registry.py`, `validate.py`, `.validator/bin/python` (jsonschema 4.26 in an
isolated venv — **jsonschema is NOT in the project env; do not add it**). **Treat that parser as the
orchestrator's instrument, not an oracle** — spot-check its output against raw markdown. The registry
must be *rebuilt from* `bugs/`, not hand-edited; confirm it matches the directory.

**Use the A/B/C split, not a raw violation count.** A count cannot distinguish "triaged, URL pending"
from "untriaged" — both fail the MAJOR+ conditional identically. Split by cause:
`A) no decision · B) decision, URL pending · C) complete`. Expect `0 / 0 / 55`.

**SC-002** — every CRITICAL has severity + ≥1 repro step + ≥1 non-null artifact.
**SC-003** — every MAJOR+ has a triage decision AND a resolvable `github_issue_url`. Spot-check ≥5
against GitHub. Confirm the MAJOR+ count equals the count of `spec-30-hunt`-labelled issues.
**SC-005** — `blocker_patched.applied=true` count == `Pilot | gate | Y` count in `session-log.md`.
Under R-007-D both are **0**; 0 == 0 satisfies it. Confirm no inline fix was applied.
**SC-006** — `git fetch origin develop:develop` **first**, then
`git diff origin/develop --name-only -- backend/ frontend/ ingestion-worker/ Makefile embedinator.sh embedinator.ps1 'docker-compose*.yml'`
→ **empty**. A stale local `develop` produces a false positive.
**SC-010** — all 7 phase-transition entries present; P7-S1..S5 each with a verdict.
**SC-012** — `public-evidence/` is now the **only tracked artifact directory**; scan every file in it
for `sk-` keys, `gAAAAA` Fernet ciphertext, bearer tokens, credential assignments, absolute
`/home/<user>/` paths. **One of the 12 is a PNG that was human-inspected, not tool-scanned** — a text
scanner cannot read it, so a "clean" result there means nothing was examined. Confirm the
`secret-scan-verify:` log line says so; a vacuous pass recorded as a scan is itself a finding.
**FR-027** — ≥1 tracked artifact per CRITICAL. 12 records in scope (1 BLOCKER + 11 CRITICAL).
**FR-028** — every promotion has a **documented** `secret-scan-verify:` line. Performed-but-undocumented
fails.

## Known traps — every one produced a false positive at an earlier gate

- Stale local `develop` → false SC-006 failure. Fetch first.
- **`wc -c` counts bytes, `maxLength` counts characters.** An em-dash is 3 bytes. Use `wc -m`, and
  measure the `title` field *without* the `BUG-NNN: ` prefix — not the filename, not the H1.
- Multi-thousand-character single lines in `session-log.md` truncate a capped read silently. Use
  `tail` or explicit line numbers.
- A case-insensitive `REGISTERED` grep matches "not registered" / "before registration".
- BUG-055..067 reference schema-valid but non-existent local artifact files (registered
  pre-convention, gitignored per FR-022). A non-null *path* satisfies the artifact check.
- Expected uncommitted state, **not** drift: 5 pre-existing `.claude/skills/gitnexus/` edits,
  untracked `docs/superpowers/`, and anything under the gitignored `notes/`.
- **Read the whole record before calling it incoherent** — several read oddly on a grep and are
  precise in full context.

## Judgment calls to audit — do not silently re-adjudicate

BUG-123 carries `UNCONFIRMED:` **in its title** (deliberate: a qualification in the body is lost when
the issue appears in a list). BUG-069's CRITICAL escalation was **declined** on two data points.
BUG-127 held MINOR with the declined MAJOR case preserved. BUG-121 must claim the shutdown path never
runs — **not** that data was lost; P7-S4 proved nothing was. A **refuted** hypothesis (split-brain)
is recorded as refuted, not dropped. If you disagree with any of these, say so as a finding with
reasoning — but do not treat a documented, reasoned call as an error.

## The round's stated limitations — verify they are stated, not whether they are flattering

`SUMMARY.md` should carry **two** limitation statements covering **eight** wrong readings in two
classes: **instrument faults** (corrupted `rg`, stale curl buffer, non-flushing log follower,
log-destroying `docker compose down`) needing *cross-check against a second tool*; and **sampling
faults** (pre-fault ingestion read, mid-recovery transient, two mid-write orchestrator reads) needing
*re-read after the mutation settles*. A single combined statement under-covers half the evidence.
**Judge whether any registered finding rests on an unverified single sample.**

## Deliverable

Graded findings (CRITICAL / WARNING / SUGGESTION), a **PASS / FAIL / CONDITIONAL-PASS** verdict, a
summary table one row per check, R-006's five conditions each explicitly true or false, and — on PASS
— the literal statement **"spec-31 UNBLOCKED"**.

Save to engram `sdd/single-round-bug-hunt/verify-report-phase-8` (type `architecture`, project
`the-embedinator`, `capture_prompt: false`). **Then RETURN a concise Result Contract as your final
message** — verdict, counts, R-006 status, the spec-31 statement, topic key. **Do not end on an idle
notification**; verify-6's agent did, and its report had to be pulled from engram by hand.

**Any CRITICAL → report and STOP.** Do not manufacture a blocker.
