# Contract: F/D/P Gate Protocol

**Feature**: spec-28
**Date**: 2026-04-23

The F/D/P (Fix now / Defer / Pause+investigate) gate is spec-28's mechanism for keeping the 4-hour exploratory session productive under conditions of unpredictable Blocker-severity findings. This contract fixes the prompt shape, the decision-recording format, and the P-resolution rule.

---

## When the gate triggers

The gate triggers when, and only when, a bug is filed with `Severity: Blocker`.

**Definition of Blocker** (per spec severity framework):
> A defect that prevents v1.0.0 from shipping — a critical user flow is broken, data loss is possible, a security boundary is breached, or the portfolio demo cannot complete its happy path.

Non-Blocker severities (Major, Minor, Cosmetic) do NOT trigger the gate. They are logged and continue without pause. They are triaged at Phase 6 close for the v1.1 roadmap.

---

## Who prompts, who decides

- **Prompting pane**: Orchestrator (pane 1). The Orchestrator receives the bug filing from Scribe (via `session-log.md` append) and issues the prompt in its own pane.
- **Deciding actor**: the user, responding in pane 1.
- **Executing pane**:
  - `F` (Fix now): Test Runner (pane 2) for test-code fixes; backend edits require Orchestrator coordination if `backend/**` is touched.
  - `D` (Defer): Scribe (pane 3) records the defer rationale; no other work.
  - `P` (Pause+investigate): Orchestrator convenes a 15-minute timeboxed investigation; resolution is a follow-up F or D decision.

---

## Exact prompt shape

The Orchestrator issues this prompt in pane 1 verbatim (substitute `BUG-XXX` and the one-line summary):

```
[ORCHESTRATOR — F/D/P GATE]
BUG-XXX surfaced: <one-line summary of the bug>
Severity: Blocker
Layer: <Frontend | Backend | Ingestion | Retrieval | Reasoning | Infrastructure | Observability>
Discovered via: <Playwright | Exploratory | Fault-injection | RAGAS>

Decision needed:
  [F]ix now — pause the current activity, fix in-session, commit, continue
  [D]efer  — log, tag "defer to v1.1", continue immediately
  [P]ause+investigate — 15-minute timeboxed investigation; must resolve to F or D

Your choice [F/D/P]:
```

**Rules**:
- The Orchestrator waits for the user's response before any further work in ANY pane. Panes 2, 3, 4 pause state is signaled via a `## HH:MM UTC — F/D/P gate open: BUG-XXX` entry in `session-log.md`.
- The Orchestrator does NOT infer or auto-select on behalf of the user. Ambiguous responses prompt a re-ask.
- The user may request additional information before deciding (e.g., "show me the last 20 log lines" or "can you re-run the repro to confirm?"). These information requests do NOT count as a decision — the gate remains open until F, D, or P is explicitly issued.

---

## Recording format

The decision is recorded in two places:

### 1. In the bug markdown (`bugs-raw/BUG-XXX-*.md`)

Under the `F/D/P decision:` header field:

```markdown
- **F/D/P decision**: F (fixed in-session; commit <sha>; test added in <test-file>:<line>)
```

Variants:
- `F (fixed in-session; commit <sha>; test added in <test-file>)` — if a regression test was added
- `F (fixed in-session; commit <sha>; test: <why-no-test-added>)` — if no regression test (must justify)
- `D (defer to v1.1; rationale: <one-sentence reason>)`
- `P→F (investigated 15m; commit <sha>; …)` — if investigation resolved to F
- `P→D (investigated 15m; rationale: <reason>)` — if investigation resolved to D

### 2. In `session-log.md`

Under the gate-opening timestamp:

```markdown
## HH:MM UTC — F/D/P gate: BUG-XXX
- Summary: <one-line>
- Layer: <layer>
- Discovery: <channel>
- Decision: <F | D | P→F | P→D>
- Rationale: <one or two sentences>
- Commit (if F or P→F): <sha>
- Issue (if D and promoted at Phase 6): <will be filled at Phase 6 close>
```

