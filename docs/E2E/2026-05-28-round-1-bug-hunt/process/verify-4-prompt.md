# verify-4 prompt — Spec-30 Round-1 Bug Hunt, Phase 4 (Chat Edge Case Hunt, US4)

> **How to use (Pilot)**: Open a SEPARATE orchestrator session (regular Claude Code — NOT the hunt Lead pane, NOT `/sdd-apply`). Paste everything below the line. The orchestrator delegates an `sdd-verify` sub-agent (model: sonnet) to run the R-002 gate on Phase 4.

---

Run the **verify-4 gate** for the SDD change **`single-round-bug-hunt`**, Phase 4 (Chat Edge Case Hunt, US4), by delegating an **`sdd-verify` sub-agent** (model: sonnet). This is the SDD **R-002** verify gate between apply-4 and apply-5. Do NOT type `/sdd-apply`.

**IMPORTANT — this change is ENGRAM-backed** (backend: engram, project `the-embedinator`), NOT OpenSpec. The native SDD dispatcher reads only OpenSpec files and is BLIND to this change — do NOT rely on it; delegate `sdd-verify` directly with the engram references below.

**State to verify:**
- Phase 4 was CLOSED at commit `b949c8c` ("chore(spec-30-r1): close hunt phase 4 — 12 findings (BUG-077..088)") on branch `030-e2e-test-v3`.
- Registry: 65 bugs (BUG-024..088), next-bug-id `BUG-089`. Phase-4 contributed 12 NEW findings (BUG-077..088).
- Self-reported census: **3 CRITICAL** (BUG-082 injection→ambiguous-intent loop, BUG-083 injection-compliance, BUG-088 unbounded in-flight LLM call) / **5 MAJOR** (BUG-077, 078, 079, 085, 087) / **4 MINOR** (BUG-080, 081, 084, 086).
- Also this phase: UPDATEs to BUG-054/056/062/066/073/074/075/080/081; 2 security PASSes (P4-S4 system-prompt-extraction, P4-S5 in-chunk injection); BUG-073 severity adjudicated by Lead as KEPT MAJOR; BUG-088 framing CORRECTED (553s bounded stall, not infinite).

**The `sdd-verify` sub-agent MUST (reads-only; it writes only the verify report):**

