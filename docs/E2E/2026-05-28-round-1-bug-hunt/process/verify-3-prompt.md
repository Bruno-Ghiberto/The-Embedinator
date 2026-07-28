# verify-3 prompt — Spec-30 Round-1 Bug Hunt, Phase 3 (Chat Happy Path, US3)

> **How to use (Pilot)**: Open a SEPARATE orchestrator session (regular Claude Code — NOT the hunt Lead pane, NOT `/sdd-apply`). Paste everything below the line. The orchestrator delegates an `sdd-verify` sub-agent (model: sonnet) to run the R-002 gate on Phase 3.

---

Run the **verify-3 gate** for the SDD change **`single-round-bug-hunt`**, Phase 3 (Chat Happy Path, US3), by delegating an **`sdd-verify` sub-agent** (model: sonnet). This is the SDD **R-002** verify gate between apply-3 and apply-4. Do NOT type `/sdd-apply`.

**IMPORTANT — this change is ENGRAM-backed** (backend: engram, project `the-embedinator`), NOT OpenSpec. The native SDD dispatcher reads only OpenSpec files and is BLIND to this change — do NOT rely on it; delegate `sdd-verify` directly with the engram references below.

**State to verify:**
- Phase 3 was CLOSED at commit `374ce59` ("chore(spec-30-r1): close hunt phase 3 — 22 findings (BUG-055..076)") on branch `030-e2e-test-v3`.
- Registry: 53 bugs (BUG-024..076), next-bug-id `BUG-077`. Phase-3 contributed 22 NEW findings (BUG-055..076: 10 MAJOR / 11 MINOR / 1 COSMETIC).

**The `sdd-verify` sub-agent MUST (reads-only; it writes only the verify report):**
1. Read the SDD spec for the R-002 gate criteria: engram `mem_search(query: "sdd/single-round-bug-hunt/spec", project: "the-embedinator")` → `mem_get_observation` (#3218). Apply the R-002 gate checks (a/b/c/d) to Phase 3.
2. Read the prior verify reports for format + precedent: verify-1 (`sdd/single-round-bug-hunt/verify-report-phase-1`, #3444/#3445 — PASS adjudicated) and verify-2 (report #3500 + decision `sdd/single-round-bug-hunt/verify-gate-2-decision` #3502 — PASS adjudicated). Follow the same report structure and adjudication style.
3. Read the apply-progress checkpoint: `sdd/single-round-bug-hunt/apply-progress` (#3227) — confirm the phase-3 checkpoint (commit 374ce59, 22 findings, phases 0–2 preserved).
4. Validate the Phase-3 registry on disk under `docs/E2E/2026-05-28-round-1-bug-hunt/`:
   - The 22 NEW findings **BUG-055..076** are each schema-complete against `contracts/bug-registry-schema.json`: severity + layer (valid enums), ≥1 reproduction step, ≥1 NON-NULL artifact path, title ≤80 chars. **PRIORITY**: all 10 MAJOR (BUG-055, 061, 062, 064, 068, 069, 071, 072, 073, 074) must have every required field.
   - `session-log.md` contains the Phase-3 phase-transition entry (`[2026-07-03T15:30:00-03:00] … Phase 3 … CLOSED`) and per-scenario verdicts P3-S1..S6.
   - Coverage: all 6 scenarios exercised (P3-S1..S6) + exit checklist complete — 5 reused golden (Q-001/005/007/014 run; **Q-018 out-of-scope decline legitimately deferred to Phase 4/US4**) + 4 new probes (P3-Q-A/B/C/D).
   - FR-014/FR-015: no unfiled CRITICAL/BLOCKER; no untriaged MAJOR.
5. **KNOWN carry-forward — do NOT fail the gate on it** (accepted, consistent with the verify-1/2 standard): BUG-055..067 reference schema-valid but **non-existent local** artifact files (registered pre-convention; artifacts are gitignored per FR-022, so uncommitted regardless). BUG-068+ have real on-disk evidence. Treat a non-null artifact PATH as satisfying the "non-null artifact" check — the same standard verify-1 and verify-2 accepted. Flag it as a SUGGESTION (spec-31 backfill), not a CRITICAL.
6. Produce a verify report: findings graded CRITICAL / WARNING / SUGGESTION, plus a **PASS / FAIL / CONDITIONAL-PASS** verdict on the R-002 gate. Save it to engram topic `sdd/single-round-bug-hunt/verify-report-phase-3` (type: architecture, project: the-embedinator, capture_prompt: false).

**Then adjudicate (orchestrator):**
- **PASS or CONDITIONAL-PASS with only WARNING/SUGGESTION** → apply-4 is UNBLOCKED. Record the decision; tell me to launch apply-4 via `docs/E2E/2026-05-28-round-1-bug-hunt/process/apply-4-launch-prompt.md`.
- **Any CRITICAL** → report the blocker and STOP; do NOT advance to apply-4.

Report back: the verdict, the count of CRITICAL/WARNING/SUGGESTION, and the verify-report topic key.