Both entries are mandatory. A bug with a Blocker-level filing and no F/D/P entry in either place fails SC-005 validation.

---

## P-resolution rule

A `P` (pause+investigate) decision is a 15-minute timeboxed investigation. At the end of 15 minutes (wall clock):

1. The Orchestrator re-prompts:
   ```
   [ORCHESTRATOR — P-RESOLUTION]
   BUG-XXX pause+investigate timebox expired (15 min).
   Investigation notes:
     <brief synthesis of what was learned during the 15 min>
   Decision required: [F]ix now | [D]efer
   Your choice [F/D]:
   ```
2. The user MUST answer F or D. Re-entering P is not allowed — the P budget is one-shot.
3. The decision is recorded as `P→F` or `P→D` with the 15-minute investigation notes attached to the bug markdown under a new `## Investigation notes` section.

**Why 15 minutes**: longer P windows can consume the 4-hour session on a single bug. If 15 min is insufficient to decide between F and D, the decision is D by default (deferred with a rationale that reads "insufficient information for in-session fix"), and the bug becomes a v1.1 investigation task.

---

## Phase-4 fault-injection interaction with the gate

Fault-injection scenarios in Phase 4 are expected to surface Blockers (that is their purpose). The gate applies:

- **FI-01 through FI-05**: if a scenario produces a Blocker, the gate opens.
- **F in fault-injection**: only feasible for test-code or CI-config changes. Backend code changes during fault-injection are deferred by default because the F path would require restoring stack state after a production fix, which risks invalidating subsequent scenarios.
- **D in fault-injection**: the common path — the fault reveals a v1.1 improvement opportunity.
- **P in fault-injection**: 15-minute investigation focused on whether the observed failure is a genuine bug vs a test-setup artifact.

---

## Phase-1 stabilization interaction with the gate

In Phase 1, the 16 failing Playwright tests are NOT Blockers on the spec's severity scale — they are pre-existing test-code drift that the spec was chartered to fix. They do NOT trigger the F/D/P gate.

However, if a Phase 1 stabilization reveals that the test was failing because of a genuine app bug (not selector drift), that bug IS a Blocker-severity finding and DOES trigger the gate.

---

## Phase-5 RAGAS interaction with the gate

RAGAS scores are informational per spec Assumptions — they do not gate shipping. If a score is surprisingly low (e.g., overall retrieval precision < 0.3), the Orchestrator MAY open an informal discussion with the user but does NOT open an F/D/P gate on the score itself. A filed bug on a specific pair's failure mode follows the normal gate rules.

---

## Forbidden variants

The following are explicitly disallowed:

- `F (fixed in-session; no test)` without a rationale — every F must justify test coverage decisions.
- `D` without a rationale — every D must give a one-sentence reason.
- `P` sustained beyond 15 minutes — the timebox is non-negotiable.
- Auto-decisions by the Orchestrator — every gate requires a human response.
- Silent triage (a Blocker goes unrecorded because the exploratory charter moved on) — if a finding slips past the gate, it is itself a violation and must be logged retroactively as a session-process bug.

---

## Validation (enforced at Phase 6 close)

```bash
# Every Blocker has an F/D/P decision recorded in its bug markdown.
for f in docs/E2E/*-bug-hunt/bugs-raw/BUG-*.md; do
  if grep -q "^- \*\*Severity\*\*: Blocker" "$f" && \
     ! grep -qE "^- \*\*F/D/P decision\*\*: (F |D |P→F |P→D )" "$f"; then
    echo "VIOLATION: $f missing F/D/P decision"
  fi
done

# Every Blocker in session-log.md has an "F/D/P gate: BUG-XXX" entry.
comm -23 \
  <(grep -l "^- \*\*Severity\*\*: Blocker" docs/E2E/*-bug-hunt/bugs-raw/*.md | xargs -I{} basename {} .md | sort) \
  <(grep -oE "F/D/P gate: BUG-[0-9]+" docs/E2E/*-bug-hunt/session-log.md | sed 's/F\/D\/P gate: //' | sort)
```

Violations fail SC-005 and block the session close.