1. Read the SDD spec for the R-002 gate criteria: engram `mem_search(query: "sdd/single-round-bug-hunt/spec", project: "the-embedinator")` → `mem_get_observation` (#3218). Apply the R-002 gate checks (a/b/c/d) to Phase 4.
2. Read the prior verify reports for format + precedent, and follow the same report structure and adjudication style:
   - verify-1: `sdd/single-round-bug-hunt/verify-report-phase-1` (#3444/#3445) — PASS
   - verify-2: report #3500 + decision `sdd/single-round-bug-hunt/verify-gate-2-decision` (#3502) — PASS
   - verify-3: report #3807 + decision #3808 — PASS
3. Read the apply-progress checkpoint: `sdd/single-round-bug-hunt/apply-progress` (#3227) — confirm the **phase-4** checkpoint (commit `b949c8c`, 12 findings) and that phases 0–3 are preserved unmodified (merge discipline, no overwrite).
4. Validate the Phase-4 registry on disk under `docs/E2E/2026-05-28-round-1-bug-hunt/`:
   - The 12 NEW findings **BUG-077..088** are each schema-complete against `specs/030-e2e-test-v3/contracts/bug-registry-schema.json`: `id` pattern, `severity` + `layer` valid enums, `phase`/`scenario_id`/`discovered_at` present, ≥1 reproduction step, ≥1 NON-NULL artifact path, `title` ≤80 chars.
   - **PRIORITY — the 3 CRITICAL (BUG-082, 083, 088) and 5 MAJOR (077, 078, 079, 085, 087) must have every required field.** This is the first phase to register CRITICALs, so check (c) carries real weight here.
   - Independently re-derive the severity census from the 12 files on disk and compare to the self-report above. Confirm 65 bug files total (BUG-024..088) and `next-bug-id.txt` = `BUG-089`.
   - Coherence spot-check: **BUG-086** is registered as MINOR/Backend while its own Notes conclude the frontend parser behaved correctly. Confirm the severity/layer assignment is coherent with the evidence, or flag it.
   - `session-log.md` contains the Phase-4 phase-transition entries (OPEN + `[2026-07-08T17:09:18-03:00] … Phase 4 … CLOSED`) and per-scenario verdicts **P4-S1..S6**.
   - Coverage: all 6 scenarios exercised + all **5 FR-021 adversarial categories** exercised.
   - FR-014/FR-015: no unfiled CRITICAL/BLOCKER; no untriaged MAJOR. Per verify-1 ADJUDICATION-1 and verify-3 precedent, these are **hunt-close (Phase-8)** requirements — `Triage (filled in Phase 8 for MAJOR+)` TBD placeholders remain acceptable at Phase-4 scope. Do not re-litigate.
5. **Verify the verify-3 WARNING-1 remediation landed.** verify-3 rated R-005-A (bug-registrar sole writer) a WARNING because BUG-071..076 lacked explicit `BugRegistrar | discovery` session-log attribution. The apply-4 launch prompt was amended to require it. **Check every Phase-4 registration batch is tagged `BugRegistrar | discovery` in `session-log.md`, never `Orchestrator | observation`.** Report whether the remediation held.
6. **SC-006 invariant (zero production code)** — run `git fetch origin develop:develop` FIRST, then diff against `origin/develop`, NOT local `develop`. verify-3's SUGGESTION-2 recorded that a stale local `develop` ref produces a false positive here. Expected: empty diff over `backend/ frontend/ ingestion-worker/ Makefile embedinator.sh embedinator.ps1 'docker-compose*.yml'`. The 4 backend files from the BUG-045 supervised fix are a pre-authorized HARD carry-forward (verify-2 adjudication #3502) — sanctioned, not a violation.
7. Also run the structural checks verify-3 ran: **R-001-A** (checkpoint fields), **R-003-B** (contiguous ID sequence, next-bug-id correctness), **R-004-A/B** (`docs/E2E/2026-05-28-round-1-bug-hunt/process/lead-prompt.md` ≤300 lines, `grep -ci speckit` = 0), **dormant-dir guard** (`git log --oneline a5e0886..HEAD -- "docs/E2E/2026-05-15-round-1-bug-hunt/"` must be EMPTY — scope it to `a5e0886..HEAD`, an unscoped `git log` returns pre-apply-0 historical commits and is a false positive).

**KNOWN carry-forwards — do NOT fail the gate on these** (accepted, consistent with the verify-1/2/3 standard):
- **BUG-055..067 reference schema-valid but non-existent local artifact files** (registered pre-convention; artifacts are gitignored per FR-022, so uncommitted regardless). Treat a non-null artifact PATH as satisfying the "non-null artifact" check. Flag as SUGGESTION (spec-31 backfill), not CRITICAL. Note: these are out of Phase-4 scope anyway.
- **Expected uncommitted working-tree state, NOT drift**: one post-close `session-log.md` line (`[2026-07-08T18:54:42-03:00] Orchestrator | observation` — P4-S6 frontend addendum + chrome-devtools methodology note, registry-count-neutral); modifications to `.claude/skills/gitnexus/*/SKILL.md`; untracked `docs/superpowers/`. None belong to the phase-4 close commit.

**Deliverable:** Produce a verify report with findings graded CRITICAL / WARNING / SUGGESTION, plus a **PASS / FAIL / CONDITIONAL-PASS** verdict on the R-002 gate, and an explicit carry-forwards section (preserve verify-3's 5 carry-forwards, updating any that Phase 4 resolved or extended). Save it to engram topic `sdd/single-round-bug-hunt/verify-report-phase-4` (type: `architecture`, project: `the-embedinator`, `capture_prompt: false`).

**Then adjudicate (orchestrator):**
- **PASS or CONDITIONAL-PASS with only WARNING/SUGGESTION** → apply-5 is UNBLOCKED. Record the decision to engram topic `sdd/single-round-bug-hunt/verify-gate-4-decision`.
- **Any CRITICAL** → report the blocker and STOP; do NOT advance to apply-5.

Report back: the verdict, the count of CRITICAL/WARNING/SUGGESTION, and the verify-report topic key.
